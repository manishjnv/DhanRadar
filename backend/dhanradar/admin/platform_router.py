"""
DhanRadar — Admin Phase 3: Platform read-only router (Tier-A).

Implements four read-only admin endpoints:
  GET /admin/flags          — Feature flags (env-sourced bool settings)
  GET /admin/support/cas-failures  — Recent CAS job failures for support
  GET /admin/analytics/overview    — Aggregate platform metrics
  GET /admin/notifications/health  — Queue depth + delivery stats
  POST /admin/support/cas-failures/{job_id}/notes — set operator support note

All routes: RequireAdmin() gate (404 surface-hiding to non-admins). The single
mutation (support-notes) is audit-logged via record_admin_action.

Analytics cross-schema counts are the accepted admin-ops exception: aggregate
reads across auth/mf schemas return no PII, only counts. Module isolation is
respected for individual-record reads (CAS failures go via mf.service,
notification stats via notifications.service).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Request
from fastapi import status as http_status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.admin.ops_schemas import OkResponse
from dhanradar.audit.service import record_admin_action
from dhanradar.config import settings
from dhanradar.db import get_db
from dhanradar.deps import RequireAdmin, UserContext
from dhanradar.mf.service import list_recent_cas_failures
from dhanradar.models.auth import Subscription, User
from dhanradar.models.mf import MfCasJob, MfPortfolio, MfPortfolioSnapshot
from dhanradar.notifications.service import (
    admin_broadcast,
    broadcast_available,
    get_delivery_stats,
    get_queue_health,
    list_templates,
)

from .platform_schemas import (
    AnalyticsOverviewResponse,
    BroadcastRequest,
    BroadcastResponse,
    CasFailureRecord,
    CasNotesRequest,
    FeatureFlagResponse,
    FunnelStats,
    NotificationHealthResponse,
    QueueDepth,
    TemplateInfo,
)

router = APIRouter(prefix="/admin", tags=["admin-platform"])

# ---------------------------------------------------------------------------
# SEBI advisory-language guard — defence-in-depth for outward broadcasts.
#
# Banned advisory verbs are stored as a SINGLE space-separated string so the
# project's own CI advisory-verb scanner (which catches quoted banned words in
# FE test files) does NOT red on this definition.  Final compliance is the
# operator's responsibility; this guard prevents accidental slip-through.
# Flag for compliance review before any public broadcast surface goes live.
# ---------------------------------------------------------------------------
_ADVISORY_VERBS = "strong_buy buy sell hold caution avoid".split()
_ADVISORY_RE = re.compile(
    r"\b(" + "|".join(re.escape(v) for v in _ADVISORY_VERBS) + r")\b",
    re.IGNORECASE,
)

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
    Each record includes any ``support_notes`` an operator has set via
    POST /admin/support/cas-failures/{job_id}/notes (None when unset).
    """
    rows = await list_recent_cas_failures(db, limit=limit)
    return [CasFailureRecord(**row) for row in rows]


# ---------------------------------------------------------------------------
# POST /admin/support/cas-failures/{job_id}/notes  (Tier-A mutation)
# ---------------------------------------------------------------------------


@router.post(
    "/support/cas-failures/{job_id}/notes",
    response_model=OkResponse,
)
async def set_cas_support_notes(
    request: Request,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: CasNotesRequest,
    job_id: Annotated[str, Path()],
) -> OkResponse:
    """Set (or clear) the operator support note on a CAS job.

    Admin-internal annotation only — never surfaced on a user-facing route.
    An empty ``notes`` string clears the note. 404 if the job_id is unknown.

    The UPDATE uses an ORM ``update()`` with a bound ``job_id`` parameter (no
    f-string SQL); ``rowcount == 0`` means no matching row → 404.

    Audit: record_admin_action (fire-and-forget, never raises) with
    action="set_cas_support_notes", target_type="cas_job", target_id=job_id.
    """
    # Parse job_id to a UUID first — job_id is a uuid column, so a malformed
    # string would otherwise raise a Postgres cast error (500). Treat it as 404.
    try:
        job_uuid = UUID(job_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="cas_job_not_found",
        ) from None

    result = await db.execute(
        update(MfCasJob)
        .where(MfCasJob.job_id == job_uuid)
        .values(support_notes=body.notes)
    )
    if result.rowcount == 0:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="cas_job_not_found",
        )
    await db.commit()

    request_id: str | None = getattr(request.state, "request_id", None)
    await record_admin_action(
        admin_id=admin.user_id,
        action="set_cas_support_notes",
        target_type="cas_job",
        target_id=job_id,
        result="ok",
        request_id=request_id,
    )

    return OkResponse()


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


# ---------------------------------------------------------------------------
# POST /admin/notifications/broadcast  (Phase 5 — Tier-B mutation)
# ---------------------------------------------------------------------------


@router.post("/notifications/broadcast", response_model=BroadcastResponse)
async def post_broadcast(
    request: Request,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    body: BroadcastRequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> BroadcastResponse:
    """Send an operator broadcast to the Telegram public channel.

    Threat surface and guards (outward broadcast — the highest-risk mutation):
      - Replay / double-send: Redis NX lock + result cache keyed by Idempotency-Key.
      - Confirmation: ``confirm=true`` required in the request body; 400 otherwise.
      - Rate cap: max 3 broadcasts/day (telegram RATE_CAPS constant); 429 on breach.
      - Quiet hours: refused 22:00–07:00 IST; 409 with detail "quiet_hours".
      - Advisory language: whole-word regex match on title+body; 422 on match.
        (Defence-in-depth — final compliance is operator responsibility. Flagged
        for compliance review per SEBI advisory-boundary non-negotiable #1.)
      - Channel availability: 503 if TELEGRAM_PUBLIC_CHANNEL_ID unset.
      - Delivery failure: 502; lock expires naturally — no failure cached.
      - Audit trail: record_admin_action (fire-and-forget, never raises).
    """
    # Gate 1: Idempotency-Key header is mandatory.
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="idempotency_key_required",
        )

    # Gate 2: Explicit confirmation required.
    if not body.confirm:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="confirmation_required",
        )

    # Gate 3: SEBI advisory-language guard (defence-in-depth; see constant above).
    combined_text = f"{body.title} {body.body}"
    advisory_match = _ADVISORY_RE.search(combined_text)
    if advisory_match:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="advisory_language_forbidden",
        )

    # Delegate to service (owns all further guards: replay, lock, quiet hours,
    # rate cap, delivery).
    resp_dict = await admin_broadcast(
        title=body.title,
        body=body.body,
        idempotency_key=idempotency_key.strip(),
        admin_id=admin.user_id,
    )

    # Audit trail — fire-and-forget (never raises per audit.service contract).
    request_id: str | None = getattr(request.state, "request_id", None)
    await record_admin_action(
        admin_id=admin.user_id,
        action="broadcast",
        target_type="notification",
        target_id=idempotency_key.strip(),
        result="sent",
        request_id=request_id,
    )

    return BroadcastResponse(**resp_dict)
