"""Unit tests for Phase 4c pt5 — dhanradar.mf.benchmark_alpha (pure TRI-alpha math)."""

from __future__ import annotations

from datetime import date, timedelta

from dhanradar.mf.benchmark_alpha import (
    LOOKBACK_DAYS,
    MIN_TRI_POINTS,
    alpha_1y_tri_pct,
    tri_trailing_return_pct,
)


def _daily_series(
    start: date, n: int, start_value: float, daily_growth: float
) -> list[tuple[date, float]]:
    """A synthetic daily TRI series, `n` calendar days starting at `start`, compounding
    at `daily_growth` per day (e.g. 0.0003 ~ a gently rising index)."""
    out: list[tuple[date, float]] = []
    value = start_value
    for i in range(n):
        out.append((start + timedelta(days=i), value))
        value *= 1.0 + daily_growth
    return out


# ---------------------------------------------------------------------------
# tri_trailing_return_pct
# ---------------------------------------------------------------------------


def test_tri_trailing_return_simple_doubling():
    anchor = date(2026, 1, 1)
    points = [
        (anchor - timedelta(days=365), 100.0),
        (anchor, 200.0),
    ]
    assert tri_trailing_return_pct(points, anchor) == 100.0


def test_tri_trailing_return_uses_latest_point_at_or_before_anchor():
    # A point AFTER anchor_date must never be used as "latest".
    anchor = date(2026, 1, 1)
    points = [
        (anchor - timedelta(days=365), 100.0),
        (anchor, 150.0),
        (anchor + timedelta(days=5), 999.0),  # future — must be ignored
    ]
    assert tri_trailing_return_pct(points, anchor) == 50.0


def test_tri_trailing_return_publish_lag_uses_most_recent_available():
    # TRI publishes with a ~2-day lag — anchor_date itself may have no row.
    anchor = date(2026, 1, 10)
    points = [
        (date(2025, 1, 8), 100.0),
        (date(2026, 1, 8), 120.0),  # most recent AT OR BEFORE anchor
    ]
    assert round(tri_trailing_return_pct(points, anchor), 4) == 20.0


def test_tri_trailing_return_falls_back_to_first_point_when_series_younger_than_lookback():
    anchor = date(2026, 6, 1)
    points = [
        (date(2026, 1, 1), 100.0),  # < 365 days old — becomes the base by fallback
        (anchor, 110.0),
    ]
    assert round(tri_trailing_return_pct(points, anchor), 4) == 10.0


def test_tri_trailing_return_none_for_fewer_than_2_eligible_points():
    anchor = date(2026, 1, 1)
    assert tri_trailing_return_pct([(anchor, 100.0)], anchor) is None
    assert tri_trailing_return_pct([], anchor) is None


def test_tri_trailing_return_none_when_all_points_after_anchor():
    anchor = date(2026, 1, 1)
    points = [(anchor + timedelta(days=1), 100.0), (anchor + timedelta(days=2), 105.0)]
    assert tri_trailing_return_pct(points, anchor) is None


def test_tri_trailing_return_none_for_nonpositive_base_value():
    anchor = date(2026, 1, 1)
    points = [(anchor - timedelta(days=365), 0.0), (anchor, 100.0)]
    assert tri_trailing_return_pct(points, anchor) is None


def test_tri_trailing_return_custom_lookback_days():
    anchor = date(2026, 1, 1)
    points = [
        (anchor - timedelta(days=180), 100.0),
        (anchor - timedelta(days=10), 105.0),
        (anchor, 110.0),
    ]
    # A 30-day lookback should use the -10d point as base, not the -180d point.
    assert round(tri_trailing_return_pct(points, anchor, lookback_days=30), 4) == round(
        (110.0 / 105.0 - 1.0) * 100.0, 4
    )


# ---------------------------------------------------------------------------
# alpha_1y_tri_pct
# ---------------------------------------------------------------------------


def test_alpha_1y_tri_pct_simple_differential():
    anchor = date(2026, 1, 1)
    tri_points = _daily_series(anchor - timedelta(days=400), 401, 100.0, 0.0)
    # Force the TRI 1Y return to a known value by overriding the endpoints directly.
    tri_points = [(anchor - timedelta(days=365), 100.0), (anchor, 106.0)] + tri_points
    result = alpha_1y_tri_pct(12.0, tri_points, anchor, min_points=2)
    # fund_1y (12.0) - tri_1y (6.0) = 6.0
    assert round(result, 4) == 6.0


def test_alpha_1y_tri_pct_none_when_return_1y_pct_is_none():
    anchor = date(2026, 1, 1)
    tri_points = _daily_series(anchor - timedelta(days=400), 401, 100.0, 0.0002)
    assert alpha_1y_tri_pct(None, tri_points, anchor) is None


def test_alpha_1y_tri_pct_none_when_tri_points_below_min_points():
    anchor = date(2026, 1, 1)
    tri_points = [(anchor - timedelta(days=365), 100.0), (anchor, 110.0)]
    assert len(tri_points) < MIN_TRI_POINTS
    assert alpha_1y_tri_pct(10.0, tri_points, anchor) is None


def test_alpha_1y_tri_pct_none_when_trailing_return_cannot_be_computed():
    anchor = date(2026, 1, 1)
    # >= MIN_TRI_POINTS rows, but ALL after anchor_date -> no eligible base.
    tri_points = [(anchor + timedelta(days=i), 100.0 + i) for i in range(MIN_TRI_POINTS + 5)]
    assert alpha_1y_tri_pct(10.0, tri_points, anchor) is None


def test_alpha_1y_tri_pct_gates_on_min_tri_points_boundary():
    anchor = date(2026, 1, 1)
    tri_points = _daily_series(
        anchor - timedelta(days=MIN_TRI_POINTS - 1), MIN_TRI_POINTS - 1, 100.0, 0.0
    )
    assert len(tri_points) == MIN_TRI_POINTS - 1
    assert alpha_1y_tri_pct(10.0, tri_points, anchor) is None


def test_lookback_days_constant_matches_signals_one_year_convention():
    assert LOOKBACK_DAYS == 365
