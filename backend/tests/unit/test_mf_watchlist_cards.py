"""
Unit tests — GET /mf/watchlist/cards (WATCHLIST_LIVE_DATA_PLAN.md Wave 1).

Coverage:
  1. Auth: 401 for an anonymous caller.
  2. Empty watchlist → 200 with an empty `items` array.
  3. 2+ funds → correct fields land in the serialized response.
  4. No-numeric leak: a smuggled unified_score/score/factor_weights key never
     survives serialize_watchlist_cards_response.
  5. Redis per-ISIN fragment cache hit path — a cached card is reused, the
     compositor is never called for that ISIN.
  6. Response header Cache-Control: private (personal membership list).

asyncio_mode = "auto" (pyproject.toml). No real DB/Redis: async fakes throughout,
same convention as test_mf_watchlist.py / test_leaderboard.py.
"""

from __future__ import annotations

import json
import re
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException, Response

from dhanradar.mf.router import watchlist_cards


class _FakeCardsDB:
    """Minimal AsyncSession stub — `select(MfWatchlistItem.isin)...scalars().all()`."""

    def __init__(self, isins: list[str] | None = None) -> None:
        self._isins = list(isins or [])

    async def execute(self, stmt: Any) -> "_FakeCardsDB":  # noqa: UP037
        return self

    def scalars(self) -> "_FakeCardsDB":  # noqa: UP037
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

    async def mget(self, keys: list[str]) -> list[str | None]:
        return [self.store.get(k) for k in keys]

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
        self.set_calls.append(key)


def _user(anonymous: bool = False) -> SimpleNamespace:
    return SimpleNamespace(is_anonymous=anonymous, user_id=str(uuid.uuid4()))


ISIN_A = "INF174K01KH7"
ISIN_B = "INF200K01234"


def _card(isin: str, *, last_nav_date: str = "2026-08-20") -> dict[str, Any]:
    return {
        "isin": isin,
        "scheme_name": f"{isin} Fund - Direct - Growth",
        "fund_name_short": f"{isin} Fund",
        "amc_name": "Test AMC",
        "sebi_category": "Large Cap Fund",
        "category": "Equity",
        "expense_ratio_pct": 0.8,
        "risk_o_meter": "Moderately High",
        "nav_latest": 120.5,
        "nav_change_pct": 0.42,
        "nav_sparkline": [{"d": "2026-08-19", "nav": 119.9}, {"d": last_nav_date, "nav": 120.5}],
        "return_1y_pct": 14.2,
        "return_3y_pct": 16.1,
        "return_5y_pct": 12.0,
        "verb_label": "on_track",
        "confidence_band": "medium",
    }


# 1 — anonymous 401 ------------------------------------------------------------


async def test_watchlist_cards_401_for_anonymous() -> None:
    db = _FakeCardsDB()
    with pytest.raises(HTTPException) as exc:
        await watchlist_cards(db=db, response=Response(), user=_user(anonymous=True))
    assert exc.value.status_code == 401


# 2 — empty watchlist ------------------------------------------------------------


async def test_watchlist_cards_empty_watchlist_returns_empty_items(monkeypatch) -> None:
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: _FakeRedis())
    db = _FakeCardsDB(isins=[])

    envelope = await watchlist_cards(db=db, response=Response(), user=_user())

    assert envelope["items"] == []
    assert envelope["as_of"] is None


# 3 — 2+ funds, correct fields ----------------------------------------------------


async def test_watchlist_cards_two_funds_have_correct_fields(monkeypatch) -> None:
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: _FakeRedis())

    cards_by_isin = {ISIN_A: _card(ISIN_A, last_nav_date="2026-08-20"), ISIN_B: _card(ISIN_B, last_nav_date="2026-08-19")}

    async def fake_get_watchlist_card(session: Any, isin: str) -> dict[str, Any]:
        return cards_by_isin[isin]

    monkeypatch.setattr("dhanradar.mf.fund_read.get_watchlist_card", fake_get_watchlist_card)
    db = _FakeCardsDB(isins=[ISIN_A, ISIN_B])

    envelope = await watchlist_cards(db=db, response=Response(), user=_user())

    assert [c["isin"] for c in envelope["items"]] == [ISIN_A, ISIN_B]
    first = envelope["items"][0]
    assert first["scheme_name"] == cards_by_isin[ISIN_A]["scheme_name"]
    assert first["verb_label"] == "on_track"
    assert first["confidence_band"] == "medium"
    assert first["nav_sparkline"][-1]["nav"] == 120.5
    assert first["return_1y_pct"] == 14.2
    # as_of = freshest nav_sparkline date across all cards.
    assert envelope["as_of"] == "2026-08-20"


