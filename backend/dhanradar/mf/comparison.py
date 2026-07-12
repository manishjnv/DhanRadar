"""
DhanRadar — fund-vs-benchmark-vs-category rebase math (Phase 4c pt4,
MF_MASTER_DB_IMPROVEMENT_PLAN.md "Phase 4c").

Pure module: no DB / network / Celery imports — golden-set testable, same pattern as
:mod:`dhanradar.mf.category_series` / :mod:`dhanradar.mf.benchmark_map`. The DB read-
orchestration for ``GET /api/v1/mf/fund/{isin}/comparison`` lives in
:func:`dhanradar.mf.fund_read.get_fund_comparison`, which calls these helpers — the
query logic changes with the schema, this math never should.

CORRECTNESS CRUX (binding): the fund line, its benchmark line, and its category-peer
line are rebased to 100.0 at ONE SHARED anchor date — the fund's own first NAV date
on/after the requested window's start. :func:`rebase_series` always synthesizes an
anchor point AT that date (value 100.0) as the series' first entry, even when the
source table (``mf_category_series`` / the internal TRI table) has no row exactly on
that date — its own 100.0 reference is the nearest available value ON OR BEFORE the
anchor (:func:`nearest_value_on_or_before`). This guarantees every emitted series
starts at exactly 100.0 and all three lines are comparable from the same starting
point — never three different anchor dates.

COMPLIANCE (ADR-0033): every value :func:`rebase_series` emits is a base-100 RATIO,
never a raw index/TRI level — this is the one seam where an internal per-day level
becomes a client-safe number.
"""

from __future__ import annotations

from datetime import date

# Category-line thin-cohort suppression reason (spec wording, binding — the frontend
# renders this string verbatim, never re-derives it).
CATEGORY_THIN_REASON = "category average unavailable — cohort too thin"

# Server-side thin-cohort thresholds (Phase 4c, binding).
MIN_CATEGORY_FUND_COUNT = 10
MIN_CATEGORY_COVERAGE = 0.6

# Honest-fallback label (spec wording, binding — verbatim, never edit without updating
# the frontend copy that renders it) for when a fund's AMFI benchmark string has no
# confident mapping, or the mapped index has no data to rebase against.
NIFTY50_FALLBACK_LABEL = "Nifty 50 (broad market — not this scheme's benchmark)"


def nearest_value_on_or_before(rows: list[tuple[date, float]], target: date) -> float | None:
    """The value of the last row with ``date <= target``.

    ``rows`` MUST be sorted ascending by date (every caller queries ORDER BY date ASC)
    — a linear scan, never re-sorts. Returns None when no row qualifies (the series
    starts after ``target`` — nothing to rebase against).
    """
    value: float | None = None
    for d, v in rows:
        if d > target:
            break
        value = v
    return value


def rebase_series(
    rows_after_anchor: list[tuple[date, float]], anchor_date: date, anchor_value: float
) -> list[dict]:
    """Rebase ``rows_after_anchor`` (dates strictly > ``anchor_date``, ascending) to
    base-100 at ``anchor_value``, PREPENDING the anchor point itself (100.0, exact) as
    the first entry.

    ``anchor_value`` need not come from a row in ``rows_after_anchor`` — it is
    typically the nearest on-or-before value found via :func:`nearest_value_on_or_before`
    against a table that has no row on the exact anchor date (a materialized daily
    table rarely lands on the same trading day as this fund's own NAV history).
    """
    points = [{"d": anchor_date.isoformat(), "v": 100.0}]
    for d, v in rows_after_anchor:
        points.append({"d": d.isoformat(), "v": round(v / anchor_value * 100.0, 4)})
    return points


def category_coverage(fund_dates: set[date], qualifying_category_dates: set[date]) -> float:
    """Fraction of the fund line's OWN dates that also have a qualifying
    (``fund_count >= MIN_CATEGORY_FUND_COUNT``) category-series value.

    0.0 for an empty ``fund_dates`` (never divides by zero).
    """
    if not fund_dates:
        return 0.0
    return len(fund_dates & qualifying_category_dates) / len(fund_dates)
