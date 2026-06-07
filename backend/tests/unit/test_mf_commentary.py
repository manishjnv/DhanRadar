"""
Unit tests for dhanradar.mf.commentary — hermetic, no Postgres, no network.

Covers the four governance gates (B20/B21/B22/B23) plus the DPDP data-
minimization contract of build_messages.

Monkeypatching strategy
-----------------------
* ``dhanradar.deps.consent_granted`` — ``assert_consent`` calls this internally;
  patching it controls B20 without a real DB or a live ``auth.users`` table.
* ``dhanradar.compliance.service.log_low_confidence`` /
  ``dhanradar.compliance.service.record_served_label`` — fire-and-forget
  compliance writes; patched to async recorders so no DB session is opened and
  we can assert call arguments.
* Gateway — a ``_FakeGateway`` with a configurable ``complete`` outcome.
* ``CompletionResult`` is not yet importable from ``dhanradar.ai_gateway`` (the
  sibling change is in-flight); tests use ``types.SimpleNamespace`` as the shim.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Optional

import pytest

from dhanradar.mf.commentary import (
    _PROMPT_VERSION,
    _SURFACE,
    MfPortfolioCommentary,
    build_messages,
    maybe_generate_commentary,
)

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class _FakeGateway:
    """Fake gateway whose ``complete`` either returns a configured result or raises."""

    def __init__(
        self,
        result: Optional[Any] = None,
        raise_exc: Optional[Exception] = None,
    ) -> None:
        self._result = result
        self._raise = raise_exc
        self.calls: list[dict] = []

    async def complete(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._raise is not None:
            raise self._raise
        return self._result


def _make_result(
    confidence: float = 0.6,
    confidence_band: str = "medium",
    contributing_signals: Optional[list[str]] = None,
    contradicting_signals: Optional[list[str]] = None,
    summary: str = "These funds collectively look steady on an educational basis.",
    model_used: str = "free_x",
) -> SimpleNamespace:
    """Build a SimpleNamespace shim for CompletionResult."""
    output = MfPortfolioCommentary(
        confidence=confidence,
        confidence_band=confidence_band,  # type: ignore[arg-type]
        contributing_signals=contributing_signals or ["a", "b"],
        contradicting_signals=contradicting_signals or [],
        summary=summary,
    )
    return SimpleNamespace(output=output, model_used=model_used)


def _usable_fund(
    verb_label: str = "on_track",
    confidence_band: str = "medium",
    contributing_signals: Optional[list[str]] = None,
    contradicting_signals: Optional[list[str]] = None,
) -> dict:
    return {
        "isin": "INF001",
        "scheme_name": "Big Cap Fund",
        "folio_number": "F1",
        "units": 100.0,
        "invested_amount": 4000.0,
        "current_value": 5000.0,
        "verb_label": verb_label,
        "confidence_band": confidence_band,
        "contributing_signals": contributing_signals or ["signal_a"],
        "contradicting_signals": contradicting_signals or [],
    }


_COMMON_KW = dict(
    user_id="00000000-0000-0000-0000-000000000001",
    job_id="job-test-001",
    category_allocation={"Equity": 100.0},
    db=object(),
    disclaimer_version="v1",
)


# ---------------------------------------------------------------------------
# Async recorder helpers
# ---------------------------------------------------------------------------

def _make_async_recorder() -> tuple[Any, list[dict]]:
    """Return (async callable, call-log list).  The callable appends kwargs each call."""
    calls: list[dict] = []

    async def _recorder(**kwargs: Any) -> bool:
        calls.append(kwargs)
        return True

    return _recorder, calls


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_consent_absent_omits_and_calls_no_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    """B20: absent consent → None returned; gateway never called; no audit."""
    monkeypatch.setattr(
        "dhanradar.deps.consent_granted",
        lambda *a, **kw: _async_false(),
    )
    record_mock, record_calls = _make_async_recorder()
    monkeypatch.setattr("dhanradar.compliance.service.record_served_label", record_mock)

    gw = _FakeGateway(result=_make_result())
    result = await maybe_generate_commentary(
        **_COMMON_KW,
        funds=[_usable_fund()],
        gateway=gw,
    )

    assert result is None
    assert gw.calls == []
    assert record_calls == []


async def _async_false(*a: Any, **kw: Any) -> bool:  # noqa: RUF029
    return False


async def _async_true(*a: Any, **kw: Any) -> bool:  # noqa: RUF029
    return True


@pytest.mark.asyncio
async def test_no_usable_labels_logs_low_confidence(monkeypatch: pytest.MonkeyPatch) -> None:
    """B22 pre-call: all funds have insufficient_data label → log + None; gateway not called."""
    monkeypatch.setattr("dhanradar.deps.consent_granted", _async_true)

    low_conf_mock, low_conf_calls = _make_async_recorder()
    record_mock, record_calls = _make_async_recorder()
    monkeypatch.setattr("dhanradar.compliance.service.log_low_confidence", low_conf_mock)
    monkeypatch.setattr("dhanradar.compliance.service.record_served_label", record_mock)

    gw = _FakeGateway(result=_make_result())
    insufficient_fund = _usable_fund(verb_label="insufficient_data")
    result = await maybe_generate_commentary(
        **_COMMON_KW,
        funds=[insufficient_fund],
        gateway=gw,
    )

    assert result is None
    assert len(low_conf_calls) == 1
    assert low_conf_calls[0]["reason"] == "portfolio_no_usable_labels"
    assert gw.calls == []
    assert record_calls == []


@pytest.mark.asyncio
async def test_happy_path_returns_summary_and_audits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: consent OK, usable labels, confidence above floor, no advisory verbs →
    summary returned; record_served_label called once with correct attributes."""
    monkeypatch.setattr("dhanradar.deps.consent_granted", _async_true)

    low_conf_mock, low_conf_calls = _make_async_recorder()
    record_mock, record_calls = _make_async_recorder()
    monkeypatch.setattr("dhanradar.compliance.service.log_low_confidence", low_conf_mock)
    monkeypatch.setattr("dhanradar.compliance.service.record_served_label", record_mock)

    expected_summary = "These funds collectively look steady on an educational basis."
    gw = _FakeGateway(
        result=_make_result(
            confidence=0.6,
            confidence_band="medium",
            contributing_signals=["a", "b"],
            summary=expected_summary,
            model_used="free_x",
        )
    )
    result = await maybe_generate_commentary(
        **_COMMON_KW,
        funds=[_usable_fund()],
        gateway=gw,
    )

    # The served commentary carries the summary plus the SEBI AI-disclaimer postfix
    # (architecture §MF line 257 / line 220).
    from dhanradar.ai_gateway.schemas import AI_DISCLAIMER

    assert result.startswith(expected_summary)
    assert result.endswith(AI_DISCLAIMER)
    assert len(record_calls) == 1
    call = record_calls[0]
    assert call["model"] == "free_x"
    assert call["surface"] == _SURFACE
    assert call["prompt_version"] == _PROMPT_VERSION
    assert low_conf_calls == []


