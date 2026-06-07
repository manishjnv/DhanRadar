"""
Unit tests for MF portfolio AI commentary (B20/B21/B22 gated).

Covers all four acceptance scenarios from the spec:
  1. Happy path — consent granted, good output, audit written, public payload correct.
  2. Consent deny — gateway never called, audit never written.
  3. Confidence floor — low confidence logged, served-label audit NOT written.
  4. Budget skip — BudgetExhaustedError → unavailable, no audit.
  + Advisory-verb rejection through QualityValidator on MFCommentary.

No network, no DB: all external call sites are monkeypatched with async spies.
asyncio_mode = "auto" (pyproject.toml) — no decorator needed.
"""

from __future__ import annotations

import pytest

from dhanradar.ai_gateway.errors import QualityValidationError
from dhanradar.ai_gateway.gateway import CompletionResult
from dhanradar.ai_gateway.quality import QualityValidator
from dhanradar.budget import BudgetExhaustedError
from dhanradar.deps import ConsentRequiredError
from dhanradar.mf.commentary import MFCommentary, generate_commentary

# ---------------------------------------------------------------------------
# Helpers — fake gateway and fake snapshot
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


class _FakeSnapshot:
    """Minimal snapshot stub matching the fields build_messages reads."""

    def __init__(self) -> None:
        self.category_allocation = {"large_cap": 0.55, "mid_cap": 0.30, "debt": 0.15}
        self.overlap_matrix = {"ISIN1": {"ISIN2": 0.12}}
        self.xirr_pct = 11.5


_FAKE_FUNDS: list[dict] = [
    {"isin": "INF000K01EW2", "scheme_name": "Fund A"},
    {"isin": "INF200K01MF3", "scheme_name": "Fund B"},
]

_FAKE_DB = object()  # db is monkeypatched away; just needs to be non-None


def _make_mf_commentary(confidence: float, band: str, commentary: str) -> MFCommentary:
    """Build a valid MFCommentary for test use."""
    signals = ["category_concentration_observed", "overlap_detected"]
    if confidence > 0.7:
        signals.append("xirr_above_benchmark")
    return MFCommentary(
        confidence=confidence,
        confidence_band=band,  # type: ignore[arg-type]
        contributing_signals=signals,
        contradicting_signals=[],
        commentary=commentary,
    )


# ---------------------------------------------------------------------------
# Async spy factories (monkeypatch targets)
# ---------------------------------------------------------------------------


def _make_consent_spy(*, raises: Exception | None = None):
    """Returns an async spy for assert_consent."""
    calls: list[tuple] = []

    async def _spy(user_id: str, purpose: str, db: object) -> None:
        calls.append((user_id, purpose))
        if raises is not None:
            raise raises

    _spy.calls = calls  # type: ignore[attr-defined]
    return _spy


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
# Acceptance 1 — happy path
# ---------------------------------------------------------------------------


async def test_happy_path_returns_ok_payload(monkeypatch):
    """Consent granted, gateway returns valid output → state==ok, audit written,
    confidence float NOT in payload (non-neg #2)."""
    commentary_text = "Your portfolio leans toward large-cap funds with some overlap."
    output = _make_mf_commentary(0.66, "medium", commentary_text)
    fake_gw = _FakeGateway(result=CompletionResult(output=output, model_used="glm-4.6-flash"))

    consent_spy = _make_consent_spy()
    record_spy = _make_record_spy()
    log_spy = _make_log_low_confidence_spy()

    monkeypatch.setattr("dhanradar.mf.commentary.assert_consent", consent_spy)
    monkeypatch.setattr("dhanradar.mf.commentary.record_served_label", record_spy)
    monkeypatch.setattr("dhanradar.mf.commentary.log_low_confidence", log_spy)

    result = await generate_commentary(
        fake_gw,
        user_id="user-123",
        db=_FAKE_DB,
        snapshot=_FakeSnapshot(),
        funds=_FAKE_FUNDS,
        request_id="req-abc",
    )

    # State and commentary present.
    assert result["state"] == "ok"
    assert result["commentary"] == commentary_text

    # Non-neg #2: confidence float MUST NOT appear in the public payload.
    assert "confidence" not in result

    # confidence_band, signals, disclaimer all present.
    assert result["confidence_band"] == "medium"
    assert len(result["contributing_signals"]) >= 2
    assert "disclaimer" in result
    assert "disclaimer_version" in result

    # Audit written exactly once with the correct fields.
    assert len(record_spy.calls) == 1
    audit_call = record_spy.calls[0]
    assert audit_call["model"] == "glm-4.6-flash"
    assert audit_call["recommendation_type"] == "educational_label"
    assert audit_call["surface"] == "mf_commentary"

    # Gateway called with the required flags.
    assert len(fake_gw.calls) == 1
    gw_call = fake_gw.calls[0]
    assert gw_call["task_type"] == "mf_pick"
    assert gw_call["contains_personal_data"] is True
    assert gw_call["cross_border_consent_verified"] is True
    assert gw_call["schema"] is MFCommentary

    # Low-confidence log NOT called on the happy path.
    assert len(log_spy.calls) == 0


# ---------------------------------------------------------------------------
# Acceptance 2 — consent deny
# ---------------------------------------------------------------------------


