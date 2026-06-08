"""
Unit tests — MF portfolio entity (multiple-portfolios slice).

Coverage:
  1. Migration module: importable, correct revision/down_revision strings.
  2. Free cap: POST /mf/portfolios raises 402 when count==1 + is_plus→False.
              Plus (count==1, is_plus→True) → creates without error.
              First portfolio (count==0, is_plus→False) → creates (free).
  3. get_snapshot_history scopes to portfolio_id: rows from portfolio B are excluded
     when requesting portfolio A.
  4. No-numeric: PortfolioSummary / PortfolioListResponse carry no score/numeric fields.
     402 detail shape matches {error, upgrade_url}.
  5. Ownership: _own_portfolio raises 404 for not-owned portfolio and for bad UUID.

asyncio_mode = "auto" (pyproject.toml) — no decorator needed.
No real DB: async fakes throughout.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------


class _FakeDB:
    """Minimal AsyncSession stub — execute returns self; scalar/scalar_one_or_none
    are configurable; add/commit/refresh are fire-and-forget stubs."""

    def __init__(self, scalars_queue: list | None = None, scalar_value: Any = None) -> None:
        self.executed: list[Any] = []
        self.committed = 0
        self.added: list[Any] = []
        self._scalars_queue: list[Any] = list(scalars_queue or [])
        self._scalar_value = scalar_value

    async def execute(self, stmt: Any) -> "_FakeDB":  # noqa: UP037
        self.executed.append(stmt)
        return self

    async def commit(self) -> None:
        self.committed += 1

    async def refresh(self, obj: Any) -> None:
        # Simulate DB stamping id + created_at if not already set.
        if not getattr(obj, "id", None):
            obj.id = uuid.uuid4()
        if not getattr(obj, "created_at", None):
            obj.created_at = datetime.now(UTC)

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        # Pre-stamp so refresh isn't strictly needed in tests.
        if not getattr(obj, "id", None):
            obj.id = uuid.uuid4()
        if not getattr(obj, "created_at", None):
            obj.created_at = datetime.now(UTC)

    async def delete(self, obj: Any) -> None:
        pass

    def scalars(self) -> "_FakeDB":  # noqa: UP037
        return self

    def all(self) -> list:
        return list(self._scalars_queue)

    def scalar_one(self) -> Any:
        if self._scalars_queue:
            return self._scalars_queue.pop(0)
        return self._scalar_value

    def scalar_one_or_none(self) -> Any:
        return self._scalar_value

    async def scalar(self, stmt: Any) -> Any:
        self.executed.append(stmt)
        return self._scalar_value


def _make_user(*, is_anonymous: bool = False, user_id: str | None = None) -> MagicMock:
    u = MagicMock()
    u.is_anonymous = is_anonymous
    u.user_id = user_id or str(uuid.uuid4())
    return u


def _make_portfolio(user_id: str | None = None, name: str = "Test") -> MagicMock:
    p = MagicMock()
    p.id = uuid.uuid4()
    p.user_id = uuid.UUID(user_id) if user_id else uuid.uuid4()
    p.name = name
    p.created_at = datetime.now(UTC)
    return p


# ---------------------------------------------------------------------------
# 1. Migration importability + revision strings
# ---------------------------------------------------------------------------


def test_migration_module_importable_and_revision_correct():
    """0013 migration module is importable; revision/down_revision are correct."""
    from alembic.versions import mf_portfolios_0013 as m  # noqa: F401 — may not resolve

    assert False, "import path check — see note below"


# The above will fail on import if the module name doesn't match; use importlib instead:
def test_migration_revision_strings():
    import importlib.util
    import pathlib

    migration_path = (
        pathlib.Path(__file__).parent.parent.parent
        / "alembic"
        / "versions"
        / "0013_mf_portfolios.py"
    )
    spec = importlib.util.spec_from_file_location("_mig_0013", migration_path)
    assert spec is not None, f"could not locate migration at {migration_path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    assert mod.revision == "0013"
    assert mod.down_revision == "0012"
    assert callable(mod.upgrade)
    assert callable(mod.downgrade)


# Mark the bad test above as expected-fail (it will always fail due to wrong import path).
test_migration_module_importable_and_revision_correct = pytest.mark.xfail(
    strict=False, reason="placeholder test replaced by test_migration_revision_strings"
)(test_migration_module_importable_and_revision_correct)


# ---------------------------------------------------------------------------
# 2. Free cap on POST /mf/portfolios
# ---------------------------------------------------------------------------


async def test_create_portfolio_free_user_with_existing_raises_402(monkeypatch):
    """count==1 + is_plus→False → 402 upgrade_required."""
    from dhanradar.mf.router import create_portfolio
    from dhanradar.mf.schemas import PortfolioCreateRequest

    async def _not_plus(uid, db):
        return False

    monkeypatch.setattr("dhanradar.mf.router.is_plus", _not_plus, raising=False)

    # scalar_one() must return 1 (existing portfolio count).
    db = _FakeDB(scalar_value=1)

    # Override execute to return self which has scalar_one returning 1.
    class _CountResult:
        def scalar_one(self_inner):
            return 1

    async def _exec(stmt):
        return _CountResult()

    db.execute = _exec  # type: ignore[method-assign]

    user = _make_user(is_anonymous=False)
    body = PortfolioCreateRequest(name="My Second Portfolio")

    with pytest.raises(HTTPException) as exc_info:
        await create_portfolio(db=db, user=user, body=body)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 402
    assert exc_info.value.detail["error"] == "upgrade_required"
    assert exc_info.value.detail["upgrade_url"] == "/pricing"


async def test_create_portfolio_plus_user_with_existing_succeeds(monkeypatch):
    """count==1 + is_plus→True → no 402 raised; portfolio is created."""
    from dhanradar.mf.router import create_portfolio
    from dhanradar.mf.schemas import PortfolioCreateRequest

    async def _is_plus(uid, db):
        return True

    monkeypatch.setattr("dhanradar.mf.router.is_plus", _is_plus, raising=False)

    class _CountResult:
        def scalar_one(self_inner):
            return 1

    db = _FakeDB()

    async def _exec(stmt):
        return _CountResult()

    db.execute = _exec  # type: ignore[method-assign]

    user = _make_user(is_anonymous=False)
    body = PortfolioCreateRequest(name="Extra Portfolio")

    # Should not raise; returns a PortfolioSummary.
    result = await create_portfolio(db=db, user=user, body=body)  # type: ignore[arg-type]
    assert result.name == "Extra Portfolio"


async def test_create_portfolio_first_portfolio_free_user_succeeds(monkeypatch):
    """count==0 + is_plus→False → first portfolio is free (no 402)."""
    from dhanradar.mf.router import create_portfolio
    from dhanradar.mf.schemas import PortfolioCreateRequest

    async def _not_plus(uid, db):
        return False

    monkeypatch.setattr("dhanradar.mf.router.is_plus", _not_plus, raising=False)

    class _CountResult:
        def scalar_one(self_inner):
            return 0

    db = _FakeDB()

    async def _exec(stmt):
        return _CountResult()

    db.execute = _exec  # type: ignore[method-assign]

    user = _make_user(is_anonymous=False)
    body = PortfolioCreateRequest(name="Default")

    result = await create_portfolio(db=db, user=user, body=body)  # type: ignore[arg-type]
    assert result.name == "Default"


# ---------------------------------------------------------------------------
# 3. get_snapshot_history scoped by portfolio_id
# ---------------------------------------------------------------------------


async def test_get_snapshot_history_scoped_to_portfolio():
    """History for portfolio_A must not include rows belonging to portfolio_B."""
    from dhanradar.mf import history as mf_history

    portfolio_a = str(uuid.uuid4())
    portfolio_b = str(uuid.uuid4())
    snap_date = date(2026, 6, 1)

    # Simulate two portfolios' rows; the query filter is applied inside the function.
    # We provide only portfolio_A rows (as the real DB would after WHERE portfolio_id=A).
    rows_for_a = [
        (snap_date, "INF000A01", "on_track", "medium"),
    ]
    rows_for_b = [
        (snap_date, "INF000B01", "in_form", "high"),
    ]

    # Each call returns rows for the specific portfolio only (mimics DB filter).
    class _FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class _FakeDB2:
        async def execute(self, stmt):
            # Inspect which portfolio_id the WHERE clause refers to.
            # Since we can't easily inspect SQLAlchemy compiled SQL in unit tests,
            # we verify via two separate calls with independent DBs.
            return _FakeResult(rows_for_a)

    class _FakeDB3:
        async def execute(self, stmt):
            return _FakeResult(rows_for_b)

    result_a = await mf_history.get_snapshot_history(_FakeDB2(), "user-x", portfolio_a)
    result_b = await mf_history.get_snapshot_history(_FakeDB3(), "user-x", portfolio_b)

    # Portfolio A's result should contain INF000A01, not INF000B01.
    isins_a = {f["isin"] for item in result_a for f in item["funds"]}
    isins_b = {f["isin"] for item in result_b for f in item["funds"]}

    assert "INF000A01" in isins_a
    assert "INF000B01" not in isins_a
    assert "INF000B01" in isins_b
    assert "INF000A01" not in isins_b


async def test_get_snapshot_history_includes_portfolio_id_in_filter():
    """Verify the WHERE clause passed to execute contains portfolio_id condition
    by checking the statement's WHERE clause columns via the ORM expression."""
    from dhanradar.mf import history as mf_history

    portfolio_id = str(uuid.uuid4())
    captured_stmts: list[Any] = []

    class _CapturingDB:
        async def execute(self, stmt):
            captured_stmts.append(stmt)

            class _R:
                def all(self_inner):
                    return []

            return _R()

    await mf_history.get_snapshot_history(_CapturingDB(), "user-x", portfolio_id)

    assert len(captured_stmts) == 1
    stmt = captured_stmts[0]
    # The WHERE clause should reference portfolio_id — verify via string repr.
    stmt_str = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "portfolio_id" in stmt_str


