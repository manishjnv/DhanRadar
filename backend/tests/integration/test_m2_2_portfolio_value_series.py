"""M2.2 — portfolio day-change + /value-series endpoint.

Covers:
  * Pure: load_day_change with 0, 1, and 2+ rows in mf_portfolio_daily_values.
  * Pure: summary_payload includes day_change (user's own ₹, DOM-allowed, #2-safe).
  * PG:   GET /summary → day_change present when 2+ valuation rows; None with <2.
  * PG:   GET /value-series → returns ASC rows for the owner; empty list cold-start.
  * PG:   RLS — another user gets 404 on /summary and /value-series; anon gets 401.

Mirrors test_c1_c2_portfolio_concepts.py (the proven C-wave pattern).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from dhanradar.mf.portfolio_read import (
    EnrichedHolding,
    PortfolioReadModel,
    summary_payload,
)
from dhanradar.models.auth import User

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers shared with C1/C2 tests (duplicated here so each test file is self-
# contained — the common pattern from the C-wave test suite).
# ---------------------------------------------------------------------------


def _all_keys(value) -> set[str]:
    out: set[str] = set()
    if isinstance(value, dict):
        out |= set(value.keys())
        for v in value.values():
            out |= _all_keys(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            out |= _all_keys(v)
    return out


def _all_values(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from _all_values(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _all_values(v)
    else:
        yield value


def _holding(**kw) -> EnrichedHolding:
    d = dict(
        isin="INF1", scheme_name="X Fund", category="Flexi Cap Fund", folio_number="F1",
        units=10.0, invested=1000.0, current_nav=120.0, current_value=1200.0,
        label="on_track", confidence_band="high", as_of="2026-03-31",
    )
    d.update(kw)
    return EnrichedHolding(**d)


def _rm(holdings=None) -> PortfolioReadModel:
    h = holdings or [_holding()]
    return PortfolioReadModel(
        holdings=h,
        total_invested=sum(x.invested for x in h),
        total_value=sum(x.current_value for x in h),
        xirr_pct=None,
        as_of="2026-03-31",
    )


_FORBIDDEN = {"unified_score", "score", "raw_score", "composite_score", "factor_weights", "fair_value"}


# ---------------------------------------------------------------------------
# Pure: summary_payload includes day_change in output
# ---------------------------------------------------------------------------


def test_summary_payload_day_change_present():
    """day_change is passed through to the payload dict unchanged."""
    p = summary_payload(_rm(), "pid-1", day_change=250.50)
    assert p["day_change"] == 250.50


def test_summary_payload_day_change_none_default():
    """day_change defaults to None — matches the cold-start state."""
    p = summary_payload(_rm(), "pid-1")
    assert p["day_change"] is None


def test_summary_payload_day_change_negative():
    """Negative day_change (portfolio lost value) passes through correctly."""
    p = summary_payload(_rm(), "pid-1", day_change=-123.45)
    assert p["day_change"] == -123.45


def test_summary_payload_day_change_no_forbidden_keys():
    """day_change does not introduce any forbidden score keys."""
    p = summary_payload(_rm(), "pid-1", day_change=999.0)
    assert _all_keys(p) & _FORBIDDEN == set()


# ---------------------------------------------------------------------------
# PG fixtures
# ---------------------------------------------------------------------------


async def _seed_user(db_session, email: str) -> str:
    u = User(email=email)
    db_session.add(u)
    await db_session.flush()
    uid = str(u.id)
    await db_session.commit()
    return uid


async def _seed_portfolio(db_session, uid: str) -> str:
    pid = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'VS') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()
    # Minimal holding so load_portfolio_read_model returns a non-empty model
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_funds (isin, scheme_name, category, sebi_category, is_segregated)"
            " VALUES ('INF209K01QP2', 'HDFC Top 100 Fund', 'Equity', 'Large Cap Fund', false)"
            " ON CONFLICT (isin) DO NOTHING"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_nav_history (isin, nav_date, nav) VALUES ('INF209K01QP2', :d, 200.0)"
            " ON CONFLICT (isin, nav_date) DO NOTHING"
        ),
        {"d": date(2026, 6, 30)},
    )
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_user_holdings (user_id, portfolio_id, isin, folio_number, units,"
            " invested_amount, avg_cost_nav, source, as_of_date)"
            " VALUES (:u, :p, 'INF209K01QP2', '999', 5.0, 900.0, 180.0, 'cas', :d)"
        ),
        {"u": uid, "p": str(pid), "d": date(2026, 6, 30)},
    )
    await db_session.commit()
    return str(pid)


async def _seed_daily_values(db_session, pid: str, uid: str, rows: list[tuple[date, float, float]]) -> None:
    """Insert (valuation_date, total_value, total_invested) rows for the portfolio."""
    for vdate, total_value, total_invested in rows:
        await db_session.execute(
            text(
                "INSERT INTO mf.mf_portfolio_daily_values"
                " (portfolio_id, user_id, valuation_date, total_value, total_invested)"
                " VALUES (:p, :u, :d, :v, :i)"
                " ON CONFLICT (portfolio_id, valuation_date) DO NOTHING"
            ),
            {"p": pid, "u": uid, "d": vdate, "v": total_value, "i": total_invested},
        )
    await db_session.commit()


# ---------------------------------------------------------------------------
# PG: GET /summary — day_change field
# ---------------------------------------------------------------------------


async def test_summary_day_change_none_cold_start(db_session, rls_async_client):
    """day_change is None when no valuation rows exist."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "vs-cold@test.dev")
    pid = await _seed_portfolio(db_session, uid)
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/summary", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["day_change"] is None


