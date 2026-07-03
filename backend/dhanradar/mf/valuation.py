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
    (a DB row mapping or plain dict — same shape `projection.project_holdings_from_ledger` reads).
    ``nav_by_isin_date`` — isin -> ASCENDING list of (nav_date, nav); the caller batches ONE query
    for every ISIN x the whole window (never per-day, never per-ISIN). A date with no NAV yet for
    an isin contributes nothing (honest, not fabricated); once a NAV exists it carries forward
    (last known value) through any gap — a weekend, a holiday, a missed fetch.

    Pure + deterministic; Decimal internally (authoritative rupee math, plan §13), float at the
    ValuationPoint boundary (matches compute_daily_value's existing contract)."""
    from dhanradar.mf.projection import _CAPITAL_FLOW_TYPES

    txns = sorted(ledger_rows, key=lambda r: r["txn_date"])
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
            navs = nav_by_isin_date.get(isin)
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
