"""
DhanRadar — Mood Compass API schemas (architecture Mood Compass public interface).

The public surface carries the `regime` bucket + `confidence_band` + commentary +
the contributing/contradicting evidence and the disclosure bundle — NEVER the numeric
mood_score / confidence number (non-neg #2) and never advice (non-neg #1).
"""

from __future__ import annotations

from pydantic import BaseModel


class MoodFactor(BaseModel):
    """A driver factor on the public surface: its human label + a COARSE 3-way
    magnitude tier ("strong"|"moderate"|"slight"). The numeric contribution /
    weight / value is NEVER carried here — only the tier string (non-neg #2)."""

    label: str
    tier: str = "slight"  # strong | moderate | slight


class MoodPublic(BaseModel):
    snapshot_date: str
    snapshot_at: str | None = None    # ISO 8601 tz-aware datetime of the snapshot (for relative time)
    regime: str                       # extreme_fear|fear|neutral|greed|extreme_greed|data_unavailable
    confidence_band: str              # high|medium|low|insufficient_data
    data_quality: str                 # ok|degraded|unavailable
    contributing_factors: list[MoodFactor] = []
    contradicting_factors: list[MoodFactor] = []
    commentary: str | None = None
    disclosure: str
    not_advice: str
    disclaimer_version: str
    trend: str | None = None       # improving|stable|deteriorating|None (ADR-0023)


class MoodHistoryItem(BaseModel):
    snapshot_date: str
    regime: str


class WhyToday(BaseModel):
    snapshot_date: str
    regime: str
    commentary: str | None = None
    contributing_factors: list[str] = []
    contradicting_factors: list[str] = []
    disclosure: str
    not_advice: str
    disclaimer_version: str


class FlowsOut(BaseModel):
    """Public FII/DII net flows (₹Cr) + Nifty put-call ratio. RAW public market facts
    (DOM-allowed, NOT a DhanRadar computed score). Null when the cache is cold."""

    fii_cr: float | None
    dii_cr: float | None
    pcr: float | None
    as_of: str | None