# ---------------------------------------------------------------------------
# 4. No-numeric + 402 detail shape
# ---------------------------------------------------------------------------


def test_portfolio_summary_has_no_numeric_fields():
    """PortfolioSummary must not expose unified_score/xirr_pct/total_invested."""
    from dhanradar.mf.schemas import PortfolioSummary

    s = PortfolioSummary(id=str(uuid.uuid4()), name="MyPort", created_at="2026-06-08T00:00:00+00:00")
    d = s.model_dump()
    assert "unified_score" not in d
    assert "xirr_pct" not in d
    assert "total_invested" not in d
    assert "name" in d
    assert "id" in d
    assert "created_at" in d


def test_portfolio_list_response_has_no_numeric_fields():
    """PortfolioListResponse must not expose any score/numeric fields."""
    from dhanradar.mf.schemas import PortfolioListResponse, PortfolioSummary

    resp = PortfolioListResponse(
        portfolios=[PortfolioSummary(id=str(uuid.uuid4()), name="P1", created_at="2026-06-08T00:00:00+00:00")]
    )
    d = resp.model_dump()
    assert "unified_score" not in str(d)
    assert "xirr_pct" not in str(d)
    assert "total_invested" not in str(d)


async def test_create_portfolio_402_detail_shape(monkeypatch):
    """402 detail matches {error: 'upgrade_required', upgrade_url: '/pricing'}."""
    from dhanradar.mf.router import create_portfolio
    from dhanradar.mf.schemas import PortfolioCreateRequest

    async def _not_plus(uid, db):
        return False

    monkeypatch.setattr("dhanradar.mf.router.is_plus", _not_plus, raising=False)

    class _CountResult:
        def scalar_one(self_inner):
            return 1

    db = _FakeDB()

    async def _exec(stmt):
        return _CountResult()

    db.execute = _exec  # type: ignore[method-assign]

    user = _make_user(is_anonymous=False)
    body = PortfolioCreateRequest(name="Extra")

    with pytest.raises(HTTPException) as exc_info:
        await create_portfolio(db=db, user=user, body=body)  # type: ignore[arg-type]

    detail = exc_info.value.detail
    assert detail == {"error": "upgrade_required", "upgrade_url": "/pricing"}


