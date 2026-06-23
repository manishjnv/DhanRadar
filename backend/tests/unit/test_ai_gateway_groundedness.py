"""
Unit tests for sampled groundedness eval (PR-4) and paid judge fallback (PR-4b).

A sampled fraction of served AI outputs is scored 0..1 by an LLM-judge (free
pool, uninstrumented); only the score is stored (Redis). Tests:
  - record_groundedness + read_groundedness_window round-trip (avg, low_flags)
  - instrumented requires samples; clamping; non-fatal contracts
  - the gateway judges when sampled (rate=1.0) and records the score
  - the gateway does NOT judge when rate=0.0
  - the judge call is UNINSTRUMENTED — it must not pollute latency or spend
  - a non-parseable judge answer records nothing (graceful)
PR-4b additions:
  - free pool all 429 → paid judge tried, score recorded, judge_calls incremented
  - paid judge also 429 → no score, graceful
  - no paid model configured → no paid fallback attempted
  - paid judge call does NOT pollute latency/spend counters
"""

from __future__ import annotations

import json

import httpx
import pytest
from openai import RateLimitError

from dhanradar.ai_gateway import AIOutputBase, OpenRouterGateway
from dhanradar.ai_gateway.metrics import (
    _JUDGE_CALLS_KEY,
    _JUDGE_SPEND_MODELS_KEY,
    read_groundedness_window,
    read_latency_window,
    read_spend_window,
    record_groundedness,
)


def _rate_limit_err() -> RateLimitError:
    """Construct a well-formed RateLimitError for test use."""
    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    resp = httpx.Response(status_code=429, request=req)
    return RateLimitError("rate limited", response=resp, body={})


class _Out(AIOutputBase):
    thesis: str = ""


def _valid() -> str:
    return json.dumps(
        {
            "confidence": 0.5,
            "confidence_band": "medium",
            "contributing_signals": ["earnings up", "inflows steady"],
            "thesis": "fundamentals improving",
        }
    )


# --- metrics round-trip -------------------------------------------------------
async def test_record_then_read_averages(patch_redis):
    await record_groundedness(0.9, redis=patch_redis)
    await record_groundedness(0.7, redis=patch_redis)
    out = await read_groundedness_window(7, redis=patch_redis)
    assert out["instrumented"] is True
    assert out["value"] == pytest.approx(0.8)
    assert out["sample_count"] == 2
    assert out["low_flags"] == 0


async def test_low_score_flagged(patch_redis):
    await record_groundedness(0.4, low_threshold=0.6, redis=patch_redis)  # below → flagged
    await record_groundedness(0.95, low_threshold=0.6, redis=patch_redis)
    out = await read_groundedness_window(7, redis=patch_redis)
    assert out["sample_count"] == 2
    assert out["low_flags"] == 1


async def test_no_samples_not_instrumented(patch_redis):
    out = await read_groundedness_window(7, redis=patch_redis)
    assert out["instrumented"] is False
    assert out["value"] is None


async def test_scores_clamped(patch_redis):
    await record_groundedness(1.5, redis=patch_redis)   # → 1.0
    await record_groundedness(-0.5, redis=patch_redis)  # → 0.0
    out = await read_groundedness_window(7, redis=patch_redis)
    assert out["value"] == pytest.approx(0.5)


class _BoomRedis:
    async def incrbyfloat(self, *a, **k):
        raise RuntimeError("down")

    async def get(self, *a, **k):
        raise RuntimeError("down")


async def test_record_never_raises():
    assert await record_groundedness(0.8, redis=_BoomRedis()) is None


async def test_read_degrades():
    out = await read_groundedness_window(7, redis=_BoomRedis())
    assert out["instrumented"] is False


# --- fake client that branches on the judge system prompt --------------------
_JUDGE_MARKER = "groundedness grader"


class _Msg:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Msg(content)


class _Usage:
    def __init__(self, total: int) -> None:
        self.total_tokens = total


class _Resp:
    def __init__(self, content: str, total: int = 100) -> None:
        self.choices = [_Choice(content)]
        self.usage = _Usage(total)


class _Completions:
    def __init__(self, output: str, grounded: object) -> None:
        self._output = output
        self._grounded = grounded
        self.calls: list[str] = []

    async def create(self, *, model, messages, **kw):
        self.calls.append(model)
        sys = messages[0].get("content", "") if messages else ""
        if _JUDGE_MARKER in sys:
            # judge call → return the grounded JSON (or a non-dict for the bad case)
            if self._grounded is None:
                return _Resp("not json at all")
            return _Resp(json.dumps({"grounded": self._grounded}))
        return _Resp(self._output)


