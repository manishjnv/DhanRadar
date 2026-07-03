"""Hide zero-balance (fully-redeemed) holdings from active portfolio views (2026-07-03).

CAS statements list closed folios; the B3 holdings projection writes them as `units <= 0` rows
in `mf_user_holdings`. Industry pattern (Groww/Kuvera/INDmoney): a fully-redeemed position is
hidden from ACTIVE views (holdings/summary/allocation/day-change); its history stays in the
ledger untouched (lifetime XIRR, the future realized-gains view). This covers the ONE seam
(`load_portfolio_read_model` + `load_day_change`, both filter `units > 0`) end-to-end through
the A3 boundary, under RLS — mirrors test_m2_2_portfolio_value_series.py's PG pattern.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from dhanradar.models.auth import User

pytestmark = pytest.mark.integration


async def _seed_user(db_session, email: str) -> str:
    u = User(email=email)
    db_session.add(u)
    await db_session.flush()
    uid = str(u.id)
    await db_session.commit()
    return uid


async def _seed_mixed_portfolio(db_session, uid: str) -> str:
    """One ACTIVE holding (10 units, invested 1000, NAV 100 -> value 1000), one fully-redeemed
    closed folio (units=0, invested 500 — a real CAS artifact) and one negative-units row (a
    ledger-correction artifact, invested 200). Unique ISINs per this file so mf_nav_history rows
    never collide with other test files sharing the session-scoped DB."""
    pid = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'ZB') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()
    for isin, units, invested in (
        ("INFZB0001AAA", 10.0, 1000.0),  # active
        ("INFZB0002BBB", 0.0, 500.0),  # fully redeemed / closed folio
        ("INFZB0003CCC", -2.0, 200.0),  # negative-units artifact
    ):
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
            {"i": isin, "d": date(2026, 6, 30)},
        )
        await db_session.execute(
            text(
                "INSERT INTO mf.mf_user_holdings (user_id, portfolio_id, isin, folio_number, units,"
                " invested_amount, avg_cost_nav, source, as_of_date) VALUES (:u, :p, :i, '1', :un,"
                " :inv, 100.0, 'cas', :d)"
            ),
            {
                "u": uid,
                "p": str(pid),
                "i": isin,
                "un": units,
                "inv": invested,
                "d": date(2026, 6, 30),
            },
        )
    await db_session.commit()
    return str(pid)


async def test_holdings_summary_allocation_hide_zero_and_negative_holdings(
    db_session, rls_async_client
):
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "zb-hide@test.dev")
    pid = await _seed_mixed_portfolio(db_session, uid)
    token, _ = create_access_token(uid)
    headers = make_auth_headers(access_token=token)

    r = await rls_async_client.get(f"/api/v1/portfolio/{pid}/holdings", headers=headers)
    assert r.status_code == 200, r.text
    holdings = r.json()["data"]["holdings"]
    assert [h["isin"] for h in holdings] == ["INFZB0001AAA"], "only the active holding should list"

    r = await rls_async_client.get(f"/api/v1/portfolio/{pid}/summary", headers=headers)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["fund_count"] == 1
    assert d["total_invested"] == 1000.0  # excludes the closed (500) + negative (200) rows
    assert d["total_value"] == 1000.0  # 10 x NAV 100 — active only

    r = await rls_async_client.get(f"/api/v1/portfolio/{pid}/allocation", headers=headers)
    assert r.status_code == 200, r.text
    alloc = r.json()["data"]
    assert alloc["fund_count"] == 1
    assert alloc["total_value"] == 1000.0


async def test_day_change_ignores_zero_and_negative_holdings(db_session, rls_async_client):
    """A second NAV date lands for ALL THREE isins — if the negative-units row leaked into the
    bottom-up sum, day_change would come out to 80 (10x10 - 2x10), not 100; the zero-unit row
    contributes 0 either way, so the negative row is what actually proves the filter is applied,
    not just harmlessly correct on a coincidence."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "zb-daychange@test.dev")
    pid = await _seed_mixed_portfolio(db_session, uid)
    for isin in ("INFZB0001AAA", "INFZB0002BBB", "INFZB0003CCC"):
        await db_session.execute(
            text(
                "INSERT INTO mf.mf_nav_history (isin, nav_date, nav) VALUES (:i, :d, 110.0)"
                " ON CONFLICT (isin, nav_date) DO NOTHING"
            ),
            {"i": isin, "d": date(2026, 7, 1)},
        )
    await db_session.commit()
    token, _ = create_access_token(uid)

    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/summary", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["day_change"] == pytest.approx(100.0, abs=0.01)  # 10 x (110-100), active only
    assert d["day_change_pct"] == pytest.approx(10.0, abs=0.01)
