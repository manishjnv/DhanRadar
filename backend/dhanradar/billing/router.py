"""
DhanRadar — Billing API router.

Endpoints:
  GET  /api/v1/billing/plans     (public)  — active plan catalog
  POST /api/v1/billing/checkout  (authed)  — create a Razorpay subscription
  POST /api/v1/billing/webhook   (public)  — Razorpay webhook (re-mounted)

The webhook REUSES the existing, security-reviewed handler from
subscriptions.router (verify-before-parse + event dedup) — same function object,
no logic duplication. The legacy /api/v1/subscriptions/webhook path stays
mounted as an alias for one release.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.billing import schemas
from dhanradar.billing import service as billing_svc
from dhanradar.db import get_db
from dhanradar.deps import UserContext, current_user_or_anonymous
from dhanradar.ratelimit import RateLimit
from dhanradar.subscriptions.router import razorpay_webhook

router = APIRouter(prefix="/billing", tags=["billing"])

# Checkout creates a payment intent — keep it modestly rate-limited per IP.
_rl_checkout = RateLimit(max_requests=20, window_seconds=60)
# Webhook guard against Razorpay retry storms (≤15 retries/event/24h is normal,
# so 200/min is generous). Signature verification is the real gate.
_rl_webhook = RateLimit(max_requests=200, window_seconds=60)


@router.get(
    "/plans",
    response_model=list[schemas.PlanOut],
    summary="List active subscription plans (public)",
)
async def list_plans(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[schemas.PlanOut]:
    plans = await billing_svc.list_active_plans(db)
    return [schemas.PlanOut.model_validate(p) for p in plans]


@router.post(
    "/checkout",
    response_model=schemas.CheckoutResponse,
    summary="Create a Razorpay subscription for the current user (idempotent)",
)
async def checkout(
    body: schemas.CheckoutRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    _rl: Annotated[None, Depends(_rl_checkout)] = None,
) -> schemas.CheckoutResponse:
    if user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not_authenticated",
        )
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="idempotency_key_required",
        )

    resp = await billing_svc.create_checkout(
        user_id=user.user_id,
        plan_id=body.plan_id,
        idempotency_key=idempotency_key,
        db=db,
    )
    return schemas.CheckoutResponse(**resp)


# Re-mount the existing webhook handler at /billing/webhook (same function).
# Dedup is path-agnostic (keyed on the Razorpay event id, not the URL), so it is
# SAFE for the Razorpay dashboard to point at both /subscriptions/webhook and
# /billing/webhook during the transition — a duplicate event is ignored once.
router.add_api_route(
    "/webhook",
    razorpay_webhook,
    methods=["POST"],
    status_code=status.HTTP_200_OK,
    summary="Razorpay webhook (re-mounted; see subscriptions.router)",
    tags=["billing"],
    dependencies=[Depends(_rl_webhook)],
)
