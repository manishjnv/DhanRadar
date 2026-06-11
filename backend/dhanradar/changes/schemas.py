"""
DhanRadar — What Changed module response schemas (Plan Group 2).

ALLOWLIST models only — no from_orm / expose-all. unified_score NEVER appears.
Confidence BAND (high/medium/low/insufficient_data) is the only confidence
surface. All reason copy is educational (descriptive label/band facts), never
advisory. Integer nav_days_ago is the ONLY numeric field permitted in the DOM
(non-neg #2 clarification: freshness metadata, not a score).
"""

from __future__ import annotations

from pydantic import BaseModel


class FundChange(BaseModel):
    """Per-fund label-change projection.

    Compliance-sensitive fields:
      label_from / label_to — non-advisory VerbLabel values
      band_from / band_to   — BAND only (high/medium/low/insufficient_data)
      change_kind           — descriptive category; never an instruction
      reasons               — plain-language educational copy; no advisory verbs
      nav_days_ago          — integer freshness metadata; NOT a score
    """

    isin: str
    scheme_name: str | None
    # Label + band snapshot (from = prior, to = latest)
    label_from: str | None          # VerbLabel or None when single snapshot
    label_to: str                   # VerbLabel: in_form/on_track/off_track/out_of_form/insufficient_data
    band_from: str | None           # ConfidenceBand or None when single snapshot
    band_to: str                    # ConfidenceBand: high/medium/low/insufficient_data
    changed: bool                   # True when label_from != label_to
    change_kind: str                # "improved"|"weakened"|"unchanged"|"new"|"insufficient_data"
    reasons: list[str]              # educational plain-language copy; [] only on error path
    as_of_from: str | None          # ISO date of the prior snapshot, or None
    as_of_to: str                   # ISO date of the latest snapshot
    # NAV freshness metadata (factual data-quality; non-neg #2 integer exception)
    nav_as_of: str | None           # ISO date string, or None
    nav_days_ago: int | None        # integer days since that NAV date, or None
    nav_is_stale: bool              # True when nav_days_ago > _NAV_STALE_DAYS


class PortfolioChangesResponse(BaseModel):
    """Full portfolio what-changed payload.

    Disclosure bundle rides along on every response (non-neg #9).
    unified_score is ABSENT by construction (no such field, no such alias).
    """

    portfolio_id: str
    changes: list[FundChange]
    # Disclosure bundle (non-neg #9) — same pattern as transparency/dashboard payloads.
    disclosure: str
    not_advice: str
    disclaimer_version: str
