"""
Compare fragment composer (COMPARE_LIVE_DATA_PLAN.md Wave C1).

`get_compare_fragment` assembles a per-ISIN fragment from existing read models:
  head · analytics (subset) · SIP (two fixed-safe illustrations) · category
  medians · benchmark comparison (rebased 1Y series).

`compose_compare_bundle_fragments` gathers N cold ISINs concurrently using one
`SessionLocal` session per task (never the shared request `AsyncSession`) bounded
by a semaphore ≤ 4.  No raw composite score fields are selected.
"""

from __future__ import annotations

import asyncio
from statistics import median

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.db import SessionLocal
from dhanradar.mf.fund_read import (
    _category_avg_returns,
    get_fund_analytics,
    get_fund_comparison,
    get_fund_head,
    get_fund_sip,
)
from dhanradar.models.mf import MfFund

_CMP_SIP_AMOUNT = 5_000  # fixed educational SIP amount
_CMP_BENCHMARK_WINDOW = "1y"

# Analytics fields safe for the compare surface (DOM-allowed standard ratios only;
# no composite score, no factor weights, no raw percentile numbers).
_ANALYTICS_FIELDS = (
    "sharpe_ratio",
    "sortino_ratio",
    "volatility_pct",
    "max_drawdown_pct",
    "rolling_1y_avg_pct",
    "rolling_1y_min_pct",
    "rolling_1y_max_pct",
    "rolling_1y_pct_positive",
    "rolling_3y_avg_pct",
    "rolling_3y_min_pct",
    "rolling_3y_max_pct",
    "rolling_3y_pct_positive",
)


async def get_compare_fragment(session: AsyncSession, isin: str) -> dict | None:
    """Compose one compare fragment for *isin*; returns ``None`` if the fund does not exist.

    Reuses the same read-only query sets as the watchlist/fund-detail endpoints — no
    new query shapes, no composite score fields.
    """
    head = await get_fund_head(session, isin)
    if head is None:
        return None

    analytics_raw = await get_fund_analytics(session, isin)
    category_avgs = await _category_avg_returns(session, head["sebi_category"])
    category_ter = await _category_median_ter(session, head["sebi_category"])
    comparison = await get_fund_comparison(session, isin, window=_CMP_BENCHMARK_WINDOW)
    sip_5y = await get_fund_sip(session, isin, amount=_CMP_SIP_AMOUNT, years=5)
    sip_10y = await get_fund_sip(session, isin, amount=_CMP_SIP_AMOUNT, years=10)

    # Extract only the allowlisted analytics keys; ignore drawdown_series,
    # calendar_year_returns, category_percentiles, etc. (not needed for C1).
    analytics: dict = {}
    if analytics_raw is not None:
        for key in _ANALYTICS_FIELDS:
            analytics[key] = analytics_raw.get(key)

    # Benchmark: extract only the fields the mf.compare_benchmark allowlist permits.
    benchmark: dict | None = None
    if comparison is not None:
        bench = comparison.get("series", {}).get("benchmark", {})
        benchmark = {
            "label": bench.get("label"),
            "is_fallback": bench.get("is_fallback", False),
            "points": bench.get("points", []),
            "window": _CMP_BENCHMARK_WINDOW,
        }

    return {
        # head facts
        "isin": head["isin"],
        "scheme_name": head["scheme_name"],
        "fund_name_short": head["fund_name_short"],
        "amc_name": head["amc_name"],
        "sebi_category": head["sebi_category"],
        "category": head["category"],
        "plan_type": head["plan_type"],
        "option_type": head["option_type"],
        "launch_date": head["launch_date"],
        "expense_ratio_pct": head["expense_ratio_pct"],
        "is_segregated": head["is_segregated"],
        "verb_label": head["verb_label"],
        "confidence_band": head["confidence_band"],
        "category_rank": head["category_rank"],
        "category_total": head["category_total"],
        "return_3m_pct": head["return_3m_pct"],
        "return_6m_pct": head["return_6m_pct"],
        "return_1y_pct": head["return_1y_pct"],
        "return_3y_pct": head["return_3y_pct"],
        "return_5y_pct": head["return_5y_pct"],
        "nav_latest": head["nav_latest"],
        "nav_date": head["nav_date"],
        "nav_change_pct": head["nav_change_pct"],
        "aum_crore": head["aum_crore"],
        # analytics subset (standard ratios + rolling returns; no score)
        **analytics,
        # category medians (mf_category_stats p50)
        "category_median_return_1y_pct": category_avgs["return_1y_pct"],
        "category_median_return_3y_pct": category_avgs["return_3y_pct"],
        "category_median_ter_pct": category_ter,
        # SIP illustrations (fixed safe values; deterministic, educational)
        "sip_5y": sip_5y,
        "sip_10y": sip_10y,
        # benchmark comparison (rebased 1Y series through compare allowlist)
        "benchmark": benchmark,
    }


async def _category_median_ter(session: AsyncSession, sebi_category: str | None) -> float | None:
    """Return the current category TER median, withholding an empty cohort."""
    if not sebi_category:
        return None
    rows = (
        await session.execute(
            select(MfFund.expense_ratio_pct).where(
                MfFund.sebi_category == sebi_category,
                MfFund.expense_ratio_pct.is_not(None),
            )
        )
    ).scalars().all()
    return float(median([float(value) for value in rows])) if rows else None


async def compose_compare_bundle_fragments(cold_isins: list[str]) -> dict[str, dict | None]:
    """Concurrently compose fragments for *cold_isins*.

    One independent ``SessionLocal`` session per ISIN (never the shared request
    ``AsyncSession``).  Concurrency bounded by a per-call semaphore ≤ 4 per the
    architect review condition (COMPARE_LIVE_DATA_PLAN.md §Architecture).
    """
    sem = asyncio.Semaphore(4)

    async def _one(isin: str) -> tuple[str, dict | None]:
        async with sem:
            async with SessionLocal() as session:
                frag = await get_compare_fragment(session, isin)
        return isin, frag

    pairs = await asyncio.gather(*(_one(isin) for isin in cold_isins))
    return dict(pairs)
