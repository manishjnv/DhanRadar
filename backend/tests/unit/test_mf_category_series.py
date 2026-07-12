"""Unit tests for Phase 4c pt2 — dhanradar.mf.category_series (pure chained-index math).

Coverage:
1. Chained-index math: a hand-computed 3-fund fixture, exact to 6 decimals.
2. fund_count correctness: per-day counts follow which schemes have a return that day.
3. Scheme-dedup: pick_canonical_isin prefers Direct+Growth, then any Growth, then the
   lowest ISIN — mirrors the Direct-Plan-Growth convention used elsewhere
   (tasks/mf_scheme_master.py, tasks/mf.py::_resolve_scheme_isins).
"""

from __future__ import annotations

from datetime import date

from dhanradar.mf.category_series import (
    MAX_ABS_DAILY_RETURN,
    CategorySeriesPoint,
    chain_index,
    daily_returns,
    median_returns_by_day,
    pick_canonical_isin,
)

# ---------------------------------------------------------------------------
# 1. Chained-index math — 3-fund fixture, hand-computed
# ---------------------------------------------------------------------------
#
# Fund A: 100.0 -> 101.0 -> 102.0 -> 103.02   (D1/D2/D3 returns: 1%, ~0.990099%, 1%)
# Fund B: 200.0 -> 202.0 -> 201.0 -> 203.01   (D1/D2/D3 returns: 1%, -0.495050%, 1%)
# Fund C: 50.0  -> 50.5  -> 51.0  -> 51.51    (D1/D2/D3 returns: 1%, ~0.990099%, 1%)
#
# D1 median = 1%              -> index = 100 * 1.01               = 101.0
# D2 median = 1/101 (A == C)  -> index = 101 * (1 + 1/101)         = 102.0  (101*(1/101)=1 exactly)
# D3 median = 1%              -> index = 102 * 1.01               = 103.02
# fund_count = 3 every day.

_D0, _D1, _D2, _D3 = date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)

_FUND_A = {_D0: 100.0, _D1: 101.0, _D2: 102.0, _D3: 103.02}
_FUND_B = {_D0: 200.0, _D1: 202.0, _D2: 201.0, _D3: 203.01}
_FUND_C = {_D0: 50.0, _D1: 50.5, _D2: 51.0, _D3: 51.51}


def test_chained_index_matches_hand_math_3fund_fixture():
    scheme_returns = {
        "A": daily_returns(_FUND_A),
        "B": daily_returns(_FUND_B),
        "C": daily_returns(_FUND_C),
    }
    daily = median_returns_by_day(scheme_returns)
    points = chain_index(daily)

    by_date = {p.series_date: p for p in points}
    assert set(by_date) == {_D1, _D2, _D3}

    assert round(by_date[_D1].index_value, 6) == 101.0
    assert round(by_date[_D2].index_value, 6) == 102.0
    assert round(by_date[_D3].index_value, 6) == 103.02

    assert round(by_date[_D1].median_daily_return, 6) == 0.01
    assert round(by_date[_D2].median_daily_return, 6) == round(1 / 101, 6)
    assert round(by_date[_D3].median_daily_return, 6) == 0.01


def test_chain_index_base_100_anchor_default():
    """The very first computed point already reflects that day's return against the
    implicit 100 anchor — no separate index=100 row is emitted for the day before."""
    points = chain_index({_D1: (0.05, 4)})
    assert points == [CategorySeriesPoint(_D1, 105.0, 0.05, 4)]


def test_chain_index_continues_off_a_supplied_anchor():
    """A nightly/backfill re-run continues the chain off the last STORED index_value
    (not a fresh 100) — this is how the SQL task stitches across date-range boundaries."""
    points = chain_index({_D2: (0.02, 5)}, base=102.0)
    assert round(points[0].index_value, 6) == round(102.0 * 1.02, 6)


# ---------------------------------------------------------------------------
# 2. fund_count correctness
# ---------------------------------------------------------------------------