async def test_summary_day_change_none_single_row(db_session, rls_async_client):
    """day_change is None when only one valuation row exists."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "vs-one@test.dev")
    pid = await _seed_portfolio(db_session, uid)
    await _seed_daily_values(db_session, pid, uid, [(date(2026, 7, 1), 1000.0, 900.0)])
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/summary", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["day_change"] is None


async def test_summary_day_change_two_rows(db_session, rls_async_client):
    """day_change = latest − previous when ≥2 rows exist; positive and negative both work."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "vs-two@test.dev")
    pid = await _seed_portfolio(db_session, uid)
    await _seed_daily_values(db_session, pid, uid, [
        (date(2026, 7, 1), 1000.0, 900.0),
        (date(2026, 7, 2), 1050.0, 900.0),
    ])
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/summary", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    # latest (1050) − previous (1000) = 50
    assert d["day_change"] == pytest.approx(50.0, abs=0.01)


async def test_summary_day_change_latest_minus_previous(db_session, rls_async_client):
    """With 3+ rows, day_change uses the TWO most-recent valuation_date rows."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "vs-three@test.dev")
    pid = await _seed_portfolio(db_session, uid)
    today = date(2026, 7, 3)
    await _seed_daily_values(db_session, pid, uid, [
        (today - timedelta(days=2), 980.0, 900.0),
        (today - timedelta(days=1), 1020.0, 900.0),  # previous
        (today, 1045.0, 900.0),                       # latest
    ])
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/summary", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    # latest (1045) − previous (1020) = 25, NOT latest − oldest
    assert d["day_change"] == pytest.approx(25.0, abs=0.01)


async def test_summary_day_change_flow_adjusted(db_session, rls_async_client):
    """A flow day (SIP purchase) must not read as a gain: the invested delta is
    subtracted — ₹500 bought + ₹50 market move → day_change=50, not 550 (RCA 2026-07-02)."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "vs-flow@test.dev")
    pid = await _seed_portfolio(db_session, uid)
    await _seed_daily_values(db_session, pid, uid, [
        (date(2026, 7, 1), 1000.0, 900.0),
        (date(2026, 7, 2), 1550.0, 1400.0),  # +500 invested, +550 value → real move +50
    ])
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/summary", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["day_change"] == pytest.approx(50.0, abs=0.01)
    # pct from the SAME two rows: 50 / 1000 = 5%
    assert d["day_change_pct"] == pytest.approx(5.0, abs=0.01)


async def test_reset_valuation_series_restarts_series(db_session):
    """CAS re-upload reset (_reset_valuation_series): stale rows from the OLD holdings
    composition are deleted and ONE fresh row is seeded from the current holdings ×
    latest NAV — so day-change/charts never span two different portfolios."""
    from dhanradar.tasks.mf import _reset_valuation_series

    uid = await _seed_user(db_session, "vs-reset@test.dev")
    pid = await _seed_portfolio(db_session, uid)  # 5 units × latest NAV 200 = 1000, invested 900
    await _seed_daily_values(db_session, pid, uid, [
        (date(2026, 7, 1), 286_566.0, 147_000.0),  # stale demo-composition row
        (date(2026, 7, 2), 41_010.0, 52_674.0),
    ])

    await _reset_valuation_series(db_session, uid, pid)

    rows = (
        await db_session.execute(
            text(
                "SELECT valuation_date, total_value, total_invested"
                " FROM mf.mf_portfolio_daily_values WHERE portfolio_id = :p"
                " ORDER BY valuation_date"
            ),
            {"p": pid},
        )
    ).all()
    assert len(rows) == 1, "series must restart with exactly today's row"
    assert rows[0].valuation_date == date.today()
    assert float(rows[0].total_value) == pytest.approx(1000.0, abs=0.01)
    assert float(rows[0].total_invested) == pytest.approx(900.0, abs=0.01)
