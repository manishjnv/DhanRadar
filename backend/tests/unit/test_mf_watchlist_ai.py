"""
Unit tests — GET /mf/watchlist/summary (WATCHLIST_LIVE_DATA_PLAN.md Wave 3).

Coverage:
  Router (`dhanradar.mf.router.watchlist_summary`):
    1. Auth: 401 for an anonymous caller.
    2. Empty watchlist → empty items, disclosure/not_advice/disclaimer_version
       present, no gateway constructed.
    3. Cache hit → the governed AI call is never made a second time.

  Consumer (`dhanradar.mf.watchlist_ai.generate_watchlist_summary`):
    4. Gate order: consent → entitlement → gateway → audit (mocks, order list +
       audit-row write assertion).
    5. Consent deny / not entitled → gateway never called, audit never called.
    6. Empty cards → consent/entitlement/gateway never touched.
    7. Gateway/budget exception → empty items, single call, no retry, no audit.
    8. Confidence floor → `log_low_confidence` called, no audit, no retry.
    9. Poisoned output (advisory imperative / numeric / foreign fund) on BOTH
       attempts → regenerate once, then empty; audit never written.
   10. Poisoned output on attempt 1, clean on attempt 2 → served + audited once.

  Serializer (`dhanradar.mf.serialization`):
   11. `mf.watchlist_ai_item` allowlist strips a poisoned extra field.
   12. A forbidden score key raises before the allowlist even runs.
   13. `serialize_watchlist_ai_response` end-to-end round-trip.

No network, no real DB/Redis: all external call sites are monkeypatched with
async fakes / stubs, same convention as test_mf_commentary.py and
test_mf_watchlist_cards.py. asyncio_mode = "auto" (pyproject.toml).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException, Request, Response

from dhanradar.ai_gateway.errors import QualityValidationError
from dhanradar.ai_gateway.gateway import CompletionResult
from dhanradar.budget import BudgetExhaustedError
from dhanradar.deps import ConsentRequiredError
from dhanradar.mf.router import watchlist_summary
from dhanradar.mf.serialization import (
    _apply_allowlist,
    _assert_no_forbidden,
    serialize_watchlist_ai_response,
)
from dhanradar.mf.watchlist_ai import WatchlistAISummary, generate_watchlist_summary

# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------


class _FakeIsinsDB:
    """Minimal AsyncSession stub — `select(MfWatchlistItem.isin)...scalars().all()`."""

    def __init__(self, isins: list[str] | None = None) -> None:
        self._isins = list(isins or [])

    async def execute(self, stmt: Any) -> "_FakeIsinsDB":  # noqa: UP037
        return self

    def scalars(self) -> "_FakeIsinsDB":  # noqa: UP037
        return self

    def all(self) -> list[str]:
        return list(self._isins)


class _FakeRedis:
    """Minimal async Redis stub — a plain dict, TTL ignored (unit-test scope)."""

    def __init__(self, seed: dict[str, str] | None = None) -> None:
        self.store: dict[str, str] = dict(seed or {})
        self.set_calls: list[str] = []

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
        self.set_calls.append(key)


def _user(anonymous: bool = False) -> SimpleNamespace:
    return SimpleNamespace(is_anonymous=anonymous, user_id=str(uuid.uuid4()))


def _request() -> Request:
    return Request(scope={"type": "http"})


ISIN_A = "INF174K01KH7"

_CARDS: list[dict[str, Any]] = [
    {
        "isin": ISIN_A,
        "scheme_name": "HDFC Flexicap Fund - Direct - Growth",
        "fund_name_short": "HDFC Flexicap Fund",
        "amc_name": "HDFC Mutual Fund",
        "category": "Equity",
        "sebi_category": "Flexi Cap Fund",
        "confidence_band": "medium",
        "verb_label": "on_track",
        "expense_ratio_pct": 0.8,
        "return_1y_pct": 14.2,
        "return_3y_pct": 16.1,
    }
]

_GOOD_SUMMARY = [
    "Your watchlist spans a single equity category.",
    "Costs across the tracked fund sit close to its category peers.",
]
_GOOD_INSIGHTS = [
    "The tracked fund carries a medium confidence band.",
    "Its educational label has stayed on track recently.",
]


def _make_output(
    confidence: float,
    band: str,
    summary_items: list[str],
    insight_items: list[str],
) -> WatchlistAISummary:
    signals = ["category_mix", "confidence_bands"]
    if confidence > 0.7:
        signals.append("expense_ratio_spread")
    return WatchlistAISummary(
        confidence=confidence,
        confidence_band=band,  # type: ignore[arg-type]
        contributing_signals=signals,
        contradicting_signals=[],
        summary_items=summary_items,
        insight_items=insight_items,
    )


class _FakeGateway:
    """Configurable async gateway stub. One entry in ``results`` per expected
    call — a ``CompletionResult`` is returned, an ``Exception`` is raised.
    Appends "gateway" to ``order`` (if given) on every call, for gate-order
    assertions."""

    def __init__(
        self,
        results: list[CompletionResult | Exception],
        order: list[str] | None = None,
    ) -> None:
        self._results = list(results)
        self._order = order
        self.calls: list[dict] = []

    async def complete(self, **kwargs) -> CompletionResult:  # type: ignore[return]
        if self._order is not None:
            self._order.append("gateway")
        idx = len(self.calls)
        self.calls.append(kwargs)
        item = self._results[idx]
        if isinstance(item, Exception):
            raise item
        return item  # type: ignore[return-value]


def _consent_spy(*, raises: Exception | None = None, order: list[str] | None = None):
    calls: list[tuple] = []

    async def _spy(user_id: str, purpose: str, db: object) -> None:
        calls.append((user_id, purpose))
        if order is not None:
            order.append("consent")
        if raises is not None:
            raise raises

    _spy.calls = calls  # type: ignore[attr-defined]
    return _spy


def _entitlement_spy(*, entitled: bool = True, order: list[str] | None = None):
    calls: list[str] = []

    async def _spy(user_id: str, db: object) -> bool:
        calls.append(user_id)
        if order is not None:
            order.append("entitlement")
        return entitled

    _spy.calls = calls  # type: ignore[attr-defined]
    return _spy


def _record_spy(order: list[str] | None = None):
    calls: list[dict] = []

    async def _spy(**kwargs) -> bool:
        calls.append(kwargs)
        if order is not None:
            order.append("audit")
        return True

    _spy.calls = calls  # type: ignore[attr-defined]
    return _spy


def _log_low_confidence_spy():
    calls: list[dict] = []

    async def _spy(**kwargs) -> bool:
        calls.append(kwargs)
        return True

    _spy.calls = calls  # type: ignore[attr-defined]
    return _spy


_FAKE_DB = object()

# ===========================================================================
# Router — GET /mf/watchlist/summary
# ===========================================================================


async def test_watchlist_summary_401_for_anonymous() -> None:
    db = _FakeIsinsDB()
    with pytest.raises(HTTPException) as exc:
        await watchlist_summary(
            request=_request(), db=db, response=Response(), user=_user(anonymous=True)
        )
    assert exc.value.status_code == 401


async def test_watchlist_summary_empty_watchlist_no_gateway_call() -> None:
    db = _FakeIsinsDB(isins=[])
    envelope = await watchlist_summary(
        request=_request(), db=db, response=Response(), user=_user()
    )

    assert envelope["summary_items"] == []
    assert envelope["insight_items"] == []
    assert envelope["disclosure"]
    assert envelope["not_advice"]
    assert envelope["disclaimer_version"]


async def test_watchlist_summary_cache_hit_never_calls_gateway_again(monkeypatch) -> None:
    user = _user()
    uid = uuid.UUID(user.user_id)
    cache_key = "mf:watchlist_ai:" + hashlib.sha256(str(uid).encode("utf-8")).hexdigest()
    cached_envelope = {
        "summary_items": ["Cached summary point."],
        "insight_items": ["Cached insight point."],
        "disclosure": "DISCLOSURE",
        "not_advice": "NOT_ADVICE",
        "disclaimer_version": "2026-06-06.v1",
    }
    fake_redis = _FakeRedis(seed={cache_key: json.dumps(cached_envelope)})
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: fake_redis)
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.watchlist_ai_consent_granted", lambda *_: _true_async())
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.watchlist_ai_cache_entitled", lambda *_: _true_async())

    async def _boom(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("gateway must not be called on a cache hit")

    monkeypatch.setattr("dhanradar.mf.watchlist_ai.generate_watchlist_summary", _boom)

    db = _FakeIsinsDB(isins=[ISIN_A])
    envelope = await watchlist_summary(request=_request(), db=db, response=Response(), user=user)

    assert envelope == cached_envelope


async def test_watchlist_summary_cache_hit_after_consent_revoke_is_withheld(monkeypatch) -> None:
    user = _user()
    uid = uuid.UUID(user.user_id)
    cache_key = "mf:watchlist_ai:" + hashlib.sha256(str(uid).encode("utf-8")).hexdigest()
    fake_redis = _FakeRedis(seed={cache_key: json.dumps({"summary_items": ["stale"], "insight_items": []})})
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: fake_redis)
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.watchlist_ai_consent_granted", lambda *_: _false_async())

    db = _FakeIsinsDB(isins=[ISIN_A])
    envelope = await watchlist_summary(request=_request(), db=db, response=Response(), user=user)

    assert envelope["summary_items"] == []
    assert envelope["insight_items"] == []


async def _true_async() -> bool:
    return True


async def _false_async() -> bool:
    return False


# ===========================================================================
# Consumer — generate_watchlist_summary
# ===========================================================================


async def test_gate_order_consent_then_entitlement_then_gateway_then_audit(monkeypatch) -> None:
    order: list[str] = []
    output = _make_output(0.72, "high", _GOOD_SUMMARY, _GOOD_INSIGHTS)
    fake_gw = _FakeGateway(
        [CompletionResult(output=output, model_used="glm-4.6-flash")], order=order
    )

    consent_spy = _consent_spy(order=order)
    entitlement_spy = _entitlement_spy(order=order)
    record_spy = _record_spy(order=order)
    log_spy = _log_low_confidence_spy()

    monkeypatch.setattr("dhanradar.mf.watchlist_ai.assert_consent", consent_spy)
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.is_commentary_entitled", entitlement_spy)
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.record_served_label", record_spy)
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.log_low_confidence", log_spy)

    result = await generate_watchlist_summary(
        fake_gw, user_id="user-123", db=_FAKE_DB, cards=_CARDS, request_id="req-abc"
    )

    assert order == ["consent", "entitlement", "gateway", "audit"]
    assert result["summary_items"] == _GOOD_SUMMARY
    assert result["insight_items"] == _GOOD_INSIGHTS
    assert result["disclosure"]
    assert result["not_advice"]
    assert result["disclaimer_version"]

    # Audit row shape.
    assert len(record_spy.calls) == 1
    audit_call = record_spy.calls[0]
    assert audit_call["surface"] == "mf_watchlist_ai"
    assert audit_call["model"] == "glm-4.6-flash"
    assert audit_call["recommendation_type"] == "educational_label"
    assert "buy" not in audit_call["label"] and "sell" not in audit_call["label"]

    # Gateway called with the required flags exactly once.
    assert len(fake_gw.calls) == 1
    gw_call = fake_gw.calls[0]
    assert gw_call["contains_personal_data"] is True
    assert gw_call["cross_border_consent_verified"] is True
    assert gw_call["judge_eligible"] is False
    assert gw_call["schema"] is WatchlistAISummary

    assert len(log_spy.calls) == 0


async def test_consent_deny_never_calls_entitlement_or_gateway(monkeypatch) -> None:
    fake_gw = _FakeGateway([AssertionError("gateway must not be called")])  # type: ignore[list-item]
    entitlement_spy = _entitlement_spy()
    consent_spy = _consent_spy(raises=ConsentRequiredError("cross_border_ai"))
    record_spy = _record_spy()

    monkeypatch.setattr("dhanradar.mf.watchlist_ai.assert_consent", consent_spy)
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.is_commentary_entitled", entitlement_spy)
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.record_served_label", record_spy)

    result = await generate_watchlist_summary(
        fake_gw, user_id="user-no-consent", db=_FAKE_DB, cards=_CARDS
    )

    assert result["summary_items"] == []
    assert result["insight_items"] == []
    assert len(entitlement_spy.calls) == 0
    assert len(fake_gw.calls) == 0
    assert len(record_spy.calls) == 0


async def test_not_entitled_never_calls_gateway(monkeypatch) -> None:
    fake_gw = _FakeGateway([AssertionError("gateway must not be called")])  # type: ignore[list-item]
    consent_spy = _consent_spy()
    entitlement_spy = _entitlement_spy(entitled=False)
    record_spy = _record_spy()

    monkeypatch.setattr("dhanradar.mf.watchlist_ai.assert_consent", consent_spy)
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.is_commentary_entitled", entitlement_spy)
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.record_served_label", record_spy)

    result = await generate_watchlist_summary(
        fake_gw, user_id="user-free-used-taster", db=_FAKE_DB, cards=_CARDS
    )

    assert result["summary_items"] == []
    assert len(fake_gw.calls) == 0
    assert len(record_spy.calls) == 0


async def test_empty_cards_never_touches_consent_or_gateway(monkeypatch) -> None:
    fake_gw = _FakeGateway([AssertionError("gateway must not be called")])  # type: ignore[list-item]
    consent_spy = _consent_spy()
    entitlement_spy = _entitlement_spy()

    monkeypatch.setattr("dhanradar.mf.watchlist_ai.assert_consent", consent_spy)
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.is_commentary_entitled", entitlement_spy)

    result = await generate_watchlist_summary(fake_gw, user_id="user-123", db=_FAKE_DB, cards=[])

    assert result["summary_items"] == []
    assert result["insight_items"] == []
    assert len(consent_spy.calls) == 0
    assert len(entitlement_spy.calls) == 0
    assert len(fake_gw.calls) == 0


async def test_gateway_exception_is_a_hard_stop_no_retry(monkeypatch) -> None:
    fake_gw = _FakeGateway([BudgetExhaustedError("free", 10, 10)])
    record_spy = _record_spy()

    monkeypatch.setattr("dhanradar.mf.watchlist_ai.assert_consent", _consent_spy())
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.is_commentary_entitled", _entitlement_spy())
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.record_served_label", record_spy)

    result = await generate_watchlist_summary(fake_gw, user_id="user-123", db=_FAKE_DB, cards=_CARDS)

    assert result["summary_items"] == []
    assert len(fake_gw.calls) == 1  # no retry on a gateway/budget exception
    assert len(record_spy.calls) == 0


async def test_confidence_floor_logs_and_never_retries(monkeypatch) -> None:
    output = _make_output(0.20, "low", _GOOD_SUMMARY, _GOOD_INSIGHTS)
    fake_gw = _FakeGateway([CompletionResult(output=output, model_used="glm-4.6-flash")])
    record_spy = _record_spy()
    log_spy = _log_low_confidence_spy()

    monkeypatch.setattr("dhanradar.mf.watchlist_ai.assert_consent", _consent_spy())
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.is_commentary_entitled", _entitlement_spy())
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.record_served_label", record_spy)
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.log_low_confidence", log_spy)

    result = await generate_watchlist_summary(fake_gw, user_id="user-123", db=_FAKE_DB, cards=_CARDS)

    assert result["summary_items"] == []
    assert len(fake_gw.calls) == 1
    assert len(log_spy.calls) == 1
    assert len(record_spy.calls) == 0


@pytest.mark.parametrize(
    "poisoned_summary",
    [
        ["You should redeem this fund now.", "Consider switching soon."],
        ["The tracked fund returned 12 percent this year.", "Costs are low."],
        ["ICICI Prudential Bluechip Fund looks strong.", "Diversified holding."],
    ],
    ids=["advisory_redeem", "numeric_leak", "foreign_fund"],
)
async def test_poisoned_output_on_both_attempts_regenerates_then_empty(
    monkeypatch, poisoned_summary: list[str]
) -> None:
    bad = _make_output(0.66, "medium", poisoned_summary, _GOOD_INSIGHTS)
    fake_gw = _FakeGateway(
        [
            CompletionResult(output=bad, model_used="glm-4.6-flash"),
            CompletionResult(output=bad, model_used="glm-4.6-flash"),
        ]
    )
    record_spy = _record_spy()

    monkeypatch.setattr("dhanradar.mf.watchlist_ai.assert_consent", _consent_spy())
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.is_commentary_entitled", _entitlement_spy())
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.record_served_label", record_spy)

    result = await generate_watchlist_summary(fake_gw, user_id="user-123", db=_FAKE_DB, cards=_CARDS)

    assert result["summary_items"] == []
    assert result["insight_items"] == []
    assert len(fake_gw.calls) == 2  # exactly one regeneration
    assert len(record_spy.calls) == 0  # rejected output is never audited


async def test_poisoned_first_attempt_clean_second_attempt_is_served_and_audited(
    monkeypatch,
) -> None:
    bad = _make_output(
        0.66, "medium", ["The fund returned 8 percent.", "Costs are low."], _GOOD_INSIGHTS
    )
    good = _make_output(0.66, "medium", _GOOD_SUMMARY, _GOOD_INSIGHTS)
    fake_gw = _FakeGateway(
        [
            CompletionResult(output=bad, model_used="glm-4.6-flash"),
            CompletionResult(output=good, model_used="qwen-2.5-72b"),
        ]
    )
    record_spy = _record_spy()

    monkeypatch.setattr("dhanradar.mf.watchlist_ai.assert_consent", _consent_spy())
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.is_commentary_entitled", _entitlement_spy())
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.record_served_label", record_spy)

    result = await generate_watchlist_summary(fake_gw, user_id="user-123", db=_FAKE_DB, cards=_CARDS)

    assert result["summary_items"] == _GOOD_SUMMARY
    assert result["insight_items"] == _GOOD_INSIGHTS
    assert len(fake_gw.calls) == 2
    assert len(record_spy.calls) == 1
    assert record_spy.calls[0]["model"] == "qwen-2.5-72b"


async def test_gateway_own_quality_error_after_pool_exhaustion_is_hard_stop(monkeypatch) -> None:
    """A GatewayError raised BY gateway.complete() itself (e.g. every free model
    failed quality/rate-limited) is the gateway's own exhausted-retry outcome —
    never regenerated a second time by this consumer."""
    fake_gw = _FakeGateway([QualityValidationError("all free models failed quality")])
    record_spy = _record_spy()

    monkeypatch.setattr("dhanradar.mf.watchlist_ai.assert_consent", _consent_spy())
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.is_commentary_entitled", _entitlement_spy())
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.record_served_label", record_spy)

    result = await generate_watchlist_summary(fake_gw, user_id="user-123", db=_FAKE_DB, cards=_CARDS)

    assert result["summary_items"] == []
    assert len(fake_gw.calls) == 1
    assert len(record_spy.calls) == 0


@pytest.mark.parametrize("text", [
    "This fund is top ranked in its category.",
    "The rating is higher than the category average.",
    "You should compare these funds before acting.",
])
async def test_non_descriptive_output_is_rejected_and_regenerated(monkeypatch, text: str) -> None:
    bad = _make_output(0.66, "medium", [text, "Costs are described plainly."], _GOOD_INSIGHTS)
    fake_gw = _FakeGateway([
        CompletionResult(output=bad, model_used="glm-4.6-flash"),
        CompletionResult(output=bad, model_used="glm-4.6-flash"),
    ])
    record_spy = _record_spy()
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.assert_consent", _consent_spy())
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.is_commentary_entitled", _entitlement_spy())
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.record_served_label", record_spy)

    result = await generate_watchlist_summary(fake_gw, user_id="user-123", db=_FAKE_DB, cards=_CARDS)

    assert result["summary_items"] == []
    assert len(fake_gw.calls) == 2
    assert len(record_spy.calls) == 0


# ===========================================================================
# Serializer — mf.watchlist_ai_item allowlist + serialize_watchlist_ai_response
# ===========================================================================


def test_watchlist_ai_item_allowlist_strips_poisoned_extra_fields() -> None:
    poisoned = {"text": "Positive trend across holdings.", "score": 91, "extra": "x"}
    cleaned = _apply_allowlist("mf.watchlist_ai_item", poisoned)
    assert cleaned == {"text": "Positive trend across holdings."}


def test_watchlist_ai_item_forbidden_score_key_raises_before_allowlist() -> None:
    poisoned = {"text": "ok", "unified_score": 50}
    with pytest.raises(RuntimeError):
        _assert_no_forbidden(poisoned)


def test_serialize_watchlist_ai_response_round_trip() -> None:
    out = serialize_watchlist_ai_response(
        summary_items=["Diversified across three categories."],
        insight_items=["One fund carries a higher expense ratio than its peers."],
        disclosure="DISCLOSURE TEXT",
        not_advice="NOT_ADVICE",
        disclaimer_version="2026-06-06.v1",
    )
    assert set(out.keys()) == {
        "summary_items",
        "insight_items",
        "disclosure",
        "not_advice",
        "disclaimer_version",
    }
    assert out["summary_items"] == ["Diversified across three categories."]
    assert out["insight_items"] == ["One fund carries a higher expense ratio than its peers."]
    assert out["disclosure"] == "DISCLOSURE TEXT"
    assert out["not_advice"] == "NOT_ADVICE"
    assert out["disclaimer_version"] == "2026-06-06.v1"
