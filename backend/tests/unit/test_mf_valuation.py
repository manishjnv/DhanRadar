"""Unit tests for mf/valuation.py (M2.2 — daily portfolio valuation series).

Pure math tests — no DB, no network, no Celery.
"""

from __future__ import annotations

import datetime

import pytest

from dhanradar.mf.valuation import (
    ENGINE_VERSION,
    ValuationPoint,
    compute_daily_value,
    replay_valuation_series,
)

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


class TestReplayValuationSeries:
    """§39.5 — full ledger x NAV replay retires the old flow-adjustment / reset patch."""

    def test_engine_version_constant(self) -> None:
        assert ENGINE_VERSION == "valuation-replay-1"

    def test_mid_window_purchase(self) -> None:
        """A purchase landing mid-window shows up as a value jump on its OWN date (I11 replay) —
        zero value before it, units x NAV from that date forward."""
        ledger_rows = [
            {
                "instrument_id": "INF1", "units": 10.0, "amount": -1000.0,
                "txn_type": "purchase", "txn_date": datetime.date(2026, 1, 3),
            },
        ]
        nav_by_isin = {
            "INF1": [(datetime.date(2026, 1, 1), 100.0), (datetime.date(2026, 1, 5), 105.0)],
        }
        points = replay_valuation_series(
            ledger_rows, nav_by_isin, datetime.date(2026, 1, 1), datetime.date(2026, 1, 5)
        )
        by_date = {p.valuation_date: p for p in points}
        assert by_date[datetime.date(2026, 1, 1)].total_value == 0.0
        assert by_date[datetime.date(2026, 1, 2)].total_value == 0.0
        assert by_date[datetime.date(2026, 1, 3)].total_value == pytest.approx(1000.0)  # 10 x 100
        assert by_date[datetime.date(2026, 1, 3)].total_invested == pytest.approx(1000.0)
        assert by_date[datetime.date(2026, 1, 5)].total_value == pytest.approx(1050.0)  # 10 x 105

    def test_nav_carry_forward_over_weekend_gap(self) -> None:
        """No NAV posts on Sat/Sun (real market data) — Friday's NAV carries forward until
        Monday's own NAV lands."""
        ledger_rows = [
            {
                "instrument_id": "INF1", "units": 10.0, "amount": -1000.0,
                "txn_type": "purchase", "txn_date": datetime.date(2026, 1, 1),
            },
        ]
        # Fri Jan-2 = 100, Mon Jan-5 = 110; no Sat/Sun rows.
        nav_by_isin = {"INF1": [(datetime.date(2026, 1, 2), 100.0), (datetime.date(2026, 1, 5), 110.0)]}
        points = replay_valuation_series(
            ledger_rows, nav_by_isin, datetime.date(2026, 1, 2), datetime.date(2026, 1, 5)
        )
        by_date = {p.valuation_date: p for p in points}
        assert by_date[datetime.date(2026, 1, 2)].total_value == pytest.approx(1000.0)  # Fri
        assert by_date[datetime.date(2026, 1, 3)].total_value == pytest.approx(1000.0)  # Sat carry
        assert by_date[datetime.date(2026, 1, 4)].total_value == pytest.approx(1000.0)  # Sun carry
        assert by_date[datetime.date(2026, 1, 5)].total_value == pytest.approx(1100.0)  # Mon's own NAV

    def test_no_nav_yet_contributes_zero(self) -> None:
        """A date before the ISIN's first known NAV contributes nothing (honest, not fabricated)."""
        ledger_rows = [
            {
                "instrument_id": "INF1", "units": 10.0, "amount": -1000.0,
                "txn_type": "purchase", "txn_date": datetime.date(2026, 1, 1),
            },
        ]
        nav_by_isin = {"INF1": [(datetime.date(2026, 1, 10), 100.0)]}
        points = replay_valuation_series(
            ledger_rows, nav_by_isin, datetime.date(2026, 1, 1), datetime.date(2026, 1, 3)
        )
        assert all(p.total_value == 0.0 for p in points)
        assert all(p.total_invested == pytest.approx(1000.0) for p in points)

    def test_empty_ledger_returns_zero_series(self) -> None:
        """No ledger rows → every day is zero (the caller decides whether to fall back instead
        of calling this at all for an empty ledger — this function itself never crashes)."""
        points = replay_valuation_series(
            [], {}, datetime.date(2026, 1, 1), datetime.date(2026, 1, 3)
        )
        assert len(points) == 3
        assert all(p.total_value == 0.0 and p.total_invested == 0.0 for p in points)

    def test_redemption_reduces_units_and_invested(self) -> None:
        """A later redemption reduces both units-held (so value drops) and net-invested."""
        ledger_rows = [
            {
                "instrument_id": "INF1", "units": 100.0, "amount": -2000.0,
                "txn_type": "purchase", "txn_date": datetime.date(2026, 1, 1),
            },
            {
                "instrument_id": "INF1", "units": -20.0, "amount": 500.0,
                "txn_type": "redemption", "txn_date": datetime.date(2026, 1, 3),
            },
        ]
        nav_by_isin = {"INF1": [(datetime.date(2026, 1, 1), 20.0)]}
        points = replay_valuation_series(
            ledger_rows, nav_by_isin, datetime.date(2026, 1, 1), datetime.date(2026, 1, 3)
        )
        by_date = {p.valuation_date: p for p in points}
        assert by_date[datetime.date(2026, 1, 2)].total_value == pytest.approx(2000.0)  # 100 x 20
        assert by_date[datetime.date(2026, 1, 3)].total_value == pytest.approx(1600.0)  # 80 x 20
        assert by_date[datetime.date(2026, 1, 3)].total_invested == pytest.approx(1500.0)  # 2000-500
