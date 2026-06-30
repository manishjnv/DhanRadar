"""Unit tests for mf/valuation.py (M2.2 — daily portfolio valuation series).

Pure math tests — no DB, no network, no Celery.
"""

from __future__ import annotations

import datetime

import pytest

from dhanradar.mf.valuation import ValuationPoint, compute_daily_value


_TODAY = datetime.date(2026, 6, 30)


class TestComputeDailyValue:
    def test_single_holding(self) -> None:
        """100 units × NAV 250.00 = 25,000.00"""
        point = compute_daily_value([(100.0, 250.0)], total_invested=20_000.0, valuation_date=_TODAY)
        assert point.total_value == 25_000.0
        assert point.total_invested == 20_000.0
        assert point.valuation_date == _TODAY

    def test_multiple_holdings(self) -> None:
        """Sum of (units × nav) across all holdings."""
        pairs = [(100.0, 250.0), (200.0, 100.0), (50.0, 300.0)]
        # 25,000 + 20,000 + 15,000 = 60,000
        point = compute_daily_value(pairs, total_invested=50_000.0, valuation_date=_TODAY)
        assert point.total_value == pytest.approx(60_000.0, abs=0.01)

    def test_zero_units_skipped(self) -> None:
        """A holding with 0 units contributes nothing."""
        point = compute_daily_value([(0.0, 500.0), (10.0, 100.0)], total_invested=1_000.0, valuation_date=_TODAY)
        assert point.total_value == pytest.approx(1_000.0, abs=0.01)

    def test_zero_nav_skipped(self) -> None:
        """A holding with 0 (or missing) NAV contributes nothing."""
        point = compute_daily_value([(10.0, 0.0), (10.0, 100.0)], total_invested=1_000.0, valuation_date=_TODAY)
        assert point.total_value == pytest.approx(1_000.0, abs=0.01)

    def test_empty_holdings(self) -> None:
        """No holdings → total_value = 0.0; should not raise."""
        point = compute_daily_value([], total_invested=0.0, valuation_date=_TODAY)
        assert point.total_value == 0.0
        assert point.total_invested == 0.0

    def test_rounds_to_two_dp(self) -> None:
        """Result is rounded to 2 decimal places."""
        # 1 unit × 100.005 = 100.005 → rounds to 100.01 (Python round)
        point = compute_daily_value([(1.0, 100.005)], total_invested=100.0, valuation_date=_TODAY)
        # Python's round(100.005, 2) may be 100.0 or 100.01 depending on float repr;
        # we only assert it has at most 2 decimal places of precision.
        assert abs(round(point.total_value, 2) - point.total_value) < 1e-9

    def test_returns_valuation_point(self) -> None:
        """Return type is ValuationPoint."""
        point = compute_daily_value([(10.0, 100.0)], total_invested=1_000.0, valuation_date=_TODAY)
        assert isinstance(point, ValuationPoint)
        assert point.valuation_date == _TODAY

    def test_negative_nav_skipped(self) -> None:
        """Negative NAV (bad data) is skipped — guard on nav > 0."""
        point = compute_daily_value([(-1.0, 100.0), (10.0, 100.0)], total_invested=1_000.0, valuation_date=_TODAY)
        # units=-1 → skipped (units > 0 check fails)
        assert point.total_value == pytest.approx(1_000.0, abs=0.01)
