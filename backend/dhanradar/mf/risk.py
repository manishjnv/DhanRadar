"""
DhanRadar — MF NAV → Risk-adjusted metrics (Phase 5, B74).

Pure module: turns a fund's OWN NAV time-series into Sharpe ratio, Sortino
ratio, annualised volatility, and rolling 1-year return stats.
No DB / network / Redis / Celery imports — golden-set testable.

Mathematics conventions (documented once here; unit tests pin exact values):

  Annualisation factor  : _PERIODS_PER_YEAR = 252  (AMFI NAV is business-daily)
                          σ_annual = σ_period × √252
  Stdev convention      : SAMPLE stdev (ddof=1, statistics.stdev) — the
                          conventional financial choice for an estimated pop.
                          stdev.  (The risk axis in signals.py uses pstdev but
                          that is a *scoring* helper; here we are producing
                          reported analytics, so sample stdev is correct.)
  Sharpe numerator      : (geometric annualised return − Rf) / σ_annual
                          where Rf = risk_free_annual (all in FRACTIONS, not %).
  Sortino denominator   : downside deviation, MAR = 0 per period.
                          dd = √( Σ min(r,0)² / n ) × √252
                          (full-sample denominator, not just negative periods —
                          matches the widely cited Sortino-Price 1994 formula).
                          Future TODO: switch per-period target to Rf/252 once the
                          macro feed is live.
  Geometric return      : ann_ret = (P_last / P_first)^(252/n) − 1
                          Consistent with the √252 annualisation for volatility.
  Minimum points        : _MIN_NAV_POINTS = 252  (< 1 trading year → refuse,
                          return all-None; a garbage ratio on sparse data is worse
                          than no ratio).

  M2.3 override         : ``risk_adjusted_stats(min_points=..., periods_per_year=...)``
                          lets a DIFFERENT-cadence series (the portfolio's own daily
                          valuation series, mf.valuation — genuinely calendar-daily,
                          365/yr) reuse this exact Sharpe/Sortino/vol math without
                          inheriting the fund-NAV 252-point / business-daily defaults.
"""

from __future__ import annotations

import datetime
import math
import statistics
from dataclasses import dataclass

from dhanradar.mf.signals import _periodic_returns, _sorted_unique

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PERIODS_PER_YEAR: int = 252          # AMFI NAV is business-daily
_MIN_NAV_POINTS: int = 252            # < 1 trading year → refuse (all-None)

