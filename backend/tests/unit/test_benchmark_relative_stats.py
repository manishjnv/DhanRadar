"""
Unit tests for `dhanradar.mf.risk.benchmark_relative_stats` (Block 0.7 — alpha /
beta / tracking error vs a mapped benchmark, index funds only).

Pure-function tests — no DB, no network. Covers:
  - Leveraged copy: fund = 1.5x the benchmark's periodic returns, zero-noise ->
    beta ~= 1.5, tracking_error ~= 0.
  - Identical series: fund == benchmark -> beta ~= 1, alpha ~= 0, TE ~= 0.
  - Insufficient data: fewer than min_points aligned common dates -> all-None.
  - Barely-overlapping calendars: two series that mostly don't share dates ->
    all-None (tests the common-date inner-join alignment, not just length).
"""

from __future__ import annotations

import datetime
import math
import statistics

import pytest

from dhanradar.mf.risk import BenchmarkRelativeStats, benchmark_relative_stats

_START = datetime.date(2023, 1, 2)


def _build_bench_series(n: int, start: datetime.date = _START) -> list[tuple[datetime.date, float]]:
    """Deterministic, non-degenerate synthetic benchmark series (small drift +
    oscillation, so periodic returns have real, non-zero variance)."""
    dates = [start + datetime.timedelta(days=i) for i in range(n)]
    vals = [100.0]
    for i in range(1, n):
        r = 0.001 * math.sin(i * 0.3) + 0.0002
        vals.append(vals[-1] * (1 + r))
    return list(zip(dates, vals))


def _leveraged_copy(
    bench_points: list[tuple[datetime.date, float]], leverage: float
) -> list[tuple[datetime.date, float]]:
    """Build a fund series whose periodic returns are EXACTLY ``leverage`` times
    the benchmark's — zero tracking error, beta == leverage by construction."""
    dates = [d for d, _ in bench_points]
    bench_vals = [v for _, v in bench_points]
    fund_vals = [100.0]
    for i in range(1, len(bench_vals)):
        bench_ret = bench_vals[i] / bench_vals[i - 1] - 1.0
        fund_vals.append(fund_vals[-1] * (1 + leverage * bench_ret))
    return list(zip(dates, fund_vals))


class TestLeveragedCopy:
    def test_beta_matches_leverage(self):
        """A fund whose EVERY periodic return is exactly 1.5x the benchmark's
        must have beta == 1.5 (perfect linear relationship, zero idiosyncratic
        noise around that line).

        Tracking error (stdev of fund_return - benchmark_return, NOT fund_return
        - beta*benchmark_return) is intentionally NOT asserted to be ~0 here: a
        1.5x-levered copy has returns that DIVERGE from the raw 1x benchmark by
        construction (diff_return = 0.5 * bench_return each period), so its
        tracking error against the plain benchmark is real and positive — this
        mirrors why real-world leveraged/inverse ETFs report large tracking
        error against their underlying index despite tracking it "perfectly"
        (R²=1) at their own leverage ratio. The expected TE is verified
        analytically below instead of assumed to be zero.
        """
        bench_points = _build_bench_series(300)
        fund_points = _leveraged_copy(bench_points, 1.5)

        stats = benchmark_relative_stats(fund_points, bench_points, risk_free_annual=0.065)

        assert stats.beta_1y is not None
        assert stats.tracking_error_pct is not None
        assert stats.alpha_1y is not None
        assert stats.beta_1y == pytest.approx(1.5, abs=1e-6)

        # Analytical check: diff_return = fund_return - bench_return = 0.5 *
        # bench_return every period (since fund_return = 1.5 * bench_return),
        # so TE = 0.5 * benchmark's own annualised volatility.
        bench_vals = [v for _, v in bench_points]
        bench_rets = [bench_vals[i] / bench_vals[i - 1] - 1.0 for i in range(1, len(bench_vals))]
        bench_annual_vol_pct = statistics.stdev(bench_rets) * math.sqrt(252) * 100.0
        assert stats.tracking_error_pct == pytest.approx(0.5 * bench_annual_vol_pct, rel=1e-9)


class TestIdenticalSeries:
    def test_beta_one_alpha_zero_te_zero(self):
        bench_points = _build_bench_series(300)
        fund_points = list(bench_points)  # identical copy

        stats = benchmark_relative_stats(fund_points, bench_points, risk_free_annual=0.065)

        assert stats.beta_1y == pytest.approx(1.0, abs=1e-6)
        assert stats.tracking_error_pct == pytest.approx(0.0, abs=1e-6)
        assert stats.alpha_1y == pytest.approx(0.0, abs=1e-4)


class TestInsufficientData:
    def test_fewer_than_min_points_returns_all_none(self):
        bench_points = _build_bench_series(50)
        fund_points = _leveraged_copy(bench_points, 1.2)

        stats = benchmark_relative_stats(fund_points, bench_points, risk_free_annual=0.065)

        assert stats == BenchmarkRelativeStats(alpha_1y=None, beta_1y=None, tracking_error_pct=None)

    def test_custom_min_points_honored(self):
        bench_points = _build_bench_series(50)
        fund_points = _leveraged_copy(bench_points, 1.2)

        # With min_points relaxed to fit the (shorter) synthetic series, a real
        # stats triple should come back instead of the all-None default.
        stats = benchmark_relative_stats(
            fund_points, bench_points, risk_free_annual=0.065, min_points=30
        )
        assert stats.beta_1y is not None
        assert stats.beta_1y == pytest.approx(1.2, abs=1e-6)


class TestBarelyOverlappingCalendars:
    def test_mostly_disjoint_dates_returns_all_none(self):
        """Fund and benchmark calendars barely overlap — only a handful of common
        dates exist even though each series individually has >= min_points rows."""
        bench_points = _build_bench_series(300, start=datetime.date(2020, 1, 1))
        # Fund series starts almost 300 days after the benchmark's last date —
        # only the last few benchmark dates and first few fund dates could ever
        # coincide, and they don't share the same calendar anyway (fund starts
        # on a date range that begins after the benchmark's window ends).
        fund_start = bench_points[-1][0] + datetime.timedelta(days=1)
        fund_points = _build_bench_series(300, start=fund_start)

        stats = benchmark_relative_stats(fund_points, bench_points, risk_free_annual=0.065)

        assert stats == BenchmarkRelativeStats(alpha_1y=None, beta_1y=None, tracking_error_pct=None)


class TestDegenerateBenchmark:
    def test_flat_benchmark_returns_all_none(self):
        """A benchmark with (near-)zero variance makes beta/alpha unstable —
        withheld, never a fabricated/exploding number."""
        dates = [_START + datetime.timedelta(days=i) for i in range(300)]
        bench_points = [(d, 100.0) for d in dates]  # perfectly flat
        fund_points = _build_bench_series(300)  # any real, non-flat series

        stats = benchmark_relative_stats(fund_points, bench_points, risk_free_annual=0.065)

        assert stats == BenchmarkRelativeStats(alpha_1y=None, beta_1y=None, tracking_error_pct=None)
