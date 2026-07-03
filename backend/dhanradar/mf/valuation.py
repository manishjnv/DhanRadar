"""
DhanRadar — Daily portfolio valuation series (M2.2).

Pure module: turns current holdings + a NAV map into a daily total portfolio
value.  No I/O, no DB, no Redis — golden-set testable.

This is the DATA layer that enables TRUE portfolio Sharpe/σ/max-drawdown
(deferred to M2.3, B88).  The Celery task calls ``compute_daily_value`` once
per portfolio per day; ``load_portfolio_valuation_series`` reads the stored
series back for the API endpoint.

Non-neg #2 (no-numeric-in-DOM): ``total_value`` and ``total_invested`` are the
owner's OWN calculated numbers and are DOM-allowed (#2-exempt per
serialization.py FORBIDDEN_SCORE_KEYS note).  The DhanRadar composite score is
never stored or returned here.

SEBI educational boundary: this module computes facts only.  No advisory label,
no recommendation, no verdict.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

#: Bump when the replay math changes — recorded for I11 replay parity (mirrors
#: projection.ENGINE_VERSION, the holdings-projection sibling of this valuation replay).
ENGINE_VERSION = "valuation-replay-1"

# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValuationPoint:
    """One day's portfolio total valuation.

    valuation_date  — the calendar date (NAV date).
    total_value     — sum of (units × NAV) for every holding on that date.
                      Zero when no holding has a NAV for this date.
    total_invested  — ledger net-invested (B86); constant over the series
                      unless a new CAS upload changes holdings.
    """

    valuation_date: datetime.date
    total_value: float
    total_invested: float


# ---------------------------------------------------------------------------
# Pure compute
# ---------------------------------------------------------------------------

def compute_daily_value(
    units_nav_pairs: list[tuple[float, float]],
    total_invested: float,
    valuation_date: datetime.date,
) -> ValuationPoint:
    """Compute one ValuationPoint from a list of (units, nav) tuples.

    Args:
        units_nav_pairs:  Each item is (units, latest_nav_for_that_isin).
                          Pairs with nav <= 0 or units <= 0 are skipped.
        total_invested:   The portfolio's net-invested amount (B86).
        valuation_date:   The date this valuation represents.

    Returns:
        ValuationPoint with total_value = Σ units × nav (rounded to 2 dp).

    The function is intentionally tolerant of empty lists (returns 0.0 value)
    so the Celery task can upsert even for a cold-start portfolio — the FE
    renders an empty / not-enough-data state rather than crashing.
    """
    total: float = 0.0
    for units, nav in units_nav_pairs:
        if units > 0 and nav > 0:
            total += units * nav
    return ValuationPoint(
        valuation_date=valuation_date,
        total_value=round(total, 2),
        total_invested=round(total_invested, 2),
    )


def _dated_flow_adjusted_returns(
    rows: list[ValuationPoint],
    flows_by_date: Mapping[datetime.date, float] | None = None,
) -> list[tuple[datetime.date, float]]:
    """Day-over-day return per row, paired with its date (single source of truth for
    ``flow_adjusted_daily_returns`` and the wealth-index builder below).

    ``flows_by_date`` (2026-07-03 fix): the ledger's REAL net cash flow per date
    (money into the portfolio positive = Σ(−amount) over every non-zero B65 row —
    dividend payouts included, same basis as XIRR). Preferred when the caller has
    the ledger: the invested-delta fallback only tracks CAPITAL types, so a
    dividend payout day would otherwise read as a fake loss."""
    out: list[tuple[datetime.date, float]] = []
    for prev, cur in zip(rows, rows[1:]):
        if prev.total_value <= 0:
            continue  # can't divide by a non-positive base — honestly skipped
        if flows_by_date is not None:
            flow = flows_by_date.get(cur.valuation_date, 0.0)
        else:
            flow = cur.total_invested - prev.total_invested
        r = (cur.total_value - prev.total_value - flow) / prev.total_value
        out.append((cur.valuation_date, r))
    return out


def flow_adjusted_daily_returns(
    rows: list[ValuationPoint],
    flows_by_date: Mapping[datetime.date, float] | None = None,
) -> list[float]:
    """Day-over-day portfolio returns, adjusted for capital flows (M2.3, B88).

    r_t = (V_t − V_{t-1} − F_t) / V_{t-1}

    F_t is the day's net external cash flow — from ``flows_by_date`` (the ledger's
    per-date Σ(−amount), payouts included) when provided, else the invested-delta
    (I_t − I_{t-1}) fallback. Subtracting it keeps a SIP/lump-sum purchase day from
    reading as a fake positive return — the same lesson as the day-change RCA
    (2026-07-02): a capital inflow is not a market move. Pairs where V_{t-1} <= 0
    are skipped (can't divide by a non-positive base). ``rows`` must be ordered
    ascending by date (load_portfolio_valuation_series's contract).
    """
    return [r for _, r in _dated_flow_adjusted_returns(rows, flows_by_date)]


def wealth_index(
    dated_returns: list[tuple[datetime.date, float]], base: float = 100.0
) -> list[tuple[datetime.date, float]]:
    """Cumulative-product wealth curve Π(1+r_t), seeded at ``base``.

    NAV-shaped output ``(date, value)`` — feeds ``risk.risk_adjusted_stats``
    (Sharpe/Sortino/vol/rolling-1Y) and ``max_drawdown_and_recovery`` below with
    the SAME series, so every M2.3 true-risk figure derives from one curve.
    """
    out: list[tuple[datetime.date, float]] = []
    value = base
    for d, r in dated_returns:
        value *= 1.0 + r
        out.append((d, value))
    return out


def twr_index_series(
    points: list[ValuationPoint], base: float = 100.0
) -> list[tuple[datetime.date, float]]:
    """Time-weighted-return wealth index, ONE ENTRY PER INPUT ROW (PR-C hero money-view / Section-2
    TWR return line — fixes the founder-reported bug where a large deposit rebased on window-start
    VALUE renders as a fake gain).

    Same Π(1+r_t) math as ``wealth_index`` but re-anchored to the FULL ``points`` list — ``wealth_index``
    only covers ``rows[1:]`` (a return needs a day-over-day pair). Here the first row, and any later
    row whose return ``_dated_flow_adjusted_returns`` honestly SKIPPED (a non-positive previous
    value — a cold-start gap), carries the index FORWARD unchanged rather than resetting: a deposit
    or a data gap never reads as a move. Seeded at ``base`` (100.0) on the first row. The client
    rebases any window purely by division — ``(idx_t / idx_window_start − 1) × 100`` — a
    presentation concern, not a recompute.
    """
    dated_returns = dict(_dated_flow_adjusted_returns(points))
    out: list[tuple[datetime.date, float]] = []
    idx = base
    for i, p in enumerate(points):
        if i > 0:
            r = dated_returns.get(p.valuation_date)
            if r is not None:
                idx *= 1.0 + r
        out.append((p.valuation_date, idx))
    return out


def max_drawdown_and_recovery(
    points: list[tuple[datetime.date, float]],
) -> tuple[float | None, int | None]:
    """Peak-to-trough decline (%) + recovery time (whole months) from a wealth-index series.

    Walks the series once tracking the running peak; whenever a NEW deepest
    drawdown is found, remembers the peak value that preceded it. Recovery is
    then the gap from that trough to the first LATER point that reclaims the
    peak value (day-count ÷ 30.44, rounded) — ``None`` when the series ends
    still underwater (not yet recovered). Returns ``(None, None)`` for an empty
    series and ``(0.0, None)`` for a series that never draws down (monotonic).
    """
    if not points:
        return None, None
    peak_value = points[0][1]
    max_dd = 0.0
    dd_peak_value = peak_value
    dd_trough_date: datetime.date | None = None
    for d, v in points:
        if v > peak_value:
            peak_value = v
        if peak_value > 0:
            dd = (peak_value - v) / peak_value * 100.0
            if dd > max_dd:
                max_dd = dd
                dd_peak_value = peak_value
                dd_trough_date = d
    if dd_trough_date is None:
        return 0.0, None

    recovery_months: int | None = None
    for d, v in points:
        if d > dd_trough_date and v >= dd_peak_value:
            recovery_months = round((d - dd_trough_date).days / 30.44)
            break
    return round(max_dd, 2), recovery_months


def replay_valuation_series(
    ledger_rows: Iterable[Mapping[str, Any]],
    nav_by_isin_date: Mapping[str, list[tuple[datetime.date, float]]],
    from_date: datetime.date,
    to_date: datetime.date,
) -> list[ValuationPoint]:
    """Replay a portfolio's FULL daily valuation series from ledger x NAV history (§39.5).

    Retires the `_reset_valuation_series` flow-adjustment patch: a composition change (S11 — the
    2026-07-02 -85% incident) is just more ledger rows, and the replayed series stays continuous
    and TRUE (it really was worth X then, Y now) because units-held and NAV are recomputed fresh
    for EVERY date in [from_date, to_date], never diffed against a stale snapshot.

    ``ledger_rows`` — any iterable of mappings with instrument_id/units/amount/txn_type/txn_date
    (+ optional nav_or_price) — same shape `projection.project_holdings_from_ledger` reads.
    ``nav_by_isin_date`` — isin -> ASCENDING list of (nav_date, nav); the caller batches ONE query
    for every ISIN x the whole window (never per-day, never per-ISIN). Once a price exists for an
    isin it carries forward (last known value) through any gap — a weekend, a holiday, a missed
    fetch.

    **Synthetic price seeding (2026-07-03 fix):** each txn's own ``nav_or_price`` is merged into
    the price series as a fallback point at its txn_date (a REAL NAV on the same date wins). This
    is the fix for the +212% RCA: a fund whose NAV history starts LATER than its transactions
    (INF740KA1XH4 — 7 months of SIPs valued at zero, then all priced at once the day NAV coverage
    began) is now valued at its actual transaction price until market data exists — value tracks
    the real money, no cliff, and the flow-adjusted returns over that stretch are ~0 instead of a
    fake crash.

    Pure + deterministic; Decimal internally (authoritative rupee math, plan §13), float at the
    ValuationPoint boundary (matches compute_daily_value's existing contract)."""
    from dhanradar.mf.projection import _CAPITAL_FLOW_TYPES

    txns = sorted(ledger_rows, key=lambda r: r["txn_date"])

    # Merge real NAVs with synthetic per-txn price points; real wins on a date collision.
    price_map: dict[str, dict[datetime.date, float]] = {}
    for t in txns:
        p = t.get("nav_or_price")  # absent key (older callers/tests) → None → no synthetic point
        if p is not None and float(p) > 0:
            price_map.setdefault(t["instrument_id"], {})[t["txn_date"]] = float(p)
    for isin, navs in nav_by_isin_date.items():
        dates = price_map.setdefault(isin, {})
        for nd, nav in navs:
            dates[nd] = float(nav)  # real NAV overwrites any synthetic point on the same date
    merged_prices: dict[str, list[tuple[datetime.date, float]]] = {
        isin: sorted(dates.items()) for isin, dates in price_map.items()
    }
    units_by_isin: dict[str, Decimal] = {}
    last_nav: dict[str, Decimal] = {}
    nav_ptr: dict[str, int] = {}
    invested_total = Decimal(0)
    points: list[ValuationPoint] = []

    txn_idx = 0
    n_txns = len(txns)
    one_day = datetime.timedelta(days=1)
    d = from_date
    while d <= to_date:
        # Apply every txn dated on-or-before today (units-held + net-invested are cumulative).
        while txn_idx < n_txns and txns[txn_idx]["txn_date"] <= d:
            r = txns[txn_idx]
            isin = r["instrument_id"]
            units_by_isin[isin] = units_by_isin.get(isin, Decimal(0)) + Decimal(str(r["units"]))
            if r["txn_type"] in _CAPITAL_FLOW_TYPES:
                invested_total += -Decimal(str(r["amount"]))
            txn_idx += 1

        total_value = Decimal(0)
        for isin, units in units_by_isin.items():
            navs = merged_prices.get(isin)
            if navs:
                idx = nav_ptr.get(isin, 0)
                while idx + 1 < len(navs) and navs[idx + 1][0] <= d:
                    idx += 1
                nav_ptr[isin] = idx
                if navs[idx][0] <= d:
                    last_nav[isin] = Decimal(str(navs[idx][1]))
            nav = last_nav.get(isin)
            if nav is not None and units > 0:
                total_value += units * nav

        points.append(
            ValuationPoint(
                valuation_date=d,
                total_value=round(float(total_value), 2),
                total_invested=round(float(invested_total), 2),
            )
        )
        d += one_day
    return points
