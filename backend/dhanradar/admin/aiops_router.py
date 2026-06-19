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

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.budget import _REDIS_KEYS, compute_budget_state
from dhanradar.compliance.service import (
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
    AiCostResponse,
    AiDashboardResponse,
    AiEvalResponse,
    AiFeedbackResponse,
    AiPromptsResponse,
    AiSafetyResponse,
    AiVersionsResponse,
    AuditRowSummary,
    BudgetSnapshot,
    EngineVersionRow,
    LabelChurnSummary,
    LowConfidenceRowSummary,
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
    """
    redis = get_redis()
    try:
        free_raw = await redis.get(_REDIS_KEYS["free"])
        premium_raw = await redis.get(_REDIS_KEYS["premium"])
    except Exception:
        # Degraded: do not mislead with "0 spend looks healthy" — flag available=False.
        return BudgetSnapshot(**compute_budget_state(None, None), available=False)
    state = compute_budget_state(free_raw, premium_raw)
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

    All absent metrics (avg_latency_ms, eval_score) return instrumented:false.
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

    return AiDashboardResponse(
        model_version=cfg.model_version,
        activated=activated,
        budget=budget,
        served_7d=served_7d,
        low_confidence_7d=low_confidence_7d,
        label_churn=churn,
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

    ``backtest`` and ``drift`` are absent from the changelog schema and always
    returned as ``instrumented:false``.  Promotion (activate) is a Phase 5 gated
    mutation — not available here.
    """
    raw_versions = await list_engine_versions(db, limit=limit)
    versions = [EngineVersionRow(**row) for row in raw_versions]
    return AiVersionsResponse(versions=versions)


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
    table read by GET /admin/quality).  Groundedness eval is not yet instrumented
    and is returned as instrumented:false.
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

    return AiEvalResponse(quality_issues=quality_issues)


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
    ``compliance.ai_low_confidence_log``.  ``advice_boundary_breaches`` is ALWAYS 0
    and instrumented:false — there is no rejection counter, so a 0 here is NOT
    confirmation that zero advisory violations occurred; this surface cannot observe
    whether the boundary held.  Groundedness is not a column in the audit table
    (instrumented:false).
    """
    summary = await safety_monitor_summary(db, days=days)

    churn_educational_raw = await label_churn_review(db, recommendation_type="educational_label")
    churn_mood_raw = await label_churn_review(db, recommendation_type="mood_regime")

    recent_audit = [AuditRowSummary(**row) for row in summary["recent_audit_rows"]]
    recent_lc = [LowConfidenceRowSummary(**row) for row in summary["recent_low_confidence"]]

    return AiSafetyResponse(
        days=summary["days"],
        served_by_type=summary["served_by_type"],
        by_confidence_band=summary["by_confidence_band"],
        low_confidence_count=summary["low_confidence_count"],
        recent_audit_rows=recent_audit,
        recent_low_confidence=recent_lc,
        label_churn_educational=_churn_to_summary(churn_educational_raw),
        label_churn_mood=_churn_to_summary(churn_mood_raw),
    )


# ---------------------------------------------------------------------------
# GET /admin/ai/feedback  — Feedback Review
# ---------------------------------------------------------------------------


@router.get("/ai/feedback", response_model=AiFeedbackResponse)
async def get_ai_feedback(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> AiFeedbackResponse:
    """Return feedback availability (no feedback table yet — placeholder).

    This endpoint exists so the AI Ops shell can render a proper 'not available'
    state rather than a 404.  A feedback table is a Phase 5+ addition.
    """
    return AiFeedbackResponse()


# ---------------------------------------------------------------------------
# GET /admin/ai/cost  — Cost & Usage
# ---------------------------------------------------------------------------


@router.get("/ai/cost", response_model=AiCostResponse)
async def get_ai_cost(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> AiCostResponse:
    """Return the AI budget governor spend snapshot.

    Budget counters are read from Redis (``ai:budget:free:today`` /
    ``ai:budget:premium:today``).  Per-model breakdown and latency are not tracked
    in the current Redis-counter implementation (instrumented:false).
    """
    budget = await _read_budget_snapshot()
    return AiCostResponse(budget=budget)