async def test_consent_deny_never_calls_gateway(monkeypatch):
    """ConsentRequiredError → unavailable/consent_required; gateway never touched."""
    # Gateway that raises AssertionError if ever called — proves it is never reached.
    fake_gw = _FakeGateway(raises=AssertionError("gateway must not be called on consent deny"))

    consent_spy = _make_consent_spy(raises=ConsentRequiredError("cross_border_ai"))
    record_spy = _make_record_spy()
    log_spy = _make_log_low_confidence_spy()

    monkeypatch.setattr("dhanradar.mf.commentary.assert_consent", consent_spy)
    monkeypatch.setattr("dhanradar.mf.commentary.record_served_label", record_spy)
    monkeypatch.setattr("dhanradar.mf.commentary.log_low_confidence", log_spy)

    result = await generate_commentary(
        fake_gw,
        user_id="user-no-consent",
        db=_FAKE_DB,
        snapshot=_FakeSnapshot(),
        funds=_FAKE_FUNDS,
    )

    assert result["state"] == "unavailable"
    assert result["reason"] == "consent_required"
    assert "disclaimer" in result

    # Gateway must never have been touched.
    assert len(fake_gw.calls) == 0

    # Audit must never have been written.
    assert len(record_spy.calls) == 0


async def test_consent_gate_value_error_fails_closed(monkeypatch):
    """assert_consent raising ValueError (unknown purpose — a programming error)
    must fail CLOSED: never raise, never call the gateway, never audit. Guards the
    never-raises contract (Tier-B security finding 1)."""
    fake_gw = _FakeGateway(raises=AssertionError("gateway must not be called on consent error"))

    consent_spy = _make_consent_spy(raises=ValueError("Unknown consent purpose"))
    record_spy = _make_record_spy()
    log_spy = _make_log_low_confidence_spy()

    monkeypatch.setattr("dhanradar.mf.commentary.assert_consent", consent_spy)
    monkeypatch.setattr("dhanradar.mf.commentary.record_served_label", record_spy)
    monkeypatch.setattr("dhanradar.mf.commentary.log_low_confidence", log_spy)

    result = await generate_commentary(
        fake_gw, user_id="user-123", db=_FAKE_DB, snapshot=_FakeSnapshot(), funds=_FAKE_FUNDS
    )

    assert result["state"] == "unavailable"
    assert result["reason"] == "consent_gate_error"
    assert len(fake_gw.calls) == 0
    assert len(record_spy.calls) == 0


# ---------------------------------------------------------------------------
# Acceptance 3 — confidence floor (B22)
# ---------------------------------------------------------------------------


async def test_confidence_floor_returns_insufficient_data(monkeypatch):
    """Confidence 0.20 < 0.30 floor → insufficient_data; log_low_confidence called;
    record_served_label NOT called."""
    output = _make_mf_commentary(0.20, "low", "Not enough signal to describe the portfolio.")
    fake_gw = _FakeGateway(result=CompletionResult(output=output, model_used="glm-4.6-flash"))

    consent_spy = _make_consent_spy()
    record_spy = _make_record_spy()
    log_spy = _make_log_low_confidence_spy()

    monkeypatch.setattr("dhanradar.mf.commentary.assert_consent", consent_spy)
    monkeypatch.setattr("dhanradar.mf.commentary.record_served_label", record_spy)
    monkeypatch.setattr("dhanradar.mf.commentary.log_low_confidence", log_spy)

    result = await generate_commentary(
        fake_gw,
        user_id="user-123",
        db=_FAKE_DB,
        snapshot=_FakeSnapshot(),
        funds=_FAKE_FUNDS,
        request_id="req-low",
    )

    assert result["state"] == "insufficient_data"
    assert "disclaimer" in result

    # Low-confidence event logged with the right score.
    assert len(log_spy.calls) == 1
    log_call = log_spy.calls[0]
    assert log_call["confidence_score"] == pytest.approx(0.20)

    # Served-label audit must NOT have been written.
    assert len(record_spy.calls) == 0


# ---------------------------------------------------------------------------
# Acceptance 4 — budget skip (B22/B20 gateway-level guard)
# ---------------------------------------------------------------------------


async def test_budget_exhausted_returns_unavailable(monkeypatch):
    """BudgetExhaustedError → state==unavailable; no audit written; no exception
    propagates to the caller."""
    fake_gw = _FakeGateway(raises=BudgetExhaustedError("free", 1000, 1000))

    consent_spy = _make_consent_spy()
    record_spy = _make_record_spy()
    log_spy = _make_log_low_confidence_spy()

    monkeypatch.setattr("dhanradar.mf.commentary.assert_consent", consent_spy)
    monkeypatch.setattr("dhanradar.mf.commentary.record_served_label", record_spy)
    monkeypatch.setattr("dhanradar.mf.commentary.log_low_confidence", log_spy)

    # Must not raise.
    result = await generate_commentary(
        fake_gw,
        user_id="user-123",
        db=_FAKE_DB,
        snapshot=_FakeSnapshot(),
        funds=_FAKE_FUNDS,
    )

    assert result["state"] == "unavailable"
    assert result["reason"] == "BudgetExhaustedError"

    # Audit must not have been written.
    assert len(record_spy.calls) == 0


# ---------------------------------------------------------------------------
# Advisory-verb rejection through QualityValidator
# ---------------------------------------------------------------------------


def test_mf_commentary_advisory_text_rejected_by_quality_validator():
    """QualityValidator screens MFCommentary fields — advisory verbs in commentary
    must raise QualityValidationError (proves the screen covers the new field)."""
    validator = QualityValidator(MFCommentary)
    with pytest.raises(QualityValidationError):
        validator.validate(
            {
                "confidence": 0.55,
                "confidence_band": "medium",
                "contributing_signals": ["category_mix", "fund_count"],
                "contradicting_signals": [],
                "commentary": "You should buy this fund for better returns.",
            }
        )
