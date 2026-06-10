"""
DhanRadar — Portfolio Intelligence response schemas (Plan Group 3).

EXPLICIT allowlist Pydantic models — no numeric score/weights/fair-value ever
reaches the client (non-neg #2). Portfolio composition percentages (overlap %,
sector %, AMC %, concentration %) ARE the user's own data — allowed in DOM.

All user-facing text is OBSERVATIONAL only ("Fund A and Fund B share 62% large-cap
allocation") — NEVER advisory ("reduce", "diversify", "switch", "rebalance", "sell").
Every response carries NOT_ADVICE + disclosure bundle (non-neg #9).
"""

from __future__ import annotations

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Overlap endpoint schemas
# ---------------------------------------------------------------------------

class FundPairOverlap(BaseModel):
    """Pairwise overlap between two funds — a factual % of shared constituent weights."""

    fund_a_isin: str
    fund_a_name: str
    fund_b_isin: str
    fund_b_name: str
    overlap_pct: float
    observation: str  # e.g. "Fund A and Fund B share similar large-cap constituents (62%)."


class CategoryOverlap(BaseModel):
    """Factual distribution of category allocation across the portfolio."""

    category: str
    allocation_pct: float
    fund_count: int
    observation: str  # e.g. "3 funds hold similar Large Cap allocations (total 58%)."


class OverlapResponse(BaseModel):
    portfolio_id: str
    as_of_date: str | None
    fund_pairs: list[FundPairOverlap]
    category_distribution: list[CategoryOverlap]
    observation_summary: str  # e.g. "Your portfolio contains 4 funds across 3 categories."
    # Cold-start / insufficient data — still a 200 with empty lists
    data_completeness: str  # "partial" | "complete" | "empty"
    # Disclosure (non-neg #9)
    disclosure: str
    not_advice: str
    disclaimer_version: str


# ---------------------------------------------------------------------------
# Concentration endpoint schemas
# ---------------------------------------------------------------------------

class ConcentrationItem(BaseModel):
    """A single concentration data point — factual % + educational context line."""

    name: str          # e.g. "Large Cap" / "SBI Mutual Fund" / fund scheme name
    allocation_pct: float
    context: str       # educational: what this % means in portfolio terms — NOT advisory


class ConcentrationResponse(BaseModel):
    portfolio_id: str
    as_of_date: str | None
    # Each list is factual portfolio composition — allowed in DOM (user's own data)
    by_category: list[ConcentrationItem]
    by_amc: list[ConcentrationItem]
    by_fund: list[ConcentrationItem]
    observation_summary: str  # e.g. "Your portfolio spans 3 AMCs and 4 funds across 3 categories."
    # Cold-start / single-fund / empty portfolio — valid 200 with empty lists
    data_completeness: str  # "partial" | "complete" | "empty"
    # Disclosure (non-neg #9)
    disclosure: str
    not_advice: str
    disclaimer_version: str
