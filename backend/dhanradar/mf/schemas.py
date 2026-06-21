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


class PortfolioLatestResponse(BaseModel):
    """Returned by GET /mf/portfolio/latest — lets the frontend navigate to the
    user's most recent report without the user supplying or re-uploading a CAS."""

    job_id: str
    portfolio_id: str
    portfolio_name: str


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
    # SEBI-canonical category from mf_funds (fills the Category column in the holdings table).
    category: str | None = None
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
    # Feature 5: market-wide category rank — ordinal integer only, never unified_score
    # (non-neg #2). None when rank not yet computed or fund has no sebi_category.
    category_rank: int | None = None
    category_total: int | None = None


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


class FundSearchItem(BaseModel):
    """Search result item for GET /api/v1/mf/search.

    Public — no scores, no numerics, no verb_label (non-neg #2).
    Fields: isin, scheme_name, amc_name, sebi_category only.
    """

    isin: str
    scheme_name: str
    amc_name: str | None = None
    sebi_category: str | None = None


class FundExplorerItem(BaseModel):
    isin: str
    scheme_name: str
    amc_name: str | None = None
    sebi_category: str
    verb_label: str
    confidence_band: str | None = None
    confidence_factors: dict[str, str] | None = None
    category_rank: int
    category_total: int
    return_3m_pct: float | None = None
    return_6m_pct: float | None = None
    return_1y_pct: float | None = None
    return_3y_pct: float | None = None
    return_5y_pct: float | None = None
    plan_type: str | None = None        # 'direct' | 'regular' | None
    option_type: str | None = None      # 'growth' | 'idcw' | 'dividend_reinvest' | 'dividend_payout' | None
    amc_level_aum_crore: float | None = None  # AMC-level AUM (ADR-0035); None until endpoint confirmed


class FundExplorerResponse(BaseModel):
    funds: list[FundExplorerItem]
    total: int
    page: int
    limit: int
    disclosure: str
    not_advice: str


class FundCategory(BaseModel):
    key: str
    display_name: str
    fund_count: int


class FundCategoriesResponse(BaseModel):
    categories: list[FundCategory]


class MFResearchAskRequest(BaseModel):
    """Request body for POST /mf/report/{job_id}/ask."""

    question: str = Field(
        min_length=1,
        max_length=500,
        description="Educational question about the user's own portfolio (max 500 chars).",
    )


class MFResearchAskResponse(BaseModel):
    """Public response shape for the research endpoint.

    NEVER includes numeric confidence float (non-neg #2).
    """

    state: str  # "ok" | "insufficient_data" | "unavailable" | "daily_cap"
    answer: str | None = None
    citations: list[str] | None = None
    refusal_triggered: bool | None = None
    confidence_band: str | None = None
    contributing_signals: list[str] | None = None
    contradicting_signals: list[str] | None = None
    disclaimer: str | None = None
    disclaimer_version: str | None = None
    reason: str | None = None  # on unavailable/daily_cap: why it failed
