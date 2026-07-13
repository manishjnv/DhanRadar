"""
Unit tests — MF watchlist routes (0079 slice).

Coverage:
  1. Migration module: importable, correct revision/down_revision strings, and
     RLS applied via db_security helpers (table listed in BOTH PERSONAL_TABLES
     and RLS_ENFORCED — the drift test asserts set equality separately).
  2. Auth: all three handlers raise 401 for anonymous callers.
  3. ISIN shape gate: _valid_isin normalizes case/whitespace and 422s garbage.
  4. Cap: add raises 422 watchlist_full at _WATCHLIST_MAX_ITEMS.
  5. get_watchlist maps rows oldest-first into WatchlistItemOut.
  6. No-numeric: WatchlistResponse carries no score/numeric fields.

asyncio_mode = "auto" (pyproject.toml). No real DB: async fakes throughout.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from dhanradar.mf.router import (
    _WATCHLIST_MAX_ITEMS,
    _valid_isin,
    add_watchlist_item,
    get_watchlist,
    remove_watchlist_item,
)


class _FakeDB:
    """Minimal AsyncSession stub for the watchlist handlers."""

    def __init__(self, scalars_all: list | None = None, scalar_value: Any = None) -> None:
        self.executed: list[Any] = []
        self.committed = 0
        self.deleted: list[Any] = []
        self._scalars_all = list(scalars_all or [])
        self._scalar_value = scalar_value

    async def execute(self, stmt: Any, params: Any = None) -> "_FakeDB":  # noqa: UP037
        self.executed.append(stmt)
        return self

    async def commit(self) -> None:
        self.committed += 1

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    def scalars(self) -> "_FakeDB":  # noqa: UP037
        return self

    def all(self) -> list:
        return list(self._scalars_all)

    def scalar_one(self) -> Any:
        return self._scalar_value

    def scalar_one_or_none(self) -> Any:
        return self._scalar_value


def _user(anonymous: bool = False) -> SimpleNamespace:
    return SimpleNamespace(is_anonymous=anonymous, user_id=str(uuid.uuid4()))


ISIN = "INF174K01KH7"


# 1 — migration wiring ---------------------------------------------------------


def test_migration_chain_and_rls_lists() -> None:
    import importlib.util
    import pathlib

    migration_path = (
        pathlib.Path(__file__).parent.parent.parent / "alembic" / "versions" / "0079_mf_watchlist.py"
    )
    spec = importlib.util.spec_from_file_location("_mig_0079", migration_path)
    assert spec is not None, f"could not locate migration at {migration_path}"
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)  # type: ignore[union-attr]
    assert mig.revision == "0079"
    assert mig.down_revision == "0078"
    assert callable(mig.upgrade)
    assert callable(mig.downgrade)

    from dhanradar.db_security import PERSONAL_TABLES, RLS_ENFORCED

    assert "mf.mf_watchlist_items" in PERSONAL_TABLES
    assert "mf.mf_watchlist_items" in RLS_ENFORCED


# 2 — anonymous 401 -----------------------------------------------------------


async def test_all_routes_401_for_anonymous() -> None:
    db = _FakeDB()
    anon = _user(anonymous=True)
    for coro in (
        get_watchlist(db=db, user=anon),
        add_watchlist_item(ISIN, db=db, user=anon),
        remove_watchlist_item(ISIN, db=db, user=anon),
    ):
        with pytest.raises(HTTPException) as exc:
            await coro
        assert exc.value.status_code == 401
    assert db.committed == 0


# 3 — isin shape gate ---------------------------------------------------------


def test_valid_isin_normalizes_and_rejects() -> None:
    assert _valid_isin(" inf174k01kh7 ") == ISIN
    for bad in ("", "SHORT", "X" * 13, "INF174K01KH!", "INF174K01KH 7"):
        with pytest.raises(HTTPException) as exc:
            _valid_isin(bad)
        assert exc.value.status_code == 422


# 4 — cap ----------------------------------------------------------------------


async def test_add_watchlist_full_422() -> None:
    db = _FakeDB(scalar_value=_WATCHLIST_MAX_ITEMS)
    with pytest.raises(HTTPException) as exc:
        await add_watchlist_item(ISIN, db=db, user=_user())
    assert exc.value.status_code == 422
    assert exc.value.detail == "watchlist_full"
    assert db.committed == 0


async def test_add_under_cap_commits() -> None:
    db = _FakeDB(scalar_value=3)
    await add_watchlist_item(ISIN, db=db, user=_user())
    assert db.committed == 1


# 5 — list mapping --------------------------------------------------------------


async def test_get_watchlist_maps_rows() -> None:
    now = datetime.now(UTC)
    rows = [
        SimpleNamespace(isin="INF0000000A1", created_at=now),
        SimpleNamespace(isin="INF0000000B2", created_at=now),
    ]
    db = _FakeDB(scalars_all=rows)
    resp = await get_watchlist(db=db, user=_user())
    assert [i.isin for i in resp.items] == ["INF0000000A1", "INF0000000B2"]
    assert resp.items[0].created_at == now.isoformat()


# 6 — remove is idempotent ------------------------------------------------------


async def test_remove_absent_row_is_204_noop() -> None:
    db = _FakeDB(scalar_value=None)
    await remove_watchlist_item(ISIN, db=db, user=_user())  # no raise
    assert db.deleted == []
    assert db.committed == 0


async def test_remove_present_row_deletes() -> None:
    row = SimpleNamespace(isin=ISIN)
    db = _FakeDB(scalar_value=row)
    await remove_watchlist_item(ISIN, db=db, user=_user())
    assert db.deleted == [row]
    assert db.committed == 1


# 7 — no numeric leakage --------------------------------------------------------


def test_watchlist_response_no_numeric_fields() -> None:
    from dhanradar.mf.schemas import WatchlistItemOut, WatchlistResponse

    fields = set(WatchlistItemOut.model_fields) | set(WatchlistResponse.model_fields)
    assert not fields & {"score", "unified_score", "fair_value", "weight"}
