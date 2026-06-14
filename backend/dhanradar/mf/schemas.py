"""
DhanRadar — MF API response schemas (Phase 5).

No-numeric-in-DOM (non-neg #2) applies to the SCORE: `unified_score`, factor
weights, and fair-value never appear in any response here. The user's OWN
portfolio facts (their invested amount, current value, XIRR, allocation) ARE their
data and are shown. Per-fund verdict = `verb_label` + `confidence_band` only.

Every report carries the SEBI disclosure bundle + NOT_ADVICE, injected at the
serializer (anti-pattern guard).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PortfolioSummary(BaseModel):
    """Public representation of a named portfolio (no numeric score/value fields)."""

    id: str
    name: str
    created_at: str


class PortfolioListResponse(BaseModel):
    portfolios: list[PortfolioSummary]


class PortfolioCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


class CasUploadResponse(BaseModel):
    job_id: str
    estimated_seconds: int = 60
    deduped: bool = False  # True if an identical CAS was already processed


class CasJobStatus(BaseModel):
    job_id: str
    status: str  # queued | parsing | scoring | done | failed
    progress_pct: int
    error_message: str | None = None


class FundReportItem(BaseModel):
    isin: str
    scheme_name: str
    folio_number: str
    units: float
    invested_amount: float | None = None
    current_value: float | None = None
    # Verdict — label + band ONLY. No unified_score / weights (non-neg #2).
    verb_label: str | None = None
    confidence_band: str | None = None
    contributing_signals: list[str] = []
    contradicting_signals: list[str] = []
    # Feature 3: label from the previous upload for delta display (↑/↓).
    # None on first-ever upload or when history is unavailable.
    previous_label: str | None = None
    # Feature 4: named confidence quality signals — string bands only (high/medium/low).
    # null on old cached reports; frontend degrades gracefully when absent.
    confidence_factors: dict[str, str] | None = None


class FundLabelHistory(BaseModel):
    """Per-fund verdict in a history snapshot — label + band ONLY (non-neg #2)."""

    isin: str
    verb_label: str
    confidence_band: str


class SnapshotHistoryItem(BaseModel):
    """One snapshot date with all scored funds for that day."""

    snapshot_date: str
    funds: list[FundLabelHistory]


class PortfolioHistoryResponse(BaseModel):
    """Plus-gated history of portfolio labels over time.

    No unified_score / total_invested / xirr_pct — only the public projection.
    """

    snapshots: list[SnapshotHistoryItem]
    disclosure: str
    not_advice: str
    disclaimer_version: str | None = None


class PortfolioReport(BaseModel):
    job_id: str
    status: str
    total_invested: float | None = None
    current_value: float | None = None
    xirr_pct: float | None = None
    category_allocation: dict[str, float] = {}
    overlap_matrix: dict[str, dict[str, float]] = {}
    funds: list[FundReportItem] = []
    # Optional non-blocking AI portfolio commentary (omitted/None on refusal or failure).
    # generate_commentary() returns a dict with a `state` key; never a plain string.
    commentary: dict | None = None
    model_version: str | None = None
    generated_at: str | None = None
    # Feature 2/3: portfolio_id exposed so the frontend can call the history endpoint.
    portfolio_id: str | None = None
    # Mandatory disclosure bundle (non-neg #9) — injected at serialization. The
    # in-force `disclaimer_version` is stamped on the SERVED surface so it matches
    # the `ai_recommendation_audit` row for this report (B26 / §4 tie-to-version).
    disclosure: str
    not_advice: str
    disclaimer_version: str | None = None
