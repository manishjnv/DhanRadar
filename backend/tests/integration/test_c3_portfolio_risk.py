"""C3 — portfolio Risk Center wired to live data (portfolio.risk free + portfolio.risk_advanced plus).

Pure tests prove the payloads are #2-safe (standard ratios serialize; no DhanRadar composite), the
volatility→band rule, and that the advanced concept serializes for a paid tier (the endpoint delegates to
exactly this). PG tests prove the endpoint end-to-end through the A3 boundary under RLS: the envelope, #2
(a raw unified_score in the DB never appears; the standard ratios DO), the **value-weighted** aggregation,
the tier-gate (advanced → 402 for a free user), and RLS owner-scoping.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from dhanradar.mf.portfolio_read import (
    PortfolioRisk,
    _vol_band,
    risk_advanced_payload,
    risk_payload,
)
from dhanradar.mf.serialization import RequestCtx, serialize_concept
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


def _risk(**kw) -> PortfolioRisk:
    d = dict(
        volatility_pct=15.0, max_drawdown_pct=None, sharpe_ratio=None, sortino_ratio=None,  # B88: deferred
        rolling_1y_avg_pct=12.0, rolling_1y_pct_positive=70.0, fund_count=3, funds_with_metrics=3,
        as_of="2026-03-31",
    )
    d.update(kw)
    return PortfolioRisk(**d)


# --- pure: payloads are #2-safe (standard ratios serialize; no composite) + the band rule ----------


def test_vol_band_thresholds():
    assert _vol_band(None) is None
    assert _vol_band(5.0) == "low"
    assert _vol_band(10.0) == "moderate"
    assert _vol_band(18.0) == "high"
    assert _vol_band(30.0) == "very_high"


def test_risk_payload_standard_ratios_no_composite():
    p = risk_payload(_risk(volatility_pct=15.0), "pid-1")
    keys = _all_keys(p)
    assert {"unified_score", "score", "risk_score", "composite_score", "factor_weights"} & keys == set()
    assert p["risk_band"] == "high" and p["volatility_pct"] == 15.0  # the indicative band + its basis
    assert p["risk_band_basis"] == "average fund volatility"  # B88: indicative, not the true portfolio σ
    assert p["max_drawdown_pct"] is None and p["recovery_months"] is None  # B88-deferred + not built


def test_risk_advanced_payload_ratios_and_unbuilt():
    p = risk_advanced_payload(_risk(), "pid-1")
    assert "unified_score" not in _all_keys(p) and "score" not in _all_keys(p)
    # B88: Sharpe/Sortino (ratios) deferred → None; rolling returns (aggregate by weight) are kept.
    assert p["sharpe_ratio"] is None and p["sortino_ratio"] is None
    assert p["rolling_1y_avg_pct"] == 12.0
    assert p["alpha"] is None and p["beta"] is None  # need a benchmark series → coming soon


def test_advanced_serializes_for_paid_tier():
    """The endpoint's paid path delegates to this: portfolio.risk_advanced is present for a pro caller,
    withheld (tier) for a free caller."""
    p = risk_advanced_payload(_risk(), "pid-1")
    withheld = serialize_concept("portfolio.risk_advanced", p, RequestCtx(tier="free"))
    assert withheld["status"] == "withheld" and withheld["meta"]["reason"] == "tier"
    served = serialize_concept("portfolio.risk_advanced", p, RequestCtx(tier="pro"))
    assert served["status"] == "present" and served["data"]["rolling_1y_avg_pct"] == 12.0


# --- PG: the endpoint end-to-end through the boundary, under RLS -----------------------------------


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


async def _seed_fund(db_session, isin: str, vol: float, sharpe: float) -> None:
    # ADR-0039: load_portfolio_read_model's NAV lookup is now bounded to the last 30 days — a
    # RECENT date keeps current_nav on the live NAV (100.0) instead of falling back to avg_cost_nav.
    recent = date.today() - timedelta(days=1)
    # Global tables → idempotent (the test DB accumulates across tests).
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_funds (isin, scheme_name, category, sebi_category, is_segregated)"
            " VALUES (:i, :n, 'Equity', 'Flexi Cap Fund', false) ON CONFLICT (isin) DO NOTHING"
        ),
        {"i": isin, "n": f"Fund {isin}"},
    )
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_nav_history (isin, nav_date, nav) VALUES (:i, :d, 100.0)"
            " ON CONFLICT (isin, nav_date) DO NOTHING"
        ),
        {"i": isin, "d": recent},
    )
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_fund_metrics (isin, volatility_pct, max_drawdown_pct, sharpe_ratio,"
            " sortino_ratio, rolling_1y_avg_pct, rolling_1y_pct_positive, as_of_date)"
            " VALUES (:i, :v, -30.0, :s, :s, 12.0, 65.0, :d) ON CONFLICT (isin) DO NOTHING"
        ),
        {"i": isin, "v": vol, "s": sharpe, "d": recent},
    )


async def _seed_portfolio_two_funds(db_session, uid: str) -> str:
    """Two holdings: fund A value 1000 (vol 10), fund B value 3000 (vol 20) → value-weighted vol = 17.5."""
    pid = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'Risk') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()
    await _seed_fund(db_session, "INFAAA01AAA1", vol=10.0, sharpe=1.0)
    await _seed_fund(db_session, "INFBBB01BBB2", vol=20.0, sharpe=2.0)
    # value = units × latest NAV (100). A: 10×100=1000, B: 30×100=3000.
    for isin, units in (("INFAAA01AAA1", 10.0), ("INFBBB01BBB2", 30.0)):
        await db_session.execute(
            text(
                "INSERT INTO mf.mf_user_holdings (user_id, portfolio_id, isin, folio_number, units,"
                " invested_amount, avg_cost_nav, source, as_of_date) VALUES (:u, :p, :i, '1', :un,"
                " 1000.00, 90.0, 'cas', :d)"
            ),
            {"u": uid, "p": str(pid), "i": isin, "un": units, "d": date(2026, 3, 31)},
        )
    # A score WITH a raw unified_score=71 — it must never reach the risk response.
    await db_session.execute(
        text(
            "INSERT INTO mf.user_fund_scores (user_id, portfolio_id, isin, unified_score, confidence_band,"
            " verb_label) VALUES (:u, :p, 'INFAAA01AAA1', 71, 'high', 'on_track')"
        ),
        {"u": uid, "p": str(pid)},
    )
    await db_session.commit()
    return str(pid)


async def test_c3_risk_endpoint_value_weighted_no_composite(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "c3@test.dev")
    pid = await _seed_portfolio_two_funds(db_session, uid)
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/risk", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    env = r.json()
    assert env["status"] == "present" and env["meta"]["access_tier"] == "free"
    d = env["data"]
    # value-weighted volatility = (1000×10 + 3000×20) / 4000 = 17.5 → band "high" (INDICATIVE, B88)
    assert abs(d["volatility_pct"] - 17.5) < 1e-6 and d["risk_band"] == "high"
    assert d["risk_band_basis"] == "average fund volatility"  # B88: indicative, not the true portfolio σ
    # B88: Sharpe/Sortino/max-drawdown are deferred (can't average ratios; σ/drawdown need the series).
    assert d["max_drawdown_pct"] is None
    assert d["recovery_months"] is None and d["fund_count"] == 2 and d["funds_with_metrics"] == 2
    # #2: the raw composite (71) never appears, key OR value.
    assert "unified_score" not in _all_keys(env)
    nums = [v for v in _all_values(env) if isinstance(v, (int, float)) and not isinstance(v, bool)]
    assert 71 not in nums, "raw unified_score leaked into the risk response (#2)"


async def test_c3_advanced_402_for_free_user(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "c3-adv@test.dev")
    pid = await _seed_portfolio_two_funds(db_session, uid)
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/risk?advanced=true", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 402, f"{r.status_code}: {r.text}"  # tier-gate = 402 (the FE renders upgrade)


async def test_c3_risk_rls_and_auth(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    a = await _seed_user(db_session, "c3-a@test.dev")
    b = await _seed_user(db_session, "c3-b@test.dev")
    pid_a = await _seed_portfolio_two_funds(db_session, a)
    token_b, _ = create_access_token(b)

    # B asks for A's portfolio → 404 (IDOR + RLS)
    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid_a}/risk", headers=make_auth_headers(access_token=token_b)
    )
    assert r.status_code == 404
    # anonymous → 401
    r2 = await rls_async_client.get(f"/api/v1/portfolio/{pid_a}/risk")
    assert r2.status_code == 401
