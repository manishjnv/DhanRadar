"""GET /mf/portfolio/holdings-isins (V4) — contract tests, direct-call pattern
(same fake-db approach as test_leaderboard's endpoint tests). The endpoint's
whole promise: auth'd + consent-gated, ISINs ONLY (no names/amounts/folios),
empty list — not 404 — when no portfolio exists."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import dhanradar.mf.router as mf_router
from dhanradar.mf.router import portfolio_holdings_isins


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return iter(self._value)


class _FakeDB:
    """Returns queued results in execute() call order."""

    def __init__(self, results):
        self._results = list(results)

    async def execute(self, _stmt):
        return _FakeResult(self._results.pop(0))


_ANON = SimpleNamespace(is_anonymous=True, user_id=None, tier="free")
_USER = SimpleNamespace(is_anonymous=False, user_id="00000000-0000-0000-0000-000000000001", tier="free")


@pytest.fixture(autouse=True)
def _no_consent_gate(monkeypatch):
    async def _ok(*, user, db):
        return None

    monkeypatch.setattr(mf_router, "_require_mf_consent", _ok)


async def test_anonymous_is_401() -> None:
    with pytest.raises(HTTPException) as exc:
        await portfolio_holdings_isins(db=_FakeDB([]), user=_ANON)
    assert exc.value.status_code == 401


async def test_no_portfolio_returns_empty_list_not_404() -> None:
    resp = await portfolio_holdings_isins(db=_FakeDB([None]), user=_USER)
    assert resp.isins == []


async def test_returns_sorted_isins_and_nothing_else() -> None:
    resp = await portfolio_holdings_isins(
        db=_FakeDB(["pid-1", ["INF200K01VT2", "INF090I01GN5"]]), user=_USER
    )
    assert resp.isins == ["INF090I01GN5", "INF200K01VT2"]
    # ISIN list is the WHOLE payload — no names, values or folio data (non-neg #2).
    assert set(resp.model_dump()) == {"isins"}