# Minimum annualised volatility (as a FRACTION) below which Sharpe/Sortino are
# withheld (NULL).  At ~0.0005 (0.05% annualised) the NAV series is effectively
# constant — near-flat or stale/placeholder data — so the ratio denominator
# collapses toward zero and the ratio explodes to ±10⁵–10⁶ (a meaningless
# "garbage rate").  The MF-analytics governance (§20) is to FAIL TOWARD
# WITHHOLDING a number, never to emit a guessed/garbage one.  This generalises
# the exact ``vol == 0`` degenerate case to the near-zero neighbourhood.  The
# measured volatility_pct is still stored (it is a real, if tiny, quantity);
# only the unstable ratios are withheld.  Legitimate low-vol debt/liquid funds
# (annualised vol ≥ ~0.1%) are unaffected — this targets the cause (vol → 0),
# not the symptom (a large |Sharpe|), so a genuinely high Sharpe survives.
_MIN_MEANINGFUL_VOL: float = 0.0005


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RiskStats:
    """Risk-adjusted metrics for a fund's NAV series.

    All values are None when the series is too short (< _MIN_NAV_POINTS points)
    or mathematically undefined / unstable (e.g. Sharpe when annualised vol is
    below _MIN_MEANINGFUL_VOL — a near-flat NAV series).
    volatility_pct is annualised stdev in PERCENT (not as a fraction).
    rolling_* stats come from rolling_1y_returns() with 30-day stepping.
    """

    sharpe_ratio: float | None
    sortino_ratio: float | None
    volatility_pct: float | None            # annualised stdev, in PERCENT
    rolling_1y_avg_pct: float | None
    rolling_1y_min_pct: float | None
    rolling_1y_max_pct: float | None
    rolling_1y_pct_positive: float | None   # 0–100


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def risk_adjusted_stats(
    points: list[tuple[datetime.date, float]],
    *,
    risk_free_annual: float,
    min_points: int = _MIN_NAV_POINTS,
    periods_per_year: int = _PERIODS_PER_YEAR,
) -> RiskStats:
    """Compute Sharpe, Sortino, annualised vol, and rolling-1Y stats.

    ``risk_free_annual`` is an annual rate as a FRACTION (e.g. 0.065 = 6.5 %).
    Returns RiskStats with all-None fields when there are fewer than
    ``min_points`` distinct points (default ``_MIN_NAV_POINTS`` = 252, the
    fund-NAV convention).

    ``min_points``/``periods_per_year`` are overridable (M2.3) for a
    DIFFERENT input cadence — e.g. the portfolio's own daily valuation series
    (`mf.valuation`) is genuinely calendar-daily (a weekend row carries the
    prior value forward — a real, not fabricated, zero return), so it
    annualises on 365 periods/year and applies its own product-level minimum
    (portfolio_read._MIN_TRUE_RISK_ROWS), not the fund-NAV 252/business-daily
    convention. Fund-NAV call sites (tasks/mf.py) pass neither kwarg and keep
    today's exact behaviour.
    """
    pts = _sorted_unique(points)
    _none = RiskStats(
        sharpe_ratio=None,
        sortino_ratio=None,
        volatility_pct=None,
        rolling_1y_avg_pct=None,
        rolling_1y_min_pct=None,
        rolling_1y_max_pct=None,
        rolling_1y_pct_positive=None,
    )
    if len(pts) < min_points:
        return _none

    # Periodic returns as FRACTIONS (signals._periodic_returns returns %, so ÷ 100).
    rets = [r / 100.0 for r in _periodic_returns(pts)]
    n = len(rets)
    if n < 1:
        return _none

    # Geometric annualised return (fraction).
    # Formula: (P_last / P_first)^(252/n) − 1
    # Using the full series span (n point-to-point returns = n+1 NAV points minus 1
    # pair; annualise over the number of PERIODS, which is n).
    p_first = pts[0][1]
    p_last = pts[-1][1]
    ann_ret = (p_last / p_first) ** (periods_per_year / n) - 1.0

    # Annualised volatility — SAMPLE stdev (ddof=1) per financial convention.
    # vol_annual = stdev_period × √periods_per_year
    if n < 2:
        # Cannot compute sample stdev with < 2 observations.
        return _none
    vol = statistics.stdev(rets) * math.sqrt(periods_per_year)   # fraction
    volatility_pct = vol * 100.0                                   # in percent

    # Sharpe ratio (dimensionless).
    # (ann_ret − Rf) / σ_annual   — all in fractions.
    sharpe: float | None
    if vol < _MIN_MEANINGFUL_VOL:
        # Near-zero vol → constant/near-flat NAV → ratio explodes → withhold.
        sharpe = None
    else:
        sharpe = (ann_ret - risk_free_annual) / vol

    # Downside deviation, MAR = 0 per period.
    # dd = √( Σ min(r, 0)² / n ) × √periods_per_year
    # Using the FULL sample n as denominator (Sortino-Price 1994).
    sum_neg_sq = sum(min(0.0, r) ** 2 for r in rets)
    dd = math.sqrt(sum_neg_sq / n) * math.sqrt(periods_per_year)

    sortino: float | None
    if dd < _MIN_MEANINGFUL_VOL:
        # No (or negligible) downside deviation — Sortino undefined / explodes
        # toward +∞; report as None (honest withholding, same floor as Sharpe).
        sortino = None
    else:
        sortino = (ann_ret - risk_free_annual) / dd

    # Rolling 1-year returns (30-day stepping).
    r1y_avg, r1y_min, r1y_max, r1y_pct_pos = rolling_1y_returns(points)

    return RiskStats(
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        volatility_pct=volatility_pct,
        rolling_1y_avg_pct=r1y_avg,
        rolling_1y_min_pct=r1y_min,
        rolling_1y_max_pct=r1y_max,
        rolling_1y_pct_positive=r1y_pct_pos,
    )


