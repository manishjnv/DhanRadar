"""M2.1 — pure-from-holdings analytics (portfolio.allocation / .concentration / .diversification).

Pure tests prove the payload builders are #2-safe (the user's own allocation %/weights serialize; no
DhanRadar composite) and the band rules. PG tests prove each endpoint end-to-end through the A3 boundary
under RLS: the envelope shape, #2 (a raw unified_score in the DB never reaches the response — key OR
value), value-weighted (current value) math, and RLS owner-scoping (404 for another user, 401 anon).

Mirrors test_c1_c2_portfolio_concepts.py / test_c3_portfolio_risk.py (the proven C-wave pattern).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from dhanradar.mf.portfolio_read import (
    EnrichedHolding,
    PortfolioReadModel,
    _concentration_band,
    _diversification_band,
    _value_buckets,
    allocation_payload,
    concentration_payload,
    diversification_payload,
)
from dhanradar.models.auth import User

pytestmark = pytest.mark.integration


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
        label="on_track", confidence_band="high", as_of="2026-03-31", amc="Alpha AMC",
    )
    d.update(kw)
    return EnrichedHolding(**d)


def _rm(holdings: list[EnrichedHolding]) -> PortfolioReadModel:
    return PortfolioReadModel(
        holdings=holdings,
        total_invested=sum(h.invested for h in holdings),
        total_value=sum(h.current_value for h in holdings),
        xirr_pct=None,
        as_of="2026-03-31",
    )


_FORBIDDEN = {"unified_score", "score", "raw_score", "composite_score", "factor_weights", "fair_value"}


# --- pure: value-weighted buckets -----------------------------------------------------------------


def test_value_buckets_weighted_and_sorted():
    rm = _rm([
        _holding(isin="A", category="Large Cap Fund", current_value=1000.0),
        _holding(isin="B", category="Flexi Cap Fund", current_value=3000.0),
    ])
    rows = _value_buckets(rm, "category")
    assert [r["bucket"] for r in rows] == ["Flexi Cap Fund", "Large Cap Fund"]  # sorted desc by weight
    assert rows[0]["weight_pct"] == 75.0 and rows[1]["weight_pct"] == 25.0
    assert round(sum(r["weight_pct"] for r in rows), 2) == 100.0


def test_value_buckets_empty_when_zero_value():
    assert _value_buckets(_rm([_holding(current_value=0.0)]), "category") == []


# --- pure: allocation payload ---------------------------------------------------------------------


def test_allocation_payload_by_category_safe():
    rm = _rm([
        _holding(isin="A", category="Large Cap Fund", current_value=1000.0),
        _holding(isin="B", category="Flexi Cap Fund", current_value=3000.0),
    ])
    p = allocation_payload(rm, "pid-1", "category")
    assert _all_keys(p) & _FORBIDDEN == set()
    assert p["by"] == "category" and p["total_value"] == 4000.0 and p["fund_count"] == 2
    assert round(sum(b["weight_pct"] for b in p["buckets"]), 2) == 100.0


def test_allocation_payload_by_amc():
    rm = _rm([
        _holding(isin="A", amc="Alpha AMC", current_value=1000.0),
        _holding(isin="B", amc="Beta AMC", current_value=3000.0),
    ])
    p = allocation_payload(rm, "pid-1", "amc")
    assert p["by"] == "amc"
    assert p["buckets"][0] == {"bucket": "Beta AMC", "value": 3000.0, "weight_pct": 75.0}


def test_allocation_payload_data_starved_by_empty_buckets():
    rm = _rm([_holding(current_value=1000.0)])
    assert allocation_payload(rm, "pid-1", "sector")["buckets"] == []
    assert allocation_payload(rm, "pid-1", "cap")["buckets"] == []


# --- pure: concentration band + payload -----------------------------------------------------------


def test_concentration_band_thresholds():
    assert _concentration_band(None, 0) is None
    assert _concentration_band(10.0, 1) == "very_high"   # a single fund is maximally concentrated
    assert _concentration_band(10.0, 3) == "low"
    assert _concentration_band(20.0, 3) == "moderate"
    assert _concentration_band(40.0, 3) == "high"
    assert _concentration_band(60.0, 3) == "very_high"


def test_concentration_payload_top_weights_no_composite():
    rm = _rm([
        _holding(isin="A", scheme_name="Alpha Fund", amc="Alpha AMC", current_value=1000.0),
        _holding(isin="B", scheme_name="Beta Fund", amc="Beta AMC", current_value=3000.0),
    ])
    p = concentration_payload(rm, "pid-1")
    assert _all_keys(p) & _FORBIDDEN == set()
    assert p["top_fund"] == {"name": "Beta Fund", "weight_pct": 75.0}
    assert p["top_amc"] == {"name": "Beta AMC", "weight_pct": 75.0}
    assert p["band"] == "very_high" and p["amc_count"] == 2 and p["fund_count"] == 2


def test_concentration_payload_empty():
    p = concentration_payload(_rm([]), "pid-1")
    assert p["top_fund"] is None and p["top_amc"] is None and p["band"] is None


# --- pure: diversification band + payload ----------------------------------------------------------


def test_diversification_band_thresholds():
    assert _diversification_band([], 0) is None
    assert _diversification_band([100.0], 1) == "low"            # single fund
    assert _diversification_band([75.0, 25.0], 2) == "low"       # top >= 70
    assert _diversification_band([55.0, 45.0], 2) == "medium"    # top >= 50, eff_n ~1.98
    assert _diversification_band([40.0, 35.0, 25.0], 3) == "high"  # well spread


def test_diversification_payload_band_only_no_composite():
    rm = _rm([
        _holding(isin="A", category="Large Cap Fund", current_value=1000.0),
        _holding(isin="B", category="Flexi Cap Fund", current_value=3000.0),
    ])
    p = diversification_payload(rm, "pid-1")
    assert _all_keys(p) & _FORBIDDEN == set()
    assert p["band"] == "low"  # top category 75% >= 70
    assert p["category_count"] == 2 and p["top_category"] == "Flexi Cap Fund"
    assert p["top_category_pct"] == 75.0 and p["fund_count"] == 2


# --- PG: the three endpoints end-to-end through the A3 boundary, under RLS -------------------------


async def _seed_user(db_session, email: str) -> str:
    # Block 0.12: these portfolio-analytics routes are now gated on mf_analytics consent;
    # grant it by default so pre-existing fixtures keep exercising the ROUTE logic under
    # test, not the (separately, unit-tested) consent gate itself.
    u = User(email=email, dpdp_consents={"mf_analytics": True})
    db_session.add(u)
    await db_session.flush()
    uid = str(u.id)
    await db_session.commit()
    return uid


async def _seed_fund(db_session, isin: str, sebi_category: str, amc: str) -> None:
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_funds (isin, scheme_name, category, sebi_category, amc_name,"
            " is_segregated) VALUES (:i, :n, 'Equity', :sc, :amc, false) ON CONFLICT (isin) DO NOTHING"
        ),
        {"i": isin, "n": f"Fund {isin}", "sc": sebi_category, "amc": amc},
    )
    # ADR-0039: load_portfolio_read_model's NAV lookup is now bounded to the last 30 days — keep
    # this RECENT so current_nav stays the live NAV (100.0), matching this file's
    # total_value==4000.0 assertions (a fixed calendar date would eventually fall outside the
    # bound and fall back to avg_cost_nav=90.0, giving 3600.0 instead).
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_nav_history (isin, nav_date, nav) VALUES (:i, :d, 100.0)"
            " ON CONFLICT (isin, nav_date) DO NOTHING"
        ),
        {"i": isin, "d": date.today() - timedelta(days=1)},
    )


async def _seed_portfolio_two_funds(db_session, uid: str) -> str:
    """Two holdings: A value 1000 (Large Cap / Alpha AMC), B value 3000 (Flexi Cap / Beta AMC).
    → category split 75/25, AMC split 75/25, top-fund 75% (very_high concentration, low diversification)."""
    pid = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'M2.1') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()
    await _seed_fund(db_session, "INFAAA01AAA1", "Large Cap Fund", "Alpha AMC")
    await _seed_fund(db_session, "INFBBB01BBB2", "Flexi Cap Fund", "Beta AMC")
    for isin, units in (("INFAAA01AAA1", 10.0), ("INFBBB01BBB2", 30.0)):  # value = units × NAV(100)
        await db_session.execute(
            text(
                "INSERT INTO mf.mf_user_holdings (user_id, portfolio_id, isin, folio_number, units,"
                " invested_amount, avg_cost_nav, source, as_of_date) VALUES (:u, :p, :i, '1', :un,"
                " 1000.00, 90.0, 'cas', :d)"
            ),
            {"u": uid, "p": str(pid), "i": isin, "un": units, "d": date(2026, 3, 31)},
        )
    # A score WITH a raw unified_score=88 — it must never reach any analytics response (#2).
    await db_session.execute(
        text(
            "INSERT INTO mf.user_fund_scores (user_id, portfolio_id, isin, unified_score,"
            " confidence_band, verb_label) VALUES (:u, :p, 'INFAAA01AAA1', 88, 'high', 'on_track')"
        ),
        {"u": uid, "p": str(pid)},
    )
    await db_session.commit()
    return str(pid)


def _assert_no_raw_score(env: dict) -> None:
    assert "unified_score" not in _all_keys(env)
    nums = [v for v in _all_values(env) if isinstance(v, (int, float)) and not isinstance(v, bool)]
    assert 88 not in nums, "raw unified_score leaked into an analytics response (#2)"


async def test_allocation_endpoint_value_weighted_no_score(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "m21-alloc@test.dev")
    pid = await _seed_portfolio_two_funds(db_session, uid)
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/allocation", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    env = r.json()
    assert env["status"] == "present" and env["meta"]["content_class"] == "CALCULATED"
    d = env["data"]
    assert d["total_value"] == 4000.0 and d["fund_count"] == 2 and d["by"] == "category"
    weights = {b["bucket"]: b["weight_pct"] for b in d["buckets"]}
    assert weights == {"Flexi Cap Fund": 75.0, "Large Cap Fund": 25.0}
    assert round(sum(b["weight_pct"] for b in d["buckets"]), 2) == 100.0
    _assert_no_raw_score(env)


async def test_allocation_endpoint_by_amc(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "m21-alloc-amc@test.dev")
    pid = await _seed_portfolio_two_funds(db_session, uid)
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/allocation?by=amc", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["by"] == "amc"
    assert {b["bucket"]: b["weight_pct"] for b in d["buckets"]} == {"Beta AMC": 75.0, "Alpha AMC": 25.0}


async def test_concentration_endpoint_top_weights_no_score(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "m21-conc@test.dev")
    pid = await _seed_portfolio_two_funds(db_session, uid)
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/concentration", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    env = r.json()
    assert env["status"] == "present"
    d = env["data"]
    assert d["top_fund"]["weight_pct"] == 75.0 and d["top_fund"]["name"] == "Fund INFBBB01BBB2"
    assert d["top_amc"] == {"name": "Beta AMC", "weight_pct": 75.0}
    assert d["band"] == "very_high" and d["fund_count"] == 2 and d["amc_count"] == 2
    _assert_no_raw_score(env)


async def test_diversification_endpoint_band_only_no_score(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "m21-div@test.dev")
    pid = await _seed_portfolio_two_funds(db_session, uid)
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/diversification", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    env = r.json()
    d = env["data"]
    assert d["band"] == "low" and d["category_count"] == 2  # top category 75% → low diversification
    assert d["top_category"] == "Flexi Cap Fund" and d["top_category_pct"] == 75.0
    _assert_no_raw_score(env)


async def test_m2_1_rls_and_auth(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    a = await _seed_user(db_session, "m21-a@test.dev")
    b = await _seed_user(db_session, "m21-b@test.dev")
    pid_a = await _seed_portfolio_two_funds(db_session, a)
    token_b, _ = create_access_token(b)

    for sub in ("allocation", "concentration", "diversification"):
        path = f"/api/v1/portfolio/{pid_a}/{sub}"
        # B asks for A's portfolio → 404 (IDOR + RLS)
        r = await rls_async_client.get(path, headers=make_auth_headers(access_token=token_b))
        assert r.status_code == 404, f"{path}: {r.status_code}"
        # anonymous → 401
        r2 = await rls_async_client.get(path)
        assert r2.status_code == 401, f"{path}: {r2.status_code}"
