"""Unit tests for Phase 4c pt4 — dhanradar.mf.comparison (pure rebase/anchor math).

Coverage:
1. rebase_series always starts at exactly 100.0, even when the anchor value comes from
   a row whose date differs from anchor_date (the "nearest on-or-before" case).
2. nearest_value_on_or_before — exact match, gap-fill, and "nothing qualifies" cases.
3. category_coverage — the 60% thin-cohort threshold math.
"""

from __future__ import annotations

from datetime import date

from dhanradar.mf.comparison import (
    CATEGORY_THIN_REASON,
    MIN_CATEGORY_COVERAGE,
    MIN_CATEGORY_FUND_COUNT,
    NIFTY50_FALLBACK_LABEL,
    category_coverage,
    nearest_value_on_or_before,
    rebase_series,
)

_D0, _D1, _D2, _D3 = date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 4)


# ---------------------------------------------------------------------------
# 1. rebase_series — every emitted series starts at exactly 100.0
# ---------------------------------------------------------------------------


def test_rebase_series_first_point_is_always_exactly_100():
    points = rebase_series([(_D1, 110.0), (_D2, 121.0)], _D0, 100.0)
    assert points[0] == {"d": _D0.isoformat(), "v": 100.0}


def test_rebase_series_math_matches_hand_computation():
    points = rebase_series([(_D1, 110.0), (_D2, 88.0)], _D0, 100.0)
    assert points == [
        {"d": _D0.isoformat(), "v": 100.0},
        {"d": _D1.isoformat(), "v": 110.0},
        {"d": _D2.isoformat(), "v": 88.0},
    ]


def test_rebase_series_anchor_value_need_not_be_a_row_in_the_input():
    """The nearest-on-or-before value (e.g. a benchmark/category table with no row
    exactly on the fund's anchor date) still yields a first point of exactly 100.0."""
    # anchor_value=1000.0 came from some earlier date NOT in rows_after_anchor.
    points = rebase_series([(_D1, 1050.0)], _D0, 1000.0)
    assert points[0]["v"] == 100.0
    assert points[1]["v"] == 105.0


def test_rebase_series_empty_rows_after_anchor_still_yields_the_anchor_point():
    points = rebase_series([], _D0, 100.0)
    assert points == [{"d": _D0.isoformat(), "v": 100.0}]


# ---------------------------------------------------------------------------
# 2. nearest_value_on_or_before
# ---------------------------------------------------------------------------


def test_nearest_value_exact_match():
    rows = [(_D0, 10.0), (_D1, 20.0), (_D2, 30.0)]
    assert nearest_value_on_or_before(rows, _D1) == 20.0


def test_nearest_value_gap_fills_to_the_last_row_before_target():
    # No row on _D1 — the materialized table skipped a day; must fall back to _D0's value.
    rows = [(_D0, 10.0), (_D2, 30.0)]
    assert nearest_value_on_or_before(rows, _D1) == 10.0


def test_nearest_value_none_when_series_starts_after_target():
    rows = [(_D2, 30.0), (_D3, 40.0)]
    assert nearest_value_on_or_before(rows, _D0) is None


def test_nearest_value_empty_rows_returns_none():
    assert nearest_value_on_or_before([], _D0) is None


def test_nearest_value_picks_the_latest_qualifying_row_not_the_first():
    rows = [(_D0, 10.0), (_D1, 20.0), (_D2, 30.0)]
    assert nearest_value_on_or_before(rows, _D2) == 30.0


# ---------------------------------------------------------------------------
# 3. category_coverage — thin-cohort threshold math
# ---------------------------------------------------------------------------


def test_category_coverage_full_overlap_is_1():
    fund_dates = {_D0, _D1, _D2}
    assert category_coverage(fund_dates, fund_dates) == 1.0


def test_category_coverage_partial_overlap():
    fund_dates = {_D0, _D1, _D2, _D3}
    qualifying = {_D0, _D1}
    assert category_coverage(fund_dates, qualifying) == 0.5


def test_category_coverage_no_overlap_is_0():
    assert category_coverage({_D0, _D1}, {_D2, _D3}) == 0.0


def test_category_coverage_empty_fund_dates_never_divides_by_zero():
    assert category_coverage(set(), {_D0}) == 0.0


def test_category_coverage_threshold_matches_spec_60_percent():
    assert MIN_CATEGORY_COVERAGE == 0.6
    assert MIN_CATEGORY_FUND_COUNT == 10
    # 3/5 = 0.6 exactly qualifies (>=, not >).
    fund_dates = {_D0, _D1, _D2, date(2026, 1, 5), date(2026, 1, 6)}
    qualifying = {_D0, _D1, _D2}
    coverage = category_coverage(fund_dates, qualifying)
    assert coverage == 0.6
    assert coverage >= MIN_CATEGORY_COVERAGE


# ---------------------------------------------------------------------------
# 4. Constants — the spec's exact wording (frontend renders these verbatim)
# ---------------------------------------------------------------------------


def test_category_thin_reason_exact_wording():
    assert CATEGORY_THIN_REASON == "category average unavailable — cohort too thin"


def test_nifty50_fallback_label_exact_wording():
    assert NIFTY50_FALLBACK_LABEL == "Nifty 50 (broad market — not this scheme's benchmark)"
