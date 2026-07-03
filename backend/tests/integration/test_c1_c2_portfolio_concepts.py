"""C1 (holdings.list enrichment) + C2 (portfolio.summary) + B86 (one invested definition).

Pure tests prove the #2-safe payload builders, the confidence-band rule, and the B86 snapshot unification
(no PG). PG tests prove both endpoints end-to-end through the A3 boundary under RLS: the envelope shape,
#2 (a raw unified_score in the DB never reaches the response — key OR value), RLS owner-scoping, and that
`invested` is the ledger net-invested everywhere (holdings == summary == the seeded table value).
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from dhanradar.mf.cas import ParsedHolding
from dhanradar.mf.portfolio_read import (
    EnrichedHolding,
    PortfolioReadModel,
    _portfolio_confidence_band,
    holdings_payload,
    summary_payload,
)
from dhanradar.models.auth import User
from dhanradar.tasks.mf import parsed_to_snapshot_holdings

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
        label="on_track", confidence_band="high", as_of="2026-03-31",
    )
    d.update(kw)
    return EnrichedHolding(**d)


# --- pure: payload builders are #2-safe + carry only the educational outputs --------------------


def test_holdings_payload_safe_fields_no_score():
    rm = PortfolioReadModel(holdings=[_holding()], total_invested=1000.0, total_value=1200.0,
                            xirr_pct=18.5, as_of="2026-03-31")
    p = holdings_payload(rm, "pid-1")
    keys = _all_keys(p)
    assert "unified_score" not in keys and "score" not in keys and "factor_weights" not in keys
    h = p["holdings"][0]
    assert h["scheme_name"] == "X Fund" and h["category"] == "Flexi Cap Fund"
    assert h["label"] == "on_track" and h["confidence_band"] == "high"
    assert h["invested_amount"] == 1000.0 and h["current_value"] == 1200.0  # user's own numbers


def test_summary_payload_facts_band_no_score():
    rm = PortfolioReadModel(
        holdings=[_holding(confidence_band="high"), _holding(isin="INF2", confidence_band="medium")],
        total_invested=2000.0, total_value=2600.0, xirr_pct=None, as_of="2026-03-31",
    )
    # xirr_pct is now passed in explicitly (CAMS-parity: the ledger-based number, not rm.xirr_pct —
    # the stale upload-time snapshot the summary no longer reads).
    p = summary_payload(rm, "pid-1", xirr_pct=21.0)
    assert "unified_score" not in _all_keys(p) and "score" not in _all_keys(p)
    assert p["total_value"] == 2600.0 and p["total_invested"] == 2000.0
    assert p["gain"] == 600.0 and round(p["gain_pct"], 1) == 30.0
    assert p["xirr_pct"] == 21.0 and p["fund_count"] == 2 and p["funds_scored"] == 2
    assert p["confidence_band"] == "medium"  # high + medium → medium (conservative aggregate)
    assert p["cost_value"] == 2000.0  # no reinvested cost passed → equals total_invested
    assert p["wt_avg_days"] is None  # not passed → default None


def test_confidence_band_rule():
    assert _portfolio_confidence_band([]) is None
    assert _portfolio_confidence_band(["high", "high"]) == "high"
    assert _portfolio_confidence_band(["high", "low"]) == "low"  # any low → low
    assert _portfolio_confidence_band(["high", "medium"]) == "medium"


def test_summary_gain_pct_none_when_no_invested():
    rm = PortfolioReadModel(holdings=[], total_invested=0.0, total_value=0.0, xirr_pct=None, as_of=None)
    p = summary_payload(rm, "pid-1")
    assert p["gain_pct"] is None and p["fund_count"] == 0 and p["confidence_band"] is None


# --- pure: B86 — the fresh-report snapshot uses ledger net-invested, not the CAS cost ----------


def test_b86_snapshot_uses_net_invested_over_cas_cost():
    p = ParsedHolding(
        isin="INF001", amfi_code=None, scheme_name="X", folio_number="F1",
        units=10.0, nav=50.0, value=550.0, cost=1000.0, as_of_date=date(2026, 3, 31), txns=[],
    )
    # No invested_map → legacy fallback to the CAS-reported cost.
    [legacy] = parsed_to_snapshot_holdings([p])
    assert legacy.invested_amount == 1000.0
    # With the projected net-invested map (B86) → the ledger value wins; the holdings table, the rebuild
    # report and the fresh report now all agree on one invested definition.
    [unified] = parsed_to_snapshot_holdings([p], invested_map={("INF001", "F1"): 700.0})
    assert unified.invested_amount == 700.0


# --- PG: both endpoints end-to-end through the A3 boundary, under RLS --------------------------


async def _seed_user(db_session, email: str) -> str:
    u = User(email=email)
    db_session.add(u)
    await db_session.flush()
    uid = str(u.id)
    await db_session.commit()
    return uid


async def _seed_portfolio_with_holding(db_session, uid: str) -> str:
    pid = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'C') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_funds (isin, scheme_name, category, sebi_category, is_segregated)"
            " VALUES ('INF200K01VT2', 'Parag Parikh Flexi Cap', 'Equity', 'Flexi Cap Fund', false)"
            " ON CONFLICT (isin) DO NOTHING"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_nav_history (isin, nav_date, nav) VALUES ('INF200K01VT2', :d, 120.0)"
            " ON CONFLICT (isin, nav_date) DO NOTHING"
        ),
        {"d": date(2026, 3, 31)},
    )
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_user_holdings (user_id, portfolio_id, isin, folio_number, units,"
            " invested_amount, avg_cost_nav, source, as_of_date) VALUES (:u, :p, 'INF200K01VT2', '777',"
            " 10.5, 1000.00, 95.0, 'cas', :d)"
        ),
        {"u": uid, "p": str(pid), "d": date(2026, 3, 31)},
    )
    # A score WITH a raw unified_score=87 — it must never reach either response.
    await db_session.execute(
        text(
            "INSERT INTO mf.user_fund_scores (user_id, portfolio_id, isin, unified_score,"
            " confidence_band, verb_label) VALUES (:u, :p, 'INF200K01VT2', 87, 'high', 'on_track')"
        ),
        {"u": uid, "p": str(pid)},
    )
    await db_session.commit()
    return str(pid)


async def test_c1_holdings_endpoint_enriched_no_score(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "c1@test.dev")
    pid = await _seed_portfolio_with_holding(db_session, uid)
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/holdings", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    env = r.json()
    assert env["status"] == "present" and env["meta"]["content_class"] == "PERSONAL"
    h = env["data"]["holdings"][0]
    assert h["scheme_name"] == "Parag Parikh Flexi Cap" and h["category"] == "Flexi Cap Fund"
    assert h["units"] == 10.5 and h["invested_amount"] == 1000.0  # net-invested (B86)
    assert h["current_value"] == 10.5 * 120.0  # units × latest NAV, not avg_cost_nav
    assert h["label"] == "on_track" and h["confidence_band"] == "high"
    # #2: no raw score, key OR value.
    assert "unified_score" not in _all_keys(env)
    nums = [v for v in _all_values(env) if isinstance(v, (int, float)) and not isinstance(v, bool)]
    assert 87 not in nums, "raw unified_score leaked into holdings (#2)"


async def test_c2_summary_endpoint_facts_band_no_score(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "c2@test.dev")
    pid = await _seed_portfolio_with_holding(db_session, uid)
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/summary", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    env = r.json()
    assert env["status"] == "present" and env["meta"]["visibility_class"] == "educational"
    d = env["data"]
    assert d["total_invested"] == 1000.0  # net-invested (B86) — matches the holdings concept
    assert d["total_value"] == 10.5 * 120.0
    assert d["gain"] == 10.5 * 120.0 - 1000.0 and d["confidence_band"] == "high"
    assert d["fund_count"] == 1
    # #2: no raw score anywhere.
    assert "unified_score" not in _all_keys(env)
    nums = [v for v in _all_values(env) if isinstance(v, (int, float)) and not isinstance(v, bool)]
    assert 87 not in nums, "raw unified_score leaked into summary (#2)"


async def test_c1_c2_rls_and_auth(db_session, rls_async_client):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    a = await _seed_user(db_session, "c-a@test.dev")
    b = await _seed_user(db_session, "c-b@test.dev")
    pid_a = await _seed_portfolio_with_holding(db_session, a)
    token_b, _ = create_access_token(b)

    for path in (f"/api/v1/portfolio/{pid_a}/holdings", f"/api/v1/portfolio/{pid_a}/summary"):
        # B asks for A's portfolio → 404 (IDOR + RLS)
        r = await rls_async_client.get(path, headers=make_auth_headers(access_token=token_b))
        assert r.status_code == 404, f"{path}: {r.status_code}"
        # anonymous → 401
        r2 = await rls_async_client.get(path)
        assert r2.status_code == 401, f"{path}: {r2.status_code}"
