"""
DhanRadar — Admin Phase 4: AI Ops console (READ-ONLY monitoring).

# LOAD-BEARING: requires Opus + adversarial review
# Every route in this file is adjacent to the AI gateway, scoring engine,
# budget governor, and compliance audit surfaces.  No mutations exist here.
# All write paths are deferred to Phase 5 (gated mutations with full Tier-B/C
# inline review + adversarial sign-off).

Prefix  : /admin   (mounted at /api/v1/admin in main.py)
Tags    : ["admin-aiops"]
Auth    : RequireAdmin() on EVERY route — 404 to non-admins (surface-hiding).

Endpoints (all GET, all read-only):
    GET /admin/ai              — AiDashboardResponse
    GET /admin/ai/versions     — AiVersionsResponse
    GET /admin/ai/prompts      — AiPromptsResponse
    GET /admin/ai/eval         — AiEvalResponse
    GET /admin/ai/safety       — AiSafetyResponse
    GET /admin/ai/feedback     — AiFeedbackResponse
    GET /admin/ai/cost         — AiCostResponse

Module isolation contract (non-neg #7):
    - Budget reads    : dhanradar.budget.compute_budget_state + Redis directly
    - Scoring reads   : dhanradar.compliance.service.list_engine_versions
                        + dhanradar.scoring.engine.config.get_config
    - Audit reads     : dhanradar.compliance.service.safety_monitor_summary
                        + dhanradar.compliance.service.label_churn_review
                        + dhanradar.compliance.service.list_distinct_prompt_versions
    - Quality reads   : dhanradar.models.mf.MfDataQualityIssue (same mf schema)
    NO cross-module JOINs; no writes anywhere in this file.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.ai_gateway.metrics import (
    read_advisory_breaches,
    read_groundedness_window,
    read_latency_window,
    read_spend_window,
)
from dhanradar.budget import (
    _CAP_OVERRIDE_KEYS,
    _REDIS_KEYS,
    compute_budget_state,
    get_effective_caps,
)
from dhanradar.compliance.service import (
    feedback_summary,
    is_engine_version_activated,
    label_churn_review,
    list_distinct_prompt_versions,
    list_engine_versions,
    safety_monitor_summary,
)
from dhanradar.db import get_db
from dhanradar.deps import RequireAdmin, UserContext
from dhanradar.redis_client import get_redis
from dhanradar.scoring.engine.config import get_config

from .aiops_schemas import (
    AdviceBoundaryBreachesInfo,
    AiCostResponse,
    AiDashboardResponse,
    AiEvalResponse,
    AiFeedbackResponse,
    AiPromptsResponse,
    AiSafetyResponse,
    AiVersionsResponse,
    AuditRowSummary,
    BacktestStatus,
    BudgetCapsResponse,
    BudgetCapsSetRequest,
    BudgetSnapshot,
    DriftStatus,
    EngineVersionRow,
    FeedbackRow,
    GroundednessInfo,
    LabelChurnSummary,
    LatencyInfo,
    LowConfidenceRowSummary,
    PerModelSpend,
    PromptTemplateCreateRequest,
    PromptTemplateRow,
    QualityIssueRow,
)

router = APIRouter(prefix="/admin", tags=["admin-aiops"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _read_budget_snapshot() -> BudgetSnapshot:
    """Async helper: read both Redis budget keys and compute the snapshot.

    On a Redis failure, return a degraded snapshot (caps known from constants, spend
    unknown) with ``available=False`` rather than 500-ing a monitoring surface — an
    operator wants this page precisely when infra is unhealthy.

    Passes effective (admin-overridable) caps into compute_budget_state so the read
    endpoint reflects any live cap overrides set via POST /admin/ai/cost/caps.
    """
    redis = get_redis()
    try:
        free_raw = await redis.get(_REDIS_KEYS["free"])
        premium_raw = await redis.get(_REDIS_KEYS["premium"])
        effective = await get_effective_caps(redis)
    except Exception:  # noqa: BLE001 — degraded monitoring, not a 500
        # Degraded: do not mislead with "0 spend looks healthy" — flag available=False.
        return BudgetSnapshot(**compute_budget_state(None, None), available=False)
    state = compute_budget_state(
        free_raw,
        premium_raw,
        free_cap=int(effective["free"]),
        premium_soft=float(effective["premium_soft"]),
        premium_hard=float(effective["premium_hard"]),
    )
    return BudgetSnapshot(**state)


def _churn_to_summary(churn: dict) -> LabelChurnSummary:
    """Coerce label_churn_review dict to the LabelChurnSummary schema."""
    return LabelChurnSummary(
        decision=churn.get("decision", "insufficient_data"),
        churn=float(churn.get("churn", 0.0)),
        requires_human_review=bool(churn.get("requires_human_review", False)),
        reason=churn.get("reason"),
    )


# ---------------------------------------------------------------------------
# GET /admin/ai  — AI Ops Dashboard
# ---------------------------------------------------------------------------


@router.get("/ai", response_model=AiDashboardResponse)
async def get_ai_dashboard(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AiDashboardResponse:
    """Return the AI Ops at-a-glance dashboard.

    Combines:
    - Active scoring model version (from file-backed config)
    - Live budget snapshot (from Redis counters)
    - Served audit count for last 7 days
    - Low-confidence log count for last 7 days
    - Label churn review for 'educational_label'
    - Rolling avg LLM response latency (gateway Redis counters)

    eval_score remains not-yet-instrumented (instrumented:false).
    """
    from dhanradar.models.compliance import AiLowConfidenceLog, AiRecommendationAudit

    cfg = get_config()
    budget = await _read_budget_snapshot()

    cutoff = datetime.now(UTC) - timedelta(days=7)

    served_7d: int = (
        await db.scalar(
            select(func.count())
            .select_from(AiRecommendationAudit)
            .where(AiRecommendationAudit.served_at >= cutoff)
        )
    ) or 0

    low_confidence_7d: int = (
        await db.scalar(
            select(func.count())
            .select_from(AiLowConfidenceLog)
            .where(AiLowConfidenceLog.logged_at >= cutoff)
        )
    ) or 0

    churn_raw = await label_churn_review(db, recommendation_type="educational_label")
    churn = _churn_to_summary(churn_raw)

    # Activation state via the registry (compliance service owns this)
    activated = await is_engine_version_activated(db, cfg.model_version)

    # Rolling avg LLM response latency from the gateway's Redis counters. Read is
    # non-fatal: a Redis failure returns instrumented=False, never 500s the page.
    latency = LatencyInfo(**await read_latency_window(7))
    eval_score = GroundednessInfo(**await read_groundedness_window(7))

    return AiDashboardResponse(
        model_version=cfg.model_version,
        activated=activated,
        budget=budget,
        served_7d=served_7d,
        low_confidence_7d=low_confidence_7d,
        label_churn=churn,
        avg_latency_ms=latency,
        eval_score=eval_score,
    )


# ---------------------------------------------------------------------------
# GET /admin/ai/versions  — Score Versioning
# ---------------------------------------------------------------------------


@router.get("/ai/versions", response_model=AiVersionsResponse)
async def get_ai_versions(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
) -> AiVersionsResponse:
    """Return the rating_engine_changelog version registry (read-only).

    ``backtest`` = the §8 backtest pass-gate outcome recorded per version at
    activation (``EngineVersionRow.backtest`` = ``{"passed": bool}``); the top-level
    status reports how many shown versions carry it.  ``drift`` reuses the existing
    label-churn review for the active educational-label scoring version (real,
    existing signal — not the per-version drift JSONB column, which is reserved for
    a future drift engine).
    """
    raw_versions = await list_engine_versions(db, limit=limit)
    versions = [EngineVersionRow(**row) for row in raw_versions]

    backtest = BacktestStatus(
        versions_with_backtest=sum(1 for v in versions if v.backtest is not None)
    )

    # Drift = label churn for the active educational-label scoring version (the
    # existing safety signal). A real reading is "instrumented"; insufficient data
    # leaves it not-instrumented.
    churn_raw = await label_churn_review(db, recommendation_type="educational_label")
    drift = DriftStatus(
        instrumented=churn_raw.get("decision", "insufficient_data") != "insufficient_data",
        decision=churn_raw.get("decision", "insufficient_data"),
        churn=float(churn_raw.get("churn", 0.0)),
        requires_human_review=bool(churn_raw.get("requires_human_review", False)),
    )

    return AiVersionsResponse(versions=versions, backtest=backtest, drift=drift)


# ---------------------------------------------------------------------------
# GET /admin/ai/prompts  — Prompt & RAG
# ---------------------------------------------------------------------------


@router.get("/ai/prompts", response_model=AiPromptsResponse)
async def get_ai_prompts(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=20, ge=1, le=100),
) -> AiPromptsResponse:
    """Return prompt version metadata (no DB registry — derived from audit trail).

    Prompts are passed in by the gateway caller at request time; there is no
    server-side prompt DB registry.  ``prompt_versions_seen`` are distinct
    ``prompt_version`` values observed in ``compliance.ai_recommendation_audit``.
    """
    versions_seen = await list_distinct_prompt_versions(db, limit=limit)
    return AiPromptsResponse(prompt_versions_seen=versions_seen)


# ---------------------------------------------------------------------------
# GET /admin/ai/eval  — Quality / Eval
# ---------------------------------------------------------------------------


@router.get("/ai/eval", response_model=AiEvalResponse)
async def get_ai_eval(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AiEvalResponse:
    """Return data quality issues + groundedness eval status.

    Data quality issues are sourced from ``mf.data_quality_issues`` (the same
    table read by GET /admin/quality).  Groundedness is the sampled LLM-judge
    score from the gateway's Redis counters (instrumented once samples exist).
    """
    from dhanradar.models.mf import MfDataQualityIssue

    now = datetime.now(UTC)
    dq_rows = (
        await db.scalars(
            select(MfDataQualityIssue)
            .where(MfDataQualityIssue.status.in_(["warning", "critical"]))
            .order_by(MfDataQualityIssue.evaluated_at.desc())
        )
    ).all()

    _LABELS: dict[str, dict[str, str]] = {
        "missing_nav": {"label": "Missing NAV (schemes, last 2 days)", "unit": "schemes"},
        "holdings_coverage": {"label": "Holdings coverage (% top-100)", "unit": "%"},
        "duplicate_scheme_codes": {"label": "Duplicate scheme codes", "unit": "count"},
        "nav_out_of_range": {"label": "NAV out of range (NAV ≤ 0)", "unit": "count"},
        "expense_ratio_out_of_range": {"label": "Expense ratio out of range (>10%)", "unit": "count"},
        "holdings_weight_deviation": {"label": "Holdings weight sum deviation (>5%)", "unit": "count"},
        "aum_data_age": {"label": "AUM data age", "unit": "months"},
        "scheme_master_age": {"label": "Scheme master age", "unit": "days"},
    }

    quality_issues: list[QualityIssueRow] = []
    for r in dq_rows:
        meta = _LABELS.get(r.metric_key, {"label": r.metric_key, "unit": ""})
        ack_until_str: str | None = None
        if r.acknowledged_until is not None:
            ack_dt = (
                r.acknowledged_until.replace(tzinfo=UTC)
                if r.acknowledged_until.tzinfo is None
                else r.acknowledged_until
            )
            if ack_dt > now:
                ack_until_str = r.acknowledged_until.isoformat()

        quality_issues.append(
            QualityIssueRow(
                metric_key=r.metric_key,
                label=meta["label"],
                current_value=float(r.current_value) if r.current_value is not None else None,
                threshold=float(r.threshold) if r.threshold is not None else None,
                unit=meta["unit"],
                status=r.status,
                acknowledged_until=ack_until_str,
            )
        )

    groundedness = GroundednessInfo(**await read_groundedness_window(7))
    return AiEvalResponse(quality_issues=quality_issues, groundedness=groundedness)


# ---------------------------------------------------------------------------
# GET /admin/ai/safety  — Safety Monitor
# ---------------------------------------------------------------------------


@router.get("/ai/safety", response_model=AiSafetyResponse)
async def get_ai_safety(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=7, ge=1, le=90),
) -> AiSafetyResponse:
    """Return the safety monitoring snapshot.

    Sourced from ``compliance.ai_recommendation_audit`` and
    ``compliance.ai_low_confidence_log``.  ``advice_boundary_breaches`` is now the
    real per-day count of advisory-screen rejections from the gateway's Redis
    counter (a breach = the model emitted a banned verb and the gate HELD; a 0 is
    a meaningful clean reading).  Groundedness is not a column in the audit table
    (instrumented:false).
    """
    summary = await safety_monitor_summary(db, days=days)

    churn_educational_raw = await label_churn_review(db, recommendation_type="educational_label")
    churn_mood_raw = await label_churn_review(db, recommendation_type="mood_regime")

    recent_audit = [AuditRowSummary(**row) for row in summary["recent_audit_rows"]]
    recent_lc = [LowConfidenceRowSummary(**row) for row in summary["recent_low_confidence"]]

    breaches = await read_advisory_breaches(days)
    advice_boundary_breaches = AdviceBoundaryBreachesInfo(
        value=breaches["value"],
        window_days=breaches["window_days"],
        instrumented=breaches["instrumented"],
        note=(
            "Count of AI responses rejected by the runtime advisory screen (the SEBI "
            "boundary held — rejected output is never served). A 0 means no breaches "
            "in the window."
            if breaches["instrumented"]
            else "Breach counter unavailable (Redis read failed) — value is not a "
            "measured reading."
        ),
    )

    groundedness = GroundednessInfo(**await read_groundedness_window(summary["days"]))

    return AiSafetyResponse(
        days=summary["days"],
        served_by_type=summary["served_by_type"],
        by_confidence_band=summary["by_confidence_band"],
        low_confidence_count=summary["low_confidence_count"],
        recent_audit_rows=recent_audit,
        recent_low_confidence=recent_lc,
        label_churn_educational=_churn_to_summary(churn_educational_raw),
        label_churn_mood=_churn_to_summary(churn_mood_raw),
        advice_boundary_breaches=advice_boundary_breaches,
        groundedness=groundedness,
    )


# ---------------------------------------------------------------------------
# GET /admin/ai/feedback  — Feedback Review
# ---------------------------------------------------------------------------


@router.get("/ai/feedback", response_model=AiFeedbackResponse)
async def get_ai_feedback(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=90),
) -> AiFeedbackResponse:
    """Return aggregate user feedback stats for the AI Ops console.

    Reads from ``compliance.ai_output_feedback`` (migration 0049). Returns the
    count of total / helpful ratings plus the 20 most-recent feedback rows
    within the requested window (default: last 30 days).
    """
    data = await feedback_summary(db, days=days)
    return AiFeedbackResponse(**data)


# ---------------------------------------------------------------------------
# GET /admin/ai/cost  — Cost & Usage
# ---------------------------------------------------------------------------


@router.get("/ai/cost", response_model=AiCostResponse)
async def get_ai_cost(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> AiCostResponse:
    """Return the AI budget governor spend snapshot.

    Budget counters are read from Redis (``ai:budget:free:today`` /
    ``ai:budget:premium:today``).  Per-model spend and latency are now sourced
    from the gateway's rolling Redis counters (instrumented once the gateway has
    recorded billed calls).
    """
    budget = await _read_budget_snapshot()
    latency = LatencyInfo(**await read_latency_window(7))
    per_model = PerModelSpend(**await read_spend_window(7))
    return AiCostResponse(budget=budget, latency=latency, per_model=per_model)


# ---------------------------------------------------------------------------
# Phase 5 mutations — Prompt Template Registry
# ---------------------------------------------------------------------------
#
# NOTE: the prompt_templates registry is NOT yet consumed by the AI gateway at
# request time.  The gateway still accepts prompts from callers.  These endpoints
# are the admin CRUD surface only.  Wiring the gateway to consume active templates
# is a future Phase 6 step.


@router.post("/ai/prompts", response_model=PromptTemplateRow, status_code=201)
async def create_prompt_template(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: PromptTemplateCreateRequest,
) -> PromptTemplateRow:
    """Create a new (INACTIVE) prompt template version.

    Version is auto-incremented per template_key: max(existing) + 1, or 1 if none.
    The new row is always created as is_active=False — use the activate endpoint to
    promote a version to active.

    Audit: records action=create_prompt_version to audit.admin_actions.
    """
    from dhanradar.audit.service import record_admin_action
    from dhanradar.models.ai_admin import PromptTemplate

    # Compute next version number for this key (max + 1, or 1 if none exist).
    existing_max = await db.scalar(
        select(func.max(PromptTemplate.version)).where(
            PromptTemplate.template_key == body.template_key
        )
    )
    next_version: int = (existing_max or 0) + 1

    row = PromptTemplate(
        template_key=body.template_key,
        version=next_version,
        body=body.body,
        notes=body.notes,
        is_active=False,
        created_by=admin.user_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    target_id = f"{body.template_key}:{next_version}"
    await record_admin_action(
        admin_id=admin.user_id,
        action="create_prompt_version",
        target_type="prompt_template",
        target_id=target_id,
        result="created",
    )

    return PromptTemplateRow(
        id=row.id,
        template_key=row.template_key,
        version=row.version,
        body=row.body,
        notes=row.notes,
        is_active=row.is_active,
        created_by=row.created_by,
        created_at=row.created_at,
    )


@router.post(
    "/ai/prompts/{template_key}/{version}/activate",
    response_model=PromptTemplateRow,
)
async def activate_prompt_template(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    template_key: str,
    version: int,
) -> PromptTemplateRow:
    """Activate a prompt template version (single active per key).

    In one transaction:
      1. Set is_active=False for ALL existing rows of this template_key.
      2. Set is_active=True for the target (template_key, version).

    Returns 404 if the target (template_key, version) does not exist.
    Reversible: activating a different version later deactivates this one.

    Audit: records action=activate_prompt_version to audit.admin_actions.
    """
    from sqlalchemy import update

    from dhanradar.audit.service import record_admin_action
    from dhanradar.models.ai_admin import PromptTemplate

    # 1. Find the target row first so we can 404 before any mutation.
    target = await db.scalar(
        select(PromptTemplate).where(
            PromptTemplate.template_key == template_key,
            PromptTemplate.version == version,
        )
    )
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="prompt_template_not_found",
        )

    # 2. Deactivate all versions of this key, then activate the target.
    await db.execute(
        update(PromptTemplate)
        .where(PromptTemplate.template_key == template_key)
        .values(is_active=False)
    )
    await db.execute(
        update(PromptTemplate)
        .where(
            PromptTemplate.template_key == template_key,
            PromptTemplate.version == version,
        )
        .values(is_active=True)
    )
    await db.commit()
    await db.refresh(target)

    target_id = f"{template_key}:{version}"
    await record_admin_action(
        admin_id=admin.user_id,
        action="activate_prompt_version",
        target_type="prompt_template",
        target_id=target_id,
        result="activated",
    )

    return PromptTemplateRow(
        id=target.id,
        template_key=target.template_key,
        version=target.version,
        body=target.body,
        notes=target.notes,
        is_active=target.is_active,
        created_by=target.created_by,
        created_at=target.created_at,
    )


# ---------------------------------------------------------------------------
# Phase 5 mutations — Budget Cap Override
# ---------------------------------------------------------------------------


@router.post("/ai/cost/caps", response_model=BudgetCapsResponse)
async def set_budget_caps(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: BudgetCapsSetRequest,
) -> BudgetCapsResponse:
    """Set (or reset) the live AI budget caps without a redeploy.

    Normal mode (reset=False):
      - Validates premium_soft_usd < premium_hard_usd (else 422).
      - INSERTs an ai_budget_caps history row for audit.
      - Pushes the three Redis override keys (no expiry — caps persist until
        explicitly changed or reset).
      - Returns the now-effective caps.

    Reset mode (reset=True):
      - DELETEs the three Redis override keys so budget_guard reverts to the
        hardcoded _CAPS defaults.
      - Still INSERTs a history row noting the reset (body values are recorded
        as the administrator's intended caps at the time of reset, for audit trail).
      - Returns the hardcoded default caps (not the body values).

    Audit: records action=set_budget_caps to audit.admin_actions.
    """
    from dhanradar.audit.service import record_admin_action
    from dhanradar.models.ai_admin import AiBudgetCap

    if not body.reset and body.premium_soft_usd >= body.premium_hard_usd:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="premium_soft_usd_must_be_less_than_premium_hard_usd",
        )

    # Write audit history row regardless of reset flag.
    from decimal import Decimal

    cap_row = AiBudgetCap(
        free_cap=body.free_cap,
        premium_soft_usd=Decimal(str(body.premium_soft_usd)),
        premium_hard_usd=Decimal(str(body.premium_hard_usd)),
        updated_by=admin.user_id,
    )
    db.add(cap_row)
    await db.commit()

    redis = get_redis()

    if body.reset:
        # Revert to hardcoded defaults by deleting override keys.
        await redis.delete(
            _CAP_OVERRIDE_KEYS["free"],
            _CAP_OVERRIDE_KEYS["premium_soft"],
            _CAP_OVERRIDE_KEYS["premium_hard"],
        )
        from dhanradar.budget import _CAPS

        effective_free = int(_CAPS["free"])
        effective_soft = float(_CAPS["premium_soft"])
        effective_hard = float(_CAPS["premium_hard"])
        result_note = "reset"
    else:
        # Push override values; no expiry — caps persist until changed or reset.
        await redis.set(_CAP_OVERRIDE_KEYS["free"], str(body.free_cap))
        await redis.set(_CAP_OVERRIDE_KEYS["premium_soft"], str(body.premium_soft_usd))
        await redis.set(_CAP_OVERRIDE_KEYS["premium_hard"], str(body.premium_hard_usd))

        effective_free = body.free_cap
        effective_soft = body.premium_soft_usd
        effective_hard = body.premium_hard_usd
        result_note = "updated"

    await record_admin_action(
        admin_id=admin.user_id,
        action="set_budget_caps",
        target_type="ai_budget",
        target_id="global",
        result=result_note,
    )

    return BudgetCapsResponse(
        free_cap=effective_free,
        premium_soft_usd=effective_soft,
        premium_hard_usd=effective_hard,
        reset=body.reset,
    )
