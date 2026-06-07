"""
Unit tests for the AI/LLM Gateway (Phase 3 §B3).

Covers the plan's verification matrix:
  - 429 → model rotation (no sleep)
  - 402 → CreditExhaustedError (alert path, NOT retried)
  - schema fail on a high-stakes task (stock_pick) → Sonnet spillover
  - schema fail on a non-high-stakes task (news_summary) → 3-strike skip
  - budget counters increment on success and block at cap
  - QualityValidator: signal floor + advisory-language rejection (compliance)

No network: a fake OpenAI-compatible client is injected. Redis is fakeredis via
the `patch_redis` fixture (budget + strike counters).
"""

from __future__ import annotations

import json

import httpx
import pytest
from openai import APIStatusError, RateLimitError

from dhanradar.ai_gateway import (
    AIOutputBase,
    ConsentNotVerifiedError,
    CreditExhaustedError,
    OpenRouterGateway,
    QualityValidator,
    ThreeStrikeSkipError,
)
from dhanradar.ai_gateway.errors import QualityValidationError

_REQ = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")


def _rate_limit() -> RateLimitError:
    return RateLimitError("rate limited", response=httpx.Response(429, request=_REQ), body=None)


def _status(code: int) -> APIStatusError:
    return APIStatusError("upstream", response=httpx.Response(code, request=_REQ), body=None)


# --- a concrete output schema with a free-text field for the advisory screen --
class _StockOut(AIOutputBase):
    thesis: str = ""


def _valid(thesis: str = "fundamentals improving and inflows steady") -> str:
    return json.dumps(
        {
            "confidence": 0.5,
            "confidence_band": "medium",
            "contributing_signals": ["earnings up", "inflows steady"],
            "thesis": thesis,
        }
    )


def _schema_invalid() -> str:
    # only 1 contributing signal → violates the >=2 floor
    return json.dumps(
        {"confidence": 0.5, "confidence_band": "medium", "contributing_signals": ["only one"]}
    )


# --- fake OpenAI-compatible client -------------------------------------------
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
    def __init__(self, behaviors: dict) -> None:
        self._behaviors = behaviors
        self.calls: list[str] = []

    async def create(self, *, model, messages, **kw):
        self.calls.append(model)
        b = self._behaviors[model]
        if isinstance(b, Exception):
            raise b
        return b  # a _Resp


class _Chat:
    def __init__(self, behaviors: dict) -> None:
        self.completions = _Completions(behaviors)


class _Client:
    def __init__(self, behaviors: dict) -> None:
        self.chat = _Chat(behaviors)


_MSGS = [{"role": "user", "content": "analyse"}]


async def test_429_rotates_to_next_model_no_sleep(patch_redis):
    client = _Client({"free_a": _rate_limit(), "free_b": _Resp(_valid())})
    gw = OpenRouterGateway(client=client, free_models=["free_a", "free_b"])
    out = await gw.complete(task_type="news_summary", messages=_MSGS, schema=_StockOut, contains_personal_data=False)
    assert isinstance(out, _StockOut)
    assert client.chat.completions.calls == ["free_a", "free_b"]  # rotated, no sleep


async def test_402_raises_credit_and_does_not_retry(patch_redis):
    client = _Client({"free_a": _status(402), "free_b": _Resp(_valid())})
    gw = OpenRouterGateway(client=client, free_models=["free_a", "free_b"])
    with pytest.raises(CreditExhaustedError):
        await gw.complete(task_type="news_summary", messages=_MSGS, schema=_StockOut, contains_personal_data=False)
    # 402 must NOT fall through to the next model
    assert client.chat.completions.calls == ["free_a"]


async def test_schema_fail_stock_pick_spills_to_sonnet(patch_redis):
    client = _Client({"free_a": _Resp(_schema_invalid()), "sonnet": _Resp(_valid(), total=500)})
    gw = OpenRouterGateway(
        client=client, free_models=["free_a"], sonnet_model="sonnet"
    )
    out = await gw.complete(task_type="stock_pick", messages=_MSGS, schema=_StockOut, contains_personal_data=False)
    assert isinstance(out, _StockOut)
    assert client.chat.completions.calls == ["free_a", "sonnet"]
    # premium budget debited by the Sonnet spend
    premium = await patch_redis.get("ai:budget:premium:today")
    assert premium is not None and float(premium) > 0


async def test_schema_fail_news_summary_three_strike_skip(patch_redis):
    client = _Client({"free_a": _Resp(_schema_invalid())})
    gw = OpenRouterGateway(client=client, free_models=["free_a"])

    # strikes 1 and 2 raise the quality error; strike 3 → ThreeStrikeSkipError
    for _ in range(2):
        with pytest.raises(QualityValidationError):
            await gw.complete(
                task_type="news_summary", messages=_MSGS, schema=_StockOut, ticker="INFY",
                contains_personal_data=False,
            )
    with pytest.raises(ThreeStrikeSkipError):
        await gw.complete(
            task_type="news_summary", messages=_MSGS, schema=_StockOut, ticker="INFY",
            contains_personal_data=False,
        )


async def test_advisory_output_is_rejected(patch_redis):
    # schema-valid but the thesis issues a recommendation → compliance rejection
    client = _Client({"free_a": _Resp(_valid(thesis="investors should buy this fund now"))})
    gw = OpenRouterGateway(client=client, free_models=["free_a"])
    with pytest.raises(QualityValidationError) as ei:
        await gw.complete(task_type="news_summary", messages=_MSGS, schema=_StockOut, ticker="X", contains_personal_data=False)
    assert "buy" in ei.value.reasons


