"""CAMS-parity batch (2026-07-03) — ledger-based lifetime XIRR, Wt.Avg.Days, dual cost basis
(reinvested IDCW), per-holding today's G/L.

Founder reconciled DhanRadar against the CAMS RTA app: value + today's gain already matched exactly.
This closes the remaining four gaps:
  * Hero "Lifetime XIRR" was a stale upload-time snapshot number — now ledger-based, over the ACTIVE
    holdings' full flow history + live value (a closed/fully-redeemed position's flows are excluded,
    the CAMS-comparable basis).
  * CAMS "Cost value" counts reinvested-IDCW payouts as cost; our net-invested (cash basis) doesn't —
    `cost_value` = total_invested + Σ(units × nav_or_price) over active `dividend_reinvest` rows.
  * CAMS "Wt.Avg.Days" — a capital-weighted average holding period via greedy FIFO lot accounting.
  * CAMS shows per-fund Today's G/L — we only had it at the portfolio level.

Covers:
  * Pure: weighted_avg_holding_days golden cases (two-lot, FIFO-redemption-consumes-oldest,
    reinvest-rows-ignored, empty/fully-redeemed -> None).
  * Pure: portfolio_wt_avg_days / reinvested_dividend_cost aggregate correctly across holdings.
  * Pure: summary_payload / holdings_payload carry the new fields through, #2-safe.
  * PG:   load_portfolio_xirr excludes a closed holding's flows.
  * PG:   load_active_holding_flows -> portfolio_wt_avg_days / reinvested_dividend_cost against real rows.
  * PG:   GET /summary and GET /holdings serve the new fields end-to-end through the A3 boundary.

Mirrors the M2.3/hide-zero-balance test pattern: unique ISINs/portfolios per test — mf_nav_history and
mf_funds are shared across the session-scoped DB.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from dhanradar.mf.portfolio_read import (
    EnrichedHolding,
    PortfolioReadModel,
    holdings_payload,
    load_active_holding_flows,
    load_portfolio_read_model,
    load_portfolio_xirr,
    portfolio_wt_avg_days,
    reinvested_dividend_cost,
    summary_payload,
    weighted_avg_holding_days,
)
from dhanradar.models.auth import User

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Pure: weighted_avg_holding_days — golden FIFO cases
# ---------------------------------------------------------------------------

_TODAY = date(2026, 7, 3)


def test_wt_avg_days_simple_two_lot():
    flows = [
        (_TODAY - timedelta(days=100), -1000.0, "purchase"),
        (_TODAY - timedelta(days=50), -500.0, "purchase"),
    ]
    # (1000*100 + 500*50) / 1500 = 125000 / 1500 = 83.33 -> 83
    assert weighted_avg_holding_days(flows, _TODAY) == 83


def test_wt_avg_days_fifo_redemption_consumes_oldest_lot():
    """A redemption consumes the OLDEST lot first — the remaining average age DROPS to the
    younger lot's age, proving FIFO (not LIFO, not pro-rata)."""
    flows = [
        (_TODAY - timedelta(days=200), -1000.0, "purchase"),  # oldest lot
        (_TODAY - timedelta(days=50), -1000.0, "purchase"),  # newer lot
        (_TODAY - timedelta(days=10), 1000.0, "redemption"),  # exactly consumes the oldest lot
    ]
    assert weighted_avg_holding_days(flows, _TODAY) == 50


def test_wt_avg_days_reinvest_rows_ignored():
    """A dividend_reinvest row (amount=0) contributes no cost and no lot effect."""
    flows = [
        (_TODAY - timedelta(days=30), -1000.0, "purchase"),
        (_TODAY - timedelta(days=5), 0.0, "dividend_reinvest"),
    ]
    assert weighted_avg_holding_days(flows, _TODAY) == 30


def test_wt_avg_days_empty_is_none():
    assert weighted_avg_holding_days([], _TODAY) is None


