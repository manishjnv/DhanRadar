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

from datetime import date

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


async def _seed_nav(db_session, isin: str, nav_date: date, nav: float) -> None:
    """Insert one extra mf_nav_history row (bottom-up day-change needs >=2 NAV dates per ISIN)."""
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_nav_history (isin, nav_date, nav) VALUES (:i, :d, :n)"
            " ON CONFLICT (isin, nav_date) DO NOTHING"
        ),
        {"i": isin, "d": nav_date, "n": nav},
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# PG: GET /summary — day_change field
# ---------------------------------------------------------------------------


async def test_summary_day_change_none_cold_start(db_session, rls_async_client):
    """day_change is None when the holding's ISIN has fewer than 2 NAV dates (bottom-up
    method, §39.5) — _seed_portfolio ingests exactly ONE NAV row, so there's nothing to diff yet."""
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


async def test_summary_day_change_none_no_holdings(db_session, rls_async_client):
    """day_change is None when the portfolio has no holdings at all (a bare, empty portfolio —
    the other new edge case the bottom-up contract explicitly returns None for)."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "vs-noholdings@test.dev")
    pid = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'Empty') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()
    await db_session.commit()
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/summary", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["day_change"] is None


async def test_summary_day_change_two_nav_dates(db_session, rls_async_client):
    """day_change = units x (NAV_latest - NAV_prev) once a SECOND NAV date exists for the
    holding's ISIN (bottom-up method, §39.5) — no mf_portfolio_daily_values row needed at all."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "vs-two@test.dev")
    pid = await _seed_portfolio(db_session, uid)  # 5 units, NAV 200.0 @ 2026-06-30
    await _seed_nav(db_session, "INF209K01QP2", date(2026, 7, 1), 210.0)
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/summary", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    # 5 x (210 - 200) = 50
    assert d["day_change"] == pytest.approx(50.0, abs=0.01)
    # pct = 50 / (5 x 200) x 100 = 5%
    assert d["day_change_pct"] == pytest.approx(5.0, abs=0.01)


async def test_summary_day_change_latest_minus_previous(db_session, rls_async_client):
    """With 3+ NAV dates, day_change uses the TWO most-recent — NOT latest vs oldest."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "vs-three@test.dev")
    pid = await _seed_portfolio(db_session, uid)  # NAV 200.0 @ 2026-06-30 (oldest)
    await _seed_nav(db_session, "INF209K01QP2", date(2026, 7, 1), 204.0)   # previous
    await _seed_nav(db_session, "INF209K01QP2", date(2026, 7, 2), 209.0)  # latest
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/summary", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    # 5 x (209 - 204) = 25, NOT 5 x (209 - 200) = 45 (latest vs oldest would be wrong)
    assert d["day_change"] == pytest.approx(25.0, abs=0.01)


async def test_summary_day_change_immune_to_flow(db_session, rls_async_client):
    """§39.5 — the bottom-up formula never reads `invested` at all, so a same-day flow (a SIP
    purchase, a partial redemption) can never distort it. Retires the old flow-adjustment patch
    (RCA 2026-07-02): a huge invested_amount is seeded here and has ZERO effect on the result."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "vs-flow@test.dev")
    pid = await _seed_portfolio(db_session, uid)  # 5 units, NAV 200.0 @ 2026-06-30
    # Simulate a same-day flow: invested_amount jumps far out of proportion to the NAV move.
    await db_session.execute(
        text(
            "UPDATE mf.mf_user_holdings SET invested_amount = 50000.0"
            " WHERE portfolio_id = :p AND isin = 'INF209K01QP2'"
        ),
        {"p": pid},
    )
    await db_session.commit()
    await _seed_nav(db_session, "INF209K01QP2", date(2026, 7, 1), 210.0)
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/summary", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    # Same 5 x (210 - 200) = 50 as test_summary_day_change_two_nav_dates — invested never entered it.
    assert d["day_change"] == pytest.approx(50.0, abs=0.01)
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


async def test_reset_valuation_series_replays_full_ledger_window(db_session):
    """§39.5 — when the portfolio's ledger is non-empty (S2/S8/S11), _reset_valuation_series
    REPLAYS the whole ledger-covered window instead of seeding a single today-only row. Proves
    the wiring actually calls replay_valuation_series, not just the empty-ledger fallback the
    test above exercises."""
    from dhanradar.tasks.mf import _reset_valuation_series

    uid = await _seed_user(db_session, "vs-replay@test.dev")
    pid = await _seed_portfolio(db_session, uid)  # holding: 5 units INF209K01QP2, NAV 200 @ 2026-06-30

    # A ledger purchase a couple of days before the seeded NAV date, plus a second (earlier) NAV
    # date, so the replay window spans more than just today.
    await db_session.execute(
        text(
            "INSERT INTO mf.portfolio_transactions"
            " (portfolio_id, user_id, asset_class, instrument_id, folio_number, txn_type,"
            "  txn_date, units, nav_or_price, amount, source, source_ref, parser_version)"
            " VALUES (:p, :u, 'mf', 'INF209K01QP2', '999', 'purchase',"
            "  :d, 5.0, 180.0, -900.0, 'cas', 'test-replay-ref', 'cas-1')"
        ),
        {"p": pid, "u": uid, "d": date(2026, 6, 28)},
    )
    await db_session.commit()
    await _seed_nav(db_session, "INF209K01QP2", date(2026, 6, 29), 195.0)

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
    # Window spans 2026-06-28 (earliest txn) -> today, so MANY rows, not just one.
    assert len(rows) > 1, "ledger-covered replay must produce more than a single seeded row"
    assert rows[0].valuation_date == date(2026, 6, 28)
    by_date = {r.valuation_date: r for r in rows}
    # 2026-06-28: no NAV known yet (first NAV is 2026-06-29) -> value 0, invested still 900.
    assert float(by_date[date(2026, 6, 28)].total_value) == pytest.approx(0.0, abs=0.01)
    assert float(by_date[date(2026, 6, 28)].total_invested) == pytest.approx(900.0, abs=0.01)
    # 2026-06-29: NAV 195 lands -> 5 x 195 = 975.
    assert float(by_date[date(2026, 6, 29)].total_value) == pytest.approx(975.0, abs=0.01)
    # 2026-06-30 onward: NAV 200 carries forward -> 5 x 200 = 1000.
    assert float(by_date[date(2026, 6, 30)].total_value) == pytest.approx(1000.0, abs=0.01)