@pytest.mark.asyncio
async def test_model_confidence_below_floor_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    """B22 post-call: model returns confidence 0.2 < 0.30 floor → None; log_low_confidence called."""
    monkeypatch.setattr("dhanradar.deps.consent_granted", _async_true)

    low_conf_mock, low_conf_calls = _make_async_recorder()
    record_mock, record_calls = _make_async_recorder()
    monkeypatch.setattr("dhanradar.compliance.service.log_low_confidence", low_conf_mock)
    monkeypatch.setattr("dhanradar.compliance.service.record_served_label", record_mock)

    gw = _FakeGateway(
        result=_make_result(
            confidence=0.2,
            confidence_band="low",
            contributing_signals=["x", "y"],
            summary="Portfolio data is sparse.",
        )
    )
    result = await maybe_generate_commentary(
        **_COMMON_KW,
        funds=[_usable_fund()],
        gateway=gw,
    )

    assert result is None
    assert len(low_conf_calls) == 1
    assert low_conf_calls[0]["reason"] == "model_confidence_below_floor"
    assert record_calls == []


@pytest.mark.asyncio
async def test_advisory_in_summary_withheld(monkeypatch: pytest.MonkeyPatch) -> None:
    """B23: advisory verb in summary → None; record_served_label NOT called."""
    monkeypatch.setattr("dhanradar.deps.consent_granted", _async_true)

    low_conf_mock, low_conf_calls = _make_async_recorder()
    record_mock, record_calls = _make_async_recorder()
    monkeypatch.setattr("dhanradar.compliance.service.log_low_confidence", low_conf_mock)
    monkeypatch.setattr("dhanradar.compliance.service.record_served_label", record_mock)

    gw = _FakeGateway(
        result=_make_result(
            confidence=0.6,
            confidence_band="medium",
            contributing_signals=["a", "b"],
            summary="you should buy more of these",
        )
    )
    result = await maybe_generate_commentary(
        **_COMMON_KW,
        funds=[_usable_fund()],
        gateway=gw,
    )

    assert result is None
    assert record_calls == []