def test_wt_avg_days_fully_redeemed_is_none():
    flows = [
        (_TODAY - timedelta(days=90), -1000.0, "purchase"),
        (_TODAY - timedelta(days=5), 1000.0, "redemption"),
    ]
    assert weighted_avg_holding_days(flows, _TODAY) is None


def test_portfolio_wt_avg_days_sums_raw_pairs_before_dividing():
    """Two holdings combine by summing the raw (cost, weighted_age) pairs BEFORE dividing — a
    holding-level round-then-average would give a different (wrong) number here."""
    grouped = {
        ("INF1", "F1"): [(_TODAY - timedelta(days=100), -1000.0, "purchase", 10.0, 100.0)],
        ("INF2", "F1"): [(_TODAY - timedelta(days=200), -2000.0, "purchase", 20.0, 100.0)],
    }
    # (1000*100 + 2000*200) / 3000 = 500000 / 3000 = 166.67 -> 167
    assert portfolio_wt_avg_days(grouped, _TODAY) == 167


def test_portfolio_wt_avg_days_empty_is_none():
    assert portfolio_wt_avg_days({}, _TODAY) is None


def test_reinvested_dividend_cost_sums_units_times_nav():
    grouped = {
        ("INF1", "F1"): [
            (date(2026, 1, 1), -1000.0, "purchase", 10.0, 100.0),
            (date(2026, 2, 1), 0.0, "dividend_reinvest", 2.0, 50.0),
        ],
    }
    assert reinvested_dividend_cost(grouped) == 100.0


def test_reinvested_dividend_cost_null_nav_is_graceful():
    grouped = {("INF1", "F1"): [(date(2026, 1, 1), 0.0, "dividend_reinvest", 2.0, None)]}
    assert reinvested_dividend_cost(grouped) == 0.0


def test_reinvested_dividend_cost_ignores_non_reinvest_rows():
    grouped = {
        ("INF1", "F1"): [(date(2026, 1, 1), -1000.0, "purchase", 10.0, 100.0)],
    }
    assert reinvested_dividend_cost(grouped) == 0.0


# ---------------------------------------------------------------------------
# Pure: summary_payload / holdings_payload carry the new fields, #2-safe
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


_FORBIDDEN = {
    "unified_score",
    "score",
    "raw_score",
    "composite_score",
    "factor_weights",
    "fair_value",
}


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


def _rm(holdings=None, total_invested=1000.0, total_value=1200.0) -> PortfolioReadModel:
    h = holdings or [_holding()]
    return PortfolioReadModel(
        holdings=h,
        total_invested=total_invested,
        total_value=total_value,
        xirr_pct=None,
        as_of="2026-03-31",
    )


def test_summary_payload_cost_value_and_gain_vs_cost():
    p = summary_payload(_rm(), "pid-1", xirr_pct=12.5, wt_avg_days=200, reinvested_cost=100.0)
    assert p["total_invested"] == 1000.0  # cash basis — unchanged
    assert p["cost_value"] == 1100.0  # 1000 + 100 reinvested
    assert p["gain_vs_cost"] == pytest.approx(100.0)  # 1200 - 1100
    assert p["gain_vs_cost_pct"] == pytest.approx(100.0 / 1100.0 * 100.0)
    assert p["xirr_pct"] == 12.5
    assert p["wt_avg_days"] == 200
    assert _all_keys(p) & _FORBIDDEN == set()


def test_summary_payload_cost_value_defaults_to_total_invested_when_no_reinvest():
    p = summary_payload(_rm(), "pid-1")
    assert p["cost_value"] == 1000.0
    assert p["gain_vs_cost"] == pytest.approx(200.0)  # 1200 - 1000, same as cash-basis gain here
    assert p["wt_avg_days"] is None
    assert p["xirr_pct"] is None  # no longer falls back to rm.xirr_pct


