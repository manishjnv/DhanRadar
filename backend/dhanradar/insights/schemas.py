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


# NB: `portfolio.concentration` moved to the A3 boundary in M2.1 (DataEnvelope, not a bespoke schema) —
# see `dhanradar.mf.portfolio_read.concentration_payload`. The old ConcentrationItem/ConcentrationResponse
# were removed; the overlap schemas below stay (overlap is data-starved, still raw Pydantic).


# ---------------------------------------------------------------------------
# Mood-context endpoint schemas
# ---------------------------------------------------------------------------

class MoodContextResponse(BaseModel):
    """
    Educational mood-context read: current market regime + portfolio structure.

    Compliance:
      - No numeric mood_score / 0-100 values in any field (non-neg #2)
      - regime is a string enum incl. data_unavailable — never an advisory verb (non-neg #1)
      - observations are deterministic templates, NOT LLM-generated
      - Disclosure bundle on every response (non-neg #9)
    """

    portfolio_id: str
    # Mood side — public read from mood module (no mood_score float, no 0-100 value)
    regime: str                        # extreme_fear|fear|neutral|greed|extreme_greed|data_unavailable
    regime_as_of: str | None           # ISO date string, None when data_unavailable
    # Portfolio structure side — reuses concentration module's public banded values only
    fund_count: int                    # number of holdings in this portfolio
    concentration_band: str            # "high" | "moderate" | "low" | "empty" — banded, not a pct
    top_category: str | None           # category with highest allocation, or None if empty
    # Templated, deterministic observations (non-LLM)
    observations: list[str]
    # Disclosure (non-neg #9) — same constants as overlap/concentration
    disclosure: str
    not_advice: str
    disclaimer_version: str