# ---------------------------------------------------------------------------
# Rolling 1-year windows
# ---------------------------------------------------------------------------

def rolling_1y_returns(
    points: list[tuple[datetime.date, float]],
) -> tuple[float | None, float | None, float | None, float | None]:
    """Compute rolling 1-year return windows stepping by 30 days.

    Returns ``(avg_pct, min_pct, max_pct, pct_positive)`` or
    ``(None, None, None, None)`` when the series spans less than 365 days.

    Algorithm:
      For k = 0, 1, 2, …:
        end-anchor e = pts[-1].date − 30*k days
        stop when e < pts[0].date + 365 days
        nav_e   = NAV of the latest point with date <= e (or None)
        nav_base = NAV of the latest point with date <= e−365 (or None)
        window return = (nav_e / nav_base − 1) × 100  if both exist and nav_base > 0
    """
    pts = _sorted_unique(points)
    if not pts:
        return None, None, None, None
    span_days = (pts[-1][0] - pts[0][0]).days
    if span_days < 365:
        return None, None, None, None

    # Build a fast date→nav lookup for nav_on_or_before.
    dates = [p[0] for p in pts]
    navs = [p[1] for p in pts]

    def nav_on_or_before(d: datetime.date) -> float | None:
        """Binary-search for the latest NAV point with date <= d."""
        lo, hi = 0, len(dates) - 1
        result_idx = -1
        while lo <= hi:
            mid = (lo + hi) // 2
            if dates[mid] <= d:
                result_idx = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return navs[result_idx] if result_idx >= 0 else None

    window_returns: list[float] = []
    k = 0
    stop_anchor = pts[0][0] + datetime.timedelta(days=365)
    while True:
        e = pts[-1][0] - datetime.timedelta(days=30 * k)
        if e < stop_anchor:
            break
        base_date = e - datetime.timedelta(days=365)
        nav_e = nav_on_or_before(e)
        nav_base = nav_on_or_before(base_date)
        if nav_e is not None and nav_base is not None and nav_base > 0:
            window_returns.append((nav_e / nav_base - 1.0) * 100.0)
        k += 1

    if not window_returns:
        return None, None, None, None

    avg_pct = sum(window_returns) / len(window_returns)
    min_pct = min(window_returns)
    max_pct = max(window_returns)
    pct_pos = 100.0 * sum(1 for r in window_returns if r > 0) / len(window_returns)
    return avg_pct, min_pct, max_pct, pct_pos


# ---------------------------------------------------------------------------
# Percentile (linear interpolation — numpy 'linear' / statistics 'inclusive')
# ---------------------------------------------------------------------------

