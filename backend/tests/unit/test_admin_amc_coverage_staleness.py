"""
Unit tests for `_compute_staleness` (admin/amc_coverage_router.py) — the pure
function that derives an AMC's (last_updated, staleness_days) staleness
indicator from the two disclosure-freshness signals available (MAX(aum_as_of),
MAX(constituents' as_of_month)). No DB — plain function of already-fetched
date values.
"""

from __future__ import annotations

from datetime import date

from dhanradar.admin.amc_coverage_router import _compute_staleness


def test_staleness_none_when_neither_signal_available():
    today = date(2026, 7, 8)
    assert _compute_staleness(today, None, None) == (None, None)


def test_first_of_month_dates_measure_from_month_end():
    # Disclosure months are stored as the FIRST of the month, which used to
    # read June-30 data as "40 days stale" on July 11 (founder-flagged).
    # A day-1 date is a month marker: staleness measures from month-END.
    import datetime as _dt

    last_updated, days = _compute_staleness(_dt.date(2026, 7, 11), None, _dt.date(2026, 6, 1))
    assert last_updated == "2026-06-30"
    assert days == 11


def test_month_end_basis_never_goes_negative_within_current_month():
    import datetime as _dt

    # Data for the CURRENT month (day-1 marker) clamps to today, never negative.
    last_updated, days = _compute_staleness(_dt.date(2026, 7, 11), None, _dt.date(2026, 7, 1))
    assert last_updated == "2026-07-11"
    assert days == 0


def test_staleness_uses_aum_as_of_when_constituents_missing():
    today = date(2026, 7, 8)
    # day-1 input = month marker -> measured from month-END (2026-07-11 fix).
    last_updated, staleness_days = _compute_staleness(today, date(2026, 6, 1), None)
    assert last_updated == "2026-06-30"
    assert staleness_days == 8


def test_staleness_uses_constituents_as_of_when_aum_missing():
    today = date(2026, 7, 8)
    last_updated, staleness_days = _compute_staleness(today, None, date(2026, 6, 15))
    assert last_updated == "2026-06-15"
    assert staleness_days == 23


def test_staleness_picks_the_later_of_the_two_signals():
    today = date(2026, 7, 8)
    # constituents is more recent than aum_as_of -> constituents wins.
    last_updated, staleness_days = _compute_staleness(today, date(2026, 5, 1), date(2026, 6, 20))
    assert last_updated == "2026-06-20"
    assert staleness_days == 18

    # aum_as_of is more recent than constituents -> aum_as_of wins; the day-1
    # month marker measures from month-end, clamped to today (2026-07-11 fix).
    last_updated2, staleness_days2 = _compute_staleness(today, date(2026, 7, 1), date(2026, 5, 1))
    assert last_updated2 == "2026-07-08"
    assert staleness_days2 == 0


def test_staleness_zero_days_when_updated_today():
    today = date(2026, 7, 8)
    last_updated, staleness_days = _compute_staleness(today, today, None)
    assert last_updated == "2026-07-08"
    assert staleness_days == 0
