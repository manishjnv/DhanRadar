"""Integration tests for the W1 fund-detail endpoints
(FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §5 rows 10/12/13/15/16/19/20, §17 W1).

Endpoints:
  GET /api/v1/mf/fund/{isin}/nav?range=...
  GET /api/v1/mf/fund/{isin}/analytics
  GET /api/v1/mf/fund/{isin}/composition
  GET /api/v1/mf/fund/{isin}/people
  GET /api/v1/mf/fund/{isin}/peers

Same infrastructure contract as test_fund_head_endpoint.py (async_client / db_session /
patch_redis). Public — no auth required (current_user_or_anonymous).
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import text

from dhanradar.models.mf import (
    MfCategoryStats,
    MfFund,
    MfFundConstituent,
    MfFundManagerHistory,
    MfFundMetrics,
    MfFundRanks,
    MfNavHistory,
)

pytestmark = pytest.mark.integration

_TODAY = datetime.date(2026, 6, 21)
_CAT = "Equity Scheme - Flexi Cap Fund"

_ISIN_A = "INF200K01884"  # the fund under test
_ISIN_B = "INF209K01YD4"  # category peer, higher volatility
_ISIN_C = "INF179K01VY7"  # category peer, lower volatility
_ISIN_UNKNOWN = "INF000U00000"  # valid ISIN shape, never seeded


@pytest.fixture(autouse=True)
async def _truncate_mf(db_session):
    """Truncate every table the W1 endpoints read, after each test."""
    yield
    await db_session.rollback()
    for tbl in (
        "mf.mf_fund_constituents",
        "mf.fund_manager_history",
        "mf.mf_category_stats",
        "mf.mf_fund_metrics",
        "mf.mf_nav_history",
        "mf.mf_fund_ranks",
        "mf.mf_funds",
    ):
        await db_session.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))
    await db_session.commit()


async def _seed_fund(
    db_session, isin: str, *, amc: str = "HDFC Asset Management Company Limited"
) -> None:
    db_session.add(
        MfFund(
            isin=isin,
            scheme_name=f"Fund {isin}",
            amc_name=amc,
            sebi_category=_CAT,
            category="Equity",
            plan_type="direct",
            option_type="growth",
            expense_ratio_pct=0.75,
            is_segregated=False,
        )
    )
    await db_session.flush()


# ---------------------------------------------------------------------------
# GET /fund/{isin}/nav
# ---------------------------------------------------------------------------


async def test_fund_nav_happy_path(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_A)
    for i in range(5):
        db_session.add(
            MfNavHistory(
                isin=_ISIN_A, nav_date=_TODAY - datetime.timedelta(days=4 - i), nav=100.0 + i
            )
        )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/nav?range=1y")
    assert resp.status_code == 200, resp.text
    env = resp.json()
    assert env["status"] == "present"
    d = env["data"]
    assert d["range"] == "1y"
    assert d["n_total"] == 5
    assert len(d["points"]) == 5
    assert d["points"][-1]["nav"] == 104.0
    assert d["to"] == _TODAY.isoformat()


async def test_fund_nav_downsample_keeps_last_point(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_A)
    # 900 daily rows, well over the 400-point cap — stride = ceil(900/400) = 3.
    start = _TODAY - datetime.timedelta(days=899)
    for i in range(900):
        db_session.add(
            MfNavHistory(
                isin=_ISIN_A, nav_date=start + datetime.timedelta(days=i), nav=100.0 + i * 0.01
            )
        )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/nav?range=max")
    assert resp.status_code == 200, resp.text
    d = resp.json()["data"]
    assert d["n_total"] == 900
    assert len(d["points"]) <= 400
    # the last raw NAV point must always be present, regardless of stride
    assert d["points"][-1]["d"] == _TODAY.isoformat()
    assert d["to"] == _TODAY.isoformat()


async def test_fund_nav_unknown_isin_404(async_client, db_session, patch_redis):
    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_UNKNOWN}/nav")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "fund_not_found"


async def test_fund_nav_no_history_empty_200(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_A)
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/nav")
    assert resp.status_code == 200, resp.text
    d = resp.json()["data"]
    assert d["points"] == []
    assert d["n_total"] == 0
    assert d["from"] is None and d["to"] is None


# ---------------------------------------------------------------------------
# GET /fund/{isin}/analytics  (analytics + rank_history)
# ---------------------------------------------------------------------------


async def test_fund_analytics_volatility_percentile_ordering(async_client, db_session, patch_redis):
    """3 funds, same category: highest vol -> highest percentile, lowest -> lowest."""
    await _seed_fund(db_session, _ISIN_A)
    await _seed_fund(db_session, _ISIN_B)
    await _seed_fund(db_session, _ISIN_C)

    for isin, rank in ((_ISIN_A, 2), (_ISIN_B, 1), (_ISIN_C, 3)):
        db_session.add(
            MfFundRanks(
                isin=isin,
                as_of_date=_TODAY,
                sebi_category=_CAT,
                rank=rank,
                total_in_cat=3,
                verb_label="on_track",
            )
        )
    db_session.add(
        MfFundMetrics(isin=_ISIN_A, nav_points=300, as_of_date=_TODAY, volatility_pct=15.0)
    )
    db_session.add(
        MfFundMetrics(isin=_ISIN_B, nav_points=300, as_of_date=_TODAY, volatility_pct=25.0)
    )
    db_session.add(
        MfFundMetrics(isin=_ISIN_C, nav_points=300, as_of_date=_TODAY, volatility_pct=5.0)
    )
    db_session.add(
        MfCategoryStats(
            sebi_category=_CAT,
            metric_key="return_1y_pct",
            as_of=_TODAY,
            p25=8.0,
            p50=10.0,
            p75=12.0,
            p90=15.0,
        )
    )
    await db_session.commit()

    resp_a = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/analytics")
    resp_b = await async_client.get(f"/api/v1/mf/fund/{_ISIN_B}/analytics")
    resp_c = await async_client.get(f"/api/v1/mf/fund/{_ISIN_C}/analytics")
    assert resp_a.status_code == resp_b.status_code == resp_c.status_code == 200

    pct_a = resp_a.json()["analytics"]["data"]["volatility_percentile"]
    pct_b = resp_b.json()["analytics"]["data"]["volatility_percentile"]
    pct_c = resp_c.json()["analytics"]["data"]["volatility_percentile"]
    # B (highest vol) > A (middle) > C (lowest vol)
    assert pct_b > pct_a > pct_c
    assert pct_c == 0.0
    assert pct_b == 100.0

    cat_pcts = resp_a.json()["analytics"]["data"]["category_percentiles"]
    assert cat_pcts["return_1y_pct"] == {"p25": 8.0, "p50": 10.0, "p75": 12.0, "p90": 15.0}
    assert "max_drawdown_pct" not in cat_pcts  # never seeded — omitted, not null


async def test_fund_analytics_no_metrics_null_shape(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_A)
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/analytics")
    assert resp.status_code == 200, resp.text
    d = resp.json()["analytics"]["data"]
    assert d["sharpe_ratio"] is None
    assert d["volatility_percentile"] is None
    assert d["category_percentiles"] == {}
    assert resp.json()["rank_history"]["data"]["points"] == []


async def test_fund_analytics_unknown_isin_404(async_client, db_session, patch_redis):
    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_UNKNOWN}/analytics")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "fund_not_found"


async def test_fund_analytics_no_score_leak(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_A)
    db_session.add(
        MfFundMetrics(
            isin=_ISIN_A, nav_points=300, as_of_date=_TODAY, sharpe_ratio=1.1, volatility_pct=12.0
        )
    )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/analytics")
    assert resp.status_code == 200
    assert "unified_score" not in resp.text
    assert '"score"' not in resp.text


# ---------------------------------------------------------------------------
# GET /fund/{isin}/composition
# ---------------------------------------------------------------------------


async def test_fund_composition_happy_path(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_A)
    month = datetime.date(2026, 5, 1)
    db_session.add(
        MfFundConstituent(
            isin=_ISIN_A,
            constituent_name="Reliance Industries",
            as_of_month=month,
            sector="Energy",
            weight_pct=8.5,
            source_amc="hdfc",
        )
    )
    db_session.add(
        MfFundConstituent(
            isin=_ISIN_A,
            constituent_name="HDFC Bank",
            as_of_month=month,
            sector="Financials",
            weight_pct=6.2,
            source_amc="hdfc",
        )
    )
    db_session.add(
        MfFundConstituent(
            isin=_ISIN_A,
            constituent_name="ICICI Bank",
            as_of_month=month,
            sector="Financials",
            weight_pct=5.1,
            source_amc="hdfc",
        )
    )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/composition")
    assert resp.status_code == 200, resp.text
    d = resp.json()["data"]
    assert [h["name"] for h in d["holdings"]] == ["Reliance Industries", "HDFC Bank", "ICICI Bank"]
    sectors = {s["name"]: s["weight_pct"] for s in d["sectors"]}
    assert sectors["Financials"] == 11.3
    assert sectors["Energy"] == 8.5
    assert d["as_of_month"] == month.isoformat()
    assert d["coverage"]["holdings_count"] == 3


async def test_fund_composition_uncovered_amc_empty_200(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_A, amc="Some Uncovered AMC")
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/composition")
    assert resp.status_code == 200, resp.text
    d = resp.json()["data"]
    assert d == {
        "holdings": [],
        "sectors": [],
        "as_of_month": None,
        "coverage": {"holdings_count": 0, "weight_covered_pct": None},
    }


async def test_fund_composition_unknown_isin_404(async_client, db_session, patch_redis):
    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_UNKNOWN}/composition")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /fund/{isin}/people  (people + amc)
# ---------------------------------------------------------------------------


async def test_fund_people_happy_path(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_A)
    await _seed_fund(db_session, _ISIN_B)  # same AMC — bumps scheme_count
    db_session.add(
        MfFundManagerHistory(
            scheme_uid=_ISIN_A,
            manager_name="Chirag Setalvad",
            start_date=datetime.date(2015, 1, 1),
            end_date=None,
            source="factsheet",
        )
    )
    db_session.add(
        MfFundManagerHistory(
            scheme_uid=_ISIN_A,
            manager_name="Prior Manager",
            start_date=datetime.date(2010, 1, 1),
            end_date=datetime.date(2014, 12, 31),
            source="factsheet",
        )
    )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/people")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    people = body["people"]["data"]
    assert len(people["managers"]) == 1
    assert people["managers"][0]["name"] == "Chirag Setalvad"
    assert people["manager_changes_5y"] == 0  # prior manager's end_date is >5y ago

    amc = body["amc"]["data"]
    assert amc["amc_name"] == "HDFC Asset Management Company Limited"
    assert amc["scheme_count"] == 2
    assert amc["category_count"] == 1


async def test_fund_people_uncovered_amc_empty_managers_200(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_A, amc="Some Uncovered AMC")
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/people")
    assert resp.status_code == 200, resp.text
    people = resp.json()["people"]["data"]
    assert people["managers"] == []
    assert people["manager_changes_5y"] == 0


async def test_fund_people_unknown_isin_404(async_client, db_session, patch_redis):
    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_UNKNOWN}/people")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /fund/{isin}/peers
# ---------------------------------------------------------------------------


async def test_fund_peers_excludes_self_and_segregated_caps_eight(
    async_client, db_session, patch_redis
):
    await _seed_fund(db_session, _ISIN_A)
    # rank=11 is deliberately outside the 1..10 peer range below — avoids a rank collision
    # with a peer (mf_fund_ranks.rank is not unique in this fixture; a collision would make
    # the abs(rank-diff) tie-break ambiguous and flake the "excludes self" assertion).
    db_session.add(
        MfFundRanks(
            isin=_ISIN_A,
            as_of_date=_TODAY,
            sebi_category=_CAT,
            rank=11,
            total_in_cat=12,
            verb_label="on_track",
        )
    )

    # 10 more funds in the same category + as_of_date; one is segregated (must be excluded).
    for i in range(10):
        isin = f"INF999K0{i:04d}"
        db_session.add(
            MfFund(
                isin=isin,
                scheme_name=f"Peer {i}",
                amc_name="Peer AMC",
                sebi_category=_CAT,
                is_segregated=(i == 9),
            )
        )
        await db_session.flush()
        db_session.add(
            MfFundRanks(
                isin=isin,
                as_of_date=_TODAY,
                sebi_category=_CAT,
                rank=i + 1,
                total_in_cat=12,
                verb_label="on_track",
            )
        )
        db_session.add(
            MfFundMetrics(isin=isin, nav_points=300, as_of_date=_TODAY, return_1y_pct=10.0 + i)
        )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/peers")
    assert resp.status_code == 200, resp.text
    peers = resp.json()["data"]["peers"]
    assert len(peers) == 8  # capped
    assert all(p["isin"] != _ISIN_A for p in peers)
    assert "INF999K00009" not in {
        p["isin"] for p in peers
    }  # segregated peer (i=9, rank 10) excluded


async def test_fund_peers_unranked_fund_empty_200(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_A)
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/peers")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["peers"] == []


async def test_fund_peers_unknown_isin_404(async_client, db_session, patch_redis):
    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_UNKNOWN}/peers")
    assert resp.status_code == 404
