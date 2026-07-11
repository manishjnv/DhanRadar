"""
Integration test (Phase 4c pt2) — seed mf_funds + mf_nav_history -> REAL
mf.mf_category_series rows via the SQL pipeline (dhanradar.tasks.mf._category_series_pipeline).

Proves:
  * The SQL path (percentile_cont + the log-sum-exp cumulative-product window) matches
    the pure-Python hand-computed fixture (dhanradar.mf.category_series) to 6 decimals —
    "fixture-vs-hand-math parity".
  * Scheme-dedup: a Direct+Growth ISIN and its own IDCW variant (same fund_name_short)
    collapse to ONE contribution — fund_count stays 3, not 4.
  * Idempotent re-run: running the SAME date range twice upserts, never duplicates.

Requires a reachable Postgres (settings.database_url) — same db_session/db_tables
fixtures as test_mf_nav_scoring.py.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import insert, select

from dhanradar.mf.category_series import chain_index, daily_returns, median_returns_by_day
from dhanradar.models.mf import MfCategorySeries, MfFund, MfNavHistory
from dhanradar.tasks.mf import _category_series_pipeline

pytestmark = pytest.mark.integration

_CATEGORY = "Equity Scheme - Large Cap Fund (CatSeries Test)"
_D0, _D1, _D2, _D3 = date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)

_FUND_A = {_D0: 100.0, _D1: 101.0, _D2: 102.0, _D3: 103.02}
_FUND_B = {_D0: 200.0, _D1: 202.0, _D2: 201.0, _D3: 203.01}
_FUND_C = {_D0: 50.0, _D1: 50.5, _D2: 51.0, _D3: 51.51}
# Same SCHEME as Fund A (same fund_name_short) but the IDCW variant, wildly different NAV —
# must be EXCLUDED by the canonical-scheme dedup, or the median/fund_count would be corrupted.
_FUND_A_IDCW_VARIANT = {_D0: 1000.0, _D1: 1.0, _D2: 2000.0, _D3: 1.0}


async def _seed_fund(db_session, isin: str, fund_name_short: str, plan_type: str, option_type: str) -> None:
    await db_session.execute(
        insert(MfFund).values(
            isin=isin,
            amfi_code=isin,
            scheme_name=f"{fund_name_short} - {plan_type}/{option_type}",
            fund_name_short=fund_name_short,
            sebi_category=_CATEGORY,
            plan_type=plan_type,
            option_type=option_type,
        )
    )


async def _seed_nav(db_session, isin: str, series: dict[date, float]) -> None:
    rows = [
        {"isin": isin, "nav_date": d, "nav": round(nav, 4), "source": "amfi"}
        for d, nav in series.items()
    ]
    await db_session.execute(insert(MfNavHistory).values(rows))


async def test_sql_pipeline_matches_hand_math_fixture_and_dedupes_scheme_variants(
    db_session, db_tables
):
    await _seed_fund(db_session, "INF_CATSER_A1", "DhanRadar CatSeries Test A", "direct", "growth")
    # Same scheme as A1 (same fund_name_short) but an IDCW variant — must be excluded.
    await _seed_fund(db_session, "INF_CATSER_A2", "DhanRadar CatSeries Test A", "regular", "idcw")
    await _seed_fund(db_session, "INF_CATSER_B1", "DhanRadar CatSeries Test B", "direct", "growth")
    await _seed_fund(db_session, "INF_CATSER_C1", "DhanRadar CatSeries Test C", "direct", "growth")

    await _seed_nav(db_session, "INF_CATSER_A1", _FUND_A)
    await _seed_nav(db_session, "INF_CATSER_A2", _FUND_A_IDCW_VARIANT)
    await _seed_nav(db_session, "INF_CATSER_B1", _FUND_B)
    await _seed_nav(db_session, "INF_CATSER_C1", _FUND_C)
    await db_session.commit()

    # --- pure-Python oracle (dhanradar.mf.category_series) on the SAME fixture --------
    scheme_returns = {
        "A": daily_returns(_FUND_A),
        "B": daily_returns(_FUND_B),
        "C": daily_returns(_FUND_C),
    }
    expected = {p.series_date: p for p in chain_index(median_returns_by_day(scheme_returns))}
    assert round(expected[_D2].index_value, 6) == 102.0  # sanity: the hand-math fixture itself

    try:
        summary = await _category_series_pipeline(
            start_date=_D1.isoformat(), end_date=_D3.isoformat()
        )
        assert "upserted 3 rows" in summary

        rows = (
            await db_session.execute(
                select(MfCategorySeries)
                .where(MfCategorySeries.category == _CATEGORY)
                .order_by(MfCategorySeries.series_date)
            )
        ).scalars().all()
        assert [r.series_date for r in rows] == [_D1, _D2, _D3]

        for r in rows:
            exp = expected[r.series_date]
            # Scheme-dedup proof: fund_count is 3 (A1/B1/C1), NOT 4 (A2 excluded).
            assert r.fund_count == 3
            assert round(float(r.index_value), 6) == round(exp.index_value, 6)
            assert round(float(r.median_daily_return), 6) == round(exp.median_daily_return, 6)

        # --- idempotent re-run: same range, same rows, no duplicates -------------------
        summary2 = await _category_series_pipeline(
            start_date=_D1.isoformat(), end_date=_D3.isoformat()
        )
        assert "upserted 3 rows" in summary2

        rows2 = (
            await db_session.execute(
                select(MfCategorySeries).where(MfCategorySeries.category == _CATEGORY)
            )
        ).scalars().all()
        assert len(rows2) == 3  # still 3 rows, not 6 — ON CONFLICT DO UPDATE, never INSERT-dup
        assert {(r.series_date, round(float(r.index_value), 6)) for r in rows2} == {
            (r.series_date, round(float(r.index_value), 6)) for r in rows
        }
    finally:
        await db_session.execute(
            MfCategorySeries.__table__.delete().where(MfCategorySeries.category == _CATEGORY)
        )
        await db_session.commit()
