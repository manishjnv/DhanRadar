"""Unit tests — Phase 2 batch metrics (docs/features/leaderboard-data-backend.md
§8): SIP XIRR, drawdown-recovery days.

Pure functions, no DB — same convention as test_leaderboard.py / test_mf_risk.py.
`_recovery_days` is a thin wrapper around the already-thoroughly-tested
`dhanradar.mf.risk.drawdown_series` (see TestDrawdownSeries in test_mf_risk.py),
so its own tests just confirm the delegation, not the drawdown algorithm itself.

The since-launch multiple used to live here too, but it's now computed in
`_leaderboard_refresh_pipeline` from the FULL mf_nav_history span (not this
pipeline's ~5.2y-capped series) — see `test_leaderboard.py`'s
`_since_launch_multiple` tests.
"""

from __future__ import annotations

from datetime import date

import pytest

from dhanradar.mf.snapshot import CashFlow, xirr
from dhanradar.tasks.mf import _recovery_days, _sip_xirr


def _month_starts(year: int, month: int, n: int) -> list[date]:
    """n exact calendar-month-start dates starting at (year, month) — same
    helper shape as test_mf_risk.py's TestComputeSipIllustration fixture."""
    out = []
    for i in range(n):
        total = (month - 1) + i
        y = year + total // 12
        m = total % 12 + 1
        out.append(date(y, m, 1))
    return out


# ---------------------------------------------------------------------------
# _sip_xirr
# ---------------------------------------------------------------------------


def test_sip_xirr_flat_nav_series_is_zero_percent() -> None:
    """All installments buy/redeem at the same NAV -> total inflow == total
    outflow nominally -> XIRR's unique root (single sign-change cashflow
    pattern) is exactly 0%."""
    starts = _month_starts(2021, 1, 36)
    points = [(d, 100.0) for d in starts]
    result = _sip_xirr(points, months=36)
    assert result == pytest.approx(0.0, abs=0.01)


def test_sip_xirr_growth_matches_independently_built_cashflows() -> None:
    """1%/month compounding NAV, purchases offset to day 5 of each month (not
    day 1) — checks the "first NAV point within the calendar month" scan picks
    the right point, by comparing against a reference cashflow list built
    directly from the same (date, nav) pairs and fed through the same xirr()."""
    starts = _month_starts(2021, 1, 36)
    points = [(d.replace(day=5), round(100.0 * (1.01**i), 6)) for i, d in enumerate(starts)]
    latest_date, latest_nav = points[-1]

    expected_flows = [CashFlow(when=d, amount=-10_000.0) for d, _ in points]
    total_units = sum(10_000.0 / nav for _, nav in points)
    expected_flows.append(CashFlow(when=latest_date, amount=total_units * latest_nav))
    expected = xirr(expected_flows)

    result = _sip_xirr(points, months=36)
    assert result is not None
    assert result == pytest.approx(expected, abs=0.01)
    assert 5.0 < result < 20.0  # sanity band around the ~12.7%/yr compounding rate


def test_sip_xirr_none_when_history_shorter_than_window() -> None:
    """Only 20 months of history for a 36-month window -> insufficient coverage
    (earliest NAV point is way more than 15 days after the window start)."""
    starts = _month_starts(2024, 1, 20)
    points = [(d, 100.0 + i) for i, d in enumerate(starts)]
    assert _sip_xirr(points, months=36) is None


def test_sip_xirr_none_when_a_trailing_month_has_no_nav_point() -> None:
    """36-month window but one calendar month inside it has zero NAV points —
    a gap the fund can't be blamed for, but the XIRR would be, so excluded."""
    starts = _month_starts(2021, 1, 36)
    points = [(d, 100.0 + i) for i, d in enumerate(starts) if i != 10]
    assert _sip_xirr(points, months=36) is None


# ---------------------------------------------------------------------------
# _recovery_days
# ---------------------------------------------------------------------------


def test_recovery_days_mirrors_drawdown_series_peak_to_recovery() -> None:
    """100 -> 150 (peak) -> 100 (trough, worst episode) -> 155 (first close at/
    above the prior peak). Days measured from the PEAK date, not the trough —
    same convention as fund_read.py's read-path (drawdown_series docstring)."""
    peak_date = date(2024, 1, 31)
    recovery_date = date(2024, 4, 30)
    points = [
        (date(2024, 1, 1), 100.0),
        (peak_date, 150.0),
        (date(2024, 3, 1), 100.0),
        (recovery_date, 155.0),
    ]
    result = _recovery_days(points)
    assert result == (recovery_date - peak_date).days


def test_recovery_days_none_when_never_recovered() -> None:
    points = [(date(2024, 1, 1), 150.0), (date(2024, 6, 1), 90.0)]
    assert _recovery_days(points) is None
