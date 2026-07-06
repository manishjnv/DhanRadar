"""Integration tests for the W1 fund-detail endpoints
(FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §5 rows 10/12/13/15/16/19/20, §17 W1).

Endpoints:
  GET /api/v1/mf/fund/{isin}/nav?range=...
  GET /api/v1/mf/fund/{isin}/analytics
  GET /api/v1/mf/fund/{isin}/composition
  GET /api/v1/mf/fund/{isin}/people
  GET /api/v1/mf/fund/{isin}/peers
  GET /api/v1/mf/fund/{isin}/factors  (W2, §10.1 — the second scored concept)

Same infrastructure contract as test_fund_head_endpoint.py (async_client / db_session /
patch_redis). Public — no auth required (current_user_or_anonymous).
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import text

from dhanradar.models.mf import (
    MfCategoryFlows,
    MfCategoryStats,
    MfFund,
    MfFundConstituent,
    MfFundManagerHistory,
    MfFundMetrics,
    MfFundRanks,
    MfNavHistory,
    MfStockCapClassification,
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
        "mf.stock_cap_classification",
        "mf.mf_category_flows",
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
            constituent_isin="INE002A01018",
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
            constituent_isin="INE040A01034",
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
            constituent_isin="INE090A01021",  # deliberately NOT in stock_cap_classification
            sector="Financials",
            weight_pct=5.1,
            source_amc="hdfc",
        )
    )
    db_session.add(
        MfStockCapClassification(
            stock_isin="INE002A01018",
            stock_name="Reliance Industries",
            cap_class="Large Cap",
            effective_period="2026H1",
            source_url="https://example.test/amfi.xlsx",
        )
    )
    db_session.add(
        MfStockCapClassification(
            stock_isin="INE040A01034",
            stock_name="HDFC Bank",
            cap_class="Large Cap",
            effective_period="2026H1",
            source_url="https://example.test/amfi.xlsx",
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
    # cap_mix: Reliance (8.5) + HDFC Bank (6.2) classified Large Cap; ICICI Bank (5.1)
    # has an equity ISIN but no classification row -> unclassified. Sums to 19.8
    # (the top-holdings weight), never renormalized to 100.
    assert d["cap_mix"] == {
        "large_pct": 14.7,
        "mid_pct": 0.0,
        "small_pct": 0.0,
        "unclassified_pct": 5.1,
        "basis": "top_holdings_weight",
        "as_of_period": "2026H1",
    }


async def test_fund_composition_over_covered_returns_null_weight_pct(
    async_client, db_session, patch_redis
):
    """Data-quality guard (docs/rca/README.md, INF789F01WY2 incident): if garbage
    rows still get weight_pct summing past 105%, report null coverage rather than
    a wrong number — holdings_count still reflects the actual row count."""
    await _seed_fund(db_session, _ISIN_A)
    month = datetime.date(2026, 5, 1)
    db_session.add(
        MfFundConstituent(
            isin=_ISIN_A,
            constituent_name="(a)  Listed/awaiting listing on Stock Exchanges",
            as_of_month=month,
            weight_pct=60.0,
            source_amc="uti",
        )
    )
    db_session.add(
        MfFundConstituent(
            isin=_ISIN_A,
            constituent_name="ABB India Ltd.",
            as_of_month=month,
            sector="Capital Goods",
            weight_pct=50.0,
            source_amc="uti",
        )
    )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/composition")
    assert resp.status_code == 200, resp.text
    d = resp.json()["data"]
    assert d["coverage"]["holdings_count"] == 2
    assert d["coverage"]["weight_covered_pct"] is None


async def test_fund_composition_uncovered_amc_empty_200(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_A, amc="Some Uncovered AMC")
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/composition")
    assert resp.status_code == 200, resp.text
    d = resp.json()["data"]
    assert d == {
        "holdings": [],
        "sectors": [],
        "cap_mix": {
            "large_pct": None,
            "mid_pct": None,
            "small_pct": None,
            "unclassified_pct": None,
            "basis": "top_holdings_weight",
            "as_of_period": None,
        },
        "as_of_month": None,
        "coverage": {"holdings_count": 0, "weight_covered_pct": None},
    }


async def test_fund_composition_unknown_isin_404(async_client, db_session, patch_redis):
    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_UNKNOWN}/composition")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /fund/{isin}/flows  (item 2 — CATEGORY-level only)
# ---------------------------------------------------------------------------


async def test_fund_flows_happy_path(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_A)
    for i, month in enumerate(
        (datetime.date(2026, 4, 1), datetime.date(2026, 5, 1), datetime.date(2026, 6, 1))
    ):
        db_session.add(
            MfCategoryFlows(
                period_month=month,
                scheme_type="Open ended Schemes",
                scheme_category="Equity",  # matches _seed_fund's fund.category, not sebi_category
                num_schemes=42,
                num_folios=100000,
                funds_mobilized_cr=1000.0 + i,
                redemption_cr=800.0 + i,
                net_flow_cr=200.0 + i,
                net_aum_cr=50000.0 + i * 100,
                source_url="https://example.test/amfi-flows.xlsx",
            )
        )
    # A different scheme_type under the SAME category label must never leak in
    # (dedup-key regression guard, migration 0068 incident).
    db_session.add(
        MfCategoryFlows(
            period_month=datetime.date(2026, 6, 1),
            scheme_type="Close Ended Schemes",
            scheme_category="Equity",
            net_flow_cr=999999.0,
            source_url="https://example.test/amfi-flows.xlsx",
        )
    )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/flows")
    assert resp.status_code == 200, resp.text
    d = resp.json()["data"]
    assert d["scheme_category"] == "Equity"
    assert d["as_of_month"] == "2026-06-01"
    assert [p["period_month"] for p in d["points"]] == ["2026-04-01", "2026-05-01", "2026-06-01"]
    assert [p["net_flow_cr"] for p in d["points"]] == [200.0, 201.0, 202.0]
    assert 999999.0 not in [p["net_flow_cr"] for p in d["points"]]


async def test_fund_flows_no_matching_rows_empty_200(async_client, db_session, patch_redis):
    """Fund has a category, but AMFI's category-flow feed has no rows for it yet
    (e.g. the amfi_category_flows source hasn't run) — empty points, still 200."""
    await _seed_fund(db_session, _ISIN_A)
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/flows")
    assert resp.status_code == 200, resp.text
    d = resp.json()["data"]
    assert d == {"points": [], "scheme_category": "Equity", "as_of_month": None}


async def test_fund_flows_no_category_null_shape(async_client, db_session, patch_redis):
    """A fund with no scheme_category at all (category master hasn't populated it) gets
    the null shape, not a 500 — never guess a category to join on (§8.4)."""
    db_session.add(
        MfFund(
            isin=_ISIN_A,
            scheme_name=f"Fund {_ISIN_A}",
            amc_name="HDFC Asset Management Company Limited",
            sebi_category=_CAT,
            category=None,
            plan_type="direct",
            option_type="growth",
            is_segregated=False,
        )
    )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/flows")
    assert resp.status_code == 200, resp.text
    d = resp.json()["data"]
    assert d == {"points": [], "scheme_category": None, "as_of_month": None}


async def test_fund_flows_unknown_isin_404(async_client, db_session, patch_redis):
    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_UNKNOWN}/flows")
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


