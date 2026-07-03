"""
DhanRadar — MF portfolio snapshot math (Phase 5, architecture §MF).

Pure, deterministic analytics: no I/O, no DB, no Redis, no side-effects.
Computes portfolio-level XIRR, category allocation, and pairwise fund-overlap
from injected holding + cash-flow data.

SEBI educational boundary: this module produces numbers (XIRR %, allocation %)
for internal tier-gated use only — no advisory labels, no buy/sell/hold signals.
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass

from scipy.optimize import brentq

# ---------------------------------------------------------------------------
# Dataclasses (frozen — value objects, never mutated)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CashFlow:
    """A single dated cash movement.

    Convention: investments are *negative* (money leaves the investor),
    redemptions and the current mark-to-market value are *positive*.
    """

    when: datetime.date
    amount: float


@dataclass(frozen=True)
class Holding:
    """One MF scheme position inside a portfolio."""

    isin: str
    units: float
    invested_amount: float
    current_value: float
    category: str
    cashflows: list[CashFlow]


@dataclass(frozen=True)
class PortfolioSnapshot:
    """Aggregate, point-in-time view of the full MF portfolio."""

    total_invested: float
    current_value: float
    xirr_pct: float | None                          # None when uncomputable
    category_allocation: dict[str, float]               # category → % of total CV
    overlap_matrix: dict[str, dict[str, float]]         # isin → isin → overlap %


# ---------------------------------------------------------------------------
# XIRR — annualized money-weighted return
# ---------------------------------------------------------------------------

def xirr(cashflows: list[CashFlow]) -> float | None:
    """Return annualized IRR as a percent (e.g. 12.34 for 12.34 %).

    Uses Brent's method on NPV(rate) = Σ amount / (1+rate)^(days/365),
    where days is measured from the *earliest* cash-flow date.

    Returns None when:
    - fewer than 2 cash flows are supplied
    - all cash flows share the same sign (no sign change → no root)
    - scipy.optimize.brentq fails to bracket or converge
    """
    if len(cashflows) < 2:
        return None

    # All-same-sign guard: a root can only exist when signs differ.
    amounts = [cf.amount for cf in cashflows]
    if all(a > 0 for a in amounts) or all(a < 0 for a in amounts):
        return None

    # Anchor t=0 at the earliest date.
    base = min(cf.when for cf in cashflows)

    def npv(rate: float) -> float:
        total = 0.0
        for cf in cashflows:
            days = (cf.when - base).days
            total += cf.amount / math.pow(1.0 + rate, days / 365.0)
        return total

    # Brent's method requires a bracket where npv changes sign.
    lo, hi = -0.9999, 10.0
    try:
        npv_lo = npv(lo)
        npv_hi = npv(hi)
        if npv_lo * npv_hi > 0:
            # No sign change in the bracket — cannot guarantee a root.
            return None
        rate = brentq(npv, lo, hi, xtol=1e-8, maxiter=500)
    except (ValueError, RuntimeError):
        return None

    return round(rate * 100.0, 2)


# ---------------------------------------------------------------------------
# Windowed XIRR — annualized return over a fixed window (M2.3), e.g. "1Y XIRR"
# ---------------------------------------------------------------------------

def windowed_xirr(
    start_value: float,
    start_date: datetime.date,
    flows: list[CashFlow],
    end_value: float,
    end_date: datetime.date,
) -> float | None:
    """Annualized return over [start_date, end_date] — reuses `xirr()`, no new root-finder.

    Modeled as three legs: a pseudo-PURCHASE of ``start_value`` on ``start_date`` (negative —
    money "invested" at the window's start) + the REAL B65-signed capital flows that happened
    strictly inside the window + a pseudo-terminal INFLOW of ``end_value`` on ``end_date``
    (positive — today's mark-to-market). The B65 investor convention (outflow negative, inflow
    positive) already matches `CashFlow`'s sign convention, so ledger flows pass straight through.

    None when ``start_value`` <= 0, ``end_date`` <= ``start_date``, or the solver can't find a
    root (delegated to `xirr()`'s own guards — e.g. a flat window with no real move).
    """
    if start_value <= 0 or end_date <= start_date:
        return None
    cashflows = [
        CashFlow(when=start_date, amount=-start_value),
        *flows,
        CashFlow(when=end_date, amount=end_value),
    ]
    return xirr(cashflows)


# ---------------------------------------------------------------------------
# Category allocation
# ---------------------------------------------------------------------------

def category_allocation(holdings: list[Holding]) -> dict[str, float]:
    """Percent of total current value per category, rounded to 2 decimals.

    The percents are computed relative to the portfolio's total current value.
    Returns {} when total current value is zero (avoids division by zero).
    """
    total_cv = sum(h.current_value for h in holdings)
    if total_cv == 0.0:
        return {}

    buckets: dict[str, float] = {}
    for h in holdings:
        buckets[h.category] = buckets.get(h.category, 0.0) + h.current_value

    return {cat: round(cv / total_cv * 100.0, 2) for cat, cv in buckets.items()}


# ---------------------------------------------------------------------------
# Overlap matrix
# ---------------------------------------------------------------------------

def overlap_matrix(
    holdings: list[Holding],
    constituents: dict[str, dict[str, float]] | None = None,
) -> dict[str, dict[str, float]]:
    """Pairwise portfolio-overlap % between MF schemes.

    ``constituents`` maps isin → {underlying_stock: weight_pct}.
    Overlap(A, B) = Σ_{shared stocks} min(weightA[s], weightB[s]).

    The matrix is symmetric; the diagonal is omitted (or implicitly 100 %).
    Returns {} when ``constituents`` is None or empty — underlying-holdings
    data is a later feed; this function never fabricates constituent weights.
    """
    if not constituents:
        return {}

    isins = [h.isin for h in holdings]
    result: dict[str, dict[str, float]] = {}

    for i, isin_a in enumerate(isins):
        weights_a = constituents.get(isin_a, {})
        row: dict[str, float] = {}
        for j, isin_b in enumerate(isins):
            if i == j:
                continue
            weights_b = constituents.get(isin_b, {})
            shared = set(weights_a) & set(weights_b)
            overlap = sum(min(weights_a[s], weights_b[s]) for s in shared)
            row[isin_b] = round(overlap, 2)
        if row:
            result[isin_a] = row

    return result


# ---------------------------------------------------------------------------
# build_snapshot — main entry point
# ---------------------------------------------------------------------------

def build_snapshot(
    holdings: list[Holding],
    constituents: dict[str, dict[str, float]] | None = None,
) -> PortfolioSnapshot:
    """Aggregate holdings into a PortfolioSnapshot.

    - ``total_invested`` = Σ invested_amount across all holdings.
    - ``current_value``  = Σ current_value across all holdings.
    - ``xirr_pct``       = XIRR computed from the *union* of all cash flows
                           across the portfolio (portfolio-level money-weighted
                           return, not a per-holding average).
    - ``category_allocation`` and ``overlap_matrix`` as per their own functions.
    """
    total_invested = sum(h.invested_amount for h in holdings)
    total_cv = sum(h.current_value for h in holdings)

    # Union of all per-holding cash flows for portfolio-level XIRR.
    all_flows: list[CashFlow] = []
    for h in holdings:
        all_flows.extend(h.cashflows)

    xirr_pct = xirr(all_flows)

    return PortfolioSnapshot(
        total_invested=total_invested,
        current_value=total_cv,
        xirr_pct=xirr_pct,
        category_allocation=category_allocation(holdings),
        overlap_matrix=overlap_matrix(holdings, constituents),
    )
