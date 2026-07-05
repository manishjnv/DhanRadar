"""fund.head read model (W0, FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §6/§17).

The ONE fund read service for the public Fund Detail page — mirrors the Portfolio v3
CQRS-lite pattern (mf/portfolio_read.py). Every payload is a hand-built PLAIN dict (never
an ORM row / Pydantic model) so the A3 `serialize_concept` scrub can see every key
(non-neg #2); `unified_score` is never selected here.

Kills the fund-detail pagination hack (30-page explorer scan) — replaced by one
single-ISIN index/PK lookup per table, no N+1 (Design principle 1, §2).
"""

from __future__ import annotations

import math
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# Reuse the explorer's young-fund guard constants rather than redefining them — one
# threshold, one place (mirrors the row-level guard already live in fund_explorer_list).
from dhanradar.mf.router import _MIN_NAV_POINTS_1Y, _MIN_NAV_POINTS_3Y
from dhanradar.models.mf import (
    MfCategoryStats,
    MfFund,
    MfFundConstituent,
    MfFundManagerHistory,
    MfFundMetrics,
    MfFundRanks,
    MfNavHistory,
)


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
        # W2 (§10.1): real once compute_market_ranks persists it; null for an
        # unranked/segregated fund or an insufficient_data read (no rateable band).
        "confidence_band": rank_row.confidence_band if rank_row else None,
        "amc_level_aum_crore": None,  # W3 field — source-blocked (B67/ADR-0035)
    }


# ---------------------------------------------------------------------------
# W1 — nav_series, analytics, rank_history, composition, people, amc, peers
# (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §5 rows 10/12/13/15/16/19/20, §17 W1)
# ---------------------------------------------------------------------------

# Window length (calendar days) per range key — see §17 W1 nav route contract.
_NAV_RANGE_DAYS: dict[str, int | None] = {
    "1m": 31,
    "3m": 93,
    "6m": 186,
    "1y": 366,
    "3y": 1100,
    "5y": 1830,
    "max": None,
}
_NAV_SERIES_CAP = 400  # downsample cap — simple stride, always keeps the last point


def _downsample(rows: list, cap: int) -> list:
    """Stride-sample `rows` (already ordered) down to <= `cap` items, keeping the last."""
    n = len(rows)
    if n <= cap:
        return rows
    stride = math.ceil(n / cap)
    sampled = rows[::stride]
    if sampled[-1] is not rows[-1]:
        sampled = [*sampled, rows[-1]]
    return sampled


async def get_fund_nav_series(
    session: AsyncSession, isin: str, range_key: str = "1y"
) -> dict | None:
    """`fund.nav_series` — daily NAV history for the window, downsampled to <=400 points.

    Growth-of-10k is derived client-side from these raw NAV points (§17 W1) — not
    duplicated server-side. The window is anchored on the fund's OWN latest NAV date
    (not wall-clock "today"), so a fund with a stale/cold feed still gets a coherent window.
    """
    fund = await session.get(MfFund, isin)
    if fund is None:
        return None

    days = _NAV_RANGE_DAYS.get(range_key, _NAV_RANGE_DAYS["1y"])
    stmt = (
        select(MfNavHistory).where(MfNavHistory.isin == isin).order_by(MfNavHistory.nav_date.asc())
    )
    if days is not None:
        latest = (
            await session.execute(
                select(func.max(MfNavHistory.nav_date)).where(MfNavHistory.isin == isin)
            )
        ).scalar_one_or_none()
        if latest is not None:
            stmt = stmt.where(MfNavHistory.nav_date >= latest - timedelta(days=days))

    rows = (await session.execute(stmt)).scalars().all()
    n_total = len(rows)
    sampled = _downsample(list(rows), _NAV_SERIES_CAP)

    return {
        "range": range_key,
        "points": [{"d": r.nav_date.isoformat(), "nav": float(r.nav)} for r in sampled],
        "from": rows[0].nav_date.isoformat() if rows else None,
        "to": rows[-1].nav_date.isoformat() if rows else None,
        "n_total": n_total,
    }


def _percentile_of_score(value: float, cohort: list[float]) -> float:
    """Percentile RANK (0-100) of `value` within `cohort` (weak method, ties averaged).

    `cohort` includes `value` itself (the fund is a member of its own category). Higher
    result = higher `value` relative to peers. n<=1 → 50.0 (nothing to compare against).
    """
    n = len(cohort)
    if n <= 1:
        return 50.0
    below = sum(1 for v in cohort if v < value)
    equal = sum(1 for v in cohort if v == value)
    return (below + 0.5 * (equal - 1)) / (n - 1) * 100.0