def test_build_messages_excludes_pii() -> None:
    """DPDP data minimization: PII fields must not appear in the user message."""
    fund_with_pii = {
        "isin": "INF001",
        "scheme_name": "Big Cap Fund",
        "folio_number": "F1",
        "units": 100.0,
        "invested_amount": 4000.0,
        "current_value": 5000.0,
        "verb_label": "on_track",
        "confidence_band": "medium",
        "contributing_signals": ["signal_a"],
        "contradicting_signals": [],
    }
    category_allocation = {"Equity": 100.0}

    messages = build_messages([fund_with_pii], category_allocation)

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"

    user_content = messages[1]["content"]
    # PII fields must be absent
    for pii_key in ("isin", "scheme_name", "folio_number", "units", "invested_amount", "current_value"):
        assert pii_key not in user_content, f"PII key '{pii_key}' found in user message"
    # Label fields must be present
    assert "verb_label" in user_content
    # The content must be valid JSON
    parsed = json.loads(user_content)
    assert "funds" in parsed
    assert "category_allocation" in parsed
    assert parsed["funds"][0]["verb_label"] == "on_track"


@pytest.mark.asyncio
async def test_non_finite_confidence_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    """B22 hardening: a NaN confidence must be treated as BELOW the floor (nan < 0.30
    is False in Python) → None returned + log_low_confidence; never published."""
    import math

    monkeypatch.setattr("dhanradar.deps.consent_granted", _async_true)
    low_conf_mock, low_conf_calls = _make_async_recorder()
    record_mock, record_calls = _make_async_recorder()
    monkeypatch.setattr("dhanradar.compliance.service.log_low_confidence", low_conf_mock)
    monkeypatch.setattr("dhanradar.compliance.service.record_served_label", record_mock)

    # SimpleNamespace bypasses Pydantic so we can inject a non-finite confidence
    # that a misbehaving model/parser could in principle produce.
    nan_output = SimpleNamespace(
        confidence=math.nan, confidence_band="low", summary="sparse data",
    )
    gw = _FakeGateway(result=SimpleNamespace(output=nan_output, model_used="free_x"))

    result = await maybe_generate_commentary(**_COMMON_KW, funds=[_usable_fund()], gateway=gw)

    assert result is None
    assert len(low_conf_calls) == 1
    assert low_conf_calls[0]["reason"] == "model_confidence_below_floor"
    assert low_conf_calls[0]["confidence_score"] is None  # non-finite → not recorded as a number
    assert record_calls == []


@pytest.mark.asyncio
async def test_audit_failure_still_serves(monkeypatch: pytest.MonkeyPatch) -> None:
    """An audit-write failure must NEVER drop a clean, screened commentary (house
    posture: serve + alert, not audit-or-nothing)."""
    monkeypatch.setattr("dhanradar.deps.consent_granted", _async_true)

    async def _raising_record(**kwargs: Any) -> bool:
        raise RuntimeError("audit DB down")

    monkeypatch.setattr("dhanradar.compliance.service.record_served_label", _raising_record)

    expected = "These funds collectively look steady on an educational basis."
    gw = _FakeGateway(result=_make_result(summary=expected))

    result = await maybe_generate_commentary(**_COMMON_KW, funds=[_usable_fund()], gateway=gw)

    assert result is not None and result.startswith(expected)  # served despite the audit write raising
