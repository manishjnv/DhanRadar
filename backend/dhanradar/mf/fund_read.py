"""fund.head read model (W0, FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §6/§17).

The ONE fund read service for the public Fund Detail page — mirrors the Portfolio v3
CQRS-lite pattern (mf/portfolio_read.py). Every payload is a hand-built PLAIN dict (never
an ORM row / Pydantic model) so the A3 `serialize_concept` scrub can see every key
(non-neg #2); `unified_score` is never selected here.

Kills the fund-detail pagination hack (30-page explorer scan) — replaced by one
single-ISIN index/PK lookup per table, no N+1 (Design principle 1, §2).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Reuse the explorer's young-fund guard constants rather than redefining them — one
# threshold, one place (mirrors the row-level guard already live in fund_explorer_list).
from dhanradar.mf.router import _MIN_NAV_POINTS_1Y, _MIN_NAV_POINTS_3Y
from dhanradar.models.mf import MfFund, MfFundMetrics, MfFundRanks, MfNavHistory


async def get_fund_head(session: AsyncSession, isin: str) -> dict | None:
    """Assemble the `fund.head` payload for one ISIN, or None if the fund doesn't exist.

    Every other source (rank, metrics, NAV) is independently optional — an unranked or
    metrics-cold fund still returns a full payload with those fields null, so the page
    loads for ANY ISIN (§17 W0 gate). `is_segregated` funds have rank/verb_label/returns
    nulled (Franklin trap rule, §3) — NAV itself still renders.
    """
    fund = await session.get(MfFund, isin)
    if fund is None:
        return None

    rank_row = (
        await session.execute(
            select(MfFundRanks)
            .where(MfFundRanks.isin == isin)
            .order_by(MfFundRanks.as_of_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    metrics = await session.get(MfFundMetrics, isin)

    nav_rows = (
        (
            await session.execute(
                select(MfNavHistory)
                .where(MfNavHistory.isin == isin)
                .order_by(MfNavHistory.nav_date.desc())
                .limit(2)
            )
        )
        .scalars()
        .all()
    )

    if fund.is_segregated:
        rank_row = None
        metrics = None

    nav_points = metrics.nav_points if metrics else 0
    nav_latest = float(nav_rows[0].nav) if nav_rows else None
    nav_date = nav_rows[0].nav_date.isoformat() if nav_rows else None
    nav_change_pct = None
    if len(nav_rows) == 2 and nav_rows[1].nav:
        prev = float(nav_rows[1].nav)
        cur = float(nav_rows[0].nav)
        nav_change_pct = (cur - prev) / prev * 100 if prev else None

    return {
        "isin": fund.isin,
        "scheme_name": fund.scheme_name,
        "fund_name_short": fund.fund_name_short,
        "amc_name": fund.amc_name,
        "sebi_category": fund.sebi_category,
        "category": fund.category,
        "plan_type": fund.plan_type,
        "option_type": fund.option_type,
        "idcw_frequency": fund.idcw_frequency,
        "launch_date": fund.launch_date.isoformat() if fund.launch_date else None,
        "expense_ratio_pct": (
            float(fund.expense_ratio_pct) if fund.expense_ratio_pct is not None else None
        ),
        "is_segregated": fund.is_segregated,
        "verb_label": rank_row.verb_label if rank_row else None,
        "category_rank": rank_row.rank if rank_row else None,
        "category_total": rank_row.total_in_cat if rank_row else None,
        "rank_as_of": rank_row.as_of_date.isoformat() if rank_row else None,
        "return_3m_pct": float(metrics.return_3m_pct)
        if metrics and metrics.return_3m_pct is not None
        else None,
        "return_6m_pct": float(metrics.return_6m_pct)
        if metrics and metrics.return_6m_pct is not None
        else None,
        "return_1y_pct": metrics.return_1y_pct
        if metrics and nav_points >= _MIN_NAV_POINTS_1Y
        else None,
        "return_3y_pct": metrics.return_3y_pct
        if metrics and nav_points >= _MIN_NAV_POINTS_3Y
        else None,
        "return_5y_pct": float(metrics.return_5y_pct)
        if metrics and metrics.return_5y_pct is not None
        else None,
        "metrics_as_of": metrics.as_of_date.isoformat() if metrics else None,
        "nav_latest": nav_latest,
        "nav_date": nav_date,
        "nav_change_pct": nav_change_pct,
        "confidence_band": None,  # W2/W3 field — shape stability, not computed yet
        "amc_level_aum_crore": None,  # W2/W3 field — source-blocked (B67/ADR-0035)
    }