async def test_fund_peers_excludes_same_amfi_code_plan_variant(
    async_client, db_session, patch_redis
):
    """Fix 3 (fund-page-quick-wins): a fund's own OTHER plan variant (same
    amfi_code — e.g. PPFAS Direct vs PPFAS Regular) must never appear as its
    own peer, even though it is rank-adjacent in the same category."""
    db_session.add(
        MfFund(
            isin=_ISIN_A,
            scheme_name="PPFAS Flexicap Fund - Direct Plan - Growth",
            amc_name="PPFAS Asset Management",
            sebi_category=_CAT,
            plan_type="direct",
            amfi_code="12345",
            fund_name_short="PPFAS Flexicap Fund",
            is_segregated=False,
        )
    )
    db_session.add(
        MfFundRanks(
            isin=_ISIN_A,
            as_of_date=_TODAY,
            sebi_category=_CAT,
            rank=2,
            total_in_cat=3,
            verb_label="on_track",
        )
    )
    # Same underlying scheme, Regular plan — same amfi_code, must be excluded.
    db_session.add(
        MfFund(
            isin=_ISIN_B,
            scheme_name="PPFAS Flexicap Fund - Regular Plan - Growth",
            amc_name="PPFAS Asset Management",
            sebi_category=_CAT,
            plan_type="regular",
            amfi_code="12345",
            fund_name_short="PPFAS Flexicap Fund",
            is_segregated=False,
        )
    )
    db_session.add(
        MfFundRanks(
            isin=_ISIN_B,
            as_of_date=_TODAY,
            sebi_category=_CAT,
            rank=1,
            total_in_cat=3,
            verb_label="on_track",
        )
    )
    # A genuine peer — different underlying scheme entirely.
    db_session.add(
        MfFund(
            isin=_ISIN_C,
            scheme_name="Other Fund - Direct Plan - Growth",
            amc_name="Other AMC",
            sebi_category=_CAT,
            plan_type="direct",
            amfi_code="99999",
            fund_name_short="Other Fund",
            is_segregated=False,
        )
    )
    db_session.add(
        MfFundRanks(
            isin=_ISIN_C,
            as_of_date=_TODAY,
            sebi_category=_CAT,
            rank=3,
            total_in_cat=3,
            verb_label="on_track",
        )
    )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/peers")
    assert resp.status_code == 200, resp.text
    peer_isins = {p["isin"] for p in resp.json()["data"]["peers"]}
    assert _ISIN_B not in peer_isins  # same amfi_code plan variant — excluded
    assert _ISIN_C in peer_isins  # genuine peer — kept


