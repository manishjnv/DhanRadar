"""M2.3 — windowed (e.g. "1Y") XIRR hero stat + per-holding XIRR (unblocked by the transaction ledger).

Covers:
  * Pure: summary_payload / holdings_payload carry the new xirr_1y_pct / xirr_1y_window_days / xirr_pct
    fields, #2-safe (no forbidden score key introduced).
  * PG:   load_windowed_xirr — cold start, too-short window, shrunk-window fallback, a real ledger flow
    inside the window, same-day flows summed, end_value <= 0.
  * PG:   load_holdings_xirr — a holding with ledger rows gets a non-null XIRR; one without gets None;
    correctly keyed by (isin, folio_number).
  * PG:   GET /summary and GET /holdings serve the new fields end-to-end through the A3 boundary.

Mirrors test_m2_2_portfolio_value_series.py (the proven M2.2 pattern). Each test seeds a UNIQUE ISIN —
mf_nav_history/mf_funds are shared across the test session.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from dhanradar.mf.portfolio_read import (
    EnrichedHolding,
    PortfolioReadModel,
    holdings_payload,
    load_holdings_xirr,
    load_windowed_xirr,
    summary_payload,
)
from dhanradar.mf.snapshot import CashFlow, windowed_xirr
from dhanradar.models.auth import User

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Pure-payload fixtures (duplicated from the C-wave pattern — self-contained file)
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


def _holding(**kw) -> EnrichedHolding:
    d = dict(
        isin="INF1",
        scheme_name="X Fund",
        category="Flexi Cap Fund",
        folio_number="F1",
        units=10.0,
        invested=1000.0,
        current_nav=120.0,
        current_value=1200.0,
        label="on_track",
        confidence_band="high",
        as_of="2026-03-31",
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


_FORBIDDEN = {
    "unified_score",
    "score",
    "raw_score",
    "composite_score",
    "factor_weights",
    "fair_value",
}


# ---------------------------------------------------------------------------
# Pure: summary_payload / holdings_payload carry the new fields
# ---------------------------------------------------------------------------


def test_summary_payload_xirr_1y_present():
    p = summary_payload(_rm(), "pid-1", xirr_1y=(14.2, 365))
    assert p["xirr_1y_pct"] == 14.2 and p["xirr_1y_window_days"] == 365


def test_summary_payload_xirr_1y_none_default():
    p = summary_payload(_rm(), "pid-1")
    assert p["xirr_1y_pct"] is None and p["xirr_1y_window_days"] is None
    assert _all_keys(p) & _FORBIDDEN == set()


def test_holdings_payload_xirr_pct_from_map():
    h1 = _holding(isin="INFA", folio_number="F1")
    h2 = _holding(isin="INFB", folio_number="F2")
    p = holdings_payload(
        _rm([h1, h2]), "pid-1", xirr_map={("INFA", "F1"): 9.5, ("INFB", "F2"): None}
    )
    by_isin = {h["isin"]: h for h in p["holdings"]}
    assert by_isin["INFA"]["xirr_pct"] == 9.5
    assert by_isin["INFB"]["xirr_pct"] is None
    assert _all_keys(p) & _FORBIDDEN == set()


def test_holdings_payload_xirr_pct_none_default_when_no_map():
    p = holdings_payload(_rm(), "pid-1")
    assert p["holdings"][0]["xirr_pct"] is None


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


async def _seed_portfolio(db_session, uid: str, isin: str) -> str:
    """A portfolio with one holding (5 units, invested 900, NAV 200 @ today). Each test MUST pass a
    UNIQUE isin — mf_nav_history/mf_funds are shared across the session-scoped DB (ON CONFLICT DO
    NOTHING), so a reused ISIN leaks state across tests."""
    pid = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'XW') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_funds (isin, scheme_name, category, sebi_category, is_segregated)"
            " VALUES (:i, 'Test Fund', 'Equity', 'Flexi Cap Fund', false)"
            " ON CONFLICT (isin) DO NOTHING"
        ),
        {"i": isin},
    )
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_nav_history (isin, nav_date, nav) VALUES (:i, :d, 200.0)"
            " ON CONFLICT (isin, nav_date) DO NOTHING"
        ),
        {"i": isin, "d": date.today()},
    )
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_user_holdings (user_id, portfolio_id, isin, folio_number, units,"
            " invested_amount, avg_cost_nav, source, as_of_date)"
            " VALUES (:u, :p, :i, '999', 5.0, 900.0, 180.0, 'cas', :d)"
        ),
        {"u": uid, "p": str(pid), "i": isin, "d": date.today()},
    )
    await db_session.commit()
    return str(pid)


async def _seed_daily_value(
    db_session, pid: str, uid: str, vdate: date, total_value: float, total_invested: float = 900.0
) -> None:
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


async def _seed_ledger_txn(
    db_session,
    pid: str,
    uid: str,
    isin: str,
    folio: str,
    txn_date: date,
    amount: float,
    txn_type: str = "purchase",
    source_ref: str | None = None,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO mf.portfolio_transactions"
            " (portfolio_id, user_id, asset_class, instrument_id, folio_number, txn_type,"
            "  txn_date, units, nav_or_price, amount, source, source_ref, parser_version)"
            " VALUES (:p, :u, 'mf', :i, :f, :tt, :d, 1.0, 100.0, :a, 'cas', :ref, 'cas-1')"
        ),
        {
            "p": pid,
            "u": uid,
            "i": isin,
            "f": folio,
            "tt": txn_type,
            "d": txn_date,
            "a": amount,
            "ref": source_ref or f"test-ref-{isin}-{folio}-{txn_date.isoformat()}-{amount}",
        },
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# PG: load_windowed_xirr
# ---------------------------------------------------------------------------


async def test_windowed_xirr_none_cold_start(db_session):
    """No mf_portfolio_daily_values row at all -> None (nothing to anchor a start value to)."""
    uid = await _seed_user(db_session, "xw-cold@test.dev")
    pid = await _seed_portfolio(db_session, uid, isin="INFXW001")

    result = await load_windowed_xirr(db_session, pid, end_value=1200.0)
    assert result is None


async def test_windowed_xirr_none_when_window_too_short(db_session):
    """Only 10 days of history exist (< 30-day floor) -> None, even though a row exists."""
    uid = await _seed_user(db_session, "xw-short@test.dev")
    pid = await _seed_portfolio(db_session, uid, isin="INFXW002")
    today = date.today()
    await _seed_daily_value(db_session, pid, uid, today - timedelta(days=10), total_value=1000.0)

    result = await load_windowed_xirr(db_session, pid, end_value=1050.0)
    assert result is None


async def test_windowed_xirr_shrinks_window_when_series_shorter_than_days(db_session):
    """Series only reaches back 200 days (< the 365-day ask) -> falls back to the EARLIEST row and
    reports the ACTUAL (shrunk) window, never a fabricated full year."""
    uid = await _seed_user(db_session, "xw-shrink@test.dev")
    pid = await _seed_portfolio(db_session, uid, isin="INFXW003")
    today = date.today()
    start_date = today - timedelta(days=200)
    await _seed_daily_value(db_session, pid, uid, start_date, total_value=1000.0)

    result = await load_windowed_xirr(db_session, pid, end_value=1100.0, days=365)
    assert result is not None
    rate, actual_days = result
    assert actual_days == 200
    assert rate == pytest.approx(windowed_xirr(1000.0, start_date, [], 1100.0, today), abs=1e-6)


async def test_windowed_xirr_full_window_with_real_ledger_flow(db_session):
    """A full 365-day window with a real mid-window ledger purchase — the returned rate matches
    windowed_xirr() called directly with the same three legs (consistency, no separate root-finder)."""
    uid = await _seed_user(db_session, "xw-full@test.dev")
    pid = await _seed_portfolio(db_session, uid, isin="INFXW004")
    today = date.today()
    start_date = today - timedelta(days=365)
    flow_date = today - timedelta(days=180)
    await _seed_daily_value(db_session, pid, uid, start_date, total_value=1000.0)
    await _seed_ledger_txn(
        db_session, pid, uid, "INFXW004", "999", flow_date, amount=-500.0, txn_type="purchase"
    )

    result = await load_windowed_xirr(db_session, pid, end_value=1650.0, days=365)
    assert result is not None
    rate, actual_days = result
    assert actual_days == 365
    expected = windowed_xirr(
        1000.0, start_date, [CashFlow(when=flow_date, amount=-500.0)], 1650.0, today
    )
    assert rate == pytest.approx(expected, abs=1e-6)


async def test_windowed_xirr_same_day_flows_are_summed_not_duplicated(db_session):
    """Two ledger rows on the SAME day inside the window are grouped into one flow (Σ amount), not
    treated as separate cash flows that would double-count the day."""
    uid = await _seed_user(db_session, "xw-sameday@test.dev")
    pid = await _seed_portfolio(db_session, uid, isin="INFXW005")
    today = date.today()
    start_date = today - timedelta(days=365)
    flow_date = today - timedelta(days=90)
    await _seed_daily_value(db_session, pid, uid, start_date, total_value=1000.0)
    await _seed_ledger_txn(
        db_session,
        pid,
        uid,
        "INFXW005",
        "999",
        flow_date,
        amount=-300.0,
        txn_type="purchase",
        source_ref="ref-a",
    )
    await _seed_ledger_txn(
        db_session,
        pid,
        uid,
        "INFXW005",
        "999",
        flow_date,
        amount=-200.0,
        txn_type="sip",
        source_ref="ref-b",
    )

    result = await load_windowed_xirr(db_session, pid, end_value=1650.0, days=365)
    assert result is not None
    rate, _ = result
    expected = windowed_xirr(
        1000.0, start_date, [CashFlow(when=flow_date, amount=-500.0)], 1650.0, today
    )
    assert rate == pytest.approx(expected, abs=1e-6)


async def test_windowed_xirr_none_when_end_value_non_positive(db_session):
    uid = await _seed_user(db_session, "xw-endzero@test.dev")
    pid = await _seed_portfolio(db_session, uid, isin="INFXW006")
    today = date.today()
    await _seed_daily_value(db_session, pid, uid, today - timedelta(days=365), total_value=1000.0)

    assert await load_windowed_xirr(db_session, pid, end_value=0.0) is None
    assert await load_windowed_xirr(db_session, pid, end_value=-50.0) is None


# ---------------------------------------------------------------------------
# PG: load_holdings_xirr
# ---------------------------------------------------------------------------


async def test_holdings_xirr_non_null_with_ledger_history(db_session):
    uid = await _seed_user(db_session, "hx-yes@test.dev")
    pid = await _seed_portfolio(db_session, uid, isin="INFHX001")
    txn_date = date.today() - timedelta(days=200)
    await _seed_ledger_txn(
        db_session, pid, uid, "INFHX001", "999", txn_date, amount=-900.0, txn_type="purchase"
    )

    result = await load_holdings_xirr(db_session, pid, current_values={("INFHX001", "999"): 1000.0})
    assert result[("INFHX001", "999")] is not None
    assert result[("INFHX001", "999")] > 0.0


async def test_holdings_xirr_none_for_untracked_holding(db_session):
    """A holding key with NO ledger rows for it maps to None, even while a sibling holding (same
    portfolio) DOES have ledger history — proves the per-holding keying, not a portfolio-wide flag."""
    uid = await _seed_user(db_session, "hx-no@test.dev")
    pid = await _seed_portfolio(db_session, uid, isin="INFHX002")
    txn_date = date.today() - timedelta(days=100)
    await _seed_ledger_txn(
        db_session, pid, uid, "INFHX002", "999", txn_date, amount=-900.0, txn_type="purchase"
    )

    result = await load_holdings_xirr(
        db_session,
        pid,
        current_values={("INFHX002", "999"): 1000.0, ("INFHX999", "no-history"): 500.0},
    )
    assert result[("INFHX002", "999")] is not None
    assert result[("INFHX999", "no-history")] is None


# ---------------------------------------------------------------------------
# PG: endpoints end-to-end through the A3 boundary
# ---------------------------------------------------------------------------


async def test_summary_endpoint_serves_xirr_1y_fields(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "ep-summary@test.dev")
    pid = await _seed_portfolio(db_session, uid, isin="INFEP001")
    today = date.today()
    start_date = today - timedelta(days=365)
    await _seed_daily_value(db_session, pid, uid, start_date, total_value=800.0)
    await _seed_ledger_txn(
        db_session,
        pid,
        uid,
        "INFEP001",
        "999",
        today - timedelta(days=180),
        amount=-100.0,
        txn_type="purchase",
    )
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/summary", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert "xirr_1y_pct" in d and "xirr_1y_window_days" in d
    assert d["xirr_1y_window_days"] == 365
    assert d["xirr_1y_pct"] is not None


async def test_summary_endpoint_xirr_1y_none_cold_start(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "ep-summary-cold@test.dev")
    pid = await _seed_portfolio(db_session, uid, isin="INFEP002")
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/summary", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["xirr_1y_pct"] is None and d["xirr_1y_window_days"] is None


async def test_holdings_endpoint_serves_xirr_pct_per_holding(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "ep-holdings@test.dev")
    pid = await _seed_portfolio(db_session, uid, isin="INFEP003")
    await _seed_ledger_txn(
        db_session,
        pid,
        uid,
        "INFEP003",
        "999",
        date.today() - timedelta(days=200),
        amount=-900.0,
        txn_type="purchase",
    )
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/holdings", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    holdings = r.json()["data"]["holdings"]
    assert len(holdings) == 1
    assert "xirr_pct" in holdings[0]
    assert holdings[0]["xirr_pct"] is not None
