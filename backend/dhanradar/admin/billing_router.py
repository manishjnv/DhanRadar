"""
DhanRadar — Admin Billing router (Phase 2).

Read-only billing-overview endpoints for the Admin Console.
ALL routes are gated by RequireAdmin() (404 to non-admins — surface-hiding).
NO mutations: no refunds, no plan changes, no subscription cancellations.

Load-bearing classification: LOAD-BEARING path (extends the admin surface,
reads billing + audit schemas). Every change requires Opus line-by-line diff
review before merge.

Module isolation (#7):
  - MRR / subscription reads delegated to billing.service
  - Payment event reads delegated to audit.service
  - Routers orchestrate only — no direct cross-schema ORM queries here

ABSENT signals / best-effort stubs:
  - webhook-health: derived from audit.payment_events (no structured
    webhook-event table); note field explains derivation to consumer
  - churn_30d / renewals_30d: best-effort (see billing.service comments)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.audit.service import list_payment_events
from dhanradar.billing.service import (
    compute_billing_overview,
    list_subscriptions,
    subscription_metrics,
)
from dhanradar.db import get_db
from dhanradar.deps import RequireAdmin, UserContext

from .billing_schemas import (
    BillingOverviewResponse,
    PaymentEventItem,
    SubscriptionListItem,
    SubscriptionMetricsResponse,
    WebhookHealthResponse,
)

router = APIRouter(prefix="/admin", tags=["admin-billing"])

# Payment statuses treated as "success" for webhook-health purposes
_SUCCESS_STATUSES = frozenset({"captured", "authorized"})
_FAILED_STATUS = "failed"


# ---------------------------------------------------------------------------
# GET /admin/billing/overview
# ---------------------------------------------------------------------------


@router.get("/billing/overview", response_model=BillingOverviewResponse)
async def get_billing_overview(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BillingOverviewResponse:
    """MRR, ARPU, active subscriptions, past-due count, and trial count."""
    data = await compute_billing_overview(db)
    return BillingOverviewResponse(**data)


# ---------------------------------------------------------------------------
# GET /admin/billing/subscriptions
# ---------------------------------------------------------------------------


@router.get("/billing/subscriptions", response_model=list[SubscriptionListItem])
async def get_subscriptions(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[str | None, Query(description="Filter by raw Razorpay status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SubscriptionListItem]:
    """Paginated subscription list with user email, plan, and price."""
    rows = await list_subscriptions(db, status=status, limit=limit, offset=offset)
    return [SubscriptionListItem(**row) for row in rows]


# ---------------------------------------------------------------------------
# GET /admin/billing/payments
# ---------------------------------------------------------------------------


@router.get("/billing/payments", response_model=list[PaymentEventItem])
async def get_payments(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PaymentEventItem]:
    """Paginated payment events from audit.payment_events (all users)."""
    rows = await list_payment_events(db, user_id=None, limit=limit, offset=offset)
    return [PaymentEventItem(**row) for row in rows]


# ---------------------------------------------------------------------------
# GET /admin/billing/subscription-metrics
# ---------------------------------------------------------------------------


@router.get("/billing/subscription-metrics", response_model=SubscriptionMetricsResponse)
async def get_subscription_metrics(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionMetricsResponse:
    """Premium count, trials, 30-day renewals and churn (best-effort)."""
    data = await subscription_metrics(db)
    return SubscriptionMetricsResponse(**data)


# ---------------------------------------------------------------------------
# GET /admin/billing/webhook-health
# ---------------------------------------------------------------------------


@router.get("/billing/webhook-health", response_model=WebhookHealthResponse)
async def get_webhook_health(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WebhookHealthResponse:
    """Best-effort webhook health derived from audit.payment_events (last 24h).

    No structured webhook-event table exists. This endpoint counts recent payment
    events and classifies them by status. The `note` field in the response
    documents the derivation.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=24)

    # Fetch last 24h payment events (up to 500 rows — enough for daily volume)
    rows = await list_payment_events(db, user_id=None, limit=500, offset=0)

    recent = [r for r in rows if r["ts"] is not None and r["ts"] >= cutoff]
    recent_count = len(recent)
    success_count = sum(1 for r in recent if r["status"] in _SUCCESS_STATUSES)
    failed_count = sum(1 for r in recent if r["status"] == _FAILED_STATUS)

    last_event_at: datetime | None = None
    if recent:
        # rows are ordered ts desc, so first row is most recent
        last_event_at = recent[0]["ts"]

    return WebhookHealthResponse(
        recent_count=recent_count,
        success_count=success_count,
        failed_count=failed_count,
        last_event_at=last_event_at,
        note=(
            "TODO: no structured webhook-event table; "
            "derived from audit.payment_events (last 24h)"
        ),
    )
