"""Integration tests for GET /api/v1/mf/fund/{isin}/comparison
(Phase 4c pt4, MF_MASTER_DB_IMPROVEMENT_PLAN.md "Phase 4c").

Same infrastructure contract as test_fund_w1_endpoints.py (async_client / db_session /
patch_redis). Public — no auth required (current_user_or_anonymous).

Coverage:
  * Rebase correctness: all three lines start at exactly 100.0 at the SAME anchor date.
  * Unmapped fund.benchmark_index -> honest Nifty 50 fallback (label + is_fallback).
  * `benchmark_key` override picks a different canonical index, never silently swapped.
  * Server-side thin-cohort suppression (fund_count < 10, and < 60% date coverage).
  * Downsampling to <=400 points keeps the first (anchor) and last point.
  * No `tri_value` key anywhere in the response (recursive walk — ADR-0033 tripwire).
  * 404 unknown ISIN, 422 invalid window / benchmark_key.
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import insert, text

from dhanradar.models.mf import (
    MfBenchmarkMap,
    MfBenchmarkTri,
    MfCategorySeries,
    MfFund,
    MfNavHistory,
)

pytestmark = pytest.mark.integration

_CAT = "Equity Scheme - Flexi Cap Fund (Comparison Test)"
_ISIN_A = "INF200K01884"
_ISIN_UNKNOWN = "INF000U00000"  # valid ISIN shape, never seeded

_D0 = datetime.date(2026, 1, 1)
_D1 = datetime.date(2026, 1, 2)
_D2 = datetime.date(2026, 1, 3)

_RAW_BENCHMARK = "Nifty 50 TRI"


@pytest.fixture(autouse=True)
async def _truncate_mf(db_session):
    yield
    await db_session.rollback()
    for tbl in (
        "mf.mf_benchmark_tri",
        "mf.mf_benchmark_map",
        "mf.mf_category_series",
        "mf.mf_nav_history",
        "mf.mf_funds",
    ):
        await db_session.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))
    await db_session.commit()


async def _seed_fund(
    db_session, isin: str = _ISIN_A, *, benchmark_index: str | None = _RAW_BENCHMARK
) -> None:
    db_session.add(
        MfFund(
            isin=isin,
            scheme_name=f"Fund {isin}",
            amc_name="HDFC Asset Management Company Limited",
            sebi_category=_CAT,
            plan_type="direct",
            option_type="growth",
            benchmark_index=benchmark_index,
            is_segregated=False,
        )
    )
    await db_session.flush()


async def _seed_nav(db_session, series: dict[datetime.date, float], isin: str = _ISIN_A) -> None:
    rows = [{"isin": isin, "nav_date": d, "nav": v, "source": "amfi"} for d, v in series.items()]
    await db_session.execute(insert(MfNavHistory).values(rows))


async def _seed_tri(db_session, index_key: str, series: dict[datetime.date, float]) -> None:
    rows = [
        {"index_key": index_key, "tri_date": d, "tri_value": v, "source": "niftyindices"}
        for d, v in series.items()
    ]
    await db_session.execute(insert(MfBenchmarkTri).values(rows))


async def _seed_category(
    db_session, series: dict[datetime.date, float], *, category: str = _CAT, fund_count: int = 15
) -> None:
    rows = [
        {"category": category, "series_date": d, "index_value": v, "fund_count": fund_count}
        for d, v in series.items()
    ]
    await db_session.execute(insert(MfCategorySeries).values(rows))


def _walk_no_forbidden_keys(obj, forbidden: tuple[str, ...] = ("tri_value",)) -> None:
    """Recursively assert no dict key anywhere in `obj` matches a forbidden name
    (ADR-0033 — raw TRI levels must never reach the client)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert k not in forbidden, f"forbidden key {k!r} found in response"
            _walk_no_forbidden_keys(v, forbidden)
    elif isinstance(obj, list):
        for item in obj:
            _walk_no_forbidden_keys(item, forbidden)


# ---------------------------------------------------------------------------
# Rebase correctness — the anchor/shared-date crux
# ---------------------------------------------------------------------------


