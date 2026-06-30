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
from dataclasses import dataclass

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
