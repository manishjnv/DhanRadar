"""
Unit tests for the advice-boundary breach counter (PR-3).

The gateway's quality validator rejects LLM output containing banned advisory
verbs (SEBI educational boundary, non-neg #1). PR-3 counts those rejections in a
per-day Redis counter, surfaced on /admin/ai/safety + /admin/health. Tests:
  - the validator tags advisory rejections (advisory_breach=True) and leaves a
    plain schema failure untagged (False)
  - a served-but-advisory gateway response increments the counter
  - a plain SCHEMA failure does NOT increment it
  - record/read round-trip; a 0 read is instrumented=True (meaningful clean pass)
  - non-fatal: a Redis failure never raises / never 500s
"""

from __future__ import annotations

import json

import pytest

from dhanradar.ai_gateway import AIOutputBase, OpenRouterGateway
from dhanradar.ai_gateway.errors import QualityValidationError
from dhanradar.ai_gateway.metrics import read_advisory_breaches, record_advisory_breach
from dhanradar.ai_gateway.quality import QualityValidator


class _Out(AIOutputBase):
    thesis: str = ""


def _advisory() -> str:
    # schema-valid but the free-text carries a banned advisory verb
    return json.dumps(
        {
            "confidence": 0.5,
            "confidence_band": "medium",
            "contributing_signals": ["earnings up", "inflows steady"],
            "thesis": "this is a strong buy right now",
        }
    )


def _schema_invalid() -> str:
    return json.dumps(
        {"confidence": 0.5, "confidence_band": "medium", "contributing_signals": ["only one"]}
    )


# --- validator tags the failure mode correctly -------------------------------
def test_validator_flags_advisory_breach():
    with pytest.raises(QualityValidationError) as ei:
        QualityValidator(_Out).validate(json.loads(_advisory()))
    assert ei.value.advisory_breach is True


def test_validator_schema_failure_is_not_an_advisory_breach():
    with pytest.raises(QualityValidationError) as ei:
        QualityValidator(_Out).validate(json.loads(_schema_invalid()))
    assert ei.value.advisory_breach is False


# --- metrics round-trip -------------------------------------------------------
async def test_record_then_read_counts_breaches(patch_redis):
    await record_advisory_breach(redis=patch_redis)
    await record_advisory_breach(redis=patch_redis)
    out = await read_advisory_breaches(7, redis=patch_redis)
    assert out["instrumented"] is True
    assert out["value"] == 2
    assert out["window_days"] == 7


async def test_zero_read_is_instrumented(patch_redis):
    # Unlike latency/spend, a 0 is a MEANINGFUL clean reading (boundary held).
    out = await read_advisory_breaches(7, redis=patch_redis)
    assert out["instrumented"] is True
    assert out["value"] == 0


class _BoomRedis:
    async def incr(self, *a, **k):
        raise RuntimeError("redis down")

    async def get(self, *a, **k):
        raise RuntimeError("redis down")


async def test_record_never_raises_on_redis_failure():
    assert await record_advisory_breach(redis=_BoomRedis()) is None


async def test_read_degrades_on_redis_failure():
    out = await read_advisory_breaches(7, redis=_BoomRedis())
    assert out["instrumented"] is False
    assert out["value"] == 0


# --- fake client -------------------------------------------------------------
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


# --- gateway integration -----------------------------------------------------
async def test_gateway_counts_advisory_rejection(patch_redis):
    # free model returns advisory text → rejected → breach recorded, then the
    # non-high-stakes task exhausts the pool and raises (strike path).
    gw = OpenRouterGateway(client=_Client(_advisory()), free_models=["free_a"], redis=patch_redis)
    with pytest.raises(QualityValidationError):
        await gw.complete(
            task_type="news_summary", messages=_MSGS, schema=_Out, contains_personal_data=False
        )
    out = await read_advisory_breaches(7, redis=patch_redis)
    assert out["value"] == 1


async def test_gateway_does_not_count_plain_schema_failure(patch_redis):
    gw = OpenRouterGateway(
        client=_Client(_schema_invalid()), free_models=["free_a"], redis=patch_redis
    )
    with pytest.raises(QualityValidationError):
        await gw.complete(
            task_type="news_summary", messages=_MSGS, schema=_Out, contains_personal_data=False
        )
    out = await read_advisory_breaches(7, redis=patch_redis)
    assert out["value"] == 0  # schema miss is NOT a boundary breach