def test_summary_payload_investor_name_passthrough_and_no_pan():
    p = summary_payload(_rm(), "pid-1", investor_name="Manish Kumar")
    assert p["investor_name"] == "Manish Kumar"
    assert "investor_pan" not in p
    assert _all_keys(p) & _FORBIDDEN == set()


def test_summary_payload_investor_name_defaults_to_none():
    p = summary_payload(_rm(), "pid-1")
    assert p["investor_name"] is None


def test_summary_payload_gain_vs_cost_pct_none_when_cost_value_zero():
    p = summary_payload(_rm(holdings=[], total_invested=0.0, total_value=0.0), "pid-1")
    assert p["cost_value"] == 0.0
    assert p["gain_vs_cost_pct"] is None


def test_holdings_payload_day_change_from_map():
    h1 = _holding(isin="INFA", folio_number="F1")
    h2 = _holding(isin="INFB", folio_number="F2")
    p = holdings_payload(_rm([h1, h2]), "pid-1", day_change_map={"INFA": (50.0, 5.0)})
    by_isin = {h["isin"]: h for h in p["holdings"]}
    assert by_isin["INFA"]["day_change"] == 50.0 and by_isin["INFA"]["day_change_pct"] == 5.0
    assert by_isin["INFB"]["day_change"] is None and by_isin["INFB"]["day_change_pct"] is None
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


async def _seed_fund_and_nav(db_session, isin: str, nav: float, nav_date: date) -> None:
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_funds (isin, scheme_name, category, sebi_category, is_segregated)"
            " VALUES (:i, :n, 'Equity', 'Flexi Cap Fund', false) ON CONFLICT (isin) DO NOTHING"
        ),
        {"i": isin, "n": f"Fund {isin}"},
    )
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_nav_history (isin, nav_date, nav) VALUES (:i, :d, :n)"
            " ON CONFLICT (isin, nav_date) DO NOTHING"
        ),
        {"i": isin, "d": nav_date, "n": nav},
    )


async def _seed_holding(
    db_session,
    uid: str,
    pid,
    isin: str,
    folio: str,
    units: float,
    invested: float,
    avg_nav: float,
    as_of: date,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_user_holdings (user_id, portfolio_id, isin, folio_number, units,"
            " invested_amount, avg_cost_nav, source, as_of_date)"
            " VALUES (:u, :p, :i, :f, :un, :inv, :nav, 'cas', :d)"
        ),
        {
            "u": uid,
            "p": str(pid),
            "i": isin,
            "f": folio,
            "un": units,
            "inv": invested,
            "nav": avg_nav,
            "d": as_of,
        },
    )


async def _seed_txn(
    db_session,
    uid: str,
    pid,
    isin: str,
    folio: str,
    txn_type: str,
    txn_date: date,
    units: float,
    nav_or_price: float | None,
    amount: float,
    ref: str,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO mf.portfolio_transactions"
            " (portfolio_id, user_id, asset_class, instrument_id, folio_number, txn_type,"
            "  txn_date, units, nav_or_price, amount, source, source_ref, parser_version)"
            " VALUES (:p, :u, 'mf', :i, :f, :tt, :d, :un, :nav, :amt, 'cas', :ref, 'cas-1')"
        ),
        {
            "p": str(pid),
            "u": uid,
            "i": isin,
            "f": folio,
            "tt": txn_type,
            "d": txn_date,
            "un": units,
            "nav": nav_or_price,
            "amt": amount,
            "ref": ref,
        },
    )


