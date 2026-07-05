"""Integration tests for the W2 fund-changes endpoint
(FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §10.6, §17 W2).

  GET /api/v1/mf/fund/{isin}/events

Same infrastructure contract as test_fund_w1_endpoints.py (async_client / db_session /
patch_redis). Public — no auth required (current_user_or_anonymous).
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import text

from dhanradar.models.mf import MfFund, MfFundEvent

pytestmark = pytest.mark.integration

_ISIN_A = "INF200K01884"
_ISIN_UNKNOWN = "INF000U00000"  # valid ISIN shape, never seeded


@pytest.fixture(autouse=True)
async def _truncate_mf(db_session):
    yield
    await db_session.rollback()
    for tbl in ("mf.mf_fund_events", "mf.mf_funds"):
        await db_session.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))
    await db_session.commit()


async def _seed_fund(db_session, isin: str) -> None:
    db_session.add(
        MfFund(
            isin=isin,
            scheme_name=f"Fund {isin}",
            amc_name="HDFC Asset Management Company Limited",
            sebi_category="Equity Scheme - Flexi Cap Fund",
            category="Equity",
            plan_type="direct",
            option_type="growth",
            is_segregated=False,
        )
    )
    await db_session.flush()


async def test_fund_events_happy_path_newest_first(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_A)
    db_session.add(
        MfFundEvent(
            isin=_ISIN_A,
            event_type="rank_change",
            as_of=datetime.date(2026, 6, 1),
            payload={"old_rank": 24, "new_rank": 18, "total": 183, "direction": "up"},
        )
    )
    db_session.add(
        MfFundEvent(
            isin=_ISIN_A,
            event_type="ter_change",
            as_of=datetime.date(2026, 6, 15),
            payload={"old_ter": 0.68, "new_ter": 0.62, "effective_date": "2026-06-15"},
        )
    )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/events")
    assert resp.status_code == 200, resp.text
    env = resp.json()
    assert env["status"] == "present"
    events = env["data"]["events"]
    assert len(events) == 2
    # newest as_of first
    assert events[0]["event_type"] == "ter_change"
    assert events[0]["as_of"] == "2026-06-15"
    assert events[0]["summary"] == "Expense ratio changed from 0.68% to 0.62%."
    assert events[1]["event_type"] == "rank_change"
    assert events[1]["summary"] == "Category rank moved from 24 to 18 of 183."
    assert env["meta"]["as_of"] == "2026-06-15"


async def test_fund_events_empty_honest_state_200(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_A)
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/events")
    assert resp.status_code == 200, resp.text
    d = resp.json()["data"]
    assert d["events"] == []


async def test_fund_events_unknown_isin_404(async_client, db_session, patch_redis):
    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_UNKNOWN}/events")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "fund_not_found"


async def test_fund_events_no_forbidden_keys(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_A)
    db_session.add(
        MfFundEvent(
            isin=_ISIN_A,
            event_type="holding_change",
            as_of=datetime.date(2026, 6, 1),
            payload={"name": "HDFC Bank", "old_weight_pct": 6.1, "new_weight_pct": 7.4},
        )
    )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/events")
    assert resp.status_code == 200
    assert "unified_score" not in resp.text
    assert '"score"' not in resp.text
