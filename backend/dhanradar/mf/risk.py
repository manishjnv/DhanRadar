"""
DhanRadar — MF NAV → Risk-adjusted metrics (Phase 5, B74).

Pure module: turns a fund's OWN NAV time-series into Sharpe ratio, Sortino
ratio, annualised volatility, rolling 1Y/3Y return stats, calendar-year
returns, drawdown/recovery, and a historical SIP illustration (W2 §10.4/§10.5).
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
from dhanradar.mf.snapshot import CashFlow, xirr

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
# Shared NAV-lookup helper (rolling windows + calendar-year returns)
# ---------------------------------------------------------------------------

def _nav_on_or_before(
    dates: list[datetime.date],
    navs: list[float],
    d: datetime.date,
    *,
    max_gap_days: int | None = None,
) -> float | None:
    """Binary-search for the latest NAV point with date <= d (dates/navs ascending,
    same length, produced by :func:`_sorted_unique`). None if no such point exists,
    or — when ``max_gap_days`` is set — the nearest point is older than that many
    days before ``d`` (guards a long stale-data gap masquerading as a genuine
    boundary NAV; unused by the rolling-window callers below, only by
    :func:`calendar_year_returns`, which needs a tight year-end match)."""
    lo, hi = 0, len(dates) - 1
    result_idx = -1
    while lo <= hi:
        mid = (lo + hi) // 2
        if dates[mid] <= d:
            result_idx = mid
            lo = mid + 1
        else:
            hi = mid - 1
    if result_idx < 0:
        return None
    if max_gap_days is not None and (d - dates[result_idx]).days > max_gap_days:
        return None
    return navs[result_idx]


# ---------------------------------------------------------------------------
# Rolling N-year windows (generalised — the 1Y and 3Y stats are the SAME
# algorithm at a different window length; do not duplicate it per window)
# ---------------------------------------------------------------------------

def rolling_window_returns(
    points: list[tuple[datetime.date, float]],
    *,
    window_days: int = 365,
    step_days: int = 30,
) -> tuple[float | None, float | None, float | None, float | None]:
    """Compute rolling ``window_days``-length return windows, stepping by
    ``step_days``.

    Returns ``(avg_pct, min_pct, max_pct, pct_positive)`` or
    ``(None, None, None, None)`` when the series spans less than ``window_days``.

    Algorithm (unchanged from the original 1Y-only implementation, just
    parameterised on the window length):
      For k = 0, 1, 2, …:
        end-anchor e = pts[-1].date − step_days*k days
        stop when e < pts[0].date + window_days days
        nav_e   = NAV of the latest point with date <= e (or None)
        nav_base = NAV of the latest point with date <= e−window_days (or None)
        window return = (nav_e / nav_base − 1) × 100  if both exist and nav_base > 0
    """
    pts = _sorted_unique(points)
    if not pts:
        return None, None, None, None
    span_days = (pts[-1][0] - pts[0][0]).days
    if span_days < window_days:
        return None, None, None, None

    dates = [p[0] for p in pts]
    navs = [p[1] for p in pts]

    window_returns: list[float] = []
    k = 0
    stop_anchor = pts[0][0] + datetime.timedelta(days=window_days)
    while True:
        e = pts[-1][0] - datetime.timedelta(days=step_days * k)
        if e < stop_anchor:
            break
        base_date = e - datetime.timedelta(days=window_days)
        nav_e = _nav_on_or_before(dates, navs, e)
        nav_base = _nav_on_or_before(dates, navs, base_date)
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


def rolling_1y_returns(
    points: list[tuple[datetime.date, float]],
) -> tuple[float | None, float | None, float | None, float | None]:
    """Rolling 1-year (365-day) windows, 30-day step. Thin back-compat wrapper
    over :func:`rolling_window_returns` — behavior is byte-for-byte unchanged
    from before the generalisation."""
    return rolling_window_returns(points, window_days=365, step_days=30)


# 3 × 365 — matches the existing 3Y convention elsewhere (signals._THREE_YEAR_DAYS).
_ROLLING_3Y_WINDOW_DAYS = 365 * 3


def rolling_3y_returns(
    points: list[tuple[datetime.date, float]],
) -> tuple[float | None, float | None, float | None, float | None]:
    """Rolling 3-year (1095-day) windows, 30-day step (W2 §10.5) — the SAME
    algorithm as :func:`rolling_1y_returns`, just a longer window."""
    return rolling_window_returns(points, window_days=_ROLLING_3Y_WINDOW_DAYS, step_days=30)


# ---------------------------------------------------------------------------
# Calendar-year returns (Jan1–Dec31), for the consistency strip + category
# quartile context (W2 §10.5)
# ---------------------------------------------------------------------------

# Tolerance for matching a NAV point to a Dec-31 year-end boundary — covers the
# New Year holiday/weekend gap (AMFI NAV is business-daily, so Dec 31 itself is
# frequently not a trading day).
_CALENDAR_YEAR_BOUNDARY_MAX_GAP_DAYS = 10


def calendar_year_returns(
    points: list[tuple[datetime.date, float]],
    *,
    as_of: datetime.date | None = None,
    n_years: int = 5,
) -> dict[int, float]:
    """Calendar-year (Jan1–Dec31) returns for the last ``n_years`` FULL years.

    Returns ``{year: return_pct}`` — a year is included only when BOTH its own
    year-end AND the prior year-end have a NAV point within
    ``_CALENDAR_YEAR_BOUNDARY_MAX_GAP_DAYS`` of the boundary date. This
    naturally excludes a fund's partial launch year (no prior year-end NAV
    exists) and any year entirely before launch — never a fabricated partial-
    year return. The current, not-yet-complete year is never included
    (``as_of`` anchors "last full year"; defaults to today).
    """
    pts = _sorted_unique(points)
    if not pts:
        return {}

    today = as_of or datetime.date.today()
    last_full_year = today.year - 1
    dates = [p[0] for p in pts]
    navs = [p[1] for p in pts]

    out: dict[int, float] = {}
    for year in range(last_full_year - n_years + 1, last_full_year + 1):
        nav_end = _nav_on_or_before(
            dates, navs, datetime.date(year, 12, 31),
            max_gap_days=_CALENDAR_YEAR_BOUNDARY_MAX_GAP_DAYS,
        )
        nav_start = _nav_on_or_before(
            dates, navs, datetime.date(year - 1, 12, 31),
            max_gap_days=_CALENDAR_YEAR_BOUNDARY_MAX_GAP_DAYS,
        )
        if nav_end is None or nav_start is None or nav_start <= 0:
            continue
        out[year] = (nav_end / nav_start - 1.0) * 100.0
    return out


# ---------------------------------------------------------------------------
# Drawdown series + worst-fall/recovery (W2 §10.5)
# ---------------------------------------------------------------------------

def drawdown_series(
    points: list[tuple[datetime.date, float]],
) -> tuple[list[tuple[datetime.date, float]], float | None, int | None]:
    """Running drawdown-from-peak series (%, always <= 0) over the FULL series,
    plus the worst (most negative) drawdown and its recovery time.

    Returns ``(series, worst_fall_pct, recovery_days)``:
      - ``series``: one ``(date, pct_from_running_peak)`` point per input point
        (the caller downsamples for the chart — reuse ``fund_read._downsample``,
        do not re-implement stride-sampling here).
      - ``worst_fall_pct``: the single most negative drawdown, or None if the
        series never fell below its running peak (< 2 points, or monotonically
        non-decreasing).
      - ``recovery_days``: calendar days from the PEAK that preceded the worst
        drawdown to the first later date the NAV climbs back to that peak value
        — None if the fund has not yet recovered from its worst fall.
    """
    pts = _sorted_unique(points)
    if len(pts) < 2:
        return [], None, None

    series: list[tuple[datetime.date, float]] = []
    peak_nav = pts[0][1]
    peak_date = pts[0][0]
    worst_pct = 0.0
    worst_trough_date: datetime.date | None = None
    worst_peak_date: datetime.date | None = None
    worst_peak_nav: float | None = None

    for d, nav in pts:
        if nav > peak_nav:
            peak_nav = nav
            peak_date = d
        pct = (nav - peak_nav) / peak_nav * 100.0 if peak_nav > 0 else 0.0
        series.append((d, pct))
        if pct < worst_pct:
            worst_pct = pct
            worst_trough_date = d
            worst_peak_date = peak_date
            worst_peak_nav = peak_nav

    if worst_trough_date is None or worst_peak_nav is None:
        # Series never fell below its running peak — no drawdown to report.
        return series, None, None

    recovery_days: int | None = None
    for d, nav in pts:
        if d > worst_trough_date and nav >= worst_peak_nav:
            recovery_days = (d - worst_peak_date).days  # type: ignore[operator]
            break

    return series, round(worst_pct, 2), recovery_days


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


# ---------------------------------------------------------------------------
# SIP illustration engine (W2 §10.4) — historical, never a projection
# ---------------------------------------------------------------------------

# SIP menu — amount/years are PROVISIONAL DEFAULTS (§18.4 founder decision
# pending); the fixed menu (not free-form input) keeps the Redis cache-key
# space bounded. The route (mf/router.py) 422s an out-of-menu value via a
# Literal-typed query param — this module never validates the menu itself,
# it just computes whatever (amount, years) it is given.
SIP_AMOUNT_MENU: tuple[int, ...] = (1000, 5000, 10000)
SIP_YEARS_MENU: tuple[int, ...] = (1, 3, 5)

# A SIP illustration under a year of actual purchases is too short to mean
# anything — the caller (mf/fund_read.py) nulls the money fields below this
# and keeps months_invested, so the young-fund case reads as honest, not broken.
SIP_MIN_MONTHS_FOR_ILLUSTRATION: int = 12


@dataclass(frozen=True)
class SipIllustration:
    """Output of :func:`compute_sip_illustration` — money fields are always
    computed here (the young-fund <12mo withholding is the CALLER's job, not
    this pure function's, so tests can see the raw numbers either way)."""

    months_invested: int
    total_invested: float
    final_value: float | None
    xirr_pct: float | None


def compute_sip_illustration(
    nav_points: list[tuple[datetime.date, float]],
    monthly_amount: float,
    years: int,
) -> SipIllustration:
    """Historical SIP illustration (§10.4): buy ``monthly_amount`` on the FIRST
    available NAV date of each calendar month, over the trailing ``years``-year
    window ending at the fund's OWN latest NAV date (not wall-clock "today" —
    mirrors the nav_series convention, so a stale/cold feed still gets a
    coherent window). All accumulated units are marked at the LATEST NAV.

    XIRR reuses the EXISTING server solver (:func:`dhanradar.mf.snapshot.xirr`)
    over the resulting cash-flow schedule (each monthly buy negative, the final
    mark-to-market positive) — no new root-finder.

    Young-fund handling: if the fund's history is SHORTER than the requested
    window, the SIP simply runs over however many months ARE available (never
    fabricated) — ``months_invested`` always reports the TRUE number of
    monthly purchases made. Returns ``months_invested=0`` / all-None money
    fields when there is no usable NAV data in the window at all.
    """
    pts = _sorted_unique(nav_points)
    if not pts:
        return SipIllustration(
            months_invested=0, total_invested=0.0, final_value=None, xirr_pct=None
        )

    latest_date, latest_nav = pts[-1]
    window_start = latest_date - datetime.timedelta(days=365 * years)

    # First NAV point of each (year, month) inside the window.
    first_of_month: dict[tuple[int, int], tuple[datetime.date, float]] = {}
    for d, nav in pts:
        if d < window_start:
            continue
        key = (d.year, d.month)
        if key not in first_of_month:
            first_of_month[key] = (d, nav)

    months = sorted(first_of_month)
    if not months:
        return SipIllustration(
            months_invested=0, total_invested=0.0, final_value=None, xirr_pct=None
        )

    units = 0.0
    total_invested = 0.0
    cashflows: list[CashFlow] = []
    for key in months:
        d, nav = first_of_month[key]
        if nav <= 0:
            continue
        units += monthly_amount / nav
        total_invested += monthly_amount
        cashflows.append(CashFlow(when=d, amount=-monthly_amount))

    final_value = round(units * latest_nav, 2)
    cashflows.append(CashFlow(when=latest_date, amount=final_value))

    return SipIllustration(
        months_invested=len(months),
        total_invested=round(total_invested, 2),
        final_value=final_value,
        xirr_pct=xirr(cashflows),
    )


# ---------------------------------------------------------------------------
# Benchmark-relative stats (alpha / beta / tracking error) — Block 0.7,
# index funds only (mf/benchmark_mapping.py gates which funds get a
# non-null benchmark_index in the first place).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BenchmarkRelativeStats:
    """Fund-vs-benchmark relative risk stats, computed on COMMON dates only
    (inner join by date — a fund's NAV calendar and its benchmark index's
    close calendar rarely line up exactly, e.g. NSE trading holidays that
    differ from AMFI NAV publication gaps).

    All three fields are None together when fewer than ``min_points`` common
    aligned dates exist, or when the benchmark's own periodic returns are
    near-degenerate (mirrors the ``_MIN_MEANINGFUL_VOL`` guard on
    :class:`RiskStats` — a near-flat benchmark series makes beta/alpha
    unstable and would otherwise explode toward a meaningless value).  Never
    fabricated on thin/degenerate data.

    alpha_1y            : CAPM alpha, annualised, in PERCENT.
    beta_1y             : fund-vs-benchmark beta (dimensionless).
    tracking_error_pct  : annualised stdev of (fund_return − bench_return), in
                          PERCENT (same √``periods_per_year`` annualisation as
                          :data:`RiskStats.volatility_pct`).
    """

    alpha_1y: float | None
    beta_1y: float | None
    tracking_error_pct: float | None


def benchmark_relative_stats(
    fund_points: list[tuple[datetime.date, float]],
    benchmark_points: list[tuple[datetime.date, float]],
    *,
    risk_free_annual: float,
    min_points: int = _MIN_NAV_POINTS,
    periods_per_year: int = _PERIODS_PER_YEAR,
) -> BenchmarkRelativeStats:
    """Compute CAPM alpha, beta, and tracking error for a fund against ONE
    benchmark index's daily-close series.

    ``risk_free_annual`` is an annual rate as a FRACTION (matches
    :func:`risk_adjusted_stats`). Both input series are sorted/deduped via
    :func:`_sorted_unique` (drops None/non-positive values) before alignment.

    Alignment: the two series are inner-joined on date (COMMON dates only) —
    never forward-filled or interpolated across a gap (that would fabricate a
    price that never existed). Periodic (point-to-point) returns are then
    computed on the ALIGNED pairs so each fund/benchmark return covers the
    exact same calendar interval.

    Beta uses the sample covariance/variance convention (``statistics.
    covariance``/``statistics.variance``, ddof=1) — the same ddof=1 sample
    convention :func:`risk_adjusted_stats` uses for volatility. Tracking error
    is the annualised sample stdev of the per-period (fund − benchmark) return
    difference. Alpha is the standard CAPM residual:
    ``ann_fund_return − (risk_free_annual + beta × (ann_bench_return − risk_free_annual))``,
    using the SAME geometric-annualisation formula as
    :func:`risk_adjusted_stats` (``(last/first)^(periods_per_year/n) − 1``)
    over the aligned window.

    Returns an all-None :class:`BenchmarkRelativeStats` when there are fewer
    than ``min_points`` common aligned dates, fewer than 2 resulting periodic
    return pairs, or the benchmark's own annualised volatility is below
    ``_MIN_MEANINGFUL_VOL`` (near-flat/degenerate benchmark series — variance
    denominator too close to zero for a stable beta).
    """
    _none = BenchmarkRelativeStats(alpha_1y=None, beta_1y=None, tracking_error_pct=None)

    fund_pts = _sorted_unique(fund_points)
    bench_pts = _sorted_unique(benchmark_points)
    if not fund_pts or not bench_pts:
        return _none

    fund_by_date = dict(fund_pts)
    bench_by_date = dict(bench_pts)
    common_dates = sorted(fund_by_date.keys() & bench_by_date.keys())
    if len(common_dates) < min_points:
        return _none

    fund_vals = [fund_by_date[d] for d in common_dates]
    bench_vals = [bench_by_date[d] for d in common_dates]

    # Paired periodic returns — both series already filtered to positive
    # values by _sorted_unique, so the prev>0 guard below is defensive, not
    # load-bearing; it keeps the two return lists index-aligned regardless.
    fund_rets: list[float] = []
    bench_rets: list[float] = []
    for i in range(1, len(common_dates)):
        f_prev, f_cur = fund_vals[i - 1], fund_vals[i]
        b_prev, b_cur = bench_vals[i - 1], bench_vals[i]
        if f_prev > 0 and b_prev > 0:
            fund_rets.append(f_cur / f_prev - 1.0)
            bench_rets.append(b_cur / b_prev - 1.0)

    n = len(fund_rets)
    if n < 2:
        return _none

    var_bench = statistics.variance(bench_rets)  # sample variance, ddof=1
    bench_annual_vol = math.sqrt(var_bench) * math.sqrt(periods_per_year) if var_bench > 0 else 0.0
    if bench_annual_vol < _MIN_MEANINGFUL_VOL:
        # Near-flat benchmark series — beta/alpha would be unstable/explosive; withhold.
        return _none

    cov = statistics.covariance(fund_rets, bench_rets)  # sample covariance, ddof=1
    beta = cov / var_bench

    diff_rets = [f - b for f, b in zip(fund_rets, bench_rets)]
    te_annual = statistics.stdev(diff_rets) * math.sqrt(periods_per_year)
    tracking_error_pct = te_annual * 100.0

    # Geometric annualised returns over the ALIGNED window (same formula as
    # risk_adjusted_stats — (last/first)^(periods_per_year/n) - 1).
    ann_fund_ret = (fund_vals[-1] / fund_vals[0]) ** (periods_per_year / n) - 1.0
    ann_bench_ret = (bench_vals[-1] / bench_vals[0]) ** (periods_per_year / n) - 1.0

    alpha = ann_fund_ret - (risk_free_annual + beta * (ann_bench_ret - risk_free_annual))
    alpha_1y = alpha * 100.0

    return BenchmarkRelativeStats(
        alpha_1y=alpha_1y,
        beta_1y=beta,
        tracking_error_pct=tracking_error_pct,
    )
