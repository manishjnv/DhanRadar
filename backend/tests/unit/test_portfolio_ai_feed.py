"""
Unit tests — GET /portfolio/{portfolio_id}/ai-feed (PORTFOLIO_LIVE_DATA_PLAN.md Wave P3).

Coverage:
  Route (`dhanradar.insights.router.portfolio_ai_feed`):
    1. Auth: 401 for an anonymous caller.
    2. Empty portfolio → empty items, no consent check, no gateway call.
    3. Revoked consent is not served from cache (cache hit but consent gone).
    4. Cache hit with matching disclaimer_version → governed call never made.

  Consumer (`dhanradar.mf.portfolio_ai.generate_portfolio_ai_feed`):
    5. Gate order: consent → entitlement → gateway → audit.
    6. Low confidence → state=insufficient_data, no raw float in payload.
    7. Advisory screen retry → unavailable when both attempts fail.
    8. Advisory screen retry → served when second attempt is clean.

  Serialization:
    9. Poisoned unified_score stripped by serialize_concept A3 boundary.
   10. Disclaimer staleness: stale cached entry triggers a live regeneration.

No network, no real DB/Redis: all external call sites are monkeypatched with
async fakes. asyncio_mode = "auto" (pyproject.toml).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException, Request, Response

from dhanradar.ai_gateway.gateway import CompletionResult
from dhanradar.insights.router import portfolio_ai_feed
from dhanradar.mf.portfolio_ai import (
    PortfolioAIFeed,
    generate_portfolio_ai_feed,
)
from dhanradar.mf.serialization import ALLOWED_FIELDS

# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------

_PORTFOLIO_ID = "65f45746-6151-442e-b5bc-2245510a48ba"

_SAMPLE_HOLDINGS = [
    SimpleNamespace(
        scheme_name="HDFC Flexicap Fund",
        category="Flexi Cap Fund",
        confidence_band="medium",
        label="on_track",
        amc="HDFC Mutual Fund",
    )
]

# Dicts as passed by the router to generate_portfolio_ai_feed
_PROMPT_HOLDINGS = [
    {
        "scheme_name": "HDFC Flexicap Fund",
        "category": "Flexi Cap Fund",
        "confidence_band": "medium",
        "label": "on_track",
        "amc_name": "HDFC Mutual Fund",
    }
]


class _FakeRedis:
    def __init__(self, seed: dict[str, str] | None = None) -> None:
        self.store: dict[str, str] = dict(seed or {})
        self.set_calls: list[str] = []

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
        self.set_calls.append(key)


class _FakePortfolioRM:
    def __init__(self, holdings: list[Any]) -> None:
        self.holdings = holdings
        self.total_value = 10000.0
        self.as_of = "2026-08-22"


class _FakeDB:
    pass


def _user(anonymous: bool = False) -> SimpleNamespace:
    return SimpleNamespace(is_anonymous=anonymous, user_id=str(uuid.uuid4()), tier="free")


def _request() -> Request:
    return Request(scope={"type": "http"})


def _make_output(confidence: float, band: str, items: list[str]) -> PortfolioAIFeed:
    signals = ["category_mix", "confidence_bands"]
    if confidence > 0.7:
        signals.append("label_spread")
    return PortfolioAIFeed(
        confidence=confidence,
        confidence_band=band,  # type: ignore[arg-type]
        contributing_signals=signals,
        contradicting_signals=[],
        items=items,
    )


class _FakeGateway:
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


def _make_result(output: PortfolioAIFeed) -> CompletionResult:
    return CompletionResult(output=output, model_used="test-model")


_GOOD_ITEMS = [
    "Your portfolio spans multiple equity categories.",
    "The tracked funds carry medium or high confidence bands.",
]

_ADVISORY_ITEM = ["You should add more funds to your portfolio.", "Consider switching to a lower-cost fund."]
_NUMERIC_ITEM = ["The portfolio gained 14% over the past year.", "Returns were above average."]


def _consent_spy(*, raises: Exception | None = None, order: list[str] | None = None):
    async def _spy(user_id: str, purpose: str, db: object) -> None:
        if order is not None:
            order.append("consent")
        if raises is not None:
            raise raises

    return _spy


def _entitlement_spy(*, entitled: bool = True, order: list[str] | None = None):
    async def _spy(user_id: str, db: object) -> bool:
        if order is not None:
            order.append("entitlement")
        return entitled

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


def _log_spy():
    calls: list[dict] = []

    async def _spy(**kwargs) -> bool:
        calls.append(kwargs)
        return True

    _spy.calls = calls  # type: ignore[attr-defined]
    return _spy


_FAKE_DB = _FakeDB()

# ===========================================================================
# Route tests
# ===========================================================================


async def test_portfolio_ai_feed_401_anonymous() -> None:
    with pytest.raises(HTTPException) as exc:
        await portfolio_ai_feed(
            portfolio_id=_PORTFOLIO_ID,
            request=_request(),
            user=_user(anonymous=True),
            db=_FAKE_DB,  # type: ignore[arg-type]
            response=Response(),
        )
    assert exc.value.status_code == 401


async def test_portfolio_ai_feed_empty_portfolio_no_consent_no_gateway(monkeypatch) -> None:
    """Empty holdings → short-circuit before consent gate and gateway."""
    consent_called = []

    async def _no_consent(user_id, purpose, db):  # pragma: no cover
        consent_called.append(True)

    # Local imports in the route resolve from the source module
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.watchlist_ai_consent_granted", lambda *_: _async_true())
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.watchlist_ai_cache_entitled", lambda *_: _async_true())
    monkeypatch.setattr(
        "dhanradar.insights.router.load_portfolio_read_model",
        lambda db, pid: _async(_FakePortfolioRM(holdings=[])),
    )
    monkeypatch.setattr("dhanradar.insights.router.get_redis", lambda: _FakeRedis())
    monkeypatch.setattr("dhanradar.insights.router._owned_portfolio_id", lambda *a, **kw: _async(None))
    monkeypatch.setattr("dhanradar.insights.router._require_mf_consent", _noop_consent())

    result = await portfolio_ai_feed(
        portfolio_id=_PORTFOLIO_ID,
        request=_request(),
        user=_user(),
        db=_FAKE_DB,  # type: ignore[arg-type]
        response=Response(),
    )
    assert result["data"]["items"] == []
    assert result["data"]["no_data_reason"] == "empty_portfolio"
    assert consent_called == []


async def test_portfolio_ai_feed_revoked_consent_not_served_from_cache(monkeypatch) -> None:
    """A valid cache entry is NOT served when cross_border_ai consent is revoked."""
    uid_str = str(uuid.uuid4())
    uid = uuid.UUID(uid_str)
    cache_key = "mf:portfolio_ai:" + hashlib.sha256(
        f"{uid}:{_PORTFOLIO_ID}".encode()
    ).hexdigest()
    cached_payload = {
        "portfolio_id": _PORTFOLIO_ID,
        "items": ["Stale cached item."],
        "state": "ok",
        "confidence_band": "medium",
        "as_of": "2026-08-22",
        "no_data_reason": None,
        "disclosure": "DISC",
        "not_advice": "NA",
        "disclaimer_version": "2026-06-06.v1",
    }
    fake_redis = _FakeRedis(seed={cache_key: json.dumps(cached_payload)})

    fake_user = _user()
    fake_user.user_id = uid_str

    monkeypatch.setattr(
        "dhanradar.mf.watchlist_ai.watchlist_ai_consent_granted",
        lambda *_: _async_false(),
    )
    monkeypatch.setattr("dhanradar.insights.router.get_redis", lambda: fake_redis)
    monkeypatch.setattr(
        "dhanradar.insights.router.load_portfolio_read_model",
        lambda db, pid: _async(_FakePortfolioRM(holdings=_SAMPLE_HOLDINGS)),
    )
    monkeypatch.setattr("dhanradar.insights.router._owned_portfolio_id", lambda *a, **kw: _async(None))
    monkeypatch.setattr("dhanradar.insights.router._require_mf_consent", _noop_consent())

    result = await portfolio_ai_feed(
        portfolio_id=_PORTFOLIO_ID,
        request=_request(),
        user=fake_user,
        db=_FAKE_DB,  # type: ignore[arg-type]
        response=Response(),
    )
    assert result["data"]["items"] == []
    assert result["data"]["no_data_reason"] == "consent_required"


async def test_portfolio_ai_feed_cache_hit_matching_disclaimer(monkeypatch) -> None:
    """Cache hit with matching disclaimer_version avoids the gateway entirely."""
    from dhanradar.compliance.service import active_disclaimer_version

    uid_str = str(uuid.uuid4())
    uid = uuid.UUID(uid_str)
    cache_key = "mf:portfolio_ai:" + hashlib.sha256(
        f"{uid}:{_PORTFOLIO_ID}".encode()
    ).hexdigest()
    disc = active_disclaimer_version()
    cached_payload = {
        "portfolio_id": _PORTFOLIO_ID,
        "items": ["Cached insight about the portfolio."],
        "state": "ok",
        "confidence_band": "medium",
        "as_of": "2026-08-22",
        "no_data_reason": None,
        "disclosure": "DISC",
        "not_advice": "NA",
        "disclaimer_version": disc,
    }
    fake_redis = _FakeRedis(seed={cache_key: json.dumps(cached_payload)})

    fake_user = _user()
    fake_user.user_id = uid_str

    gateway_called = []

    async def _boom(*a, **kw):
        gateway_called.append(True)
        raise AssertionError("gateway must not be called on a valid cache hit")

    monkeypatch.setattr("dhanradar.mf.watchlist_ai.watchlist_ai_consent_granted", lambda *_: _async_true())
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.watchlist_ai_cache_entitled", lambda *_: _async_true())
    monkeypatch.setattr("dhanradar.insights.router.get_redis", lambda: fake_redis)
    monkeypatch.setattr(
        "dhanradar.insights.router.load_portfolio_read_model",
        lambda db, pid: _async(_FakePortfolioRM(holdings=_SAMPLE_HOLDINGS)),
    )
    monkeypatch.setattr("dhanradar.insights.router._owned_portfolio_id", lambda *a, **kw: _async(None))
    monkeypatch.setattr("dhanradar.insights.router._require_mf_consent", _noop_consent())
    monkeypatch.setattr("dhanradar.mf.portfolio_ai.generate_portfolio_ai_feed", _boom)

    result = await portfolio_ai_feed(
        portfolio_id=_PORTFOLIO_ID,
        request=_request(),
        user=fake_user,
        db=_FAKE_DB,  # type: ignore[arg-type]
        response=Response(),
    )
    assert result["data"]["items"] == ["Cached insight about the portfolio."]
    assert gateway_called == []


# ===========================================================================
# Consumer — generate_portfolio_ai_feed
# ===========================================================================


async def test_generate_gate_order_consent_entitlement_gateway_audit(monkeypatch) -> None:
    order: list[str] = []
    record = _record_spy(order)

    monkeypatch.setattr("dhanradar.mf.portfolio_ai.assert_consent", _consent_spy(order=order))
    monkeypatch.setattr("dhanradar.mf.portfolio_ai.watchlist_ai_cache_entitled", _entitlement_spy(order=order))
    monkeypatch.setattr("dhanradar.mf.portfolio_ai.record_served_label", record)

    gw = _FakeGateway([_make_result(_make_output(0.8, "high", _GOOD_ITEMS))], order=order)
    result = await generate_portfolio_ai_feed(
        gw,
        user_id="user-1",
        portfolio_id=_PORTFOLIO_ID,
        db=_FAKE_DB,  # type: ignore[arg-type]
        holdings=_PROMPT_HOLDINGS,
    )
    assert order == ["consent", "entitlement", "gateway", "audit"]
    assert result["state"] == "ok"
    assert result["items"] == _GOOD_ITEMS
    assert "confidence" not in result  # raw float never serialized


async def test_generate_low_confidence_no_raw_float(monkeypatch) -> None:
    log = _log_spy()
    monkeypatch.setattr("dhanradar.mf.portfolio_ai.assert_consent", _consent_spy())
    monkeypatch.setattr("dhanradar.mf.portfolio_ai.watchlist_ai_cache_entitled", _entitlement_spy())
    monkeypatch.setattr("dhanradar.mf.portfolio_ai.record_served_label", _record_spy())
    monkeypatch.setattr("dhanradar.mf.portfolio_ai.log_low_confidence", log)

    gw = _FakeGateway([_make_result(_make_output(0.20, "low", _GOOD_ITEMS))])
    result = await generate_portfolio_ai_feed(
        gw,
        user_id="user-1",
        portfolio_id=_PORTFOLIO_ID,
        db=_FAKE_DB,  # type: ignore[arg-type]
        holdings=_PROMPT_HOLDINGS,
    )
    assert result["state"] == "insufficient_data"
    assert result["items"] == []
    assert "confidence" not in result
    assert log.calls  # log_low_confidence was called


async def test_generate_advisory_screen_retry_then_unavailable(monkeypatch) -> None:
    """Both attempts fail advisory screen → state=unavailable, audit never written."""
    record = _record_spy()
    monkeypatch.setattr("dhanradar.mf.portfolio_ai.assert_consent", _consent_spy())
    monkeypatch.setattr("dhanradar.mf.portfolio_ai.watchlist_ai_cache_entitled", _entitlement_spy())
    monkeypatch.setattr("dhanradar.mf.portfolio_ai.record_served_label", record)

    poisoned_output = _make_output(0.8, "high", _ADVISORY_ITEM)
    gw = _FakeGateway([
        _make_result(poisoned_output),
        _make_result(poisoned_output),
    ])
    result = await generate_portfolio_ai_feed(
        gw,
        user_id="user-1",
        portfolio_id=_PORTFOLIO_ID,
        db=_FAKE_DB,  # type: ignore[arg-type]
        holdings=_PROMPT_HOLDINGS,
    )
    assert result["state"] == "unavailable"
    assert result["items"] == []
    assert len(gw.calls) == 2  # retried once
    assert record.calls == []  # audit never written


async def test_generate_advisory_screen_retry_second_clean(monkeypatch) -> None:
    """First attempt fails advisory screen, second is clean → served + audited."""
    record = _record_spy()
    monkeypatch.setattr("dhanradar.mf.portfolio_ai.assert_consent", _consent_spy())
    monkeypatch.setattr("dhanradar.mf.portfolio_ai.watchlist_ai_cache_entitled", _entitlement_spy())
    monkeypatch.setattr("dhanradar.mf.portfolio_ai.record_served_label", record)

    gw = _FakeGateway([
        _make_result(_make_output(0.8, "high", _ADVISORY_ITEM)),
        _make_result(_make_output(0.8, "high", _GOOD_ITEMS)),
    ])
    result = await generate_portfolio_ai_feed(
        gw,
        user_id="user-1",
        portfolio_id=_PORTFOLIO_ID,
        db=_FAKE_DB,  # type: ignore[arg-type]
        holdings=_PROMPT_HOLDINGS,
    )
    assert result["state"] == "ok"
    assert result["items"] == _GOOD_ITEMS
    assert len(record.calls) == 1


# ===========================================================================
# Serialization — poisoned unified_score stripped + allowlist coverage
# ===========================================================================


def test_portfolio_ai_feed_allowlist_includes_all_required_fields() -> None:
    required = {"portfolio_id", "items", "state", "confidence_band", "as_of",
                "no_data_reason", "disclosure", "not_advice", "disclaimer_version"}
    assert required.issubset(ALLOWED_FIELDS["portfolio.ai_feed"])


def test_portfolio_ai_feed_unified_score_stripped_by_a3(monkeypatch) -> None:
    """unified_score never survives the serialize_concept A3 boundary."""
    from dhanradar.mf.serialization import RequestCtx, serialize_concept

    poisoned = {
        "portfolio_id": _PORTFOLIO_ID,
        "items": ["A factual portfolio observation."],
        "state": "ok",
        "confidence_band": "medium",
        "as_of": "2026-08-22",
        "no_data_reason": None,
        "disclosure": "DISC",
        "not_advice": "NA",
        "disclaimer_version": "2026-06-06.v1",
        "unified_score": 0.72,  # must be stripped
    }
    envelope = serialize_concept("portfolio.ai_feed", poisoned, RequestCtx())
    assert "unified_score" not in (envelope["data"] or {})
    assert envelope["data"]["items"] == ["A factual portfolio observation."]


# ===========================================================================
# Disclaimer staleness — stale cache triggers live regeneration
# ===========================================================================


async def test_stale_disclaimer_triggers_live_regeneration(monkeypatch) -> None:
    uid_str = str(uuid.uuid4())
    uid = uuid.UUID(uid_str)
    cache_key = "mf:portfolio_ai:" + hashlib.sha256(
        f"{uid}:{_PORTFOLIO_ID}".encode()
    ).hexdigest()
    stale_payload = {
        "portfolio_id": _PORTFOLIO_ID,
        "items": ["Old stale insight."],
        "state": "ok",
        "confidence_band": "medium",
        "as_of": "2026-08-22",
        "no_data_reason": None,
        "disclosure": "DISC",
        "not_advice": "NA",
        "disclaimer_version": "STALE-VERSION-2024",
    }
    fake_redis = _FakeRedis(seed={cache_key: json.dumps(stale_payload)})
    generate_calls = []

    async def _fake_generate(*a, **kw):
        generate_calls.append(kw)
        from dhanradar.compliance.service import active_disclaimer_version
        from dhanradar.scoring.engine.schemas import DISCLOSURE_BUNDLE, NOT_ADVICE
        return {
            "portfolio_id": _PORTFOLIO_ID,
            "items": ["Fresh insight after disclaimer update."],
            "state": "ok",
            "confidence_band": "medium",
            "as_of": "2026-08-22",
            "no_data_reason": None,
            "disclosure": DISCLOSURE_BUNDLE,
            "not_advice": NOT_ADVICE,
            "disclaimer_version": active_disclaimer_version(),
        }

    fake_user = _user()
    fake_user.user_id = uid_str

    monkeypatch.setattr("dhanradar.mf.watchlist_ai.watchlist_ai_consent_granted", lambda *_: _async_true())
    monkeypatch.setattr("dhanradar.mf.watchlist_ai.watchlist_ai_cache_entitled", lambda *_: _async_true())
    monkeypatch.setattr("dhanradar.insights.router.get_redis", lambda: fake_redis)
    monkeypatch.setattr(
        "dhanradar.insights.router.load_portfolio_read_model",
        lambda db, pid: _async(_FakePortfolioRM(holdings=_SAMPLE_HOLDINGS)),
    )
    monkeypatch.setattr("dhanradar.insights.router._owned_portfolio_id", lambda *a, **kw: _async(None))
    monkeypatch.setattr("dhanradar.insights.router._require_mf_consent", _noop_consent())
    monkeypatch.setattr("dhanradar.mf.portfolio_ai.generate_portfolio_ai_feed", _fake_generate)

    result = await portfolio_ai_feed(
        portfolio_id=_PORTFOLIO_ID,
        request=_request(),
        user=fake_user,
        db=_FAKE_DB,  # type: ignore[arg-type]
        response=Response(),
    )
    assert generate_calls, "generate_portfolio_ai_feed must be called for a stale disclaimer"
    assert result["data"]["items"] == ["Fresh insight after disclaimer update."]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _async(value):
    return value


async def _async_true() -> bool:
    return True


async def _async_false() -> bool:
    return False


def _noop_consent():
    async def _noop(*, user, db):
        pass
    return _noop

