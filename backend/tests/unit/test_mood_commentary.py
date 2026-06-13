"""
Unit tests for Market Mood AI commentary (B35-e), the second governed gateway consumer.

Covers the governed-gate behaviour (mirrors test_mf_commentary, minus the consent gate
since mood is market-wide aggregate data with no PII):
  1. Happy path — valid output → commentary returned, audit written, gateway called with
     contains_personal_data=False and task_type=mood_commentary.
  2. Confidence floor (B22) — confidence < 0.30 → None, low-confidence logged, NO audit.
  3. Budget exhausted — BudgetExhaustedError → None, no audit, never raises.
  4. Gateway error — GatewayError subclass → None, no audit, never raises.
  + Advisory-verb rejection through QualityValidator on MoodCommentary.

No network, no DB: all external call sites are monkeypatched with async spies.
asyncio_mode = "auto" (pyproject.toml) — no decorator needed.
"""

from __future__ import annotations

import pytest

from dhanradar.ai_gateway.errors import (
    AllFreeModelsFailedError,
    QualityValidationError,
)
from dhanradar.ai_gateway.gateway import CompletionResult
from dhanradar.ai_gateway.quality import QualityValidator
from dhanradar.budget import BudgetExhaustedError
from dhanradar.mood.commentary import (
    MoodCommentary,
    build_messages,
    generate_mood_commentary,
)
from dhanradar.mood.compute import MoodResult

# ---------------------------------------------------------------------------
# Helpers — fake gateway, mood result, mood commentary
# ---------------------------------------------------------------------------


class _FakeGateway:
    """Configurable async gateway stub. Records kwargs passed to complete()."""

    def __init__(self, result: CompletionResult | None = None, raises: Exception | None = None) -> None:
        self._result = result
        self._raises = raises
        self.calls: list[dict] = []

    async def complete(self, **kwargs) -> CompletionResult:  # type: ignore[return]
        self.calls.append(kwargs)
        if self._raises is not None:
            raise self._raises
        return self._result  # type: ignore[return-value]


def _mood_result(regime: str = "greed", band: str = "high", dq: str = "ok") -> MoodResult:
    return MoodResult(
        mood_score=72.0,
        regime=regime,
        confidence_score=0.8,
        confidence_band=band,
        inputs_available=9,
        data_quality=dq,
        input_vector={"nifty_trend": 0.8},
        contributing_factors=["nifty_trend", "fii_flows"],
        contradicting_factors=["india_vix"],
        commentary_allowed=True,
    )


def _make_mood_commentary(confidence: float, band: str, commentary: str) -> MoodCommentary:
    signals = ["nifty_trend_positive", "fii_inflows"]
    if confidence > 0.7:
        signals.append("breadth_strong")
    return MoodCommentary(
        confidence=confidence,
        confidence_band=band,  # type: ignore[arg-type]
        contributing_signals=signals,
        contradicting_signals=[],
        commentary=commentary,
    )


def _make_record_spy():
    calls: list[dict] = []

    async def _spy(**kwargs) -> bool:
        calls.append(kwargs)
        return True

    _spy.calls = calls  # type: ignore[attr-defined]
    return _spy


def _make_log_low_confidence_spy():
    calls: list[dict] = []

    async def _spy(**kwargs) -> bool:
        calls.append(kwargs)
        return True

    _spy.calls = calls  # type: ignore[attr-defined]
    return _spy


# ---------------------------------------------------------------------------
# build_messages — PII-free, no numeric mood_score
# ---------------------------------------------------------------------------


def test_build_messages_is_pii_free_and_carries_no_numeric_score():
    """The prompt must carry the regime/band/signals but NEVER the numeric mood_score
    or confidence float (non-neg #2)."""
    msgs = build_messages(_mood_result())
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    blob = msgs[1]["content"]
    assert "greed" in blob
    assert "nifty_trend" in blob
    # Numeric mood score / confidence float must not leak into the prompt context.
    assert "72.0" not in blob
    assert "0.8" not in blob


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------


