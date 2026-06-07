"""
DhanRadar — MF NAV → FundSignals (Phase 5, B29).

Pure module: turns a fund's OWN NAV time series into the engine-facing axis
values + confidence inputs the scoring bridge consumes.  No DB / network / Redis
/ Celery imports — golden-set testable.

The MF module "FEEDS signals and CONSUMES the unified score" (architecture §S /
scoring_bridge): this file produces the signal inputs only.  It NEVER reimplements
scoring and never derives the label — the engine's rule table does that.

What a NAV series alone supports (and ONLY these — honest partial coverage):
  * momentum axis — trailing total return mapped to 0–100 (50 = flat).
  * risk axis     — annualized volatility + max-drawdown penalty; HIGHER axis
                    score = LOWER risk (ranking_configs risk_factor_formula note).
  * freshness / stale — from the age of the latest NAV point.

Deliberately LEFT None (require fundamentals the NAV feed does not carry):
  * quality, valuation, trend.  The engine drops a None axis and renormalizes the
    rest, flags ``partial_coverage``, and caps confidence at ``medium``.  That is
    the correct fail-safe — a NAV-only read must never present as high-confidence.

The CATEGORY-RELATIVE label rule inputs (outperform_1y/3y, underperform_12m, …)
are NOT set here: they need a peer/category benchmark (the mf_nav_monthly_agg
cohort query — a later increment).  With them unset the rule table yields
``on_track`` — an honest REAL label that asserts no category red flag, never
advice.

All numeric weights / mappings below are PROVISIONAL v1 heuristics; every engine
result is already tagged ``provisional_model`` until the backtest + two-person
activation gate clears them (B6 / B28).
"""

from __future__ import annotations

import datetime
import statistics

from dhanradar.mf.scoring_bridge import FundSignals

# ---------------------------------------------------------------------------
# Tunables (provisional v1 — not frozen; see module docstring / B6)
# ---------------------------------------------------------------------------

# Minimum distinct NAV points before any signal can be computed.  Fewer than
# this → all axes None → engine refuses with insufficient_data (honest).
_MIN_POINTS = 4

# Momentum: trailing-return window (use the longest available up to this many days).
_MOMENTUM_LOOKBACK_DAYS = 365
# +1% trailing return ⇒ +1 momentum point around the flat midpoint (50).
# So +50% → 100 (capped), −50% → 0 (capped).
_MOMENTUM_K = 1.0

# Risk: per-period volatility and max-drawdown penalties (percentage-point based).
_VOL_PENALTY_K = 4.0      # 1% per-period stdev → 4 risk points off
_VOL_PENALTY_CAP = 50.0
_DD_PENALTY_K = 1.0       # 20% max drawdown → 20 risk points off
_DD_PENALTY_CAP = 50.0

# Freshness decay from the age (days) of the latest NAV point.
_FRESH_DAYS = 7           # ≤ a week old → fully fresh
_STALE_DAYS = 30          # > a month old → flagged stale + freshness floored


# ---------------------------------------------------------------------------
# Helpers (pure)
# ---------------------------------------------------------------------------

def _sorted_unique(points: list[tuple[datetime.date, float]]) -> list[tuple[datetime.date, float]]:
    """Sort points ascending by date and collapse duplicate dates (keep last)."""
    by_date: dict[datetime.date, float] = {}
    for d, nav in points:
        if nav is None or nav <= 0:
            continue
        by_date[d] = float(nav)
    return [(d, by_date[d]) for d in sorted(by_date)]


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return min(max(x, lo), hi)


def _trailing_return_pct(
    points: list[tuple[datetime.date, float]], lookback_days: int
) -> float | None:
    """Percentage return from the earliest point within ``lookback_days`` of the
    latest point, to the latest point.  None if no suitable base point."""
    if len(points) < 2:
        return None
    latest_date, latest_nav = points[-1]
    cutoff = latest_date - datetime.timedelta(days=lookback_days)
    base: tuple[datetime.date, float] | None = None
    for d, nav in points:
        if d >= cutoff:
            base = (d, nav)
            break
    if base is None:
        base = points[0]
    base_nav = base[1]
    if base_nav <= 0:
        return None
    return (latest_nav / base_nav - 1.0) * 100.0