def test_fund_count_reflects_which_schemes_have_a_return_that_day():
    scheme_returns = {
        "S1": {_D1: 0.01, _D2: 0.02},
        "S2": {_D1: 0.03},
        "S3": {_D2: 0.04, _D3: 0.05},
    }
    daily = median_returns_by_day(scheme_returns)

    assert daily[_D1] == (0.02, 2)  # median(0.01, 0.03), count=2
    assert daily[_D2] == (0.03, 2)  # median(0.02, 0.04), count=2
    assert daily[_D3] == (0.05, 1)  # only S3


def test_daily_returns_a_schemes_first_nav_date_has_no_return():
    """A newly-launched scheme's very first NAV date contributes no return (no prior
    NAV to divide against) — it must not silently degrade the day's median."""
    returns = daily_returns({_D0: 100.0})
    assert returns == {}


# ---------------------------------------------------------------------------
# 3. Scheme-dedup — pick_canonical_isin
# ---------------------------------------------------------------------------


def test_pick_canonical_isin_prefers_direct_growth():
    variants = [
        ("ISIN_REG_GROWTH", "regular", "growth"),
        ("ISIN_DIR_GROWTH", "direct", "growth"),
        ("ISIN_DIR_IDCW", "direct", "idcw"),
    ]
    assert pick_canonical_isin(variants) == "ISIN_DIR_GROWTH"


def test_pick_canonical_isin_falls_back_to_any_growth():
    variants = [
        ("ISIN_REG_IDCW", "regular", "idcw"),
        ("ISIN_REG_GROWTH", "regular", "growth"),
    ]
    assert pick_canonical_isin(variants) == "ISIN_REG_GROWTH"


def test_pick_canonical_isin_falls_back_to_lowest_isin_when_no_growth_variant():
    variants = [
        ("ISIN_B_IDCW", "regular", "idcw"),
        ("ISIN_A_IDCW", "direct", "idcw"),
    ]
    assert pick_canonical_isin(variants) == "ISIN_A_IDCW"


# ---------------------------------------------------------------------------
# 4. Return-sanity hardening (the 2018-05-03 Overnight-Fund 99x lesson) —
#    daily_returns() must drop insane single-day moves before they ever reach the
#    median/fund_count, not just clamp them downstream.
# ---------------------------------------------------------------------------


def test_daily_returns_excludes_ln_blowup_return_of_minus_one():
    # prev=100 -> cur=0 is r == -1.0 exactly — the LN(1+r) domain boundary.
    returns = daily_returns({_D0: 100.0, _D1: 0.0})
    assert returns == {}


def test_daily_returns_excludes_scale_change_return_of_99():
    # prev=1 -> cur=100 is r == 99.0 — a 100x jump (face-value/scale change or bad data).
    returns = daily_returns({_D0: 1.0, _D1: 100.0})
    assert returns == {}


def test_daily_returns_excludes_large_negative_return_beyond_bound():
    # r == -0.6, beyond the -MAX_ABS_DAILY_RETURN floor but still > -1 (not an LN blowup).
    returns = daily_returns({_D0: 100.0, _D1: 40.0})
    assert returns == {}


def test_daily_returns_includes_a_real_world_return():
    # r == 0.04 (4%) — well within bound, must be kept.
    returns = daily_returns({_D0: 100.0, _D1: 104.0})
    assert round(returns[_D1], 6) == 0.04


def test_daily_returns_includes_return_exactly_at_the_bound():
    # r == MAX_ABS_DAILY_RETURN exactly (0.5) — inclusive boundary ("<=").
    returns = daily_returns({_D0: 100.0, _D1: 150.0})
    assert round(returns[_D1], 6) == MAX_ABS_DAILY_RETURN


def test_fund_count_reflects_exclusion_of_an_insane_return():
    # S2's D1 return is a scale-change (10000%) and must be excluded — fund_count for
    # D1 drops to 1 (S1 only), not 2.
    scheme_returns = {
        "S1": daily_returns({_D0: 100.0, _D1: 101.0}),
        "S2": daily_returns({_D0: 1.0, _D1: 100.0}),  # r=99.0, excluded
    }
    daily = median_returns_by_day(scheme_returns)
    median, count = daily[_D1]
    assert round(median, 6) == 0.01
    assert count == 1
