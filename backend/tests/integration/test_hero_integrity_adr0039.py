"""ADR-0039 — hero data-integrity layer: per-holding data-states, per-metric basis + coverage,
honest degradation, integrity tripwire.

Covers:
  * Pure: `_classify_holding` — all four data_states (placeholder > unpriced > ledger_backed/
    stated_only priority order) + the `covered_keys=None` backward-compatible default.
  * Pure: `classify_holdings` post-step reclassification (placeholder/unpriced holdings untouched).
  * Pure: `basis_coverage_pct` — the shared coverage-% math (full/partial/near-full/zero-total).
  * Pure: `summary_payload`'s `value_priced_pct` / `invested_missing_count` over a mixed-basis
    portfolio, and the gain_pct/gain_vs_cost_pct sign-flip fix (None on a NEGATIVE denominator, not
    just a zero one).
  * Pure: `hero_integrity_checks` — each of the 5 checks triggers on a deliberately-broken payload;
    a clean payload returns [].
  * PG: `load_windowed_xirr`'s `active_keys` filter excludes a closed position's in-window flow.
  * PG: `load_day_change`'s 4th tuple element (covered ISINs) excludes an unpriced/single-NAV-date
    holding.
  * PG: a full 4-state (ledger_backed/stated_only/unpriced/placeholder) portfolio through
    GET /summary end-to-end — every ADR-0039 field asserted to an exact hand-computed value.

Mirrors the CAMS-parity/M2.3 test pattern: unique ISINs per test — mf_nav_history/mf_funds are
shared across the session-scoped DB.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from dhanradar.mf.portfolio_read import (
    EnrichedHolding,
    PortfolioReadModel,
    _classify_holding,
    basis_coverage_pct,
    classify_holdings,
    hero_integrity_checks,
    load_day_change,
    load_windowed_xirr,
    summary_payload,
)
from dhanradar.models.auth import User

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Pure: _classify_holding
# ---------------------------------------------------------------------------


def test_classify_placeholder_overrides_everything():
    """A CAMS: placeholder isin classifies 'placeholder' even with a live NAV and covered_keys hit —
    isin format is checked FIRST, before pricing or ledger-coverage."""
    state, basis = _classify_holding("CAMS:X001", 100.0, 90.0, "1", {("CAMS:X001", "1")})
    assert state == "placeholder"


def test_classify_unpriced_cost_fallback():
    state, basis = _classify_holding("INF1", None, 90.0, "1", None)
    assert state == "unpriced" and basis == "cost_fallback"


def test_classify_unpriced_none_basis_when_no_fallback_either():
    state, basis = _classify_holding("INF1", None, None, "1", None)
    assert state == "unpriced" and basis == "none"


def test_classify_defaults_ledger_backed_when_covered_keys_none():
    """Backward-compatible default — the read model's first pass (holdings/risk/allocation/etc.
    callers) has no ledger-flow knowledge yet."""
    state, basis = _classify_holding("INF1", 100.0, 90.0, "1", None)
    assert state == "ledger_backed" and basis == "live_nav"


def test_classify_stated_only_when_key_not_covered():
    state, basis = _classify_holding("INF1", 100.0, 90.0, "1", {("OTHER", "1")})
    assert state == "stated_only" and basis == "live_nav"


def test_classify_ledger_backed_when_key_covered():
    state, basis = _classify_holding("INF1", 100.0, 90.0, "1", {("INF1", "1")})
    assert state == "ledger_backed" and basis == "live_nav"


# ---------------------------------------------------------------------------
# Pure: classify_holdings post-step
# ---------------------------------------------------------------------------


def _holding(**kw) -> EnrichedHolding:
    d = dict(
        isin="INF1",
        scheme_name="X Fund",
        category="Flexi Cap Fund",
        folio_number="1",
        units=10.0,
        invested=1000.0,
        current_nav=100.0,
        current_value=1000.0,
        label=None,
        confidence_band=None,
        as_of="2026-07-01",
    )
    d.update(kw)
    return EnrichedHolding(**d)


def test_classify_holdings_upgrades_ledger_backed_default_only():
    covered = _holding(isin="INF1", folio_number="1")  # default data_state='ledger_backed'
    uncovered = _holding(isin="INF2", folio_number="1")  # default data_state='ledger_backed' too
    placeholder = _holding(
        isin="CAMS:X1", folio_number="1", data_state="placeholder", value_basis="cost_fallback"
    )
    unpriced = _holding(
        isin="INF3", folio_number="1", data_state="unpriced", value_basis="cost_fallback"
    )
    rm = PortfolioReadModel(
        holdings=[covered, uncovered, placeholder, unpriced],
        total_invested=4000.0,
        total_value=4000.0,
        xirr_pct=None,
        as_of="2026-07-01",
    )
    out = classify_holdings(rm, {("INF1", "1")})
    by_isin = {h.isin: h for h in out.holdings}
    assert by_isin["INF1"].data_state == "ledger_backed"
    assert by_isin["INF2"].data_state == "stated_only"
    assert by_isin["CAMS:X1"].data_state == "placeholder"  # untouched
    assert by_isin["INF3"].data_state == "unpriced"  # untouched


# ---------------------------------------------------------------------------
# Pure: basis_coverage_pct
# ---------------------------------------------------------------------------


def test_basis_coverage_pct_full_is_none():
    assert basis_coverage_pct(1000.0, 1000.0) is None


def test_basis_coverage_pct_partial():
    assert basis_coverage_pct(200.0, 1000.0) == 20


def test_basis_coverage_pct_near_full_rounds_to_none():
    assert basis_coverage_pct(995.0, 1000.0) is None


def test_basis_coverage_pct_zero_total_is_none():
    assert basis_coverage_pct(0.0, 0.0) is None


# ---------------------------------------------------------------------------
# Pure: summary_payload — value_priced_pct / invested_missing_count / sign-flip fix
# ---------------------------------------------------------------------------


def test_summary_payload_value_priced_pct_mixed_basis():
    live1 = _holding(isin="INF1", current_value=600.0, value_basis="live_nav")
    live2 = _holding(isin="INF2", current_value=400.0, value_basis="live_nav")
    stale = _holding(
        isin="INF3", current_value=1000.0, value_basis="cost_fallback", data_state="unpriced"
    )
    rm = PortfolioReadModel(
        holdings=[live1, live2, stale],
        total_invested=2000.0,
        total_value=2000.0,
        xirr_pct=None,
        as_of="2026-07-01",
    )
    p = summary_payload(rm, "pid-1")
    # live1+live2 = 1000 of 2000 total -> 50%
    assert p["value_priced_pct"] == 50


def test_summary_payload_value_priced_pct_none_when_fully_priced():
    live = _holding(isin="INF1", current_value=1000.0, value_basis="live_nav")
    rm = PortfolioReadModel(
        holdings=[live], total_invested=1000.0, total_value=1000.0, xirr_pct=None, as_of=None
    )
    p = summary_payload(rm, "pid-1")
    assert p["value_priced_pct"] is None


def test_summary_payload_invested_missing_count():
    missing = _holding(isin="INF1", units=10.0, invested=0.0)
    present = _holding(isin="INF2", units=10.0, invested=500.0)
    rm = PortfolioReadModel(
        holdings=[missing, present],
        total_invested=500.0,
        total_value=2000.0,
        xirr_pct=None,
        as_of=None,
    )
    p = summary_payload(rm, "pid-1")
    assert p["invested_missing_count"] == 1


def test_summary_payload_invested_missing_count_zero_when_none_missing():
    h = _holding(isin="INF1", units=10.0, invested=500.0)
    rm = PortfolioReadModel(
        holdings=[h], total_invested=500.0, total_value=1000.0, xirr_pct=None, as_of=None
    )
    p = summary_payload(rm, "pid-1")
    assert p["invested_missing_count"] == 0


def test_summary_payload_gain_pct_none_on_negative_invested():
    """The sign-flip bug (ADR-0039): a NEGATIVE total_invested used to pass the old `if
    rm.total_invested` truthy check and silently flip gain_pct's sign. Now None whenever the
    denominator is <= 0, not just == 0."""
    rm = PortfolioReadModel(
        holdings=[_holding()],
        total_invested=-500.0,
        total_value=1000.0,
        xirr_pct=None,
        as_of=None,
    )
    p = summary_payload(rm, "pid-1")
    assert p["gain"] == 1500.0
    assert p["gain_pct"] is None  # NOT -300.0 (the old sign-flip)


def test_summary_payload_gain_vs_cost_pct_none_on_negative_cost_value():
    rm = PortfolioReadModel(
        holdings=[_holding()],
        total_invested=0.0,
        total_value=1000.0,
        xirr_pct=None,
        as_of=None,
    )
    p = summary_payload(rm, "pid-1", reinvested_cost=-500.0)  # cost_value = 0 + -500 = -500
    assert p["cost_value"] == -500.0
    assert p["gain_vs_cost_pct"] is None


# ---------------------------------------------------------------------------
# Pure: hero_integrity_checks
# ---------------------------------------------------------------------------


def _clean_rm_and_payload():
    h = _holding(isin="INF1", current_value=1000.0)
    rm = PortfolioReadModel(
        holdings=[h], total_invested=800.0, total_value=1000.0, xirr_pct=None, as_of=None
    )
    payload = {
        "total_value": 1000.0,
        "total_invested": 800.0,
        "gain": 200.0,
        "fund_count": 1,
        "value_priced_pct": 50,
        "xirr_coverage_pct": None,
        "wt_avg_days_coverage_pct": None,
        "day_change_coverage_pct": None,
    }
    return rm, payload


def test_hero_integrity_checks_clean_payload_passes():
    rm, payload = _clean_rm_and_payload()
    assert hero_integrity_checks(rm, payload) == []


def test_hero_integrity_checks_total_value_mismatch():
    rm, payload = _clean_rm_and_payload()
    payload["total_value"] = 5000.0
    assert "total_value_mismatch" in hero_integrity_checks(rm, payload)


def test_hero_integrity_checks_coverage_out_of_range():
    rm, payload = _clean_rm_and_payload()
    payload["xirr_coverage_pct"] = 150
    assert "coverage_out_of_range" in hero_integrity_checks(rm, payload)


def test_hero_integrity_checks_fund_count_mismatch():
    rm, payload = _clean_rm_and_payload()
    payload["fund_count"] = 99
    assert "fund_count_mismatch" in hero_integrity_checks(rm, payload)


def test_hero_integrity_checks_placeholder_live_nav():
    h = _holding(
        isin="CAMS:X1", data_state="placeholder", value_basis="live_nav", current_value=1000.0
    )
    rm = PortfolioReadModel(
        holdings=[h], total_invested=800.0, total_value=1000.0, xirr_pct=None, as_of=None
    )
    payload = {"total_value": 1000.0, "total_invested": 800.0, "gain": 200.0, "fund_count": 1}
    assert "placeholder_live_nav" in hero_integrity_checks(rm, payload)


def test_hero_integrity_checks_gain_mismatch():
    rm, payload = _clean_rm_and_payload()
    payload["gain"] = 999999.0
    assert "gain_mismatch" in hero_integrity_checks(rm, payload)


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


async def _seed_fund(db_session, isin: str) -> None:
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_funds (isin, scheme_name, category, sebi_category, is_segregated)"
            " VALUES (:i, :n, 'Equity', 'Flexi Cap Fund', false) ON CONFLICT (isin) DO NOTHING"
        ),
        {"i": isin, "n": f"Fund {isin}"},
    )


async def _seed_nav(db_session, isin: str, d: date, nav: float) -> None:
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_nav_history (isin, nav_date, nav) VALUES (:i, :d, :n)"
            " ON CONFLICT (isin, nav_date) DO NOTHING"
        ),
        {"i": isin, "d": d, "n": nav},
    )


async def _seed_holding(
    db_session,
    uid: str,
    pid,
    isin: str,
    folio: str,
    units: float,
    invested: float,
    avg_cost_nav: float | None,
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
            "nav": avg_cost_nav,
            "d": as_of,
        },
    )


async def _seed_daily_value(
    db_session, pid, uid: str, vdate: date, total_value: float, total_invested: float = 0.0
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_portfolio_daily_values"
            " (portfolio_id, user_id, valuation_date, total_value, total_invested)"
            " VALUES (:p, :u, :d, :v, :i) ON CONFLICT (portfolio_id, valuation_date) DO NOTHING"
        ),
        {"p": str(pid), "u": uid, "d": vdate, "v": total_value, "i": total_invested},
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


# ---------------------------------------------------------------------------
# PG: load_windowed_xirr active_keys filter
# ---------------------------------------------------------------------------


async def test_load_windowed_xirr_active_keys_excludes_closed_position(db_session):
    uid = await _seed_user(db_session, "hero-xirr1y@test.dev")
    pid = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'W') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()
    today = date.today()
    active_isin, closed_isin = "INFW001ACTIVE", "INFW001CLOSED"
    await _seed_fund(db_session, active_isin)
    await _seed_nav(db_session, active_isin, today, 100.0)

    # Active holding: a small real purchase inside the window.
    await _seed_txn(
        db_session,
        uid,
        pid,
        active_isin,
        "1",
        "purchase",
        today - timedelta(days=100),
        1.0,
        1000.0,
        -1000.0,
        "w-active-purchase",
    )
    # Closed position: a HUGE purchase+redemption inside the SAME window — must NOT leak in.
    await _seed_txn(
        db_session,
        uid,
        pid,
        closed_isin,
        "1",
        "purchase",
        today - timedelta(days=90),
        1000.0,
        1.0,
        -100_000.0,
        "w-closed-purchase",
    )
    await _seed_txn(
        db_session,
        uid,
        pid,
        closed_isin,
        "1",
        "redemption",
        today - timedelta(days=80),
        -1000.0,
        200.0,
        200_000.0,
        "w-closed-redemption",
    )
    # load_windowed_xirr anchors its window on the daily-valuation series — seed one row far enough
    # back that the window doesn't shrink below the 30-day floor.
    await _seed_daily_value(db_session, pid, uid, today - timedelta(days=200), total_value=1000.0)
    await db_session.commit()

    active_keys = {(active_isin, "1")}
    result = await load_windowed_xirr(
        db_session, pid, end_value=1000.0, days=365, active_keys=active_keys
    )
    # Without filtering, the closed position's +100,000 net flow inside the window would dominate
    # and/or break the solver; with filtering, only the tiny active purchase matters.
    assert result is not None
    rate, _window_days = result
    assert abs(rate) < 1000.0, f"closed holding's flow leaked into the windowed XIRR: {rate}"


# ---------------------------------------------------------------------------
# PG: load_day_change covered-ISIN set
# ---------------------------------------------------------------------------


async def test_load_day_change_covered_isins_excludes_single_nav_date_holding(db_session):
    uid = await _seed_user(db_session, "hero-daychange@test.dev")
    pid = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'D') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()
    today = date.today()
    two_date_isin, one_date_isin = "INFD001TWO", "INFD001ONE"
    await _seed_fund(db_session, two_date_isin)
    await _seed_fund(db_session, one_date_isin)
    await _seed_nav(db_session, two_date_isin, today - timedelta(days=1), 100.0)
    await _seed_nav(db_session, two_date_isin, today, 110.0)
    await _seed_nav(db_session, one_date_isin, today, 200.0)  # only ONE date -> excluded
    await _seed_holding(db_session, uid, pid, two_date_isin, "1", 10.0, 1000.0, 100.0, today)
    await _seed_holding(db_session, uid, pid, one_date_isin, "1", 5.0, 1000.0, 200.0, today)
    await db_session.commit()

    result = await load_day_change(db_session, pid)
    assert result is not None
    _change, _pct, anchor, covered_isins = result
    assert anchor == today
    assert covered_isins == frozenset({two_date_isin})


# ---------------------------------------------------------------------------
# PG: full 4-state portfolio through GET /summary — every ADR-0039 field exact
# ---------------------------------------------------------------------------


async def test_summary_endpoint_four_state_portfolio_tagged_and_coverage_correct(
    db_session, rls_async_client
):
    """The scenario ADR-0039 exists for: one holding in each of the four data_states, hand-computed
    expected values for every new field. See the module docstring's fixture design."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "hero-4state@test.dev")
    pid = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, '4State') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()
    today = date.today()
    yesterday = today - timedelta(days=1)

    backed_isin = "INFHERO4BACKED1"
    stated_isin = "INFHERO4STATED1"
    unpriced_isin = "INFHERO4UNPRICE"
    placeholder_isin = "CAMS:HERO4PLACE"

    # ledger_backed: 2 NAV dates (day-change covers it), a real ledger purchase.
    await _seed_fund(db_session, backed_isin)
    await _seed_nav(db_session, backed_isin, yesterday, 100.0)
    await _seed_nav(db_session, backed_isin, today, 100.0)
    await _seed_holding(db_session, uid, pid, backed_isin, "1", 10.0, 800.0, 100.0, today)
    await _seed_txn(
        db_session,
        uid,
        pid,
        backed_isin,
        "1",
        "purchase",
        today - timedelta(days=200),
        10.0,
        80.0,
        -800.0,
        "hero4-backed-purchase",
    )

    # stated_only: live NAV but only ONE date (day-change excludes it) and NO ledger rows at all —
    # invested_amount=0 (a holdings-only source that never captured cost -> invested_missing_count).
    await _seed_fund(db_session, stated_isin)
    await _seed_nav(db_session, stated_isin, today, 100.0)
    await _seed_holding(db_session, uid, pid, stated_isin, "1", 10.0, 0.0, 100.0, today)

    # unpriced: a NAV row exists but 40 days old (OUTSIDE the 30-day bound) — proves the staleness
    # bound actually rejects it (if it leaked through, current_value would be 10*999=9990, not 500).
    await _seed_fund(db_session, unpriced_isin)
    await _seed_nav(db_session, unpriced_isin, today - timedelta(days=40), 999.0)
    await _seed_holding(db_session, uid, pid, unpriced_isin, "1", 10.0, 500.0, 50.0, today)

    # placeholder: unresolved CAMS: isin — no fund/NAV rows possible.
    await _seed_holding(db_session, uid, pid, placeholder_isin, "1", 5.0, 200.0, 40.0, today)

    await db_session.commit()
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/summary", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]

    # total_value = 1000 (backed) + 1000 (stated, live NAV) + 500 (unpriced, cost_fallback,
    # NOT 9990 - proves the 30-day staleness bound) + 200 (placeholder, cost_fallback) = 2700.
    assert d["total_value"] == pytest.approx(2700.0, abs=0.01)
    assert d["total_invested"] == pytest.approx(1500.0, abs=0.01)  # 800+0+500+200
    assert d["fund_count"] == 4

    # value_priced_pct: (1000 backed + 1000 stated, both live_nav) / 2700 = 74.07 -> 74.
    assert d["value_priced_pct"] == 74

    # invested_missing_count: only stated_only has invested_amount <= 0 with units > 0.
    assert d["invested_missing_count"] == 1

    # xirr_coverage_pct / wt_avg_days_coverage_pct: covered_value = backed's own value (1000, the
    # ONLY holding with ledger rows) / 2700 = 37.03 -> 37.
    assert d["xirr_pct"] is not None
    assert d["xirr_coverage_pct"] == 37
    assert d["wt_avg_days"] == 200  # one 200-day-old lot, nothing consumed it
    assert d["wt_avg_days_coverage_pct"] == 37

    # day_change_coverage_pct: only backed_isin has 2 NAV dates at the anchor (stated_isin has only
    # one) -> covered value = 1000 / 2700 = 37.
    assert d["day_change_coverage_pct"] == 37
    assert d["valuation_as_of"] == today.isoformat()

    # Rule 5 tripwire: a well-formed 4-state fixture must NOT trip any check (asserted indirectly —
    # no way to read the log from here; the exact-value assertions above already prove consistency).