async def _seed_cams_portfolio(db_session, uid: str, suffix: str) -> tuple[str, str, str]:
    """One ACTIVE holding (10 units @ NAV 100, dated yesterday -> value 1000, net-invested 1000)
    with a purchase 400 days ago + a reinvested-IDCW row 100 days ago; one CLOSED (fully-redeemed,
    units=0) holding with a purchase + a HUGE redemption — if the closed holding's flows ever
    leaked into the active-only XIRR/Wt.Avg.Days, both would be wildly different from the
    ~0%/~400-day answers the tests assert. `suffix` MUST be unique per test — mf_nav_history/
    mf_funds are shared across the session-scoped DB. Returns (portfolio_id, active_isin, closed_isin).
    """
    pid = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'CAMS') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()
    today = date.today()
    yesterday = today - timedelta(days=1)
    active_isin = f"INFCAMSA{suffix}"
    closed_isin = f"INFCAMSB{suffix}"

    # Active fund's NAV is dated YESTERDAY so a test can add a second (today-dated) NAV row later
    # to exercise the 2-NAV-dates day-change path without ever seeding a NAV "in the future".
    await _seed_fund_and_nav(db_session, active_isin, 100.0, yesterday)
    await _seed_fund_and_nav(db_session, closed_isin, 1000.0, today)

    await _seed_holding(db_session, uid, pid, active_isin, "1", 10.0, 1000.0, 100.0, yesterday)
    await _seed_holding(db_session, uid, pid, closed_isin, "1", 0.0, 0.0, 1000.0, today)

    await _seed_txn(
        db_session,
        uid,
        pid,
        active_isin,
        "1",
        "purchase",
        today - timedelta(days=400),
        10.0,
        100.0,
        -1000.0,
        "cams-a-purchase",
    )
    await _seed_txn(
        db_session,
        uid,
        pid,
        active_isin,
        "1",
        "dividend_reinvest",
        today - timedelta(days=100),
        2.0,
        50.0,
        0.0,
        "cams-a-reinvest",
    )
    await _seed_txn(
        db_session,
        uid,
        pid,
        closed_isin,
        "1",
        "purchase",
        today - timedelta(days=400),
        100.0,
        1.0,
        -100.0,
        "cams-b-purchase",
    )
    await _seed_txn(
        db_session,
        uid,
        pid,
        closed_isin,
        "1",
        "redemption",
        today - timedelta(days=10),
        -100.0,
        1000.0,
        100_000.0,
        "cams-b-redemption",
    )
    await db_session.commit()
    return str(pid), active_isin, closed_isin


# ---------------------------------------------------------------------------
# PG: load_portfolio_xirr / load_active_holding_flows — closed-holding exclusion
# ---------------------------------------------------------------------------


async def test_load_portfolio_xirr_excludes_closed_holding_flows(db_session):
    uid = await _seed_user(db_session, "cams-xirr@test.dev")
    pid, active_isin, _closed_isin = await _seed_cams_portfolio(db_session, uid, "X001")

    rm = await load_portfolio_read_model(db_session, pid)
    assert [h.isin for h in rm.holdings] == [active_isin]  # closed holding already hidden (units=0)
    active_keys = {(h.isin, h.folio_number) for h in rm.holdings}

    xirr_pct = await load_portfolio_xirr(db_session, pid, rm.total_value, active_keys)
    # Only the active holding's flows: -1000 @ -400d, +1000 (= rm.total_value) terminal -> ~0%.
    # If the closed holding's 100,000 redemption leaked in, this would be far from 0.
    assert xirr_pct is not None
    assert abs(xirr_pct) < 5.0, f"closed holding's flow leaked into ledger XIRR: {xirr_pct}"


async def test_load_portfolio_xirr_empty_active_keys_is_none(db_session):
    uid = await _seed_user(db_session, "cams-xirr-empty@test.dev")
    pid, _active_isin, _closed_isin = await _seed_cams_portfolio(db_session, uid, "X002")
    assert await load_portfolio_xirr(db_session, pid, 1000.0, set()) is None