async def test_comparison_all_three_lines_start_at_100_same_anchor(
    async_client, db_session, patch_redis
):
    await _seed_fund(db_session)
    await _seed_nav(db_session, {_D0: 100.0, _D1: 101.0, _D2: 102.0})
    await db_session.execute(
        insert(MfBenchmarkMap).values(
            benchmark_name_raw=_RAW_BENCHMARK, index_key="nifty50_tri", mapped_by="test"
        )
    )
    await _seed_tri(db_session, "nifty50_tri", {_D0: 1000.0, _D1: 1010.0, _D2: 1030.0})
    await _seed_category(db_session, {_D0: 50.0, _D1: 51.0, _D2: 52.5})
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/comparison?window=max")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["window"] == "max"
    assert body["anchor_date"] == _D0.isoformat()

    fund = body["series"]["fund"]
    bench = body["series"]["benchmark"]
    cat = body["series"]["category"]

    assert fund[0] == {"d": _D0.isoformat(), "v": 100.0}
    assert fund[-1]["v"] == pytest.approx(102.0)

    assert bench["is_fallback"] is False
    assert bench["label"] == _RAW_BENCHMARK  # mapped -> raw AMFI string, verbatim
    assert bench["points"][0] == {"d": _D0.isoformat(), "v": 100.0}
    assert bench["points"][-1]["v"] == pytest.approx(103.0)  # 1030/1000*100

    assert cat["reason"] is None
    assert cat["points"][0] == {"d": _D0.isoformat(), "v": 100.0}
    assert cat["points"][-1]["v"] == pytest.approx(105.0)  # 52.5/50*100

    assert body["disclosure"]
    assert body["not_advice"]
    _walk_no_forbidden_keys(body)


# ---------------------------------------------------------------------------
# Honest fallback — unmapped benchmark_index
# ---------------------------------------------------------------------------


async def test_comparison_unmapped_benchmark_falls_back_to_nifty50(
    async_client, db_session, patch_redis
):
    # No MfBenchmarkMap row for this raw string at all — unmapped.
    await _seed_fund(db_session, benchmark_index="NIFTY Banking & PSU Debt Index A-II")
    await _seed_nav(db_session, {_D0: 100.0, _D1: 101.0})
    await _seed_tri(db_session, "nifty50_tri", {_D0: 1000.0, _D1: 1020.0})
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/comparison?window=max")
    assert resp.status_code == 200, resp.text
    bench = resp.json()["series"]["benchmark"]

    assert bench["is_fallback"] is True
    assert bench["label"] == "Nifty 50 (broad market — not this scheme's benchmark)"
    assert bench["points"][0]["v"] == 100.0
    assert bench["points"][-1]["v"] == pytest.approx(102.0)  # 1020/1000*100


async def test_comparison_no_benchmark_index_falls_back_to_nifty50(
    async_client, db_session, patch_redis
):
    await _seed_fund(db_session, benchmark_index=None)
    await _seed_nav(db_session, {_D0: 100.0})
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/comparison?window=max")
    assert resp.status_code == 200, resp.text
    bench = resp.json()["series"]["benchmark"]
    assert bench["is_fallback"] is True
    assert bench["points"] == []  # no nifty50 TRI seeded — honest empty, never crashes


# ---------------------------------------------------------------------------
# benchmark_key override — never silently swapped
# ---------------------------------------------------------------------------


async def test_comparison_benchmark_key_override_picks_a_different_index(
    async_client, db_session, patch_redis
):
    await _seed_fund(db_session)  # mapped to nifty50_tri by default
    await _seed_nav(db_session, {_D0: 100.0, _D1: 101.0})
    await db_session.execute(
        insert(MfBenchmarkMap).values(
            benchmark_name_raw=_RAW_BENCHMARK, index_key="nifty50_tri", mapped_by="test"
        )
    )
    await _seed_tri(db_session, "nifty50_tri", {_D0: 1000.0, _D1: 1010.0})
    await _seed_tri(db_session, "nifty500_tri", {_D0: 2000.0, _D1: 2100.0})
    await db_session.commit()

    resp = await async_client.get(
        f"/api/v1/mf/fund/{_ISIN_A}/comparison?window=max&benchmark_key=nifty500_tri"
    )
    assert resp.status_code == 200, resp.text
    bench = resp.json()["series"]["benchmark"]

    assert bench["is_fallback"] is False
    assert bench["label"] == "Nifty 500 TRI"
    assert bench["points"][-1]["v"] == pytest.approx(105.0)  # 2100/2000*100, NOT nifty50's 101.0


