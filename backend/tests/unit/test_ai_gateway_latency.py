"""
Unit tests for AI-gateway latency instrumentation (PR-1).

Exercises the real feature end-to-end against fakeredis (the `patch_redis`
fixture):
  - record_latency + read_latency_window round-trip (avg, sample_count, window)
  - a served gateway.complete() call records a latency sample
  - non-fatal contracts: a Redis failure on record NEVER raises; a read failure
    degrades to instrumented=False instead of 500-ing
  - absurd / negative samples are ignored (do not pollute the average)
"""

from __future__ import annotations

import json

from dhanradar.ai_gateway import AIOutputBase, OpenRouterGateway
from dhanradar.ai_gateway.metrics import read_latency_window, record_latency


class _StockOut(AIOutputBase):
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


# --- minimal fake OpenAI-compatible client -----------------------------------
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
    def __init__(self, content: str) -> None:
        self._content = content

    async def create(self, *, model, messages, **kw):
        return _Resp(self._content)


class _Chat:
    def __init__(self, content: str) -> None:
        self.completions = _Completions(content)


class _Client:
    def __init__(self, content: str) -> None:
        self.chat = _Chat(content)


_MSGS = [{"role": "user", "content": "analyse"}]


# --- metrics helper round-trip -----------------------------------------------
async def test_record_then_read_reports_average(patch_redis):
    await record_latency(100.0, redis=patch_redis)
    await record_latency(300.0, redis=patch_redis)
    out = await read_latency_window(7, redis=patch_redis)
    assert out["instrumented"] is True
    assert out["sample_count"] == 2
    assert out["value_ms"] == 200.0  # (100 + 300) / 2
    assert out["window_days"] == 7


async def test_read_with_no_samples_is_not_instrumented(patch_redis):
    out = await read_latency_window(7, redis=patch_redis)
    assert out["instrumented"] is False
    assert out["value_ms"] is None
    assert out["sample_count"] == 0


async def test_both_keys_get_a_ttl(patch_redis):
    # Regression for the Tier-B C1 finding: every write must set a TTL on BOTH
    # keys so a partial failure can never leave an unbounded key that later
    # deflates the rolling average.
    import datetime

    day = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d")
    await record_latency(150.0, redis=patch_redis)
    sum_ttl = await patch_redis.ttl(f"ai:latency:sum:{day}")
    count_ttl = await patch_redis.ttl(f"ai:latency:count:{day}")
    assert sum_ttl > 0
    assert count_ttl > 0


async def test_negative_and_absurd_samples_are_ignored(patch_redis):
    await record_latency(-5.0, redis=patch_redis)          # negative → ignored
    await record_latency(10_000_000.0, redis=patch_redis)  # > 10 min → ignored
    await record_latency(250.0, redis=patch_redis)         # the only real sample
    out = await read_latency_window(7, redis=patch_redis)
    assert out["sample_count"] == 1
    assert out["value_ms"] == 250.0


# --- non-fatal contracts ------------------------------------------------------
class _BoomRedis:
    async def incr(self, *a, **k):
        raise RuntimeError("redis down")

    async def get(self, *a, **k):
        raise RuntimeError("redis down")


async def test_record_latency_never_raises_on_redis_failure():
    # Must return None silently, not propagate — would otherwise break an AI call.
    assert await record_latency(123.0, redis=_BoomRedis()) is None


async def test_read_latency_window_degrades_on_redis_failure():
    out = await read_latency_window(7, redis=_BoomRedis())
    assert out["instrumented"] is False
    assert out["value_ms"] is None


# --- the actual feature: a served gateway call records a sample ---------------
async def test_gateway_complete_records_latency_sample(patch_redis):
    gw = OpenRouterGateway(client=_Client(_valid()), free_models=["free_a"], redis=patch_redis)
    res = await gw.complete(
        task_type="news_summary",
        messages=_MSGS,
        schema=_StockOut,
        contains_personal_data=False,
    )
    assert res.model_used == "free_a"
    out = await read_latency_window(7, redis=patch_redis)
    assert out["instrumented"] is True
    assert out["sample_count"] == 1
    assert out["value_ms"] is not None and out["value_ms"] >= 0.0