# 4 — no numeric score leak -------------------------------------------------------


_FORBIDDEN_RE = re.compile(r'"unified_score"|"score"|"factor_weights"')


async def test_watchlist_cards_never_leaks_a_smuggled_score_field(monkeypatch) -> None:
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: _FakeRedis())

    poisoned = dict(_card(ISIN_A))
    poisoned["unified_score"] = 87.5
    poisoned["score"] = 42
    poisoned["factor_weights"] = {"consistency": 0.4}

    async def fake_get_watchlist_card(session: Any, isin: str) -> dict[str, Any]:
        return poisoned

    monkeypatch.setattr("dhanradar.mf.fund_read.get_watchlist_card", fake_get_watchlist_card)
    db = _FakeCardsDB(isins=[ISIN_A])

    envelope = await watchlist_cards(db=db, response=Response(), user=_user())

    serialized = json.dumps(envelope)
    assert not _FORBIDDEN_RE.search(serialized), serialized
    assert "unified_score" not in envelope["items"][0]
    assert "score" not in envelope["items"][0]
    assert "factor_weights" not in envelope["items"][0]


# 5 — redis fragment cache hit reuses the cached card, never recomputes ----------


async def test_watchlist_cards_redis_cache_hit_reuses_cached_fragment(monkeypatch) -> None:
    cached_card = _card(ISIN_A, last_nav_date="2026-08-18")
    fake_redis = _FakeRedis(seed={f"mf:watchlist_card:{ISIN_A}": json.dumps(cached_card)})
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: fake_redis)

    async def fail_if_called(session: Any, isin: str) -> dict[str, Any]:
        raise AssertionError("compositor must not run on a cache hit")

    monkeypatch.setattr("dhanradar.mf.fund_read.get_watchlist_card", fail_if_called)
    db = _FakeCardsDB(isins=[ISIN_A])

    envelope = await watchlist_cards(db=db, response=Response(), user=_user())

    assert envelope["items"][0]["isin"] == ISIN_A
    assert envelope["items"][0]["nav_sparkline"][-1]["d"] == "2026-08-18"
    assert fake_redis.set_calls == []  # never re-written on a hit


async def test_watchlist_cards_cache_miss_writes_fragment_back(monkeypatch) -> None:
    fake_redis = _FakeRedis()
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: fake_redis)

    async def fake_get_watchlist_card(session: Any, isin: str) -> dict[str, Any]:
        return _card(isin)

    monkeypatch.setattr("dhanradar.mf.fund_read.get_watchlist_card", fake_get_watchlist_card)
    db = _FakeCardsDB(isins=[ISIN_A])

    await watchlist_cards(db=db, response=Response(), user=_user())

    assert fake_redis.set_calls == [f"mf:watchlist_card:{ISIN_A}"]


# 6 — Cache-Control: private -------------------------------------------------------


async def test_watchlist_cards_response_header_is_private(monkeypatch) -> None:
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: _FakeRedis())
    db = _FakeCardsDB(isins=[])
    resp = Response()

    await watchlist_cards(db=db, response=resp, user=_user())

    assert resp.headers["Cache-Control"] == "private"


# 7 — mixed cache hit + miss in one request keeps order and composes only the miss


async def test_watchlist_cards_mixed_hit_and_miss_keeps_order(monkeypatch) -> None:
    cached_card = _card(ISIN_A, last_nav_date="2026-08-18")
    fake_redis = _FakeRedis(seed={f"mf:watchlist_card:{ISIN_A}": json.dumps(cached_card)})
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: fake_redis)

    async def fake_get_watchlist_card(session: Any, isin: str) -> dict[str, Any]:
        assert isin == ISIN_B, "compositor must only run for the cache miss"
        return _card(isin)

    monkeypatch.setattr("dhanradar.mf.fund_read.get_watchlist_card", fake_get_watchlist_card)
    db = _FakeCardsDB(isins=[ISIN_A, ISIN_B])

    envelope = await watchlist_cards(db=db, response=Response(), user=_user())

    assert [c["isin"] for c in envelope["items"]] == [ISIN_A, ISIN_B]
    assert fake_redis.set_calls == [f"mf:watchlist_card:{ISIN_B}"]