async def test_comparison_invalid_benchmark_key_422(async_client, db_session, patch_redis):
    await _seed_fund(db_session)
    await db_session.commit()
    resp = await async_client.get(
        f"/api/v1/mf/fund/{_ISIN_A}/comparison?benchmark_key=not_a_real_key"
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Server-side thin-cohort suppression (never emitted silently thin)
# ---------------------------------------------------------------------------


async def test_comparison_category_omitted_when_fund_count_below_10(
    async_client, db_session, patch_redis
):
    await _seed_fund(db_session)
    await _seed_nav(db_session, {_D0: 100.0, _D1: 101.0, _D2: 102.0})
    await _seed_category(db_session, {_D0: 50.0, _D1: 51.0, _D2: 52.0}, fund_count=5)
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/comparison?window=max")
    assert resp.status_code == 200, resp.text
    cat = resp.json()["series"]["category"]
    assert cat["points"] is None
    assert cat["reason"] == "category average unavailable — cohort too thin"


async def test_comparison_category_omitted_when_coverage_below_60pct(
    async_client, db_session, patch_redis
):
    await _seed_fund(db_session)
    # Fund has 5 NAV dates; category only qualifies (fund_count>=10) on 2 of them (40% < 60%).
    await _seed_nav(
        db_session,
        {_D0: 100.0, _D1: 101.0, _D2: 102.0, _D2 + datetime.timedelta(days=1): 103.0,
         _D2 + datetime.timedelta(days=2): 104.0},
    )
    await _seed_category(db_session, {_D0: 50.0, _D1: 51.0}, fund_count=15)
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/comparison?window=max")
    assert resp.status_code == 200, resp.text
    cat = resp.json()["series"]["category"]
    assert cat["points"] is None
    assert cat["reason"] == "category average unavailable — cohort too thin"


async def test_comparison_no_sebi_category_omits_category_line(
    async_client, db_session, patch_redis
):
    db_session.add(
        MfFund(
            isin=_ISIN_A,
            scheme_name="Fund no category",
            sebi_category=None,
            benchmark_index=_RAW_BENCHMARK,
            is_segregated=False,
        )
    )
    await db_session.flush()
    await _seed_nav(db_session, {_D0: 100.0})
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/comparison?window=max")
    assert resp.status_code == 200, resp.text
    cat = resp.json()["series"]["category"]
    assert cat["points"] is None
    assert cat["reason"] == "category average unavailable — cohort too thin"


# ---------------------------------------------------------------------------
# Downsampling — <=400 points, first (anchor) + last always kept
# ---------------------------------------------------------------------------


async def test_comparison_downsample_keeps_first_and_last(async_client, db_session, patch_redis):
    await _seed_fund(db_session)
    start = _D0
    nav_series = {start + datetime.timedelta(days=i): 100.0 + i * 0.01 for i in range(900)}
    await _seed_nav(db_session, nav_series)
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/comparison?window=max")
    assert resp.status_code == 200, resp.text
    fund = resp.json()["series"]["fund"]

    assert len(fund) <= 400
    assert fund[0]["d"] == start.isoformat()
    assert fund[0]["v"] == 100.0
    last_date = start + datetime.timedelta(days=899)
    assert fund[-1]["d"] == last_date.isoformat()


# ---------------------------------------------------------------------------
# 404 / empty-window edge cases
# ---------------------------------------------------------------------------


async def test_comparison_unknown_isin_404(async_client, db_session, patch_redis):
    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_UNKNOWN}/comparison")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "fund_not_found"


async def test_comparison_invalid_window_422(async_client, db_session, patch_redis):
    await _seed_fund(db_session)
    await db_session.commit()
    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/comparison?window=10y")
    assert resp.status_code == 422


async def test_comparison_no_nav_history_honest_empty_200(async_client, db_session, patch_redis):
    await _seed_fund(db_session)
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/mf/fund/{_ISIN_A}/comparison?window=max")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["anchor_date"] is None
    assert body["series"]["fund"] == []
    assert body["series"]["category"]["points"] is None
    _walk_no_forbidden_keys(body)