async def get_fund_analytics(session: AsyncSession, isin: str) -> dict | None:
    """`fund.analytics` — risk/return stats (`mf_fund_metrics`) + category percentile
    context. Fund exists but metrics not yet computed → all-null shape, still 200.
    """
    fund = await session.get(MfFund, isin)
    if fund is None:
        return None

    metrics = await session.get(MfFundMetrics, isin)
    if metrics is None:
        return {
            "sharpe_ratio": None,
            "sortino_ratio": None,
            "volatility_pct": None,
            "max_drawdown_pct": None,
            "rolling_1y_avg_pct": None,
            "rolling_1y_min_pct": None,
            "rolling_1y_max_pct": None,
            "rolling_1y_pct_positive": None,
            "as_of": None,
            "volatility_percentile": None,
            "category_percentiles": {},
        }

    rank_row = (
        await session.execute(
            select(MfFundRanks)
            .where(MfFundRanks.isin == isin)
            .order_by(MfFundRanks.as_of_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    volatility_percentile: float | None = None
    category_percentiles: dict[str, dict[str, float | None]] = {}

    if rank_row is not None:
        cat_max_rank_date = (
            await session.execute(
                select(func.max(MfFundRanks.as_of_date)).where(
                    MfFundRanks.sebi_category == rank_row.sebi_category
                )
            )
        ).scalar_one_or_none()

        if metrics.volatility_pct is not None and cat_max_rank_date is not None:
            cohort = (
                (
                    await session.execute(
                        select(MfFundMetrics.volatility_pct)
                        .join(MfFundRanks, MfFundRanks.isin == MfFundMetrics.isin)
                        .where(
                            MfFundRanks.sebi_category == rank_row.sebi_category,
                            MfFundRanks.as_of_date == cat_max_rank_date,
                            MfFundMetrics.volatility_pct.is_not(None),
                        )
                    )
                )
                .scalars()
                .all()
            )
            volatility_percentile = round(
                _percentile_of_score(
                    float(metrics.volatility_pct), [float(v) for v in cohort if v is not None]
                ),
                1,
            )

        cat_max_stats_date = (
            await session.execute(
                select(func.max(MfCategoryStats.as_of)).where(
                    MfCategoryStats.sebi_category == rank_row.sebi_category
                )
            )
        ).scalar_one_or_none()
        if cat_max_stats_date is not None:
            stat_rows = (
                (
                    await session.execute(
                        select(MfCategoryStats).where(
                            MfCategoryStats.sebi_category == rank_row.sebi_category,
                            MfCategoryStats.as_of == cat_max_stats_date,
                            MfCategoryStats.metric_key.in_(
                                ("return_1y_pct", "return_3y_pct", "max_drawdown_pct")
                            ),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for s in stat_rows:
                if s.p25 is None and s.p50 is None and s.p75 is None and s.p90 is None:
                    continue
                category_percentiles[s.metric_key] = {
                    "p25": s.p25,
                    "p50": s.p50,
                    "p75": s.p75,
                    "p90": s.p90,
                }

    return {
        "sharpe_ratio": metrics.sharpe_ratio,
        "sortino_ratio": metrics.sortino_ratio,
        "volatility_pct": metrics.volatility_pct,
        "max_drawdown_pct": metrics.max_drawdown_pct,
        "rolling_1y_avg_pct": metrics.rolling_1y_avg_pct,
        "rolling_1y_min_pct": metrics.rolling_1y_min_pct,
        "rolling_1y_max_pct": metrics.rolling_1y_max_pct,
        "rolling_1y_pct_positive": metrics.rolling_1y_pct_positive,
        "as_of": metrics.as_of_date.isoformat(),
        "volatility_percentile": volatility_percentile,
        "category_percentiles": category_percentiles,
    }


_RANK_HISTORY_WINDOW_DAYS = 366  # trailing 12 months


async def get_fund_rank_history(session: AsyncSession, isin: str) -> dict | None:
    """`fund.rank_history` — trailing 12 months of `mf_fund_ranks`, one point per as_of_date."""
    fund = await session.get(MfFund, isin)
    if fund is None:
        return None

    latest = (
        await session.execute(
            select(func.max(MfFundRanks.as_of_date)).where(MfFundRanks.isin == isin)
        )
    ).scalar_one_or_none()
    if latest is None:
        return {"points": []}

    cutoff = latest - timedelta(days=_RANK_HISTORY_WINDOW_DAYS)
    rows = (
        (
            await session.execute(
                select(MfFundRanks)
                .where(MfFundRanks.isin == isin, MfFundRanks.as_of_date >= cutoff)
                .order_by(MfFundRanks.as_of_date.asc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "points": [
            {"as_of": r.as_of_date.isoformat(), "rank": r.rank, "total": r.total_in_cat}
            for r in rows
        ]
    }


async def get_fund_composition(session: AsyncSession, isin: str) -> dict | None:
    """`fund.composition` — latest disclosed month's top holdings + sector rollup.

    Source covers top-10 AMCs only (ADR-0033(a)) — an uncovered AMC returns the same
    shape with empty lists and null as_of_month/coverage, never a 404 (no-suppress, §14.1).
    """
    fund = await session.get(MfFund, isin)
    if fund is None:
        return None

    latest_month = (
        await session.execute(
            select(func.max(MfFundConstituent.as_of_month)).where(MfFundConstituent.isin == isin)
        )
    ).scalar_one_or_none()
    if latest_month is None:
        return {
            "holdings": [],
            "sectors": [],
            "as_of_month": None,
            "coverage": {"holdings_count": 0, "weight_covered_pct": None},
        }

    rows = (
        (
            await session.execute(
                select(MfFundConstituent).where(
                    MfFundConstituent.isin == isin, MfFundConstituent.as_of_month == latest_month
                )
            )
        )
        .scalars()
        .all()
    )
    # Sort by weight desc in Python (top-10 rows per fund — trivial size); None-weight last.
    rows = sorted(
        rows, key=lambda r: float(r.weight_pct) if r.weight_pct is not None else -1.0, reverse=True
    )

    holdings = [
        {
            "name": r.constituent_name,
            "sector": r.sector,
            "weight_pct": float(r.weight_pct) if r.weight_pct is not None else None,
        }
        for r in rows
    ]

    sector_totals: dict[str, float] = {}
    for r in rows:
        if r.weight_pct is None:
            continue
        key = r.sector or "Other"
        sector_totals[key] = sector_totals.get(key, 0.0) + float(r.weight_pct)
    sectors = [
        {"name": name, "weight_pct": round(wt, 3)}
        for name, wt in sorted(sector_totals.items(), key=lambda kv: kv[1], reverse=True)
    ]

    weighted = [float(r.weight_pct) for r in rows if r.weight_pct is not None]
    weight_covered_pct = round(sum(weighted), 2) if weighted else None
    # Data-quality guard (docs/rca/README.md, INF789F01WY2 incident): a coverage
    # sum past 105% means garbage rows (section-header/subtotal leak) reached
    # this fund despite the ingestion-side guard — report null, never a wrong
    # number.
    if weight_covered_pct is not None and weight_covered_pct > 105:
        weight_covered_pct = None

    return {
        "holdings": holdings,
        "sectors": sectors,
        "as_of_month": latest_month.isoformat(),
        "coverage": {"holdings_count": len(rows), "weight_covered_pct": weight_covered_pct},
    }


_MANAGER_CHANGE_WINDOW_DAYS = 365 * 5  # trailing 5 years


async def get_fund_people(session: AsyncSession, isin: str) -> tuple[dict, dict] | None:
    """`fund.people` + `fund.amc` — manager tenure/changes and AMC facts. Returns
    (people_payload, amc_payload), or None if the fund itself doesn't exist.

    `fund_manager_history.scheme_uid` IS the fund ISIN — confirmed in
    `market_data/amc_managers.py` ("scheme_uid — SEBI ISIN; the canonical scheme
    identifier") — a direct equality join, not a lookup table (see report deviations).
    Coverage is 5 AMCs only — an uncovered AMC gets empty managers, still 200.
    """
    fund = await session.get(MfFund, isin)
    if fund is None:
        return None

    rows = (
        (
            await session.execute(
                select(MfFundManagerHistory)
                .where(MfFundManagerHistory.scheme_uid == isin)
                .order_by(MfFundManagerHistory.start_date.asc())
            )
        )
        .scalars()
        .all()
    )

    today = date.today()
    cutoff = today - timedelta(days=_MANAGER_CHANGE_WINDOW_DAYS)
    managers = [
        {
            "name": r.manager_name,
            "start_date": r.start_date.isoformat(),
            "tenure_years": round((today - r.start_date).days / 365.25, 1),
        }
        for r in rows
        if r.end_date is None
    ]
    manager_changes_5y = sum(1 for r in rows if r.end_date is not None and r.end_date >= cutoff)
    people = {"managers": managers, "manager_changes_5y": manager_changes_5y}

    amc_row = (
        await session.execute(
            select(
                func.count(MfFund.isin),
                func.count(func.distinct(MfFund.sebi_category)),
            ).where(MfFund.amc_name == fund.amc_name)
        )
    ).one()
    amc = {
        "amc_name": fund.amc_name,
        "scheme_count": amc_row[0] or 0,
        "category_count": amc_row[1] or 0,
    }

    return people, amc


_PEERS_CAP = 8


async def get_fund_peers(session: AsyncSession, isin: str) -> dict | None:
    """`fund.peers` — rank-adjacent same-category funds (feeds Alternatives + Similar).

    Unranked or segregated fund → empty peers, still 200 (§5 row 19/20).
    """
    fund = await session.get(MfFund, isin)
    if fund is None:
        return None
    if fund.is_segregated:
        return {"peers": []}

    rank_row = (
        await session.execute(
            select(MfFundRanks)
            .where(MfFundRanks.isin == isin)
            .order_by(MfFundRanks.as_of_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if rank_row is None:
        return {"peers": []}

    rows = (
        await session.execute(
            select(MfFundRanks, MfFund, MfFundMetrics)
            .join(MfFund, MfFund.isin == MfFundRanks.isin)
            .outerjoin(MfFundMetrics, MfFundMetrics.isin == MfFundRanks.isin)
            .where(
                MfFundRanks.sebi_category == rank_row.sebi_category,
                MfFundRanks.as_of_date == rank_row.as_of_date,
                MfFundRanks.isin != isin,
                MfFund.is_segregated.is_(False),
            )
        )
    ).all()

    nearest = sorted(rows, key=lambda row: abs(row[0].rank - rank_row.rank))[:_PEERS_CAP]

    peers = []
    for r, f, m in nearest:
        nav_points = m.nav_points if m else 0
        peers.append(
            {
                "isin": f.isin,
                "scheme_name": f.scheme_name,
                "fund_name_short": f.fund_name_short,
                "amc_name": f.amc_name,
                "verb_label": r.verb_label,
                "category_rank": r.rank,
                "return_1y_pct": m.return_1y_pct
                if m and nav_points >= _MIN_NAV_POINTS_1Y
                else None,
                "return_3y_pct": m.return_3y_pct
                if m and nav_points >= _MIN_NAV_POINTS_3Y
                else None,
                "expense_ratio_pct": float(f.expense_ratio_pct)
                if f.expense_ratio_pct is not None
                else None,
                "volatility_pct": m.volatility_pct if m else None,
            }
        )

    return {"peers": peers}


async def get_fund_factors(session: AsyncSession, isin: str) -> tuple[dict, dict] | None:
    """`fund.factors` + `fund.signals` (W2, §10.1) — confidence band/factors and the
    contributing/contradicting signal words, from the latest `mf_fund_ranks` row.
    Returns (factors_payload, signals_payload), or None if the fund doesn't exist.

    An unranked fund (or a fund whose latest eval was insufficient_data) still
    returns 200 with null factors/band — never a fabricated read (no-suppress, §14.1).
    `confidence_factors` is the engine's own named confidence-quality bands
    (consistency/recency/volatility/data_coverage today) — NOT a per-axis
    quality/valuation/momentum/risk/trend score (the engine does not compute one;
    see the W2 report deviations).
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

    as_of = rank_row.as_of_date.isoformat() if rank_row else None
    factors = {
        "factors": rank_row.confidence_factors if rank_row else None,
        "confidence_band": rank_row.confidence_band if rank_row else None,
        "as_of": as_of,
    }
    signals = {
        "contributing": list(rank_row.contributing_signals or []) if rank_row else [],
        "contradicting": list(rank_row.contradicting_signals or []) if rank_row else [],
        "as_of": as_of,
    }
    return factors, signals
