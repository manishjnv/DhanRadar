"""
DhanRadar — Admin Phase 3: Platform read-only router (Tier-A).

Implements four read-only admin endpoints:
  GET /admin/flags          — Feature flags (env-sourced bool settings)
  GET /admin/support/cas-failures  — Recent CAS job failures for support
  GET /admin/analytics/overview    — Aggregate platform metrics
  GET /admin/notifications/health  — Queue depth + delivery stats

All routes: RequireAdmin() gate (404 surface-hiding to non-admins).
NO mutations — this router is strictly read-only.

Analytics cross-schema counts are the accepted admin-ops exception: aggregate
reads across auth/mf schemas return no PII, only counts. Module isolation is
respected for individual-record reads (CAS failures go via mf.service,
notification stats via notifications.service).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.config import settings
from dhanradar.db import get_db
from dhanradar.deps import RequireAdmin, UserContext
from dhanradar.mf.service import list_recent_cas_failures
from dhanradar.models.auth import Subscription, User
from dhanradar.models.mf import MfCasJob, MfPortfolio, MfPortfolioSnapshot
from dhanradar.notifications.service import (
    broadcast_available,
    get_delivery_stats,
    get_queue_health,
    list_templates,
)

from .platform_schemas import (
    AnalyticsOverviewResponse,
    CasFailureRecord,
    FeatureFlagResponse,
    FunnelStats,
    NotificationHealthResponse,
    QueueDepth,
    TemplateInfo,
)

router = APIRouter(prefix="/admin", tags=["admin-platform"])

# ---------------------------------------------------------------------------
# GET /admin/flags
# ---------------------------------------------------------------------------

_FLAG_DESCRIPTIONS: dict[str, str] = {
    "AUDIT_ARCHIVE_ENABLED": (
        "Archive AI recommendation audit records to cold storage"
    ),
    "COOKIE_SECURE": (
        "Enforce Secure flag on session cookies (disable only in local dev)"
    ),
    "DPDP_CONSENT_ENFORCED": (
        "Enforce DPDP consent check on data-processing routes"
    ),
}


@router.get("/flags", response_model=list[FeatureFlagResponse])
async def list_feature_flags(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> list[FeatureFlagResponse]:
    """Return the three operator-visible boolean settings.

    All flags are env-sourced and read-only — no runtime toggle is available.
    ``mutable`` is always False; the operator must restart the service to change
    a flag value.
    """
    flag_values: dict[str, bool] = {
        "AUDIT_ARCHIVE_ENABLED": settings.AUDIT_ARCHIVE_ENABLED,
        "COOKIE_SECURE": settings.COOKIE_SECURE,
        "DPDP_CONSENT_ENFORCED": settings.DPDP_CONSENT_ENFORCED,
    }
    return [
        FeatureFlagResponse(
            key=key,
            value=value,
            description=_FLAG_DESCRIPTIONS[key],
            source="env",
            mutable=False,
        )
        for key, value in flag_values.items()
    ]


# ---------------------------------------------------------------------------
# GET /admin/support/cas-failures
# ---------------------------------------------------------------------------


@router.get("/support/cas-failures", response_model=list[CasFailureRecord])
async def get_cas_failures(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[CasFailureRecord]:
    """Return the most recent CAS job failures for support triage.

    Results come from mf.service.list_recent_cas_failures (module isolation).
    ``support_notes`` per failure is ABSENT — no support_notes column exists.
    TODO: add support_notes when a notes column is added to mf_cas_jobs.
    """
    rows = await list_recent_cas_failures(db, limit=limit)
    return [CasFailureRecord(**row) for row in rows]


# ---------------------------------------------------------------------------
# GET /admin/analytics/overview
# ---------------------------------------------------------------------------


@router.get("/analytics/overview", response_model=AnalyticsOverviewResponse)
async def get_analytics_overview(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AnalyticsOverviewResponse:
    """Return aggregate platform metrics.

    Cross-schema aggregate queries are the accepted admin analytics exception
    (admin-only, no PII, counts only). All queries use SQLAlchemy ORM or
    parameterised text() — no f-string SQL.
    """
    now_utc = datetime.now(UTC)
    cutoff_30d = now_utc - timedelta(days=30)

    # Signups
    signups_total = int(
        (await db.scalar(select(func.count()).select_from(User))) or 0
    )
    signups_30d = int(
        (await db.scalar(
            select(func.count()).select_from(User).where(User.created_at >= cutoff_30d)
        )) or 0
    )

    # CAS uploads
    cas_uploads_total = int(
        (await db.scalar(select(func.count()).select_from(MfCasJob))) or 0
    )
    cas_uploads_30d = int(
        (await db.scalar(
            select(func.count()).select_from(MfCasJob).where(
                MfCasJob.created_at >= cutoff_30d
            )
        )) or 0
    )

    # Portfolios
    portfolios_created = int(
        (await db.scalar(select(func.count()).select_from(MfPortfolio))) or 0
    )

    # Reports generated (one snapshot row = one report generated)
    reports_generated = int(
        (await db.scalar(select(func.count()).select_from(MfPortfolioSnapshot))) or 0
    )

    # Premium conversions — subscriptions where plan is not 'free' (Razorpay plan field)
    # auth.subscriptions.plan carries the raw plan code; non-free = any paid tier.
    premium_conversions = int(
        (await db.scalar(
            select(func.count()).select_from(Subscription).where(
                Subscription.plan != "free"
            )
        )) or 0
    )

    funnel = FunnelStats(
        cas_uploaded=cas_uploads_total,
        portfolio_created=portfolios_created,
        report_generated=reports_generated,
    )

    conversion_rate_pct = (
        round(reports_generated / cas_uploads_total * 100, 2)
        if cas_uploads_total > 0
        else 0.0
    )

    return AnalyticsOverviewResponse(
        signups_total=signups_total,
        signups_30d=signups_30d,
        cas_uploads_total=cas_uploads_total,
        cas_uploads_30d=cas_uploads_30d,
        portfolios_created=portfolios_created,
        reports_generated=reports_generated,
        premium_conversions=premium_conversions,
        funnel=funnel,
        conversion_rate_pct=conversion_rate_pct,
    )


# ---------------------------------------------------------------------------
# GET /admin/notifications/health
# ---------------------------------------------------------------------------


@router.get("/notifications/health", response_model=NotificationHealthResponse)
async def get_notifications_health(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationHealthResponse:
    """Return notification subsystem health: queue depth, delivery stats, templates.

    Queue depth reads Redis LLEN — best-effort (0 on Redis error).
    Delivery stats query notify.notification_log.
    Template list comes from the in-code _RENDERERS registry (no DB query).
    broadcast_available reflects whether TELEGRAM_PUBLIC_CHANNEL_ID is set.
    """
    queue = await get_queue_health()
    stats = await get_delivery_stats(db)
    templates = list_templates()
    can_broadcast = broadcast_available()

    return NotificationHealthResponse(
        queue_depth=QueueDepth(
            telegram=queue.get("telegram", 0),
            email=queue.get("email", 0),
        ),
        sent=stats["sent"],
        failed=stats["failed"],
        rate_capped=stats["rate_capped"],
        deferred=stats["deferred"],
        last_sent_at=stats.get("last_sent_at"),
        templates=[TemplateInfo(id=t["id"]) for t in templates],
        broadcast_available=can_broadcast,
    )
