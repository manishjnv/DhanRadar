"""
DhanRadar — fund-vs-own-benchmark TRI alpha (Phase 4c pt5 / MF_MASTER_DB_IMPROVEMENT_PLAN.md
"Phase 4").

Pure module: no DB / network / Celery imports — golden-set testable, same pattern as
`dhanradar.mf.category_series` / `dhanradar.mf.benchmark_map`.

What this computes: a SIMPLE 1-year return differential — the fund's own trailing-1Y NAV
return (`return_1y_pct`, already computed by `dhanradar.mf.signals.extended_horizon_stats`)
minus its OWN SEBI-declared benchmark's trailing-1Y TRI return, over the SAME Actual/365
trailing window, anchored on the SAME latest-NAV date used for the fund's own return_1y_pct.

Deliberately NOT the CAPM alpha in `dhanradar.mf.risk.benchmark_relative_stats` (annualised,
regression-based, index-funds-only, price-index track) — this is the plain, honest
differential described by MF_MASTER_DB_IMPROVEMENT_PLAN.md's Phase 4 spec ("this fund
returned +4.7% vs its benchmark +6.1% = -1.4% alpha"), extended (Phase 4c pt5) to run
against the TRI track (`mf.mf_benchmark_tri`, populated via `mf.mf_benchmark_map`) for ANY
fund with a resolved benchmark, not just index funds.

COMPLIANCE (ADR-0033, binding): the TRI series feeding this module is internal-compute
only. `alpha_1y_tri_pct` (the differential) IS allowed client-facing per the Phase 4 spec,
but no surface wires it up this session — see tests/unit/test_mf_benchmark_tri_compliance.py.
"""

from __future__ import annotations

from datetime import date, timedelta

#: Same 1-year lookback `dhanradar.mf.signals._trailing_return_pct` uses for
#: return_1y_pct — kept as an explicit, importable constant so the two windows can
#: never silently drift apart.
LOOKBACK_DAYS = 365

#: Minimum number of TRI rows required in the loaded window before a fund's alpha is
#: computed at all (mirrors mf_metrics_refresh's own nav_points >= 252 gate for 1Y
#: stats — MF_MASTER_DB_IMPROVEMENT_PLAN.md "Phase 4"/B2 spec).
MIN_TRI_POINTS = 252


def tri_trailing_return_pct(
    tri_points: list[tuple[date, float]],
    anchor_date: date,
    *,
    lookback_days: int = LOOKBACK_DAYS,
) -> float | None:
    """Trailing return (in PERCENT) of a TRI series over `lookback_days` ending at (or
    just before) `anchor_date` — mirrors `dhanradar.mf.signals._trailing_return_pct`'s
    algorithm exactly, but anchored explicitly (the fund's own latest NAV date) rather
    than the series' own last point, so the TRI series and the fund's NAV series don't
    need to share a calendar.

    "latest" = the most recent TRI point at or before `anchor_date` (TRI publishes with
    a ~2-day lag, so this is rarely `anchor_date` itself). "base" = the earliest TRI
    point within `lookback_days` of that latest point (falls back to the series' very
    first point if the series is younger than `lookback_days`, same honest-partial
    convention as `_trailing_return_pct`). None if there are fewer than 2 usable points
    at or before `anchor_date`, or the base value is not strictly positive.
    """
    eligible = sorted(p for p in tri_points if p[0] <= anchor_date)
    if len(eligible) < 2:
        return None
    latest_date, latest_value = eligible[-1]
    cutoff = latest_date - timedelta(days=lookback_days)
    base: tuple[date, float] | None = None
    for d, v in eligible:
        if d >= cutoff:
            base = (d, v)
            break
    if base is None:
        base = eligible[0]
    base_value = base[1]
    if base_value <= 0:
        return None
    return (latest_value / base_value - 1.0) * 100.0


def alpha_1y_tri_pct(
    return_1y_pct: float | None,
    tri_points: list[tuple[date, float]],
    anchor_date: date,
    *,
    min_points: int = MIN_TRI_POINTS,
    lookback_days: int = LOOKBACK_DAYS,
) -> float | None:
    """`return_1y_pct - tri_1y` — the fund's trailing-1Y NAV return minus its mapped
    benchmark's trailing-1Y TRI return, both in PERCENT.

    Returns None (never fabricated) when:
      * `return_1y_pct` itself is None (fund has no 1Y NAV return — insufficient data);
      * `tri_points` has fewer than `min_points` rows (thin/just-mapped index — mirrors
        mf_metrics_refresh's own nav_points >= 252 gate for other 1Y stats);
      * `tri_trailing_return_pct` cannot produce a base point (degenerate series).
    """
    if return_1y_pct is None:
        return None
    if len(tri_points) < min_points:
        return None
    tri_1y = tri_trailing_return_pct(tri_points, anchor_date, lookback_days=lookback_days)
    if tri_1y is None:
        return None
    return return_1y_pct - tri_1y