class _Chat:
    def __init__(self, output: str, grounded: object) -> None:
        self.completions = _Completions(output, grounded)


class _Client:
    def __init__(self, output: str, grounded: object = 0.9) -> None:
        self.chat = _Chat(output, grounded)


_MSGS = [{"role": "user", "content": "context about the fund"}]


# --- gateway integration -----------------------------------------------------
async def test_gateway_judges_when_sampled(patch_redis):
    gw = OpenRouterGateway(
        client=_Client(_valid(), grounded=0.85),
        free_models=["free_a"],
        redis=patch_redis,
        groundedness_sample_rate=1.0,  # always judge
    )
    res = await gw.complete(
        task_type="news_summary", messages=_MSGS, schema=_Out, contains_personal_data=False
    )
    assert res.model_used == "free_a"
    out = await read_groundedness_window(7, redis=patch_redis)
    assert out["instrumented"] is True
    assert out["value"] == pytest.approx(0.85)
    assert out["sample_count"] == 1


async def test_gateway_does_not_judge_when_rate_zero(patch_redis):
    gw = OpenRouterGateway(
        client=_Client(_valid()),
        free_models=["free_a"],
        redis=patch_redis,
        groundedness_sample_rate=0.0,  # never judge
    )
    await gw.complete(
        task_type="news_summary", messages=_MSGS, schema=_Out, contains_personal_data=False
    )
    out = await read_groundedness_window(7, redis=patch_redis)
    assert out["instrumented"] is False


async def test_judge_eligible_false_skips_judge(patch_redis):
    # A synchronous user-facing caller opts out → no judge even at rate 1.0.
    gw = OpenRouterGateway(
        client=_Client(_valid(), grounded=0.9),
        free_models=["free_a"],
        redis=patch_redis,
        groundedness_sample_rate=1.0,
    )
    await gw.complete(
        task_type="news_summary",
        messages=_MSGS,
        schema=_Out,
        contains_personal_data=False,
        judge_eligible=False,
    )
    out = await read_groundedness_window(7, redis=patch_redis)
    assert out["instrumented"] is False


async def test_judge_call_does_not_pollute_latency_or_spend(patch_redis):
    gw = OpenRouterGateway(
        client=_Client(_valid(), grounded=0.9),
        free_models=["free_a"],
        redis=patch_redis,
        groundedness_sample_rate=1.0,
    )
    await gw.complete(
        task_type="news_summary", messages=_MSGS, schema=_Out, contains_personal_data=False
    )
    # only the served (non-judge) call is timed / tallied — judge is uninstrumented
    latency = await read_latency_window(7, redis=patch_redis)
    spend = await read_spend_window(7, redis=patch_redis)
    assert latency["sample_count"] == 1
    assert spend["total_calls"] == 1


async def test_unparseable_judge_records_nothing(patch_redis):
    gw = OpenRouterGateway(
        client=_Client(_valid(), grounded=None),  # judge returns non-JSON
        free_models=["free_a"],
        redis=patch_redis,
        groundedness_sample_rate=1.0,
    )
    await gw.complete(
        task_type="news_summary", messages=_MSGS, schema=_Out, contains_personal_data=False
    )
    out = await read_groundedness_window(7, redis=patch_redis)
    assert out["instrumented"] is False  # no score parsed → nothing recorded


# --- PR-4b: cheap paid judge fallback ----------------------------------------


class _CompletionsPaidJudgeFallback:
    """Serve calls succeed; free-pool JUDGE calls all 429; paid judge returns a score."""

    def __init__(
        self, output: str, paid_model: str, paid_score: float | None
    ) -> None:
        self._output = output
        self._paid_model = paid_model
        self._paid_score = paid_score
        self.calls: list[str] = []

    async def create(self, *, model, messages, **kw):
        self.calls.append(model)
        sys_msg = messages[0].get("content", "") if messages else ""
        if _JUDGE_MARKER in sys_msg:
            if model == self._paid_model:
                if self._paid_score is None:
                    raise _rate_limit_err()
                return _Resp(json.dumps({"grounded": self._paid_score}))
            # all free-pool judge calls → 429
            raise _rate_limit_err()
        return _Resp(self._output)


class _ChatPaid:
    def __init__(self, output: str, paid_model: str, paid_score: float | None) -> None:
        self.completions = _CompletionsPaidJudgeFallback(output, paid_model, paid_score)