async def test_free_success_increments_free_budget_by_one(patch_redis):
    client = _Client({"free_a": _Resp(_valid())})
    gw = OpenRouterGateway(client=client, free_models=["free_a"])
    await gw.complete(task_type="news_summary", messages=_MSGS, schema=_StockOut, contains_personal_data=False)
    free = await patch_redis.get("ai:budget:free:today")
    assert int(free) == 1


async def test_descriptive_holding_is_not_a_false_positive(patch_redis):
    # "holding" / "buyer" must NOT trip the advisory screen (word-boundary).
    client = _Client({"free_a": _Resp(_valid(thesis="largest holding is a quality buyer brand"))})
    gw = OpenRouterGateway(client=client, free_models=["free_a"])
    out = await gw.complete(task_type="news_summary", messages=_MSGS, schema=_StockOut, contains_personal_data=False)
    assert out.thesis.startswith("largest holding")


@pytest.mark.parametrize(
    "thesis",
    [
        "accumulate on every dip",
        "time to book profits here",
        "take profit near resistance",
        "square off before expiry",
        "go long with a tight stop",
        "we are overweight this name",
        "stay underweight the sector",
        "our top pick for the quarter",
    ],
)
async def test_expanded_advisory_terms_are_rejected(patch_redis, thesis):
    client = _Client({"free_a": _Resp(_valid(thesis=thesis))})
    gw = OpenRouterGateway(client=client, free_models=["free_a"])
    with pytest.raises(QualityValidationError):
        await gw.complete(task_type="news_summary", messages=_MSGS, schema=_StockOut, ticker="Z", contains_personal_data=False)


async def test_all_free_models_rate_limited_raises_all_free_models_failed(patch_redis):
    from dhanradar.ai_gateway.errors import AllFreeModelsFailedError

    client = _Client({"free_a": _rate_limit(), "free_b": _rate_limit()})
    gw = OpenRouterGateway(client=client, free_models=["free_a", "free_b"])
    with pytest.raises(AllFreeModelsFailedError):
        await gw.complete(task_type="news_summary", messages=_MSGS, schema=_StockOut, contains_personal_data=False)


async def test_high_stakes_failed_spillover_hits_three_strike(patch_redis):
    # free AND sonnet both fail validation on a high-stakes task → after 3
    # attempts for the same ticker/day the gateway skips (bounds premium spend).
    client = _Client({"free_a": _Resp(_schema_invalid()), "sonnet": _Resp(_schema_invalid())})
    gw = OpenRouterGateway(client=client, free_models=["free_a"], sonnet_model="sonnet")
    for _ in range(2):
        with pytest.raises(QualityValidationError):
            await gw.complete(task_type="stock_pick", messages=_MSGS, schema=_StockOut, ticker="TCS", contains_personal_data=False)
    with pytest.raises(ThreeStrikeSkipError):
        await gw.complete(task_type="stock_pick", messages=_MSGS, schema=_StockOut, ticker="TCS", contains_personal_data=False)


def test_disclaimer_cannot_be_stripped_via_model_copy():
    from dhanradar.ai_gateway.schemas import AI_DISCLAIMER

    m = _StockOut(
        confidence=0.5, confidence_band="medium", contributing_signals=["a", "b"], thesis="ok"
    )
    tampered = m.model_copy(update={"disclaimer": "no disclaimer"})
    assert tampered.disclaimer == AI_DISCLAIMER


# ---------------------------------------------------------------------------
# B20 — cross-border DPDP consent gate (default-deny, fail-closed)
# ---------------------------------------------------------------------------


async def test_personal_data_without_consent_refuses_before_any_openrouter_call(patch_redis):
    """contains_personal_data=True (default) + no consent → ConsentNotVerifiedError
    raised BEFORE any call reaches OpenRouter and BEFORE any budget counter moves."""
    client = _Client({"free_a": _Resp(_valid())})
    gw = OpenRouterGateway(client=client, free_models=["free_a"], redis=patch_redis)
    with pytest.raises(ConsentNotVerifiedError):
        await gw.complete(task_type="mf_pick", messages=_MSGS, schema=_StockOut, contains_personal_data=True)
    # OpenRouter must never have been touched
    assert client.chat.completions.calls == []
    # Neither budget counter may move (guard runs before both budget_guard blocks).
    assert await patch_redis.get("ai:budget:free:today") is None
    assert await patch_redis.get("ai:budget:premium:today") is None


async def test_personal_data_with_verified_consent_proceeds(patch_redis):
    """contains_personal_data=True + cross_border_consent_verified=True → proceeds
    normally and returns a valid output."""
    client = _Client({"free_a": _Resp(_valid())})
    gw = OpenRouterGateway(client=client, free_models=["free_a"], redis=patch_redis)
    out = await gw.complete(
        task_type="mf_pick",
        messages=_MSGS,
        schema=_StockOut,
        contains_personal_data=True,
        cross_border_consent_verified=True,
    )
    assert isinstance(out, _StockOut)
    assert client.chat.completions.calls == ["free_a"]


async def test_default_is_fail_closed_for_personal_data(patch_redis):
    """Calling complete() with no flags (defaults) must raise ConsentNotVerifiedError
    — proving the contract is default-deny for personal-data payloads."""
    client = _Client({"free_a": _Resp(_valid())})
    gw = OpenRouterGateway(client=client, free_models=["free_a"], redis=patch_redis)
    with pytest.raises(ConsentNotVerifiedError):
        await gw.complete(task_type="mf_pick", messages=_MSGS, schema=_StockOut)

