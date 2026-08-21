"""
Unit tests — GET /mf/watchlist/similar (WATCHLIST_LIVE_DATA_PLAN.md Wave 2 item 2).

Coverage:
  1. Auth: 401 for an anonymous caller.
  2. Empty watchlist → 200 with an empty `items` array, `as_of` null.
  3. 2+ peers → correct fields land in the serialized response.
  4. No-numeric leak: a smuggled unified_score/score/factor_weights key never
     survives serialize_watchlist_similar_response.
  5. Response header Cache-Control: private.
  6. `dedupe_similar_candidates` (pure): excludes every caller-saved ISIN, drops
     a candidate ISIN that reappears (same fund ranks in two anchor categories),
     and caps at `cap` — no database needed (mirrors mf/fund_events.py's pure
     detector test convention).

asyncio_mode = "auto" (pyproject.toml). No real DB: async fakes throughout, same
convention as test_mf_watchlist_cards.py.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException, Response

from dhanradar.mf.fund_read import dedupe_similar_candidates
from dhanradar.mf.router import watchlist_similar


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


def _user(anonymous: bool = False) -> SimpleNamespace:
    return SimpleNamespace(is_anonymous=anonymous, user_id=str(uuid.uuid4()))


ISIN_A = "INF174K01KH7"
ISIN_B = "INF200K01234"
ISIN_C = "INF300K05678"


def _similar(isin: str) -> dict[str, Any]:
    return {
        "isin": isin,
        "scheme_name": f"{isin} Fund - Direct - Growth",
        "fund_name_short": f"{isin} Fund",
        "amc_name": "Test AMC",
        "category": "Equity",
        "sebi_category": "Large Cap Fund",
        "verb_label": "on_track",
        "confidence_band": "medium",
        "return_1y_pct": 14.2,
        "return_3y_pct": 16.1,
        "expense_ratio_pct": 0.8,
        "similar_to": "Held Fund",
    }


# 1 — anonymous 401 ------------------------------------------------------------


async def test_watchlist_similar_401_for_anonymous() -> None:
    db = _FakeIsinsDB()
    with pytest.raises(HTTPException) as exc:
        await watchlist_similar(db=db, response=Response(), user=_user(anonymous=True))
    assert exc.value.status_code == 401


# 2 — empty watchlist ------------------------------------------------------------


async def test_watchlist_similar_empty_watchlist_returns_empty_items(monkeypatch) -> None:
    async def fake_get_watchlist_similar(session: Any, isins: list[str], *, cap: int):
        assert isins == []
        return [], None

    monkeypatch.setattr("dhanradar.mf.fund_read.get_watchlist_similar", fake_get_watchlist_similar)
    db = _FakeIsinsDB(isins=[])

    envelope = await watchlist_similar(db=db, response=Response(), user=_user())

    assert envelope["items"] == []
    assert envelope["as_of"] is None


# 3 — 2+ peers, correct fields ----------------------------------------------------


async def test_watchlist_similar_two_peers_have_correct_fields(monkeypatch) -> None:
    peers = [_similar(ISIN_B), _similar(ISIN_C)]

    async def fake_get_watchlist_similar(session: Any, isins: list[str], *, cap: int):
        return peers, "2026-08-20"

    monkeypatch.setattr("dhanradar.mf.fund_read.get_watchlist_similar", fake_get_watchlist_similar)
    db = _FakeIsinsDB(isins=[ISIN_A])

    envelope = await watchlist_similar(db=db, response=Response(), user=_user())

    assert [p["isin"] for p in envelope["items"]] == [ISIN_B, ISIN_C]
    first = envelope["items"][0]
    assert first["verb_label"] == "on_track"
    assert first["confidence_band"] == "medium"
    assert first["similar_to"] == "Held Fund"
    assert envelope["as_of"] == "2026-08-20"


# 4 — no numeric score leak -------------------------------------------------------


_FORBIDDEN_RE = re.compile(r'"unified_score"|"score"|"factor_weights"')


async def test_watchlist_similar_never_leaks_a_smuggled_score_field(monkeypatch) -> None:
    poisoned = dict(_similar(ISIN_B))
    poisoned["unified_score"] = 87.5
    poisoned["score"] = 42
    poisoned["factor_weights"] = {"consistency": 0.4}

    async def fake_get_watchlist_similar(session: Any, isins: list[str], *, cap: int):
        return [poisoned], "2026-08-20"

    monkeypatch.setattr("dhanradar.mf.fund_read.get_watchlist_similar", fake_get_watchlist_similar)
    db = _FakeIsinsDB(isins=[ISIN_A])

    envelope = await watchlist_similar(db=db, response=Response(), user=_user())

    serialized = json.dumps(envelope)
    assert not _FORBIDDEN_RE.search(serialized), serialized
    assert "unified_score" not in envelope["items"][0]
    assert "score" not in envelope["items"][0]
    assert "factor_weights" not in envelope["items"][0]


# 5 — Cache-Control: private -------------------------------------------------------


async def test_watchlist_similar_response_header_is_private(monkeypatch) -> None:
    async def fake_get_watchlist_similar(session: Any, isins: list[str], *, cap: int):
        return [], None

    monkeypatch.setattr("dhanradar.mf.fund_read.get_watchlist_similar", fake_get_watchlist_similar)
    db = _FakeIsinsDB(isins=[])
    resp = Response()

    await watchlist_similar(db=db, response=resp, user=_user())

    assert resp.headers["Cache-Control"] == "private"


# ---------------------------------------------------------------------------
# 6 — dedupe_similar_candidates (pure) — no DB needed.
# ---------------------------------------------------------------------------


class _FakeRank:
    def __init__(self, isin: str, sebi_category: str, rank: int, verb_label: str = "on_track", confidence_band: str = "medium") -> None:
        self.isin = isin
        self.sebi_category = sebi_category
        self.as_of_date = date(2026, 8, 20)
        self.rank = rank
        self.verb_label = verb_label
        self.confidence_band = confidence_band


class _FakeFund:
    def __init__(self, isin: str, category: str = "Equity", sebi_category: str = "Large Cap Fund") -> None:
        self.isin = isin
        self.scheme_name = f"{isin} Fund - Direct - Growth"
        self.fund_name_short = f"{isin} Fund"
        self.amc_name = "Test AMC"
        self.category = category
        self.sebi_category = sebi_category
        self.expense_ratio_pct = 0.8


class _FakeMetrics:
    def __init__(self, return_1y_pct: float = 12.0, return_3y_pct: float = 14.0, nav_points: int = 800) -> None:
        self.return_1y_pct = return_1y_pct
        self.return_3y_pct = return_3y_pct
        self.nav_points = nav_points


def test_dedupe_excludes_every_caller_saved_isin() -> None:
    candidates = [
        (_FakeRank(ISIN_A, "Large Cap Fund", 1), _FakeFund(ISIN_A), _FakeMetrics()),
        (_FakeRank(ISIN_B, "Large Cap Fund", 2), _FakeFund(ISIN_B), _FakeMetrics()),
    ]
    out = dedupe_similar_candidates(
        candidates,
        excluded_isins={ISIN_A},
        anchor_name_by_category={"Large Cap Fund": "Held Fund"},
        cap=6,
    )
    assert [row["isin"] for row in out] == [ISIN_B]


def test_dedupe_drops_a_repeated_candidate_isin() -> None:
    # ISIN_B ranks in two anchor category+run pairs (e.g. two watched funds
    # share the same category) — it must appear only once in the output.
    candidates = [
        (_FakeRank(ISIN_B, "Large Cap Fund", 2), _FakeFund(ISIN_B), _FakeMetrics()),
        (_FakeRank(ISIN_B, "Large Cap Fund", 2), _FakeFund(ISIN_B), _FakeMetrics()),
        (_FakeRank(ISIN_C, "Large Cap Fund", 3), _FakeFund(ISIN_C), _FakeMetrics()),
    ]
    out = dedupe_similar_candidates(
        candidates, excluded_isins=set(), anchor_name_by_category={}, cap=6
    )
    assert [row["isin"] for row in out] == [ISIN_B, ISIN_C]


def test_dedupe_caps_at_requested_count() -> None:
    candidates = [
        (_FakeRank(f"INF{i:03d}K01KH7", "Large Cap Fund", i), _FakeFund(f"INF{i:03d}K01KH7"), _FakeMetrics())
        for i in range(10)
    ]
    out = dedupe_similar_candidates(
        candidates, excluded_isins=set(), anchor_name_by_category={}, cap=6
    )
    assert len(out) == 6


def test_dedupe_returns_string_returns_null_below_min_nav_points() -> None:
    candidates = [
        (_FakeRank(ISIN_B, "Large Cap Fund", 2), _FakeFund(ISIN_B), _FakeMetrics(nav_points=10)),
    ]
    out = dedupe_similar_candidates(
        candidates, excluded_isins=set(), anchor_name_by_category={}, cap=6
    )
    assert out[0]["return_1y_pct"] is None
    assert out[0]["return_3y_pct"] is None


def test_dedupe_similar_to_uses_anchor_category_name() -> None:
    candidates = [(_FakeRank(ISIN_B, "Large Cap Fund", 2), _FakeFund(ISIN_B), _FakeMetrics())]
    out = dedupe_similar_candidates(
        candidates,
        excluded_isins=set(),
        anchor_name_by_category={"Large Cap Fund": "Parag Parikh Flexi Cap"},
        cap=6,
    )
    assert out[0]["similar_to"] == "Parag Parikh Flexi Cap"