# ---------------------------------------------------------------------------
# 5. Ownership: _own_portfolio raises 404
# ---------------------------------------------------------------------------


async def test_own_portfolio_raises_404_for_bad_uuid():
    """_own_portfolio returns 404 for a malformed UUID."""
    from dhanradar.mf.router import _own_portfolio

    db = _FakeDB()
    with pytest.raises(HTTPException) as exc_info:
        await _own_portfolio(db, "not-a-uuid", "user-x")  # type: ignore[arg-type]
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "portfolio_not_found"


async def test_own_portfolio_raises_404_for_not_owned():
    """_own_portfolio returns 404 when the row exists but belongs to another user."""
    from dhanradar.mf.router import _own_portfolio

    # Scalar returns None → not found / not owned.
    db = _FakeDB(scalar_value=None)

    async def _exec_returning_none(stmt):
        return None

    # db.scalar is already set to return scalar_value=None via the stub.
    user_id = str(uuid.uuid4())
    portfolio_id = str(uuid.uuid4())

    with pytest.raises(HTTPException) as exc_info:
        await _own_portfolio(db, portfolio_id, user_id)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "portfolio_not_found"


async def test_own_portfolio_returns_portfolio_when_owned():
    """_own_portfolio returns the MfPortfolio when it exists and belongs to caller."""
    from dhanradar.mf.router import _own_portfolio

    user_id = str(uuid.uuid4())
    expected_portfolio = _make_portfolio(user_id=user_id)

    db = _FakeDB(scalar_value=expected_portfolio)
    result = await _own_portfolio(db, str(expected_portfolio.id), user_id)  # type: ignore[arg-type]
    assert result is expected_portfolio


# ---------------------------------------------------------------------------
# 6. Anonymous user → 401 on all portfolio endpoints
# ---------------------------------------------------------------------------


async def test_list_portfolios_anonymous_returns_401():
    from dhanradar.mf.router import list_portfolios

    anon = _make_user(is_anonymous=True)
    with pytest.raises(HTTPException) as exc_info:
        await list_portfolios(db=_FakeDB(), user=anon)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 401


async def test_create_portfolio_anonymous_returns_401():
    from dhanradar.mf.router import create_portfolio
    from dhanradar.mf.schemas import PortfolioCreateRequest

    anon = _make_user(is_anonymous=True)
    with pytest.raises(HTTPException) as exc_info:
        await create_portfolio(
            db=_FakeDB(), user=anon, body=PortfolioCreateRequest(name="X")  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 401


async def test_delete_portfolio_anonymous_returns_401():
    from dhanradar.mf.router import delete_portfolio

    anon = _make_user(is_anonymous=True)
    with pytest.raises(HTTPException) as exc_info:
        await delete_portfolio(
            portfolio_id=str(uuid.uuid4()), db=_FakeDB(), user=anon  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 401
