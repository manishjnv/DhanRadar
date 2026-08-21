"""
Unit tests — GET /mf/watchlist/changes (WATCHLIST_LIVE_DATA_PLAN.md Wave 2 item 1).

Coverage:
  1. Auth: 401 for an anonymous caller.
  2. Empty watchlist → 200 with an empty `items` array, `as_of` null.
  3. 2+ events → correct fields land in the serialized response.
  4. No-numeric leak: a smuggled unified_score/score/factor_weights key never
     survives serialize_watchlist_changes_response.
  5. `since`/`limit` query params thread through to the batch composer unchanged.
  6. A malformed `since` string is rejected 422 before the composer ever runs.
  7. Response header Cache-Control: private.

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

from dhanradar.mf.router import watchlist_changes


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


def _change(isin: str, *, as_of: str = "2026-08-20", event_type: str = "rank_change") -> dict[str, Any]:
    return {
        "isin": isin,
        "scheme_name": f"{isin} Fund - Direct - Growth",
        "fund_name_short": f"{isin} Fund",
        "event_type": event_type,
        "as_of": as_of,
        "summary": "Category rank moved from 24 to 18 of 183.",
        "severity": "info",
    }


# 1 — anonymous 401 ------------------------------------------------------------


async def test_watchlist_changes_401_for_anonymous() -> None:
    db = _FakeIsinsDB()
    with pytest.raises(HTTPException) as exc:
        await watchlist_changes(db=db, response=Response(), user=_user(anonymous=True))
    assert exc.value.status_code == 401


# 2 — empty watchlist ------------------------------------------------------------


async def test_watchlist_changes_empty_watchlist_returns_empty_items(monkeypatch) -> None:
    async def fake_get_watchlist_changes(session: Any, isins: list[str], *, since, limit) -> list[dict]:
        assert isins == []
        return []

    monkeypatch.setattr("dhanradar.mf.fund_read.get_watchlist_changes", fake_get_watchlist_changes)
    db = _FakeIsinsDB(isins=[])

    envelope = await watchlist_changes(db=db, response=Response(), user=_user())

    assert envelope["items"] == []
    assert envelope["as_of"] is None


# 3 — 2+ events, correct fields ----------------------------------------------------


async def test_watchlist_changes_two_events_have_correct_fields(monkeypatch) -> None:
    events = [_change(ISIN_A, as_of="2026-08-20"), _change(ISIN_B, as_of="2026-08-19", event_type="ter_change")]

    async def fake_get_watchlist_changes(session: Any, isins: list[str], *, since, limit) -> list[dict]:
        return events

    monkeypatch.setattr("dhanradar.mf.fund_read.get_watchlist_changes", fake_get_watchlist_changes)
    db = _FakeIsinsDB(isins=[ISIN_A, ISIN_B])

    envelope = await watchlist_changes(db=db, response=Response(), user=_user())

    assert [c["isin"] for c in envelope["items"]] == [ISIN_A, ISIN_B]
    first = envelope["items"][0]
    assert first["event_type"] == "rank_change"
    assert first["summary"] == events[0]["summary"]
    assert first["severity"] == "info"
    # as_of = freshest event date across all items.
    assert envelope["as_of"] == "2026-08-20"


# 4 — no numeric score leak -------------------------------------------------------


_FORBIDDEN_RE = re.compile(r'"unified_score"|"score"|"factor_weights"')


async def test_watchlist_changes_never_leaks_a_smuggled_score_field(monkeypatch) -> None:
    poisoned = dict(_change(ISIN_A))
    poisoned["unified_score"] = 87.5
    poisoned["score"] = 42
    poisoned["factor_weights"] = {"consistency": 0.4}

    async def fake_get_watchlist_changes(session: Any, isins: list[str], *, since, limit) -> list[dict]:
        return [poisoned]

    monkeypatch.setattr("dhanradar.mf.fund_read.get_watchlist_changes", fake_get_watchlist_changes)
    db = _FakeIsinsDB(isins=[ISIN_A])

    envelope = await watchlist_changes(db=db, response=Response(), user=_user())

    serialized = json.dumps(envelope)
    assert not _FORBIDDEN_RE.search(serialized), serialized
    assert "unified_score" not in envelope["items"][0]
    assert "score" not in envelope["items"][0]
    assert "factor_weights" not in envelope["items"][0]


# 5 — since/limit passthrough ------------------------------------------------------


async def test_watchlist_changes_since_and_limit_thread_through(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_get_watchlist_changes(session: Any, isins: list[str], *, since, limit) -> list[dict]:
        captured["since"] = since
        captured["limit"] = limit
        return []

    monkeypatch.setattr("dhanradar.mf.fund_read.get_watchlist_changes", fake_get_watchlist_changes)
    db = _FakeIsinsDB(isins=[ISIN_A])

    await watchlist_changes(db=db, response=Response(), user=_user(), since="2026-08-01", limit=25)

    assert captured["since"] == date(2026, 8, 1)
    assert captured["limit"] == 25


async def test_watchlist_changes_default_limit_is_nine(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_get_watchlist_changes(session: Any, isins: list[str], *, since, limit) -> list[dict]:
        captured["since"] = since
        captured["limit"] = limit
        return []

    monkeypatch.setattr("dhanradar.mf.fund_read.get_watchlist_changes", fake_get_watchlist_changes)
    db = _FakeIsinsDB(isins=[])

    await watchlist_changes(db=db, response=Response(), user=_user())

    assert captured["since"] is None
    assert captured["limit"] == 9


# 6 — malformed since is rejected before the composer runs -------------------------


async def test_watchlist_changes_malformed_since_is_422(monkeypatch) -> None:
    async def fail_if_called(session: Any, isins: list[str], *, since, limit) -> list[dict]:
        raise AssertionError("composer must not run on a malformed since")

    monkeypatch.setattr("dhanradar.mf.fund_read.get_watchlist_changes", fail_if_called)
    db = _FakeIsinsDB(isins=[ISIN_A])

    with pytest.raises(HTTPException) as exc:
        await watchlist_changes(db=db, response=Response(), user=_user(), since="not-a-date")
    assert exc.value.status_code == 422


# 7 — Cache-Control: private -------------------------------------------------------


async def test_watchlist_changes_response_header_is_private(monkeypatch) -> None:
    async def fake_get_watchlist_changes(session: Any, isins: list[str], *, since, limit) -> list[dict]:
        return []

    monkeypatch.setattr("dhanradar.mf.fund_read.get_watchlist_changes", fake_get_watchlist_changes)
    db = _FakeIsinsDB(isins=[])
    resp = Response()

    await watchlist_changes(db=db, response=resp, user=_user())

    assert resp.headers["Cache-Control"] == "private"
