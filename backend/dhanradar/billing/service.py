"""
DhanRadar — Billing service.

list_active_plans: read the billing.plans catalog (public).

create_checkout: create a Razorpay subscription for the AUTHENTICATED user.
Security properties:
  - user_id comes from the session (caller), never from the request body.
  - plan_id is validated against billing.plans (active only) so the amount is
    catalog-controlled, not client-controlled.
  - Idempotent: a Redis result cache keyed by (user_id, Idempotency-Key)
    returns the prior response on replay; a short-lived NX lock prevents two
    concurrent identical requests from both creating a subscription
    (double-charge guard).
  - Razorpay key SECRET is never returned (only the public key_id).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import razorpay
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.config import settings
from dhanradar.models.billing import Plan
from dhanradar.redis_client import get_redis

logger = logging.getLogger(__name__)

_RESULT_TTL = 86400           # 24 h — replay window for an Idempotency-Key
_LOCK_TTL = 60               # s — in-flight guard; MUST exceed _CALL_TIMEOUT so a
                             # slow gateway call cannot outlive the lock (else a
                             # concurrent retry could create a 2nd subscription).
_CALL_TIMEOUT = 25           # s — hard cap on the Razorpay call (< _LOCK_TTL).
# Razorpay subscription billing cycles to authorise. 12 = one year of monthly
# (Razorpay requires total_count; the real value is plan-dependent — revisit
# when the Razorpay dashboard plans are created, PRE-BILLING).
_TOTAL_COUNT = 12


def _create_razorpay_subscription(plan_id: str, user_id: str) -> dict[str, Any]:
    """Synchronous Razorpay call — run via asyncio.to_thread so it neither
    blocks the event loop nor can exceed the idempotency lock TTL."""
    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )
    return client.subscription.create(
        {
            "plan_id": plan_id,
            "total_count": _TOTAL_COUNT,
            "customer_notify": 1,
            "notes": {"user_id": user_id},
        }
    )


async def list_active_plans(db: AsyncSession) -> list[Plan]:
    res = await db.execute(
        select(Plan).where(Plan.active.is_(True)).order_by(Plan.price_inr)
    )
    return list(res.scalars().all())


async def create_checkout(
    user_id: str,
    plan_id: str,
    idempotency_key: str,
    db: AsyncSession,
) -> dict[str, Any]:
    redis = get_redis()
    result_key = f"billing:checkout:result:{user_id}:{idempotency_key}"
    lock_key = f"billing:checkout:lock:{user_id}:{idempotency_key}"

    # 1. Replay → return the prior response. The cached entry is bound to the
    #    plan_id: reusing an Idempotency-Key with a DIFFERENT plan is a client
    #    bug, not a second charge — reject it rather than return stale data.
    cached = await redis.get(result_key)
    if cached:
        record = json.loads(cached)
        if record.get("plan_id") != plan_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="idempotency_key_conflict",
            )
        return record["resp"]

    # 2. Validate the plan from the catalog (amount is catalog-controlled).
    #    Done before acquiring the lock so a bad plan never holds a lock.
    plan = await db.scalar(
        select(Plan).where(Plan.id == plan_id, Plan.active.is_(True))
    )
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="plan_not_found",
        )

    # 3. Concurrency guard — only one in-flight creation per idem key.
    acquired = await redis.set(lock_key, "1", nx=True, ex=_LOCK_TTL)
    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="checkout_in_progress",
        )

    # 4. Create the Razorpay subscription. user_id is pinned in notes from the
    #    SESSION. Run in a thread with a hard timeout < _LOCK_TTL so the call
    #    cannot block the event loop or outlive the lock (double-charge guard).
    #    (Assumes billing.plans.id == the Razorpay plan id — documented
    #    PRE-BILLING assumption; populate the catalog to match the dashboard.)
    try:
        sub = await asyncio.wait_for(
            asyncio.to_thread(_create_razorpay_subscription, plan.id, user_id),
            timeout=_CALL_TIMEOUT,
        )
    except (Exception, asyncio.TimeoutError) as exc:  # gateway error or timeout
        # Lock is intentionally NOT released here: it expires with _LOCK_TTL so
        # an immediate retry is blocked (409) rather than risking a duplicate.
        logger.error("Razorpay subscription.create failed for user=%s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="payment_gateway_unavailable",
        )

    resp: dict[str, Any] = {
        "order_id": sub.get("id"),
        "amount_inr": plan.price_inr,
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,  # public id only — never the secret
    }

    # 5. Cache the (plan-bound) result so a retry with the same key is idempotent.
    await redis.set(result_key, json.dumps({"plan_id": plan_id, "resp": resp}), ex=_RESULT_TTL)
    return resp
