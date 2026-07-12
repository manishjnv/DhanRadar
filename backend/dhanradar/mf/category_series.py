"""
DhanRadar — per-category chained median-return index math (Phase 4c pt2).

Pure module: turns per-scheme NAV series into a per-category, chained, base-100 index —
the reference math for what `dhanradar.tasks.mf.category_series_refresh` persists into
`mf.mf_category_series` via SQL (percentile_cont + a cumulative-product window function,
same numbers — the SQL path exists because 14k ISINs x 10y of Python loops is too slow /
can OOM the box; this module is the golden-set-testable spec it must match).
No DB / network / Celery imports — same pattern as `dhanradar.mf.cohort`.

Methodology (binding — MF_MASTER_DB_IMPROVEMENT_PLAN.md "Phase 4c"):
  * For each category and each trading day: daily_return_i = nav_i(t)/nav_i(t-1) - 1 for
    every scheme with both NAVs; median_return(t) = median over schemes; fund_count(t) =
    that count.
  * index(t) = index(t-1) * (1 + median_return(t)); base 100.0 at the series START — the
    first stored point already reflects that day's return against an implicit 100 anchor
    the day before. This avoids start-date bias and tolerates schemes entering/leaving the
    category (a chart window rebases later with one division: index[t]/index[t0]*100).
  * ``category`` is the same grouping key `dhanradar.mf.cohort` groups peers by
    (`mf_funds.sebi_category`), and ONLY ONE series-contribution per SCHEME: plan/option
    variants (Direct/Regular x Growth/IDCW) of the same scheme collapse to a single
    canonical NAV series before the median is taken (cohort.py's on-the-fly peer set does
    NOT dedupe variants; this materialized table does, mirroring the platform-wide
    SCHEME_KEY counting rule — models/mf.py::SCHEME_KEY). Canonical-variant priority
    mirrors the "Direct-Plan-Growth is the representative variant" convention already
    established elsewhere (tasks/mf_scheme_master.py::secondary_isin_for,
    tasks/mf.py::_resolve_scheme_isins): Direct+Growth > any Growth > lowest ISIN.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CategorySeriesPoint:
    """One row of the materialized category index — same shape as mf.mf_category_series."""

    series_date: date
    index_value: float
    median_daily_return: float | None
    fund_count: int


def pick_canonical_isin(variants: list[tuple[str, str | None, str | None]]) -> str:
    """Pick the ONE canonical ISIN for a scheme from its plan/option variant rows.

    ``variants`` is a non-empty list of (isin, plan_type, option_type) for the SAME scheme
    (same SCHEME_KEY = COALESCE(fund_name_short, isin)). Priority: Direct+Growth > any
    Growth > lowest ISIN (deterministic fallback for a scheme with only IDCW variants).
    """

    def _priority(v: tuple[str, str | None, str | None]) -> tuple[int, str]:
        isin, plan_type, option_type = v
        if plan_type == "direct" and option_type == "growth":
            rank = 0
        elif option_type == "growth":
            rank = 1
        else:
            rank = 2
        return (rank, isin)

    return min(variants, key=_priority)[0]


def daily_returns(nav_by_date: dict[date, float]) -> dict[date, float]:
    """Day-over-day returns for ONE scheme's NAV series.

    Uses each date's immediately-preceding date IN THE SERIES (not calendar t-1) as the
    prior trading day — correct for AMFI data (rows only exist on trading days) and
    naturally tolerant of a scheme's own gaps (a newly-launched scheme's first NAV date
    has no return; a scheme with a data gap compares against its last known NAV point).
    """
    dates = sorted(nav_by_date)
    out: dict[date, float] = {}
    for prev_d, cur_d in zip(dates, dates[1:]):
        prev_nav = nav_by_date[prev_d]
        cur_nav = nav_by_date[cur_d]
        if prev_nav and prev_nav > 0:
            out[cur_d] = cur_nav / prev_nav - 1.0
    return out


def median_returns_by_day(
    scheme_returns: dict[str, dict[date, float]],
) -> dict[date, tuple[float, int]]:
    """Combine every scheme's per-day return into the category's (median, fund_count)."""
    by_day: dict[date, list[float]] = {}
    for returns in scheme_returns.values():
        for d, r in returns.items():
            by_day.setdefault(d, []).append(r)
    return {d: (statistics.median(rs), len(rs)) for d, rs in by_day.items()}


def chain_index(
    daily: dict[date, tuple[float, int]], *, base: float = 100.0
) -> list[CategorySeriesPoint]:
    """Chain a category's per-day (median_return, fund_count) into a base-100 index.

    Sorted ascending by date. ``base`` is the anchor to chain OFF (pass the last stored
    index_value to continue an existing series across a nightly/backfill boundary);
    defaults to 100.0 for a series' first-ever computed point.
    """
    points: list[CategorySeriesPoint] = []
    index_value = base
    for d in sorted(daily):
        median_return, fund_count = daily[d]
        index_value = index_value * (1.0 + median_return)
        points.append(CategorySeriesPoint(d, index_value, median_return, fund_count))
    return points
