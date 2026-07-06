"""Integration test — GET /api/v1/mf/fund/{isin}/people tenure_return_pct (B98 Step 3).

Endpoint: GET /api/v1/mf/fund/{isin}/people
Public — no auth required.

Covered:
  1. Current manager whose start_date is covered by NAV history -> tenure_return_pct
     + tenure_return_as_of computed correctly (return from the NAV on/before
     start_date to the latest NAV — reuses risk.py's `_nav_on_or_before`, no
     new return math).
  2. Current manager whose start_date PRE-DATES all NAV history -> field
     omitted entirely (fail-closed — never fabricated/zeroed).
  3. A departed manager (end_date set) never gets a tenure_return_pct at all
     (only current managers are eligible).
  4. No fund_manager_history rows at all -> managers == [], no crash (existing
     no-suppress behavior unchanged).
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import text

from dhanradar.models.mf import MfFund, MfFundManagerHistory, MfNavHistory

pytestmark = pytest.mark.integration

_TODAY = datetime.date(2026, 6, 21)

_ISIN_A = "INF300P01111"  # start_date covered by NAV history
_ISIN_B = "INF300P02222"  # start_date pre-dates all NAV history
_ISIN_C = "INF300P03333"  # departed manager only
_ISIN_D = "INF300P04444"  # no manager rows at all

_CAT = "Equity Scheme - Flexi Cap Fund"


@pytest.fixture(autouse=True)
async def _truncate_mf(db_session):
    yield
    await db_session.rollback()
    for tbl in ("mf.fund_manager_history", "mf.mf_nav_history", "mf.mf_funds"):
        await db_session.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))
    await db_session.commit()


async def _seed_fund(db_session, isin: str, scheme_name: str) -> None:
    db_session.add(
        MfFund(
            isin=isin,
            scheme_name=scheme_name,
            amc_name="Test AMC Limited",
            sebi_category=_CAT,
            category="Equity",
            plan_type="direct",
            option_type="growth",
            expense_ratio_pct=0.75,
            launch_date=datetime.date(2015, 1, 1),
            is_segregated=False,
        )
    )
    await db_session.flush()


async def test_tenure_return_computed_when_nav_covers_start_date(
    async_client, db_session, patch_redis
):
    await _seed_fund(db_session, _ISIN_A, "Test Covered Fund")
    db_session.add_all(
        [
            MfNavHistory(isin=_ISIN_A, nav_date=datetime.date(2023, 1, 1), nav=100.0),
            MfNavHistory(isin=_ISIN_A, nav_date=_TODAY, nav=150.0),
        ]
    )
    db_session.add(
        MfFundManagerHistory(
            scheme_uid=_ISIN_A,
            manager_name="Priya Sharma",
            start_date=datetime.date(2023, 6, 1),
            end_date=None,
            source="test",
            run_id=1,
        )
    )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/people")
    assert resp.status_code == 200, resp.text
    managers = resp.json()["people"]["data"]["managers"]
    assert len(managers) == 1
    m = managers[0]
    assert m["name"] == "Priya Sharma"
    # NAV on/before 2023-06-01 is the 2023-01-01 point (100.0); latest is 150.0.
    assert m["tenure_return_pct"] == pytest.approx(50.0, abs=0.01)
    assert m["tenure_return_as_of"] == _TODAY.isoformat()


async def test_tenure_return_omitted_when_nav_predates_manager(
    async_client, db_session, patch_redis
):
    await _seed_fund(db_session, _ISIN_B, "Test Uncovered Fund")
    db_session.add(
        MfNavHistory(isin=_ISIN_B, nav_date=_TODAY, nav=150.0),
    )
    db_session.add(
        MfFundManagerHistory(
            scheme_uid=_ISIN_B,
            manager_name="Rahul Mehta",
            start_date=datetime.date(2015, 6, 1),  # before the only NAV point on record
            end_date=None,
            source="test",
            run_id=1,
        )
    )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_B}/people")
    assert resp.status_code == 200, resp.text
    m = resp.json()["people"]["data"]["managers"][0]
    assert "tenure_return_pct" not in m
    assert "tenure_return_as_of" not in m


async def test_departed_manager_never_gets_tenure_return(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_C, "Test Departed Fund")
    db_session.add(
        MfNavHistory(isin=_ISIN_C, nav_date=_TODAY, nav=150.0),
    )
    db_session.add(
        MfFundManagerHistory(
            scheme_uid=_ISIN_C,
            manager_name="Departed Manager",
            start_date=datetime.date(2018, 1, 1),
            end_date=datetime.date(2022, 1, 1),
            source="test",
            run_id=1,
        )
    )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_C}/people")
    assert resp.status_code == 200, resp.text
    assert resp.json()["people"]["data"]["managers"] == []


async def test_no_manager_rows_returns_empty_managers(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_D, "Test No Manager Fund")
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_D}/people")
    assert resp.status_code == 200, resp.text
    assert resp.json()["people"]["data"]["managers"] == []
