"""
DhanRadar — Admin Phase 4: AI Ops console read-only response schemas.

# LOAD-BEARING: requires Opus + adversarial review
# Every schema here gates the AI Ops admin surface (scoring, AI gateway,
# budget governor, compliance audit).  No mutation schemas.  All values are
# read-only snapshots; instrumented:false fields document absent instrumentation.

Pydantic models for the 7 GET-only AI Ops endpoints:
    AiDashboardResponse    — /admin/ai (dashboard)
    AiVersionsResponse     — /admin/ai/versions
    AiPromptsResponse      — /admin/ai/prompts
    AiEvalResponse         — /admin/ai/eval
    AiSafetyResponse       — /admin/ai/safety
    AiFeedbackResponse     — /admin/ai/feedback
    AiCostResponse         — /admin/ai/cost
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------


class InstrumentedFalse(BaseModel):
    """Placeholder for a metric that is not yet instrumented/stored.

    The ``instrumented`` flag is always False here; ``note`` explains why.
    """

    instrumented: bool = False
    note: str = ""


class ModelSpendRow(BaseModel):
    """One model's spend over the window: billed call count + accumulated USD.

    Free-pool models show ``calls`` with ``usd=0`` (free tier); paid/premium
    models also carry ``usd``.
    """

    model: str
    calls: int
    usd: float


class PerModelSpend(BaseModel):
    """Per-model AI spend breakdown (Redis daily counters; PR-2).

    ``instrumented`` is the discriminator the frontend reads: True once the
    gateway has recorded at least one billed call in the window.
    """

    instrumented: bool = False
    window_days: int = 7
    models: list[ModelSpendRow] = []
    total_calls: int = 0
    total_usd: float = 0.0
    note: str = ""


class LatencyInfo(BaseModel):
    """Average LLM response latency over a rolling window (Redis daily counters).

    ``instrumented`` is the discriminator the frontend reads: True once the
    gateway has recorded at least one sample in the window, otherwise False (no
    samples yet, or the Redis read degraded). ``value_ms`` is the rolling mean in
    milliseconds, ``sample_count`` the number of timed responses behind it.
    """

    instrumented: bool = False
    value_ms: float | None = None
    sample_count: int = 0
    window_days: int = 7
    note: str = ""


class GroundednessInfo(BaseModel):
    """Sampled LLM-judge groundedness over a rolling window (Redis daily counters; PR-4).

    A sampled fraction of served AI outputs is scored 0..1 for how well its claims
    are supported by its input context. ``value`` is the mean score (None until a
    sample exists), ``sample_count`` how many outputs were judged, ``low_flags`` how
    many scored below the low threshold. ``instrumented`` requires ≥1 sample (a 0
    mean is not meaningful without a denominator). Only scores are stored — never
    the judged context or output (DPDP-safe).
    """

    instrumented: bool = False
    value: float | None = None
    sample_count: int = 0
    low_flags: int = 0
    window_days: int = 7
    note: str = ""


class BudgetSnapshot(BaseModel):
    """Live budget counters from Redis (ai:budget:free:today / ai:budget:premium:today)."""

    free_calls_today: int
    free_cap: int
    premium_usd_today: float
    premium_soft_cap: float
    premium_hard_cap: float
    free_remaining: int
    premium_remaining_usd: float
    # False when the Redis budget counters could not be read (degraded, not a 500).
    available: bool = True


class LabelChurnSummary(BaseModel):
    """Lightweight label-churn slice for the dashboard (from label_churn_review)."""

    decision: str
    churn: float
    requires_human_review: bool
    reason: str | None = None


class EngineVersionRow(BaseModel):
    """One row from compliance.rating_engine_changelog (read-only)."""

    model_version: str
    created_by: str | None
    approved_by: str | None
    # Display-only enrichments (UUID → auth.users.email); None if unresolvable.
    created_by_email: str | None = None
    approved_by_email: str | None = None
    two_person_ok: bool
    activated: bool
    activated_at: str | None  # ISO-8601 or null
    created_at: str | None    # ISO-8601 or null
    backtest: dict | None = None
    drift: dict | None = None


# ---------------------------------------------------------------------------
# /admin/ai  — AI Ops Dashboard
# ---------------------------------------------------------------------------


class AiDashboardResponse(BaseModel):
    """GET /admin/ai — top-level AI ops at-a-glance."""

    model_version: str
    activated: bool
    budget: BudgetSnapshot
    served_7d: int                          # total audit rows in last 7 days
    low_confidence_7d: int                  # low-confidence log rows in last 7 days
    label_churn: LabelChurnSummary          # churn review for "educational_label"
    # Rolling avg LLM response latency (Redis daily counters; instrumented once
    # the gateway records samples). eval_score remains not-yet-instrumented.
    avg_latency_ms: LatencyInfo = LatencyInfo(
        note="no latency samples recorded yet"
    )
    eval_score: GroundednessInfo = GroundednessInfo(
        note="no groundedness samples recorded yet"
    )


# ---------------------------------------------------------------------------
# /admin/ai/versions  — Score Versioning
# ---------------------------------------------------------------------------


class BacktestStatus(BaseModel):
    """Backtest pass-gate summary (PR-5). The real per-version outcome lives on each
    ``EngineVersionRow.backtest`` (``{"passed": bool}`` written at activation); this
    top-level flag says the §8 gate is tracked. ``versions_with_backtest`` counts how
    many returned rows carry a recorded outcome (vs not-asserted)."""

    instrumented: bool = True
    versions_with_backtest: int = 0
    note: str = (
        "§8 backtest pass-gate outcome per version (see each row's backtest; "
        "absent = not asserted). DhanRadar records the activation gate's pass/fail, "
        "not a historical-accuracy backtest score."
    )


class DriftStatus(BaseModel):
    """Label-drift signal (PR-5): reuses the existing label-churn review for the
    active educational-label scoring version — how much the same fund's label moves.
    ``instrumented`` is True once a churn reading is available."""

    instrumented: bool = False
    decision: str = "insufficient_data"
    churn: float = 0.0
    requires_human_review: bool = False
    note: str = (
        "Drift = label churn for the active educational_label scoring version "
        "(share of funds whose label changed). High churn ⇒ review the methodology."
    )


class AiVersionsResponse(BaseModel):
    """GET /admin/ai/versions — scoring model version registry."""

    versions: list[EngineVersionRow]
    backtest: BacktestStatus = BacktestStatus()
    drift: DriftStatus = DriftStatus()


# ---------------------------------------------------------------------------
# /admin/ai/prompts  — Prompt & RAG
# ---------------------------------------------------------------------------


class AiPromptsResponse(BaseModel):
    """GET /admin/ai/prompts — prompt version history (no DB registry)."""

    registry: bool = False
    note: str = (
        "Prompts are passed in by the gateway caller at request time; "
        "no server-side prompt DB registry exists. "
        "prompt_versions_seen are distinct values observed in ai_recommendation_audit."
    )
    prompt_versions_seen: list[str]


# ---------------------------------------------------------------------------
# /admin/ai/eval  — Quality / Eval
# ---------------------------------------------------------------------------


class QualityIssueRow(BaseModel):
    """One row from mf.data_quality_issues (same shape as ops_router)."""

    metric_key: str
    label: str
    current_value: float | None
    threshold: float | None
    unit: str
    status: str
    acknowledged_until: str | None


class AiEvalResponse(BaseModel):
    """GET /admin/ai/eval — groundedness eval + data quality issues."""

    quality_issues: list[QualityIssueRow]
    groundedness: GroundednessInfo = GroundednessInfo(
        note="no groundedness samples recorded yet"
    )


# ---------------------------------------------------------------------------
# /admin/ai/safety  — Safety Monitor
# ---------------------------------------------------------------------------


class AuditRowSummary(BaseModel):
    """Compact view of one ai_recommendation_audit row."""

    id: str
    served_at: str | None
    recommendation_type: str
    label: str | None
    confidence_band: str | None
    model: str | None
    surface: str | None
    prompt_version: str | None
    request_id: str | None


class LowConfidenceRowSummary(BaseModel):
    """Compact view of one ai_low_confidence_log row."""

    id: str
    logged_at: str | None
    surface: str | None
    identifier: str | None
    confidence_score: float | None
    confidence_band: str | None
    model: str | None
    reason: str | None
    request_id: str | None


class AdviceBoundaryBreachesInfo(BaseModel):
    """Advisory-boundary breach counter (PR-3).

    Counts LLM responses REJECTED by the gateway's SEBI advisory screen over the
    window. A breach means the model emitted a banned advisory verb and the gate
    HELD (the output was never served) — it is NOT advice that reached a user.
    When instrumented, a 0 is now a MEANINGFUL clean reading (boundary held, no
    breaches), not the old "cannot observe" placeholder.
    """

    value: int = 0
    window_days: int = 7
    instrumented: bool = False
    note: str = (
        "Count of AI responses rejected by the runtime advisory screen (the SEBI "
        "boundary held — rejected output is never served to a user). A 0 means no "
        "breaches were recorded in the window."
    )


class AiSafetyResponse(BaseModel):
    """GET /admin/ai/safety — safety monitor snapshot."""

    days: int
    served_by_type: dict[str, int]
    by_confidence_band: dict[str, int]
    low_confidence_count: int
    recent_audit_rows: list[AuditRowSummary]
    recent_low_confidence: list[LowConfidenceRowSummary]
    label_churn_educational: LabelChurnSummary
    label_churn_mood: LabelChurnSummary
    advice_boundary_breaches: AdviceBoundaryBreachesInfo = AdviceBoundaryBreachesInfo()
    groundedness: GroundednessInfo = GroundednessInfo(
        note="no groundedness samples recorded yet"
    )


# ---------------------------------------------------------------------------
# /admin/ai/feedback  — Feedback Review
# ---------------------------------------------------------------------------


class FeedbackRow(BaseModel):
    """One row returned in the admin feedback summary."""

    id: str
    audit_id: str
    helpful: bool
    feedback_text: str | None = None
    created_at: str | None = None


class AiFeedbackResponse(BaseModel):
    """GET /admin/ai/feedback — user feedback aggregates."""

    available: bool = True
    days: int = 30
    total: int = 0
    helpful: int = 0
    helpful_pct: float | None = None
    recent: list[FeedbackRow] = []


# ---------------------------------------------------------------------------
# /admin/ai/cost  — Cost & Usage
# ---------------------------------------------------------------------------


class AiCostResponse(BaseModel):
    """GET /admin/ai/cost — AI budget governor spend + caps."""

    budget: BudgetSnapshot
    per_model: PerModelSpend = PerModelSpend(
        note="no per-model spend recorded yet"
    )
    latency: LatencyInfo = LatencyInfo(
        note="no latency samples recorded yet"
    )


# ---------------------------------------------------------------------------
# Phase 5 mutation schemas — prompt template registry
# ---------------------------------------------------------------------------


class PromptTemplateCreateRequest(BaseModel):
    """Body for POST /admin/ai/prompts — create a new (inactive) template version."""

    template_key: str = Field(..., min_length=1, description="Stable identifier for this prompt")
    body: str = Field(..., min_length=1, description="Full prompt text")
    notes: str | None = Field(None, description="Human-readable change notes")


class PromptTemplateRow(BaseModel):
    """One prompt_template row returned by create / activate endpoints."""

    id: UUID
    template_key: str
    version: int
    body: str
    notes: str | None
    is_active: bool
    created_by: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Phase 5 mutation schemas — budget cap override
# ---------------------------------------------------------------------------


class BudgetCapsSetRequest(BaseModel):
    """Body for POST /admin/ai/cost/caps — set or reset AI budget caps."""

    # Upper bounds are money-safety guards (V5): they prevent a fat-finger from
    # neutering the AI hard-cap (default ~$9.50/day). Generous ceilings — raise
    # deliberately in code if a higher legitimate cap is ever needed.
    free_cap: int = Field(
        ..., gt=0, le=1_000_000, description="Daily free-tier call count cap"
    )
    premium_soft_usd: float = Field(
        ..., gt=0, le=200.0, description="Premium soft-warn threshold in USD"
    )
    premium_hard_usd: float = Field(
        ..., gt=0, le=200.0, description="Premium hard-stop cap in USD"
    )
    reset: bool = Field(
        False,
        description=(
            "When true, delete Redis override keys and revert to hardcoded defaults. "
            "The cap values in the body are still written to the audit history row."
        ),
    )


class BudgetCapsResponse(BaseModel):
    """Response for POST /admin/ai/cost/caps — effective caps after the mutation."""

    free_cap: int
    premium_soft_usd: float
    premium_hard_usd: float
    reset: bool = False
