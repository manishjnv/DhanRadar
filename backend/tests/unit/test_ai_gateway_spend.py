"""
Unit tests for AI-gateway per-model spend instrumentation (PR-2).

Exercises the real feature against fakeredis (the `patch_redis` fixture):
  - record_model_spend + read_spend_window round-trip (calls, usd, totals, sort)
  - a served FREE gateway call records calls=1 / usd=0 for that model
  - the Sonnet spillover records per-model USD for the sonnet model
  - the cheap paid fallback records per-model USD for the paid model
  - non-fatal contracts: a Redis failure on record NEVER raises; a read failure
    degrades to instrumented=False instead of 500-ing
  - the call tally is counted once (in _call), never double-counted by the USD site
"""

from __future__ import annotations

import json

import pytest

from dhanradar.ai_gateway import AIOutputBase, OpenRouterGateway
from dhanradar.ai_gateway.metrics import read_spend_window, record_model_spend


class _Out(AIOutputBase):
    thesis: str = ""


def _valid() -> str:
    return json.dumps(
        {
            "confidence": 0.5,
            "confidence_band": "medium",
            "contributing_signals": ["earnings up", "inflows steady"],
            "thesis": "fundamentals improving and inflows steady",
        }
    )


def _schema_invalid() -> str:
    return json.dumps(
        {"confidence": 0.5, "confidence_band": "medium", "contributing_signals": ["only one"]}
    )


# --- fake OpenAI-compatible client (behaviors keyed by model) ----------------
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
        return b


class _Chat:
    def __init__(self, behaviors: dict) -> None:
        self.completions = _Completions(behaviors)


class _Client:
    def __init__(self, behaviors: dict) -> None:
        self.chat = _Chat(behaviors)


def _rate_limit():
    import httpx
    from openai import RateLimitError

    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return RateLimitError("rate limited", response=httpx.Response(429, request=req), body=None)


_MSGS = [{"role": "user", "content": "analyse"}]


# --- metrics helper round-trip -----------------------------------------------
async def test_record_then_read_aggregates_per_model(patch_redis):
    await record_model_spend("model_a", calls=1, redis=patch_redis)
    await record_model_spend("model_a", calls=1, redis=patch_redis)
    await record_model_spend("model_b", calls=1, usd=0.25, redis=patch_redis)
    out = await read_spend_window(7, redis=patch_redis)

    assert out["instrumented"] is True
    assert out["total_calls"] == 3
    assert out["total_usd"] == pytest.approx(0.25)
    by_model = {m["model"]: m for m in out["models"]}
    assert by_model["model_a"]["calls"] == 2
    assert by_model["model_a"]["usd"] == pytest.approx(0.0)
    assert by_model["model_b"]["usd"] == pytest.approx(0.25)
    # sorted by usd desc → the paid model is first
    assert out["models"][0]["model"] == "model_b"


async def test_read_with_no_spend_is_not_instrumented(patch_redis):
    out = await read_spend_window(7, redis=patch_redis)
    assert out["instrumented"] is False
    assert out["models"] == []
    assert out["total_calls"] == 0


async def test_usd_only_write_does_not_add_a_call(patch_redis):
    # calls=0 (the USD-site shape) must add spend without inflating the tally.
    await record_model_spend("m", calls=1, redis=patch_redis)
    await record_model_spend("m", usd=1.5, redis=patch_redis)  # calls defaults to 0
    out = await read_spend_window(7, redis=patch_redis)
    row = out["models"][0]
    assert row["calls"] == 1
    assert row["usd"] == pytest.approx(1.5)


# --- non-fatal contracts ------------------------------------------------------
class _BoomRedis:
    async def sadd(self, *a, **k):
        raise RuntimeError("redis down")

    async def smembers(self, *a, **k):
        raise RuntimeError("redis down")


async def test_record_model_spend_never_raises_on_redis_failure():
    assert await record_model_spend("m", calls=1, usd=1.0, redis=_BoomRedis()) is None


async def test_read_spend_window_degrades_on_redis_failure():
    out = await read_spend_window(7, redis=_BoomRedis())
    assert out["instrumented"] is False
    assert out["models"] == []


# --- the feature end-to-end through the gateway ------------------------------
async def test_free_call_records_call_with_zero_usd(patch_redis):
    gw = OpenRouterGateway(client=_Client({"free_a": _Resp(_valid())}), free_models=["free_a"], redis=patch_redis)
    res = await gw.complete(
        task_type="news_summary", messages=_MSGS, schema=_Out, contains_personal_data=False
    )
    assert res.model_used == "free_a"
    out = await read_spend_window(7, redis=patch_redis)
    row = {m["model"]: m for m in out["models"]}["free_a"]
    assert row["calls"] == 1
    assert row["usd"] == pytest.approx(0.0)  # free model → no USD


async def test_sonnet_spillover_records_per_model_usd(patch_redis):
    # free_a fails schema on a high-stakes task → spill to sonnet (charged).
    gw = OpenRouterGateway(
        client=_Client({"free_a": _Resp(_schema_invalid()), "sonnet": _Resp(_valid(), total=500)}),
        free_models=["free_a"],
        sonnet_model="sonnet",
        redis=patch_redis,
    )
    res = await gw.complete(
        task_type="stock_pick", messages=_MSGS, schema=_Out, contains_personal_data=False
    )
    assert res.model_used == "sonnet"
    out = await read_spend_window(7, redis=patch_redis)
    by_model = {m["model"]: m for m in out["models"]}
    assert by_model["sonnet"]["calls"] == 1
    assert by_model["sonnet"]["usd"] > 0.0  # 500 tokens * $6/M = $0.003
    # the failed free call is still tallied (a billed response), at $0
    assert by_model["free_a"]["calls"] == 1
    assert by_model["free_a"]["usd"] == pytest.approx(0.0)


async def test_paid_fallback_records_per_model_usd(patch_redis):
    # free pool 429s → cheap paid fallback serves (charged).
    gw = OpenRouterGateway(
        client=_Client({"free_a": _rate_limit(), "paid_x": _Resp(_valid())}),
        free_models=["free_a"],
        paid_fallback_models=["paid_x"],
        paid_fallback_tasks=["news_sentiment"],
        redis=patch_redis,
    )
    res = await gw.complete(
        task_type="news_sentiment", messages=_MSGS, schema=_Out, contains_personal_data=False
    )
    assert res.model_used == "paid_x"
    out = await read_spend_window(7, redis=patch_redis)
    by_model = {m["model"]: m for m in out["models"]}
    assert by_model["paid_x"]["calls"] == 1
    # 100 tokens * $0.5/M default rate = $0.00005 → strictly > 0 proves USD
    # was actually recorded (a >= 0 assertion would pass on a silent zero).
    assert by_model["paid_x"]["usd"] > 0.0
    # the 429'd free model never served → not recorded
    assert "free_a" not in by_model
