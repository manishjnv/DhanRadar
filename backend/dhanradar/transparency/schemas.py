"""
DhanRadar — Transparency module response schemas (Plan Group 9 / PU2).

ALLOWLIST models only — never from_orm/expose-all. unified_score NEVER appears.
Confidence BAND (high/medium/low/insufficient_data) is the only confidence
surface. All driver copy is educational (data-quality facts), never advisory.
"""

from __future__ import annotations

from pydantic import BaseModel


class DataSource(BaseModel):
    """One data source that contributed to this fund's assessment."""

    name: str   # e.g. "AMFI NAV Feed", "CAMS/KARVY CAS"
    type: str   # e.g. "nav_data", "holdings"


class FreshnessMeta(BaseModel):
    """NAV + holdings freshness facts.

    nav_as_of / nav_days_ago describe the most-recent NAV date available; they
    are FACTUAL DATA-QUALITY metadata, not the score. Allowed in DOM per
    non-neg #2 clarification in the feature spec.
    """

    nav_as_of: str | None        # ISO date string "2026-06-10", or null
    nav_days_ago: int | None     # integer days since that NAV date, or null
    is_stale: bool                  # True when nav_days_ago > STALE_THRESHOLD_DAYS
    holdings_as_of: str | None   # ISO date from mf_user_holdings.as_of_date


class InsufficientDataRefusal(BaseModel):
    """Explicit refusal block shown when confidence_band == insufficient_data.

    PU2: this is a deliberate honesty signal, not an error. The UI must
    render it as a positive statement ("we won't guess") rather than a failure.
    """

    reason: str     # short user-facing sentence
    detail: str     # educational detail — what data is needed, never advisory


class FundTransparency(BaseModel):
    """Per-fund transparency projection.

    All compliance-sensitive fields:
      label             — non-advisory VerbLabel value
      confidence_band   — BAND only (high/medium/low/insufficient_data)
      drivers           — plain-language data-quality reasons (educational, not advice)
      what_would_change — directional, educational "what would move this label / raise
                          confidence" guidance (G10 show-your-working). Qualitative
                          only — never a numeric weight, score, or threshold; never
                          advice (no buy/sell/switch). [] when refusal.
      refusal           — non-null ONLY when confidence_band == insufficient_data (PU2)
      sources           — data source names + types
      freshness         — NAV + holdings freshness metadata
    """

    isin: str
    scheme_name: str
    category: str | None
    label: str              # VerbLabel: in_form/on_track/off_track/out_of_form/insufficient_data
    confidence_band: str    # ConfidenceBand: high/medium/low/insufficient_data
    drivers: list[str]      # educational plain-language data-quality reasons; [] when refusal
    what_would_change: list[str]  # G10 — directional educational guidance; [] when refusal
    refusal: InsufficientDataRefusal | None  # PU2 — non-null only on insufficient_data
    sources: list[DataSource]
    freshness: FreshnessMeta
    scored_at: str | None    # ISO datetime — when this label was computed
    model_version: str


class PortfolioTransparencyResponse(BaseModel):
    """Full portfolio transparency payload.

    Disclosure bundle rides along on every response (non-neg #9).
    unified_score is ABSENT by construction (no such field, no such alias).
    """

    portfolio_id: str
    generated_at: str           # ISO UTC datetime of this response
    funds: list[FundTransparency]
    # Disclosure bundle (non-neg #9) — same pattern as dashboard/mood payloads.
    disclosure: str
    not_advice: str
    disclaimer_version: str