async def test_happy_path_returns_commentary_and_audits(monkeypatch):
    commentary_text = "Market sentiment skews positive, led by the Nifty's trend and FII inflows."
    output = _make_mood_commentary(0.74, "high", commentary_text)
    fake_gw = _FakeGateway(result=CompletionResult(output=output, model_used="glm-4.6-flash"))

    record_spy = _make_record_spy()
    log_spy = _make_log_low_confidence_spy()
    monkeypatch.setattr("dhanradar.mood.commentary.record_served_label", record_spy)
    monkeypatch.setattr("dhanradar.mood.commentary.log_low_confidence", log_spy)

    result = await generate_mood_commentary(fake_gw, result=_mood_result(), request_id="req-1")

    assert result == commentary_text

    # Gateway called on the non-personal path with the mood task type and schema.
    assert len(fake_gw.calls) == 1
    gw_call = fake_gw.calls[0]
    assert gw_call["task_type"] == "mood_commentary"
    assert gw_call["contains_personal_data"] is False
    assert "cross_border_consent_verified" not in gw_call  # no consent on the non-personal path
    assert gw_call["schema"] is MoodCommentary

    # Audit written exactly once with the correct surface; low-confidence NOT logged.
    assert len(record_spy.calls) == 1
    audit = record_spy.calls[0]
    assert audit["surface"] == "mood_commentary"
    assert audit["model"] == "glm-4.6-flash"
    assert audit["recommendation_type"] == "educational_label"
    assert audit["label"] == "ai_commentary"
    assert len(log_spy.calls) == 0


# ---------------------------------------------------------------------------
# 2. Confidence floor (B22)
# ---------------------------------------------------------------------------


async def test_confidence_floor_returns_none_and_logs(monkeypatch):
    output = _make_mood_commentary(0.20, "low", "Signals are mixed and inconclusive.")
    fake_gw = _FakeGateway(result=CompletionResult(output=output, model_used="glm-4.6-flash"))

    record_spy = _make_record_spy()
    log_spy = _make_log_low_confidence_spy()
    monkeypatch.setattr("dhanradar.mood.commentary.record_served_label", record_spy)
    monkeypatch.setattr("dhanradar.mood.commentary.log_low_confidence", log_spy)

    result = await generate_mood_commentary(fake_gw, result=_mood_result(), request_id="req-low")

    assert result is None
    # Low-confidence event logged with the right score; served-label audit NOT written.
    assert len(log_spy.calls) == 1
    assert log_spy.calls[0]["confidence_score"] == pytest.approx(0.20)
    assert log_spy.calls[0]["surface"] == "mood_commentary"
    assert len(record_spy.calls) == 0


# ---------------------------------------------------------------------------
# 3. Budget exhausted — best-effort, never raises
# ---------------------------------------------------------------------------


async def test_budget_exhausted_returns_none(monkeypatch):
    fake_gw = _FakeGateway(raises=BudgetExhaustedError("free", 1000, 1000))
    record_spy = _make_record_spy()
    log_spy = _make_log_low_confidence_spy()
    monkeypatch.setattr("dhanradar.mood.commentary.record_served_label", record_spy)
    monkeypatch.setattr("dhanradar.mood.commentary.log_low_confidence", log_spy)

    result = await generate_mood_commentary(fake_gw, result=_mood_result())

    assert result is None
    assert len(record_spy.calls) == 0
    assert len(log_spy.calls) == 0


# ---------------------------------------------------------------------------
# 4. Gateway error — best-effort, never raises
# ---------------------------------------------------------------------------


async def test_gateway_error_returns_none(monkeypatch):
    fake_gw = _FakeGateway(raises=AllFreeModelsFailedError("mood_commentary"))
    record_spy = _make_record_spy()
    log_spy = _make_log_low_confidence_spy()
    monkeypatch.setattr("dhanradar.mood.commentary.record_served_label", record_spy)
    monkeypatch.setattr("dhanradar.mood.commentary.log_low_confidence", log_spy)

    result = await generate_mood_commentary(fake_gw, result=_mood_result())

    assert result is None
    assert len(record_spy.calls) == 0


# ---------------------------------------------------------------------------
# Advisory-verb rejection through QualityValidator
# ---------------------------------------------------------------------------


def test_mood_commentary_advisory_text_rejected_by_quality_validator():
    """QualityValidator screens MoodCommentary string fields — an advisory verb in the
    commentary must raise QualityValidationError (proves the screen covers the field)."""
    validator = QualityValidator(MoodCommentary)
    with pytest.raises(QualityValidationError):
        validator.validate(
            {
                "confidence": 0.6,
                "confidence_band": "medium",
                "contributing_signals": ["nifty_trend", "vix"],
                "contradicting_signals": [],
                "commentary": "You should sell equities and switch to cash now.",
            }
        )