async def test_load_active_holding_flows_wt_avg_days_and_reinvested_cost(db_session):
    uid = await _seed_user(db_session, "cams-flows@test.dev")
    pid, active_isin, _closed_isin = await _seed_cams_portfolio(db_session, uid, "X003")

    rm = await load_portfolio_read_model(db_session, pid)
    active_keys = {(h.isin, h.folio_number) for h in rm.holdings}
    grouped = await load_active_holding_flows(db_session, pid, active_keys)

    assert set(grouped.keys()) == {(active_isin, "1")}  # closed holding's rows excluded

    today = date.today()
    # Only the 400-day-old purchase carries cost (the dividend_reinvest row is amount=0, skipped).
    assert portfolio_wt_avg_days(grouped, today) == 400
    # 2 units x nav 50 = 100 reinvested cost.
    assert reinvested_dividend_cost(grouped) == pytest.approx(100.0, abs=0.01)


# ---------------------------------------------------------------------------
# PG: GET /summary and GET /holdings — end-to-end through the A3 boundary
# ---------------------------------------------------------------------------


async def test_summary_endpoint_serves_cams_parity_fields(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "cams-ep-summary@test.dev")
    pid, _active_isin, _closed_isin = await _seed_cams_portfolio(db_session, uid, "X004")
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/summary", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]

    assert d["total_invested"] == 1000.0  # cash basis, unchanged
    assert d["cost_value"] == pytest.approx(1100.0, abs=0.01)  # + 2 x 50 reinvested
    assert d["gain_vs_cost"] == pytest.approx(d["total_value"] - 1100.0, abs=0.01)
    assert d["wt_avg_days"] == 400
    assert d["xirr_pct"] is not None
    assert abs(d["xirr_pct"]) < 5.0


async def test_holdings_endpoint_day_change_none_before_two_nav_dates(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "cams-ep-dc-cold@test.dev")
    pid, active_isin, _closed_isin = await _seed_cams_portfolio(db_session, uid, "X005")
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/holdings", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    holdings = r.json()["data"]["holdings"]
    assert len(holdings) == 1 and holdings[0]["isin"] == active_isin
    assert holdings[0]["day_change"] is None and holdings[0]["day_change_pct"] is None


async def test_summary_endpoint_serves_investor_name_never_pan(db_session, rls_async_client):
    """Hero polish (2026-07-04): the summary payload carries the owner's own investor_name
    (CAS-captured full_name) but NEVER investor_pan — own name to own session is DPDP-fine,
    the PAN is not."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "cams-ep-investor-name@test.dev")
    pid, _active_isin, _closed_isin = await _seed_cams_portfolio(db_session, uid, "X007")
    await db_session.execute(
        text("UPDATE auth.users SET full_name = :n, investor_pan = :p WHERE id = :u"),
        {"n": "Manish Kumar", "p": "ABCDE1234F", "u": uid},
    )
    await db_session.commit()
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/summary", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["investor_name"] == "Manish Kumar"
    assert "investor_pan" not in d
    assert "ABCDE1234F" not in r.text


async def test_summary_endpoint_investor_name_null_when_not_captured(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "cams-ep-investor-name-null@test.dev")
    pid, _active_isin, _closed_isin = await _seed_cams_portfolio(db_session, uid, "X008")
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/summary", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["investor_name"] is None


async def test_holdings_endpoint_day_change_present_once_two_nav_dates_exist(
    db_session, rls_async_client
):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "cams-ep-dc-warm@test.dev")
    pid, active_isin, _closed_isin = await _seed_cams_portfolio(db_session, uid, "X006")
    # Second (later) NAV date — the active fund's first NAV was seeded yesterday (100.0), so
    # today's 110.0 gives the two-most-recent-dates the bottom-up day-change formula needs.
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_nav_history (isin, nav_date, nav) VALUES (:i, :d, 110.0)"
            " ON CONFLICT (isin, nav_date) DO NOTHING"
        ),
        {"i": active_isin, "d": date.today()},
    )
    await db_session.commit()
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/holdings", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    holdings = r.json()["data"]["holdings"]
    # 10 units x (110 - 100) = 100
    assert holdings[0]["day_change"] == pytest.approx(100.0, abs=0.01)
    assert holdings[0]["day_change_pct"] == pytest.approx(10.0, abs=0.01)
