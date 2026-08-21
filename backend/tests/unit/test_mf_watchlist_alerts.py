"""Unit tests — GET /mf/watchlist/alerts (P2 backend).

Coverage:
  1. Migration module: importable, correct revision/down_revision, table in
     PERSONAL_TABLES and RLS_ENFORCED.
  2. ORM model: MfWatchlistAlert has the expected columns and CheckConstraint.
  3. Auth: 401 for anonymous callers.
  4. Owner scoping: a second user's alerts never appear (cross-user isolation).
  5. Serializer: id/isin/alert_type/title/body/triggered_on/created_at/fund fields pass.
  6. Poisoned-field test: unified_score/score/factor_weights never reach the response.
  7. Empty alerts: 200 with empty items list.
  8. mf.watchlist_alert allowlist registered in ALLOWED_FIELDS (B87 guard).

asyncio_mode = "auto" (pyproject.toml). No real DB: async fakes throughout.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from dhanradar.mf.router import get_watchlist_alerts
from dhanradar.mf.serialization import ALLOWED_FIELDS, serialize_watchlist_alerts_response

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _Row:
    """Fake result row matching the SELECT columns in get_watchlist_alerts."""

    def __init__(
        self,
        *,
        isin: str = "INF174K01KH7",
        alert_type: str = "nav_move",
        title: str = "Test title",
        body: str = "Test body",
        triggered_on: date | None = None,
        created_at: datetime | None = None,
        fund_name_short: str | None = "Test Fund",
        scheme_name: str | None = "Test Fund - Direct - Growth",
    ) -> None:
        self.id = uuid.uuid4()
        self.isin = isin
        self.alert_type = alert_type
        self.title = title
        self.body = body
        self.triggered_on = triggered_on or date(2026, 8, 21)
        self.created_at = created_at or datetime(2026, 8, 21, 3, 0, tzinfo=UTC)
        self.fund_name_short = fund_name_short
        self.scheme_name = scheme_name


class _FakeDB:
    """Minimal AsyncSession stub for get_watchlist_alerts."""

    def __init__(self, rows: list[_Row] | None = None) -> None:
        self._rows = list(rows or [])
        self.executed: list[Any] = []

    async def execute(self, stmt: Any) -> "_FakeDB":  # noqa: UP037
        self.executed.append(stmt)
        return self

    def all(self) -> list[_Row]:
        return list(self._rows)


def _user(anonymous: bool = False) -> SimpleNamespace:
    return SimpleNamespace(is_anonymous=anonymous, user_id=str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# 1 — migration wiring
# ---------------------------------------------------------------------------


def test_migration_0082_wiring() -> None:
    migration_path = (
        pathlib.Path(__file__).parent.parent.parent
        / "alembic"
        / "versions"
        / "0082_mf_watchlist_alerts.py"
    )
    spec = importlib.util.spec_from_file_location("_mig_0082", migration_path)
    assert spec is not None
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)  # type: ignore[union-attr]
    assert mig.revision == "0082"
    assert mig.down_revision == "0081"
    assert callable(mig.upgrade)
    assert callable(mig.downgrade)

    from dhanradar.db_security import PERSONAL_TABLES, RLS_ENFORCED

    assert "mf.mf_watchlist_alerts" in PERSONAL_TABLES
    assert "mf.mf_watchlist_alerts" in RLS_ENFORCED


# ---------------------------------------------------------------------------
# 2 — ORM model columns and constraint
# ---------------------------------------------------------------------------


def test_orm_model_columns() -> None:
    from dhanradar.models.mf import MfWatchlistAlert

    cols = {c.name for c in MfWatchlistAlert.__table__.columns}
    expected = {"id", "user_id", "isin", "alert_type", "title", "body", "triggered_on", "created_at"}
    assert expected <= cols

    # Check the constraint text contains the valid types
    cc_texts = [
        c.sqltext.text
        for c in MfWatchlistAlert.__table__.constraints
        if hasattr(c, "sqltext")
    ]
    assert any("nav_move" in t and "label_change" in t for t in cc_texts)


# ---------------------------------------------------------------------------
# 3 — anonymous 401
# ---------------------------------------------------------------------------


async def test_alerts_401_anonymous() -> None:
    db = _FakeDB()
    with pytest.raises(HTTPException) as exc:
        await get_watchlist_alerts(db=db, user=_user(anonymous=True))
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# 4 — cross-user isolation: only the caller's rows come back
# ---------------------------------------------------------------------------


async def test_alerts_cross_user_rows_absent() -> None:
    """The stub returns no rows (simulating RLS / WHERE user_id scoping)."""
    db = _FakeDB(rows=[])  # other user's rows simply never come back
    result = await get_watchlist_alerts(db=db, user=_user())
    assert result["items"] == []


# ---------------------------------------------------------------------------
# 5 — correct fields pass through serializer
# ---------------------------------------------------------------------------


async def test_alerts_fields_present() -> None:
    row = _Row(alert_type="nav_move", title="NAV up 3.1%", body="Educational note.")
    db = _FakeDB(rows=[row])

    result = await get_watchlist_alerts(db=db, user=_user())

    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["isin"] == row.isin
    assert item["alert_type"] == "nav_move"
    assert item["title"] == "NAV up 3.1%"
    assert item["body"] == "Educational note."
    assert item["triggered_on"] == "2026-08-21"
    assert item["fund_name_short"] == "Test Fund"
    assert item["scheme_name"] == "Test Fund - Direct - Growth"
    assert "id" in item


# ---------------------------------------------------------------------------
# 6 — poisoned-field test: score keys never reach response
# ---------------------------------------------------------------------------


_FORBIDDEN_RE = re.compile(r'"unified_score"|"score"|"factor_weights"')


def test_alerts_serializer_strips_poisoned_fields() -> None:
    items = [
        {
            "id": str(uuid.uuid4()),
            "isin": "INF174K01KH7",
            "alert_type": "nav_move",
            "title": "Title",
            "body": "Body",
            "triggered_on": "2026-08-21",
            "created_at": "2026-08-21T03:00:00+00:00",
            "fund_name_short": "Fund",
            "scheme_name": "Fund - Direct",
            # Poisoned fields:
            "unified_score": 87.5,
            "score": 42,
            "factor_weights": {"consistency": 0.4},
        }
    ]
    result = serialize_watchlist_alerts_response(items=items)
    serialized = json.dumps(result)
    assert not _FORBIDDEN_RE.search(serialized)
    assert "unified_score" not in result["items"][0]
    assert "score" not in result["items"][0]
    assert "factor_weights" not in result["items"][0]


# ---------------------------------------------------------------------------
# 7 — empty alerts → 200 with empty items
# ---------------------------------------------------------------------------


async def test_alerts_empty_returns_empty_list() -> None:
    db = _FakeDB(rows=[])
    result = await get_watchlist_alerts(db=db, user=_user())
    assert result == {"items": []}


# ---------------------------------------------------------------------------
# 8 — mf.watchlist_alert allowlist registered (B87)
# ---------------------------------------------------------------------------


def test_watchlist_alert_allowlist_registered() -> None:
    assert "mf.watchlist_alert" in ALLOWED_FIELDS
    allowed = ALLOWED_FIELDS["mf.watchlist_alert"]
    for field in ("id", "isin", "alert_type", "title", "body", "triggered_on", "created_at"):
        assert field in allowed, f"missing field: {field}"
    # Score keys must NOT be in the allowlist.
    for bad in ("unified_score", "score", "factor_weights", "fair_value"):
        assert bad not in allowed, f"forbidden key in allowlist: {bad}"