class _ClientPaid:
    def __init__(self, output: str, paid_model: str, paid_score: float | None = 0.75) -> None:
        self.chat = _ChatPaid(output, paid_model, paid_score)


_PAID_MODEL = "deepseek/deepseek-chat-v3-0324"


async def test_paid_judge_used_when_free_pool_429(patch_redis):
    """Free pool all 429 → paid judge tried and score recorded."""
    gw = OpenRouterGateway(
        client=_ClientPaid(_valid(), paid_model=_PAID_MODEL, paid_score=0.75),
        free_models=["free_a", "free_b"],
        redis=patch_redis,
        groundedness_sample_rate=1.0,
        grounded_judge_paid_model=_PAID_MODEL,
    )
    await gw.complete(
        task_type="news_summary", messages=_MSGS, schema=_Out, contains_personal_data=False
    )
    # Score was recorded from the paid judge.
    out = await read_groundedness_window(7, redis=patch_redis)
    assert out["instrumented"] is True
    assert out["value"] == pytest.approx(0.75)
    # The paid judge call count key was written.
    import datetime
    day = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d")
    raw = await patch_redis.get(_JUDGE_CALLS_KEY.format(model=_PAID_MODEL, day=day))
    assert int(raw) == 1
    # The model appears in the judge models set.
    members = await patch_redis.smembers(_JUDGE_SPEND_MODELS_KEY.format(day=day))
    assert _PAID_MODEL in members


async def test_paid_judge_also_429_returns_no_score(patch_redis):
    """Both free pool and paid judge 429 → no score recorded, call completes normally."""
    gw = OpenRouterGateway(
        client=_ClientPaid(_valid(), paid_model=_PAID_MODEL, paid_score=None),
        free_models=["free_a"],
        redis=patch_redis,
        groundedness_sample_rate=1.0,
        grounded_judge_paid_model=_PAID_MODEL,
    )
    res = await gw.complete(
        task_type="news_summary", messages=_MSGS, schema=_Out, contains_personal_data=False
    )
    assert res.model_used == "free_a"  # serve result unaffected
    out = await read_groundedness_window(7, redis=patch_redis)
    assert out["instrumented"] is False  # no score written


async def test_no_paid_model_no_fallback(patch_redis):
    """When grounded_judge_paid_model is empty, no paid call is attempted."""

    class _FreeAll429:
        """All calls 429 for the judge; serve always succeeds."""

        def __init__(self, output: str) -> None:
            self._output = output
            self.judge_calls: list[str] = []

        async def create(self, *, model, messages, **kw):
            sys_msg = messages[0].get("content", "") if messages else ""
            if _JUDGE_MARKER in sys_msg:
                self.judge_calls.append(model)
                raise _rate_limit_err()
            return _Resp(self._output)

    completions = _FreeAll429(_valid())

    class _ChatFree:
        def __init__(self) -> None:
            self.completions = completions

    class _ClientFree:
        def __init__(self) -> None:
            self.chat = _ChatFree()

    gw = OpenRouterGateway(
        client=_ClientFree(),
        free_models=["free_a"],
        redis=patch_redis,
        groundedness_sample_rate=1.0,
        grounded_judge_paid_model="",  # disabled
    )
    await gw.complete(
        task_type="news_summary", messages=_MSGS, schema=_Out, contains_personal_data=False
    )
    # Only free judge was attempted, no paid model used.
    assert completions.judge_calls == ["free_a"]
    out = await read_groundedness_window(7, redis=patch_redis)
    assert out["instrumented"] is False


async def test_paid_judge_does_not_pollute_latency_or_spend(patch_redis):
    """Paid judge call via _judge_call does NOT add to latency or serve-path spend."""
    gw = OpenRouterGateway(
        client=_ClientPaid(_valid(), paid_model=_PAID_MODEL, paid_score=0.8),
        free_models=["free_a"],
        redis=patch_redis,
        groundedness_sample_rate=1.0,
        grounded_judge_paid_model=_PAID_MODEL,
    )
    await gw.complete(
        task_type="news_summary", messages=_MSGS, schema=_Out, contains_personal_data=False
    )
    latency = await read_latency_window(7, redis=patch_redis)
    spend = await read_spend_window(7, redis=patch_redis)
    # Exactly one served response timed and tallied (the free_a serve call).
    assert latency["sample_count"] == 1
    assert spend["total_calls"] == 1
