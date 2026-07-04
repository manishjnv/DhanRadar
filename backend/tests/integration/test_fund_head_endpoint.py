"""Integration tests for GET /api/v1/mf/fund/{isin} (`fund.head`, W0).

Endpoint: GET /api/v1/mf/fund/{isin}
Public — no auth required (current_user_or_anonymous), same rate limiter as the explorer.

Infrastructure contract (same as test_mf_search / test_dashboard / test_changes):
  - async_client — httpx.AsyncClient over ASGITransport(app); no lifespan.
  - db_session   — function-scoped AsyncSession.
  - patch_redis  — fakeredis.aioredis.FakeRedis (rate limiter reads it).

Covered:
  1. Fully seeded fund (rank + metrics + 2 NAVs) → 200, present envelope, real fields.
  2. Unknown ISIN → 404 problem+json (fund_not_found).
  3. No unified_score / raw score anywhere in the serialized body (non-neg #2).
  4. Young fund (nav_points < 252) → return_1y_pct suppressed (young-fund guard).
  5. Unranked fund (no mf_fund_ranks row) → 200, verb_label/category_rank null.
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import text

from dhanradar.models.mf import MfFund, MfFundMetrics, MfFundRanks, MfNavHistory

pytestmark = pytest.mark.integration

_TODAY = datetime.date(2026, 6, 21)
_YESTERDAY = _TODAY - datetime.timedelta(days=1)

_ISIN_FULL = "INF200K01884"  # ranked, metrics-warm, 2 NAV rows
_ISIN_UNRANKED = "INF209K01YD4"  # metrics-warm, NO rank row
_ISIN_YOUNG = "INF179K01VY7"  # ranked, nav_points below the 1Y guard
_ISIN_UNKNOWN = "INF000U00000"  # valid ISIN shape, never seeded

_CAT = "Equity Scheme - Flexi Cap Fund"


@pytest.fixture(autouse=True)
async def _truncate_mf(db_session):
    """Truncate the tables this endpoint reads, after each test."""
    yield
    await db_session.rollback()
    for tbl in ("mf.mf_fund_metrics", "mf.mf_nav_history", "mf.mf_fund_ranks", "mf.mf_funds"):
        await db_session.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))
    await db_session.commit()


async def _seed_full_fund(db_session) -> None:
    db_session.add(
        MfFund(
            isin=_ISIN_FULL,
            scheme_name="HDFC Flexi Cap Fund",
            amc_name="HDFC Asset Management Company Limited",
            sebi_category=_CAT,
            category="Equity",
            plan_type="direct",
            option_type="growth",
            expense_ratio_pct=0.750,
            launch_date=datetime.date(2010, 1, 1),
            is_segregated=False,
        )
    )
    await db_session.flush()
    db_session.add(
        MfFundRanks(
            isin=_ISIN_FULL,
            as_of_date=_TODAY,
            sebi_category=_CAT,
            rank=3,
            total_in_cat=50,
            verb_label="on_track",
        )
    )
    db_session.add(
        MfFundMetrics(
            isin=_ISIN_FULL,
            return_3m_pct=2.1,
            return_6m_pct=5.0,
            return_1y_pct=12.5,
            return_3y_pct=15.0,
            return_5y_pct=18.0,
            nav_points=300,
            as_of_date=_TODAY,
        )
    )
    db_session.add(MfNavHistory(isin=_ISIN_FULL, nav_date=_YESTERDAY, nav=100.0))
    db_session.add(MfNavHistory(isin=_ISIN_FULL, nav_date=_TODAY, nav=105.0))
    await db_session.commit()


async def test_fund_head_full_seed_present_envelope(async_client, db_session, patch_redis):
    await _seed_full_fund(db_session)

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_FULL}")
    assert resp.status_code == 200, resp.text

    env = resp.json()
    assert env["status"] == "present"
    assert env["meta"]["visibility_class"] == "educational"
    d = env["data"]
    assert d["verb_label"] == "on_track"
    assert d["category_rank"] == 3 and d["category_total"] == 50
    assert d["nav_latest"] == 105.0
    assert d["nav_date"] == _TODAY.isoformat()
    assert d["return_1y_pct"] == 12.5
    assert round(d["nav_change_pct"], 2) == 5.0


async def test_fund_head_unknown_isin_404(async_client, db_session, patch_redis):
    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_UNKNOWN}")
    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"] == "fund_not_found"
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_fund_head_no_score_leak(async_client, db_session, patch_redis):
    await _seed_full_fund(db_session)

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_FULL}")
    assert resp.status_code == 200
    assert "unified_score" not in resp.text
    assert '"score"' not in resp.text


async def test_fund_head_young_fund_suppresses_1y_return(async_client, db_session, patch_redis):
    db_session.add(
        MfFund(
            isin=_ISIN_YOUNG,
            scheme_name="New Launch Small Cap Fund",
            sebi_category=_CAT,
            is_segregated=False,
        )
    )
    await db_session.flush()
    db_session.add(
        MfFundMetrics(
            isin=_ISIN_YOUNG,
            return_1y_pct=9.0,
            nav_points=100,  # below _MIN_NAV_POINTS_1Y (252)
            as_of_date=_TODAY,
        )
    )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_YOUNG}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["return_1y_pct"] is None


async def test_fund_head_unranked_fund_null_verb_label(async_client, db_session, patch_redis):
    db_session.add(
        MfFund(
            isin=_ISIN_UNRANKED,
            scheme_name="Axis Flexi Cap Fund",
            sebi_category=_CAT,
            is_segregated=False,
        )
    )
    await db_session.flush()
    db_session.add(
        MfFundMetrics(isin=_ISIN_UNRANKED, return_1y_pct=8.0, nav_points=300, as_of_date=_TODAY)
    )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_UNRANKED}")
    assert resp.status_code == 200, resp.text
    d = resp.json()["data"]
    assert d["verb_label"] is None
    assert d["category_rank"] is None
