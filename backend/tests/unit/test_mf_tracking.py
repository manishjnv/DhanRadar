"""
Unit tests — MF Plus tracking (score history + portfolio snapshot + monthly beat).

Coverage:
  1. append_score_history writes label+band+model_version+isin, never unified_score.
  2. get_snapshot_history returns label+band only, never unified_score/total_invested/xirr_pct.
  3. Monthly beat skips Free users, writes history only for Plus users.
  4. GET /mf/history: anonymous→401, Free→402, Plus→200 with disclosure, no numeric.

asyncio_mode = "auto" (pyproject.toml) — no decorator needed.
No real DB: all external call sites are monkeypatched with async fakes.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeDB:
    """Captures execute/commit calls; execute returns self (so .scalars()/.all() chain)."""

    def __init__(self, rows: list | None = None) -> None:
        self.executed: list[Any] = []
        self.committed = 0
        self._rows = rows or []
        # append_score_history returns result_proxy.rowcount == 1; expose 1 so
        # the existing tests that ignore the return value continue to pass, and
        # the new bool-return contract resolves to True (inserted).
        self.rowcount = 1

    async def execute(self, stmt: Any) -> _FakeDB:
        self.executed.append(stmt)
        return self

    async def commit(self) -> None:
        self.committed += 1

    def scalars(self) -> _FakeDB:
        return self

    def all(self) -> list:
        return self._rows


def _make_result(
    isin: str = "INF000TEST01",
    verb_label: str = "on_track",
    confidence_band: str = "medium",
    model_version: str = "v1",
    unified_score: int = 72,
) -> MagicMock:
    """Build a fake ScoringResult with the fields append_score_history reads."""
    r = MagicMock()
    r.identifier = isin
    r.verb_label = MagicMock()
    r.verb_label.value = verb_label
    r.confidence_band = MagicMock()
    r.confidence_band.value = confidence_band
    r.model_version = model_version
    r.unified_score = unified_score  # present on object but must NOT be written
    return r


def _make_snap(
    total_invested: float = 10000.0,
    current_value: float = 11000.0,
    xirr_pct: float = 12.5,
) -> MagicMock:
    s = MagicMock()
    s.total_invested = total_invested
    s.current_value = current_value
    s.xirr_pct = xirr_pct
    s.category_allocation = {"large_cap": 100.0}
    s.overlap_matrix = {}
    return s


# ---------------------------------------------------------------------------
# 1. append_score_history — captures correct fields, NEVER unified_score
# ---------------------------------------------------------------------------


async def test_append_score_history_writes_label_fields(monkeypatch):
    """append_score_history passes verb_label/confidence_band/model_version/isin
    to the INSERT but never unified_score."""
    from dhanradar.mf import history as mf_history

    captured_values: dict = {}

    class _FakeInsert:
        def values(self, **kw) -> _FakeInsert:
            captured_values.update(kw)
            return self

        def on_conflict_do_nothing(self, **kw) -> _FakeInsert:
            return self

    def _fake_insert(model):
        return _FakeInsert()

    db = _FakeDB()
    result = _make_result(
        isin="INF000TEST01",
        verb_label="on_track",
        confidence_band="medium",
        model_version="v1",
        unified_score=99,
    )

    # insert is a module-level import in history.py; MfUserFundScoreHistory is
    # imported locally inside the function — patch it at its source module.
    fake_model = MagicMock()
    with patch("dhanradar.mf.history.insert", _fake_insert):
        with patch("dhanradar.models.mf.MfUserFundScoreHistory", fake_model):
            await mf_history.append_score_history(
                db,
                user_id="user-a",
                result=result,
                snapshot_date=date(2026, 6, 1),
                source="cas_upload",
                portfolio_id="portfolio-a",
            )

    # verify only public fields were written
    assert captured_values["verb_label"] == "on_track"
    assert captured_values["confidence_band"] == "medium"
    assert captured_values["model_version"] == "v1"
    assert captured_values["isin"] == "INF000TEST01"
    assert captured_values["source"] == "cas_upload"
    assert "unified_score" not in captured_values


async def test_append_score_history_commits(monkeypatch):
    """append_score_history always commits after the insert."""
    from dhanradar.mf import history as mf_history

    db = _FakeDB()
    result = _make_result()

    class _FakeInsert:
        def values(self, **kw) -> _FakeInsert:
            return self

        def on_conflict_do_nothing(self, **kw) -> _FakeInsert:
            return self

    with patch("dhanradar.mf.history.insert", lambda _: _FakeInsert()):
        with patch("dhanradar.models.mf.MfUserFundScoreHistory", MagicMock()):
            await mf_history.append_score_history(
                db,
                user_id="user-a",
                result=result,
                snapshot_date=date(2026, 6, 1),
                source="monthly_rescore",
                portfolio_id="portfolio-a",
            )

    assert db.committed >= 1


# ---------------------------------------------------------------------------
# 2. get_snapshot_history — label+band only; no unified_score/numerics
# ---------------------------------------------------------------------------


async def test_get_snapshot_history_shape_no_numerics():
    """get_snapshot_history returns only isin/verb_label/confidence_band per fund
    — never unified_score, total_invested, or xirr_pct."""
    from dhanradar.mf import history as mf_history

    # Rows returned by the db query: (snapshot_date, isin, verb_label, confidence_band)
    snap_date = date(2026, 6, 1)
    fake_rows = [
        (snap_date, "INF000A01", "on_track", "medium"),
        (snap_date, "INF000B01", "in_form", "high"),
    ]

    class _FakeResult:
        def all(self):
            return fake_rows

    class _FakeDB2:
        async def execute(self, stmt):
            return _FakeResult()

    result = await mf_history.get_snapshot_history(_FakeDB2(), "user-123", "portfolio-abc")

    assert len(result) == 1
    item = result[0]
    assert item["snapshot_date"] == "2026-06-01"
    assert len(item["funds"]) == 2

    for fund in item["funds"]:
        assert "isin" in fund
        assert "verb_label" in fund
        assert "confidence_band" in fund
        # Must never contain numeric fields
        assert "unified_score" not in fund
        assert "total_invested" not in fund
        assert "xirr_pct" not in fund


async def test_get_snapshot_history_groups_multiple_dates():
    """Multiple snapshot dates are returned in descending order, each grouping its funds."""
    from dhanradar.mf import history as mf_history

    d1 = date(2026, 6, 1)
    d2 = date(2026, 5, 1)
    fake_rows = [
        (d1, "INF000A01", "on_track", "medium"),
        (d2, "INF000A01", "off_track", "low"),
    ]

    class _FakeResult:
        def all(self):
            return fake_rows

    class _FakeDB2:
        async def execute(self, stmt):
            return _FakeResult()

    result = await mf_history.get_snapshot_history(_FakeDB2(), "user-123", "portfolio-abc")
    assert len(result) == 2
    # First item is the most recent date (d1)
    assert result[0]["snapshot_date"] == "2026-06-01"
    assert result[1]["snapshot_date"] == "2026-05-01"


# ---------------------------------------------------------------------------
# 3. Monthly beat — Plus gate controls who gets history
# ---------------------------------------------------------------------------


async def test_monthly_rescore_skips_free_users(monkeypatch):
    """_monthly_rescore calls append_score_history for Plus users only; Free users
    are skipped before any score or history write.

    Uses a thin wrapper around _monthly_rescore that replaces the heavy DB/engine
    dependencies via patches on the actual imported modules (_load_nav_series is a
    module-level function, score_fund/upsert are module-level imports).
    """
    import dhanradar.mf.history as _mf_history_mod
    import dhanradar.tasks.mf as mf_tasks

    user_a = str(uuid.uuid4())  # Plus
    user_b = str(uuid.uuid4())  # Free

    append_calls: list[dict] = []
    persist_calls: list[dict] = []

    async def _fake_is_plus(uid: str, db: Any) -> bool:
        return uid == user_a

    async def _fake_append(db_arg=None, **kw) -> bool:
        append_calls.append(kw)
        return True

    async def _fake_persist(db_arg=None, **kw) -> None:
        persist_calls.append(kw)

    async def _fake_prior(db_arg=None, *a, **kw) -> None:
        return None

    async def _fake_score_fund(engine, signals):
        return _make_result(isin=signals.isin)

    async def _fake_load_nav(db, isins, lookback_days=400):
        return ({i: [(date(2026, 6, 1), 100.0)] for i in isins}, {i: 100.0 for i in isins})

    def _fake_compute_signals(isin, series, **kw):
        m = MagicMock()
        m.isin = isin
        return m

    def _make_holding(uid, isin):
        h = MagicMock()
        h.user_id = uid
        h.isin = isin
        h.units = 10.0
        h.invested_amount = 1000.0
        return h

    user_a_holding = _make_holding(user_a, "INF000A01")
    user_b_holding = _make_holding(user_b, "INF000B01")

    # Per-user sessions: answer two queries — first is holdings select, rest ignored.
    class _FakeScalars:
        def __init__(self, items):
            self._items = items

        def all(self):
            return self._items

    class _FakeHoldingResult:
        def __init__(self, holding):
            self._holding = holding

        def scalars(self):
            return _FakeScalars([self._holding])

    class _FakeHoldingSession:
        def __init__(self, uid):
            self._uid = uid
            self._n = 0

        async def execute(self, stmt):
            self._n += 1
            holding = user_a_holding if self._uid == user_a else user_b_holding
            if self._n == 1:
                # portfolio owner/name resolve
                r = MagicMock()
                r.first = lambda: (self._uid, "Portfolio")
                return r
            if self._n == 2:
                # holdings select
                return _FakeHoldingResult(holding)
            # scheme-name batch fetch (and any later reads)
            r = MagicMock()
            r.all = lambda: [(holding.isin, "Test Fund")]
            return r

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

    class _FakeUserSession:
        def __init__(self):
            self._n = 0

        async def execute(self, stmt):
            self._n += 1
            r = MagicMock()
            if self._n == 1:
                # distinct (portfolio_id, isin) pre-pass rows (B58-f2) — the
                # harness conflates pid with uid (one portfolio per user).
                r.all = lambda: [(user_a, "INF000A01"), (user_b, "INF000B01")]
            else:
                # portfolio → owner resolve
                r.all = lambda: [(user_a, user_a), (user_b, user_b)]
            return r

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

    session_call_count = {"n": 0}
    user_order = [user_a, user_b]

    class _FakeSessionMaker:
        def __call__(self):
            n = session_call_count["n"]
            session_call_count["n"] += 1
            if n == 0:
                return _FakeUserSession()
            uid = user_order[(n - 1) % len(user_order)]
            return _FakeHoldingSession(uid)

    # Module-level imports in tasks/mf — patchable directly on the module object.
    monkeypatch.setattr(mf_tasks, "score_fund", _fake_score_fund, raising=True)
    monkeypatch.setattr(mf_tasks, "_load_nav_series", _fake_load_nav, raising=True)
    monkeypatch.setattr(mf_tasks, "compute_fund_signals", _fake_compute_signals, raising=True)
    monkeypatch.setattr(mf_tasks, "build_snapshot", lambda holdings: _make_snap(), raising=True)
    monkeypatch.setattr(mf_tasks, "upsert_user_fund_score", AsyncMock(), raising=True)
    # Cohort context build is hoisted out of the per-portfolio loop (B58-f2):
    # it must run exactly ONCE per rescore, over Plus users' isins only.
    fake_build = AsyncMock(return_value=mf_tasks._EMPTY_COHORT_CONTEXT)
    monkeypatch.setattr(mf_tasks, "_build_cohort_context", fake_build, raising=True)
    # history helpers are imported locally inside _monthly_rescore — patch at source.
    monkeypatch.setattr(_mf_history_mod, "append_score_history", _fake_append)
    monkeypatch.setattr(_mf_history_mod, "persist_portfolio_snapshot", _fake_persist)
    monkeypatch.setattr(_mf_history_mod, "get_prior_label", _fake_prior)
    # is_plus is imported locally too — patch at source (dhanradar.deps).
    monkeypatch.setattr("dhanradar.deps.is_plus", _fake_is_plus)

    # Patch the sessionmaker ATTRIBUTE _monthly_rescore imports at call time —
    # patching sqlalchemy.ext.asyncio.async_sessionmaker was a no-op (the real
    # TaskSessionLocal is created at dhanradar.db import time), which left this
    # test running against a real DB connection and asserting vacuously.
    with patch("dhanradar.db.admin_task_session", _FakeSessionMaker()):
        with patch("dhanradar.scoring.engine.RatingEngine", MagicMock()):
            with patch("dhanradar.redis_client.get_redis", lambda: MagicMock()):
                summary = await mf_tasks._monthly_rescore()

    # Append must have been called for user_a (Plus) ONLY — never user_b (Free).
    assert append_calls, "the Plus user's holding must reach append_score_history"
    for call in append_calls:
        assert call.get("user_id") == user_a, f"Expected only user_a but got {call}"

    assert "rescored 1" in summary

    # B58-f2 acceptance: ONE context build per run, over the Plus user's isins
    # only (user_b is Free — their holding never reaches the cohort build).
    assert fake_build.await_count == 1
    built_isins = fake_build.await_args.args[1]
    assert built_isins == ["INF000A01"]


# ---------------------------------------------------------------------------
# 4. GET /mf/history endpoint gating
# ---------------------------------------------------------------------------


def _make_user(*, is_anonymous: bool = False, user_id: str = "user-plus") -> MagicMock:
    u = MagicMock()
    u.is_anonymous = is_anonymous
    u.user_id = user_id
    return u


async def test_portfolio_history_anonymous_returns_401():
    """Anonymous user → 401 before any Plus check."""
    from fastapi import HTTPException

    from dhanradar.mf.router import portfolio_history

    anon = _make_user(is_anonymous=True)
    db = _FakeDB()

    with pytest.raises(HTTPException) as exc_info:
        await portfolio_history(db=db, user=anon)

    assert exc_info.value.status_code == 401


async def test_portfolio_history_free_user_returns_402(monkeypatch):
    """Free (non-Plus) user → 402 with upgrade_required detail."""
    from fastapi import HTTPException

    from dhanradar.mf.router import portfolio_history

    async def _not_plus(uid, db):
        return False

    monkeypatch.setattr("dhanradar.mf.router.is_plus", _not_plus, raising=False)

    free_user = _make_user(is_anonymous=False, user_id="user-free")
    db = _FakeDB()

    with pytest.raises(HTTPException) as exc_info:
        await portfolio_history(db=db, user=free_user)

    assert exc_info.value.status_code == 402
    assert exc_info.value.detail["error"] == "upgrade_required"
    assert exc_info.value.detail["upgrade_url"] == "/pricing"


async def test_portfolio_history_plus_user_returns_response(monkeypatch):
    """Plus user with consent → 200 with disclosure fields, no numeric fields."""
    import uuid as _uuid

    from dhanradar.mf.router import portfolio_history

    async def _is_plus(uid, db):
        return True

    async def _no_consent_error(*, user, db):
        pass  # consent granted

    async def _fake_history(db, user_id, portfolio_id):
        return [
            {
                "snapshot_date": "2026-06-01",
                "funds": [
                    {"isin": "INF000A01", "verb_label": "on_track", "confidence_band": "medium"}
                ],
            }
        ]

    fake_pid = str(_uuid.uuid4())

    async def _fake_own_portfolio(db, portfolio_id, user_id):
        m = MagicMock()
        m.id = _uuid.UUID(portfolio_id)
        return m

    monkeypatch.setattr("dhanradar.mf.router.is_plus", _is_plus, raising=False)
    monkeypatch.setattr("dhanradar.mf.router._require_mf_consent", _no_consent_error, raising=False)
    monkeypatch.setattr("dhanradar.mf.router.mf_history.get_snapshot_history", _fake_history, raising=False)
    monkeypatch.setattr("dhanradar.mf.router._own_portfolio", _fake_own_portfolio, raising=False)

    plus_user = _make_user(is_anonymous=False, user_id="user-plus")
    db = _FakeDB()

    response = await portfolio_history(db=db, user=plus_user, portfolio_id=fake_pid)

    assert response.disclosure is not None and len(response.disclosure) > 0
    assert response.not_advice == "NOT_ADVICE"
    assert response.disclaimer_version is not None
    assert len(response.snapshots) == 1
    assert response.snapshots[0].snapshot_date == "2026-06-01"
    assert len(response.snapshots[0].funds) == 1

    # Serialize to dict and verify no numeric leak
    response_dict = response.model_dump()
    assert "unified_score" not in str(response_dict)
    assert "xirr_pct" not in str(response_dict)
    assert "total_invested" not in str(response_dict)


async def test_portfolio_history_response_has_disclosure_bundle(monkeypatch):
    """PortfolioHistoryResponse always carries disclosure + not_advice + disclaimer_version."""
    import uuid as _uuid

    from dhanradar.mf.router import portfolio_history

    async def _is_plus(uid, db):
        return True

    async def _no_consent(*, user, db):
        pass

    async def _empty_history(db, user_id, portfolio_id):
        return []

    fake_pid = str(_uuid.uuid4())

    async def _fake_own_portfolio(db, portfolio_id, user_id):
        m = MagicMock()
        m.id = _uuid.UUID(portfolio_id)
        return m

    monkeypatch.setattr("dhanradar.mf.router.is_plus", _is_plus, raising=False)
    monkeypatch.setattr("dhanradar.mf.router._require_mf_consent", _no_consent, raising=False)
    monkeypatch.setattr("dhanradar.mf.router.mf_history.get_snapshot_history", _empty_history, raising=False)
    monkeypatch.setattr("dhanradar.mf.router._own_portfolio", _fake_own_portfolio, raising=False)

    response = await portfolio_history(
        db=_FakeDB(), user=_make_user(is_anonymous=False), portfolio_id=fake_pid
    )
    d = response.model_dump()

    assert d["disclosure"] != ""
    assert d["not_advice"] == "NOT_ADVICE"
    assert d["disclaimer_version"] is not None
    # No numeric leak at all
    assert "unified_score" not in d
    assert "xirr_pct" not in d
    assert "total_invested" not in d