def percentile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolation percentile on an ascending sorted list.

    Given ascending ``v`` of length n ≥ 1:
      rank = (q / 100) × (n − 1)
      lo   = floor(rank)
      frac = rank − lo
      result = v[lo] + frac × (v[lo+1] − v[lo])  if lo+1 < n else v[lo]

    For n == 1 returns v[0] regardless of q.
    This is identical to numpy's ``np.percentile(v, q, interpolation='linear')``
    (also called the "inclusive" or "H2" method).
    """
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    rank = (q / 100.0) * (n - 1)
    lo = int(math.floor(rank))
    frac = rank - lo
    if lo + 1 < n:
        return sorted_values[lo] + frac * (sorted_values[lo + 1] - sorted_values[lo])
    return sorted_values[lo]


# ---------------------------------------------------------------------------
# Category-level percentile distribution
# ---------------------------------------------------------------------------

def category_percentiles(
    values: list[float | None],
    min_count: int,
) -> dict[str, float] | None:
    """Compute p25/p50/p75/p90 from a list of nullable floats.

    Filters out None values, sorts ascending. Returns None if fewer than
    ``min_count`` valid values (avoids noisy percentiles on thin cohorts).
    Returns dict with keys "p25", "p50", "p75", "p90" on success.
    """
    valid = sorted(v for v in values if v is not None)
    if len(valid) < min_count:
        return None
    return {
        "p25": percentile(valid, 25.0),
        "p50": percentile(valid, 50.0),
        "p75": percentile(valid, 75.0),
        "p90": percentile(valid, 90.0),
    }


# ---------------------------------------------------------------------------
# Risk-free rate resolution (RBI 91-day T-bill; nightly Sharpe/Sortino input)
# ---------------------------------------------------------------------------

# RBI DBIE is a fragile, undocumented SPA that can silently zero-fill or go
# stale — the ingested T-bill yield is trusted ONLY when it looks like a real,
# fresh, published rate. Outside that window this fails CLOSED to the
# existing hardcoded placeholder (config.RISK_FREE_RATE_ANNUAL) rather than
# risk a garbage Sharpe/Sortino denominator.
_TBILL_MAX_AGE_DAYS: int = 45
_TBILL_MIN_SANE_PCT: float = 3.0
_TBILL_MAX_SANE_PCT: float = 10.0


@dataclass(frozen=True)
class RiskFreeRateResolution:
    """Outcome of resolving the nightly Sharpe/Sortino risk-free rate.

    ``rate_annual`` is always populated (a FRACTION, e.g. 0.0675 = 6.75%) —
    this function never raises and never returns an unvalidated rate.
    ``source`` is ``"tbill"`` when the ingested RBI 91-day T-bill yield
    (``mf.macro_indicators``, indicator_key='tbill_91d_yield_pct') was used,
    else ``"placeholder"``. ``as_of_date`` is the T-bill row's date when used,
    else None. ``rejected_reason`` is None when a T-bill rate was used,
    otherwise one of "missing" / "stale" / "insane_value" — the caller logs
    ONE structured warning per run keyed off this.
    """

    rate_annual: float
    source: str
    as_of_date: datetime.date | None
    rejected_reason: str | None


def resolve_risk_free_rate(
    *,
    tbill_value_pct: float | None,
    tbill_as_of: datetime.date | None,
    today: datetime.date,
    placeholder_annual: float,
    max_age_days: int = _TBILL_MAX_AGE_DAYS,
    min_sane_pct: float = _TBILL_MIN_SANE_PCT,
    max_sane_pct: float = _TBILL_MAX_SANE_PCT,
) -> RiskFreeRateResolution:
    """Resolve the annual risk-free rate for ``risk_adjusted_stats()``, fail-CLOSED.

    Pure function — no DB access; the caller queries the latest
    ``mf.macro_indicators`` row for indicator_key='tbill_91d_yield_pct' and
    passes its value/as_of_date in (or None/None if no row exists).

    Uses the ingested T-bill rate only when ALL hold:
      - a row exists (``tbill_value_pct``/``tbill_as_of`` both not None)
      - ``tbill_as_of`` is within ``max_age_days`` of ``today``
      - ``tbill_value_pct`` is within [``min_sane_pct``, ``max_sane_pct``]
        (guards a DBIE zero-fill or other garbage publish)

    Otherwise returns ``placeholder_annual`` unchanged — the pre-existing
    hardcoded Sharpe/Sortino denominator.
    """
    if tbill_value_pct is None or tbill_as_of is None:
        return RiskFreeRateResolution(
            rate_annual=placeholder_annual,
            source="placeholder",
            as_of_date=None,
            rejected_reason="missing",
        )

    age_days = (today - tbill_as_of).days
    if age_days > max_age_days:
        return RiskFreeRateResolution(
            rate_annual=placeholder_annual,
            source="placeholder",
            as_of_date=None,
            rejected_reason="stale",
        )

    if not (min_sane_pct <= tbill_value_pct <= max_sane_pct):
        return RiskFreeRateResolution(
            rate_annual=placeholder_annual,
            source="placeholder",
            as_of_date=None,
            rejected_reason="insane_value",
        )

    return RiskFreeRateResolution(
        rate_annual=tbill_value_pct / 100.0,
        source="tbill",
        as_of_date=tbill_as_of,
        rejected_reason=None,
    )