def _periodic_returns(points: list[tuple[datetime.date, float]]) -> list[float]:
    """Point-to-point percentage returns across the series."""
    out: list[float] = []
    for (_, prev), (_, cur) in zip(points, points[1:]):
        if prev > 0:
            out.append((cur / prev - 1.0) * 100.0)
    return out


def _max_drawdown_pct(points: list[tuple[datetime.date, float]]) -> float:
    """Largest peak-to-trough decline over the series, as a positive percentage."""
    peak = float("-inf")
    max_dd = 0.0
    for _, nav in points:
        if nav > peak:
            peak = nav
        if peak > 0:
            dd = (peak - nav) / peak * 100.0
            if dd > max_dd:
                max_dd = dd
    return max_dd


def _momentum_axis(points: list[tuple[datetime.date, float]]) -> float | None:
    ret = _trailing_return_pct(points, _MOMENTUM_LOOKBACK_DAYS)
    if ret is None:
        return None
    return _clamp(50.0 + ret * _MOMENTUM_K)


def _risk_axis(points: list[tuple[datetime.date, float]]) -> float | None:
    """Higher score = LOWER risk (controlled volatility + shallow drawdown)."""
    rets = _periodic_returns(points)
    if len(rets) < 2:
        return None
    vol = statistics.pstdev(rets)  # per-period stdev in percentage points
    dd = _max_drawdown_pct(points)
    vol_penalty = min(vol * _VOL_PENALTY_K, _VOL_PENALTY_CAP)
    dd_penalty = min(dd * _DD_PENALTY_K, _DD_PENALTY_CAP)
    return _clamp(100.0 - vol_penalty - dd_penalty)


def _freshness(latest_date: datetime.date, as_of: datetime.date) -> tuple[float, bool]:
    """Return (freshness 0–1, stale flag) from the age of the latest NAV."""
    age = (as_of - latest_date).days
    if age <= _FRESH_DAYS:
        return 1.0, False
    if age >= _STALE_DAYS:
        return 0.5, True
    # Linear decay 1.0 → 0.6 across the (_FRESH_DAYS, _STALE_DAYS) band.
    span = _STALE_DAYS - _FRESH_DAYS
    frac = (age - _FRESH_DAYS) / span
    return 1.0 - 0.4 * frac, False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def compute_fund_signals(
    isin: str,
    points: list[tuple[datetime.date, float]],
    *,
    as_of: datetime.date | None = None,
) -> FundSignals:
    """Build :class:`FundSignals` from a fund's NAV series.

    ``points`` is ``[(nav_date, nav), …]`` in any order (sorted + de-duped here).
    With fewer than ``_MIN_POINTS`` usable points every axis is left None, so the
    engine returns ``insufficient_data`` — the honest fail-safe.  Otherwise the
    momentum + risk axes are populated (quality/valuation/trend stay None →
    partial_coverage → confidence capped at medium).
    """
    pts = _sorted_unique(points)
    if len(pts) < _MIN_POINTS:
        # Honest refusal: not enough history to say anything → insufficient_data.
        return FundSignals(isin=isin)

    as_of = as_of or datetime.date.today()
    momentum = _momentum_axis(pts)
    risk = _risk_axis(pts)
    freshness, stale = _freshness(pts[-1][0], as_of)

    # Surface the data-derived facts as contributing context (never advisory).
    contributing: list[str] = []
    if momentum is not None:
        contributing.append("trailing return computed from NAV history")
    if risk is not None:
        contributing.append("volatility/drawdown computed from NAV history")

    return FundSignals(
        isin=isin,
        momentum=momentum,
        risk=risk,
        # quality / valuation / trend require fundamentals → left None on purpose.
        freshness=freshness,
        stale=stale,
        liquid=True,            # open-ended MF units are redeemable; no illiquidity signal from NAV.
        sources_reliable=True,  # AMFI is the authoritative NAV source.
        contributing=contributing,
    )