async def test_fund_peers_prefers_same_plan_type_on_rank_tie(async_client, db_session, patch_redis):
    """Fix 3: among candidates equally rank-near the viewed fund, the one
    sharing its plan_type ranks first — a tie-break, never a filter."""
    await _seed_fund(db_session, _ISIN_A)  # plan_type="direct"
    db_session.add(
        MfFundRanks(
            isin=_ISIN_A,
            as_of_date=_TODAY,
            sebi_category=_CAT,
            rank=5,
            total_in_cat=9,
            verb_label="on_track",
        )
    )
    db_session.add(
        MfFund(
            isin=_ISIN_B,
            scheme_name="Regular Tie Peer",
            amc_name="Peer AMC",
            sebi_category=_CAT,
            plan_type="regular",
            is_segregated=False,
        )
    )
    db_session.add(
        MfFundRanks(
            isin=_ISIN_B,
            as_of_date=_TODAY,
            sebi_category=_CAT,
            rank=1,  # distance 4 from A's rank=5
            total_in_cat=9,
            verb_label="on_track",
        )
    )
    db_session.add(
        MfFund(
            isin=_ISIN_C,
            scheme_name="Direct Tie Peer",
            amc_name="Peer AMC",
            sebi_category=_CAT,
            plan_type="direct",
            is_segregated=False,
        )
    )
    db_session.add(
        MfFundRanks(
            isin=_ISIN_C,
            as_of_date=_TODAY,
            sebi_category=_CAT,
            rank=9,  # distance 4 from A's rank=5 — ties with B
            total_in_cat=9,
            verb_label="on_track",
        )
    )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/peers")
    assert resp.status_code == 200, resp.text
    isins_in_order = [p["isin"] for p in resp.json()["data"]["peers"]]
    # Same rank-distance (4) from both — the same-plan_type (direct) candidate
    # must sort first.
    assert isins_in_order.index(_ISIN_C) < isins_in_order.index(_ISIN_B)


# ---------------------------------------------------------------------------
# GET /fund/{isin}/factors  (W2, §10.1 — factors + signals, the second scored concept)
# ---------------------------------------------------------------------------


async def test_fund_factors_happy_path(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_A)
    db_session.add(
        MfFundRanks(
            isin=_ISIN_A,
            as_of_date=_TODAY,
            sebi_category=_CAT,
            rank=2,
            total_in_cat=10,
            verb_label="in_form",
            confidence_band="high",
            confidence_factors={"consistency": "high", "recency": "medium"},
            contributing_signals=["Outperformed category over 1 year"],
            contradicting_signals=[],
        )
    )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/factors")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    factors = body["factors"]["data"]
    assert factors["confidence_band"] == "high"
    assert factors["factors"] == {"consistency": "high", "recency": "medium"}
    assert factors["as_of"] == _TODAY.isoformat()

    signals = body["signals"]["data"]
    assert signals["contributing"] == ["Outperformed category over 1 year"]
    assert signals["contradicting"] == []
    assert signals["as_of"] == _TODAY.isoformat()


async def test_fund_factors_no_forbidden_tokens_and_bands_only(
    async_client, db_session, patch_redis
):
    """Non-neg #2: no raw score/weight/fair-value token anywhere in the response, and
    every factor value is one of the three allowed band words — never a bare numeric."""
    await _seed_fund(db_session, _ISIN_A)
    db_session.add(
        MfFundRanks(
            isin=_ISIN_A,
            as_of_date=_TODAY,
            sebi_category=_CAT,
            rank=1,
            total_in_cat=5,
            verb_label="on_track",
            confidence_band="medium",
            confidence_factors={"consistency": "high", "data_coverage": "low"},
            contributing_signals=[],
            contradicting_signals=["Below category median over 3 years"],
        )
    )
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/factors")
    assert resp.status_code == 200, resp.text
    for forbidden in ("unified_score", '"score"', "raw_score", "factor_weights", "fair_value"):
        assert forbidden not in resp.text

    factors = resp.json()["factors"]["data"]["factors"]
    assert set(factors.values()) <= {"high", "medium", "low"}


async def test_fund_factors_unranked_fund_nulls_200(async_client, db_session, patch_redis):
    await _seed_fund(db_session, _ISIN_A)
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/factors")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["factors"]["data"] == {"factors": None, "confidence_band": None, "as_of": None}
    assert body["signals"]["data"] == {"contributing": [], "contradicting": [], "as_of": None}


async def test_fund_factors_unknown_isin_404(async_client, db_session, patch_redis):
    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_UNKNOWN}/factors")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "fund_not_found"
