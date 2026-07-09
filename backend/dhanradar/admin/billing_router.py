"""
DhanRadar — Admin Billing router (Phase 2 + Phase 5).

Read-only billing-overview endpoints (Phase 2) + two gated mutations
(Phase 5):
  - POST /admin/billing/refund          — operator-initiated Razorpay refund
  - POST /admin/billing/users/{id}/plan — operator comp / tier-override

ALL routes are gated by RequireAdmin() (404 to non-admins — surface-hiding).

Load-bearing classification: LOAD-BEARING path (extends the admin surface,
reads billing + audit schemas, and Phase 5 writes to Razorpay + DB).
Every change requires Opus line-by-line diff review before merge.

Module isolation (#7):
  - MRR / subscription reads and mutations delegated to billing.service
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

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.audit.service import list_payment_events, record_admin_action
from dhanradar.billing.service import (
    admin_refund_payment,
    admin_set_user_plan,
    compute_billing_overview,
    list_subscriptions,
    subscription_metrics,
)
from dhanradar.db import get_admin_db
from dhanradar.deps import RequireAdmin, UserContext

from ._people import resolve_user_emails
from .billing_schemas import (
    BillingOverviewResponse,
    PaymentEventItem,
    PlanChangeRequest,
    PlanChangeResponse,
    RefundRequest,
    RefundResponse,
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
    db: Annotated[AsyncSession, Depends(get_admin_db)],
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
    db: Annotated[AsyncSession, Depends(get_admin_db)],
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
    db: Annotated[AsyncSession, Depends(get_admin_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PaymentEventItem]:
    """Paginated payment events from audit.payment_events (all users).

    Each row carries the payer's email (display-only enrichment) so the
    operator never has to cross-reference a raw user UUID.
    """
    rows = await list_payment_events(db, user_id=None, limit=limit, offset=offset)
    emails = await resolve_user_emails(db, {row.get("user_id") for row in rows})
    return [
        PaymentEventItem(**row, email=emails.get(str(row.get("user_id"))))
        for row in rows
    ]


# ---------------------------------------------------------------------------
# GET /admin/billing/subscription-metrics
# ---------------------------------------------------------------------------


@router.get("/billing/subscription-metrics", response_model=SubscriptionMetricsResponse)
async def get_subscription_metrics(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
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
    db: Annotated[AsyncSession, Depends(get_admin_db)],
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


# ---------------------------------------------------------------------------
# POST /admin/billing/refund  (Phase 5 — load-bearing mutation)
# ---------------------------------------------------------------------------


@router.post("/billing/refund", response_model=RefundResponse, status_code=status.HTTP_200_OK)
async def post_refund(
    request: Request,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
    body: RefundRequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> RefundResponse:
    """Operator-initiated Razorpay refund.

    Requires a non-empty ``Idempotency-Key`` request header.  The key is
    bound to the payment_id + amount_inr: a replay with the same key but a
    different amount is rejected with 409 idempotency_key_conflict.

    The Razorpay call runs in a thread with a hard timeout; on timeout or
    gateway error the in-flight lock is NOT released (prevents duplicate
    refunds on immediate retry).  Returns 502 on gateway failure.

    Audit trail: two fire-and-forget writes on success —
      record_payment_event (end-user's payment)
      record_admin_action  (operator attribution)
    """
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="idempotency_key_required",
        )

    result = await admin_refund_payment(
        payment_id=body.razorpay_payment_id,
        amount_inr=body.amount_inr,
        reason=body.reason,
        idempotency_key=idempotency_key,
        admin_id=admin.user_id,
        db=db,
    )

    # Fire-and-forget admin audit — failure MUST NOT break the handler.
    await record_admin_action(
        admin_id=admin.user_id,
        action="refund_payment",
        target_type="payment",
        target_id=body.razorpay_payment_id,
        result="refunded",
        request_id=getattr(request.state, "request_id", None),
    )

    return RefundResponse(**result)


# ---------------------------------------------------------------------------
# POST /admin/billing/users/{user_id}/plan  (Phase 5 — load-bearing mutation)
# ---------------------------------------------------------------------------


@router.post(
    "/billing/users/{user_id}/plan",
    response_model=PlanChangeResponse,
    status_code=status.HTTP_200_OK,
)
async def post_user_plan(
    request: Request,
    user_id: str,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
    body: PlanChangeRequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,  # accepted, ignored
) -> PlanChangeResponse:
    """Operator comp / plan-change (NO Razorpay charge).

    Sets the user's tier and optionally a time-window grant (pro_access_until
    + pro_access_reason).  Naturally idempotent — setting the same tier twice
    is a safe DB no-op.  An ``Idempotency-Key`` header is accepted but ignored.

    Returns 404 when user_id is not a valid UUID or does not resolve to a user.
    Returns 422 when tier is not a valid UserTierEnum value.
    """
    result = await admin_set_user_plan(
        user_id=user_id,
        tier=body.tier,
        grant_until=body.grant_until,
        reason=body.reason,
        admin_id=admin.user_id,
        db=db,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="not_found",
        )

    # Fire-and-forget admin audit — failure MUST NOT break the handler.
    await record_admin_action(
        admin_id=admin.user_id,
        action="set_user_plan",
        target_type="user",
        target_id=user_id,
        result=body.tier,
        request_id=getattr(request.state, "request_id", None),
    )

    return PlanChangeResponse(**result)
