"""
Unit tests for the mood NEWS-SENTIMENT signal (Phase 2, 11th factor) — no network.

The gateway is a fake that runs the REAL QualityValidator over a supplied raw dict,
so the advisory-verb screen and schema validation are genuinely exercised (an
advisory verb in the output is rejected exactly as the live gateway would).

Covered:
  - norm_news_sentiment direction: positive → >0.5, negative → <0.5, neutral = 0.5
  - positive headlines → >0.5; negative → <0.5
  - no/empty headlines → None (no gateway call)
  - gateway error → None
  - an LLM output containing a banned advisory verb → filtered → None
  - below the confidence floor → None
  - the prompt carries headline text only, no numeric score
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from dhanradar.ai_gateway.errors import GatewayError, QualityValidationError
from dhanradar.ai_gateway.gateway import CompletionResult
from dhanradar.ai_gateway.quality import QualityValidator
from dhanradar.mood import news_sentiment as ns
from dhanradar.mood.signals import norm_news_sentiment


# ---------------------------------------------------------------------------
# Fake gateway — runs the real QualityValidator (advisory screen + schema)
# ---------------------------------------------------------------------------
class _ValidatingGateway:
    """complete() validates `raw` with the real QualityValidator for the given
    schema, then returns a CompletionResult — mirroring the live gateway's
    structure + advisory screen. Raises GatewayError (QualityValidationError) on a
    rejected output, exactly as the real gateway does."""

    def __init__(self, raw: dict):
        self._raw = raw

    async def complete(self, *, task_type, messages, schema, **kwargs):  # noqa: ANN001
        output = QualityValidator(schema).validate(self._raw)  # raises on advisory/schema fail
        return CompletionResult(output=output, model_used="test-model")


class _RaisingGateway:
    async def complete(self, *, task_type, messages, schema, **kwargs):  # noqa: ANN001
        raise GatewayError("simulated gateway failure")


def _db_with_headlines(headlines: list[str]) -> AsyncMock:
    """An AsyncMock db whose get_recent_headlines (patched in news.service) returns
    `headlines`. We patch the service function rather than build SQL."""
    return AsyncMock()


def _raw(tone: str, *, confidence: float = 0.6, extra_signal: str = "broad market coverage") -> dict:
    return {
        "confidence": confidence,
        "confidence_band": "medium",
        "contributing_signals": ["earnings season headlines", extra_signal],
        "contradicting_signals": [],
        "tone": tone,
    }


# ---------------------------------------------------------------------------
# norm_news_sentiment
# ---------------------------------------------------------------------------
def test_norm_news_sentiment_direction():
    assert norm_news_sentiment("positive") > 0.5
    assert norm_news_sentiment("slightly_positive") > 0.5
    assert norm_news_sentiment("neutral") == 0.5
    assert norm_news_sentiment("slightly_negative") < 0.5
    assert norm_news_sentiment("negative") < 0.5
    assert norm_news_sentiment("not_a_tone") is None  # unknown → signal absent


# ---------------------------------------------------------------------------
# fetch_news_sentiment
# ---------------------------------------------------------------------------
async def test_positive_headlines_give_above_half(monkeypatch):
    monkeypatch.setattr(
        "dhanradar.news.service.get_recent_headlines",
        AsyncMock(return_value=["Markets rally as inflation cools", "FIIs return to equities"]),
    )
    gw = _ValidatingGateway(_raw("positive"))
    val = await ns.fetch_news_sentiment(gw, _db_with_headlines([]))
    assert val is not None and val > 0.5


async def test_negative_headlines_give_below_half(monkeypatch):
    monkeypatch.setattr(
        "dhanradar.news.service.get_recent_headlines",
        AsyncMock(return_value=["Sensex tumbles on global selloff", "Rupee hits record low"]),
    )
    gw = _ValidatingGateway(_raw("negative"))
    val = await ns.fetch_news_sentiment(gw, _db_with_headlines([]))
    assert val is not None and val < 0.5


async def test_no_headlines_returns_none_without_calling_gateway(monkeypatch):
    monkeypatch.setattr(
        "dhanradar.news.service.get_recent_headlines", AsyncMock(return_value=[])
    )
    gw = AsyncMock()  # must NOT be called
    val = await ns.fetch_news_sentiment(gw, _db_with_headlines([]))
    assert val is None
    gw.complete.assert_not_called()


async def test_headline_read_failure_returns_none(monkeypatch):
    monkeypatch.setattr(
        "dhanradar.news.service.get_recent_headlines",
        AsyncMock(side_effect=RuntimeError("db down")),
    )
    val = await ns.fetch_news_sentiment(AsyncMock(), _db_with_headlines([]))
    assert val is None


async def test_gateway_error_returns_none(monkeypatch):
    monkeypatch.setattr(
        "dhanradar.news.service.get_recent_headlines",
        AsyncMock(return_value=["Some market headline today"]),
    )
    val = await ns.fetch_news_sentiment(_RaisingGateway(), _db_with_headlines([]))
    assert val is None


async def test_advisory_verb_in_output_is_filtered_to_none(monkeypatch):
    """An advisory verb in the model output is rejected by the real QualityValidator
    (→ GatewayError) and surfaces as a withheld signal (None)."""
    monkeypatch.setattr(
        "dhanradar.news.service.get_recent_headlines",
        AsyncMock(return_value=["Market headline today"]),
    )
    bad = _raw("positive", extra_signal="investors should buy this dip")  # 'buy' trips the screen
    # sanity: the validator really rejects this raw output
    try:
        QualityValidator(ns.NewsSentiment).validate(bad)
        raise AssertionError("expected QualityValidationError")
    except QualityValidationError:
        pass
    val = await ns.fetch_news_sentiment(_ValidatingGateway(bad), _db_with_headlines([]))
    assert val is None


async def test_below_confidence_floor_returns_none(monkeypatch):
    monkeypatch.setattr(
        "dhanradar.news.service.get_recent_headlines",
        AsyncMock(return_value=["Market headline today"]),
    )
    gw = _ValidatingGateway(_raw("positive", confidence=0.2))  # < 0.30 floor
    val = await ns.fetch_news_sentiment(gw, _db_with_headlines([]))
    assert val is None


# ---------------------------------------------------------------------------
# Prompt hygiene — headlines only, no numeric score
# ---------------------------------------------------------------------------
def test_build_messages_carries_headlines_no_numeric_score():
    msgs = ns.build_messages(["Nifty ends flat", "RBI holds rates"])
    blob = " ".join(m["content"] for m in msgs)
    assert "Nifty ends flat" in blob
    assert "RBI holds rates" in blob
    # no injected mood_score / confidence float in the prompt context we build
    assert "mood_score" not in blob
