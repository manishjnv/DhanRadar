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
# Billing cycles (Razorpay `total_count`) are per-plan (billing.plans.total_count),
# not a hardcoded constant (B8).


def _create_razorpay_subscription(
    razorpay_plan_id: str, total_count: int, user_id: str
) -> dict[str, Any]:
    """Synchronous Razorpay call — run via asyncio.to_thread so it neither
    blocks the event loop nor can exceed the idempotency lock TTL.

    `razorpay_plan_id` is the REAL dashboard plan id (not the internal catalog
    id, B7); `total_count` is the plan's own cycle count (not a constant, B8)."""
    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )
    return client.subscription.create(
        {
            "plan_id": razorpay_plan_id,
            "total_count": total_count,
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

    # 2b. FAIL-SAFE (B7/B8): never call Razorpay with a missing/internal plan id
    #     or an unset cycle count. Until the catalog row is seeded with the REAL
    #     dashboard plan id + total_count, checkout is refused — it is impossible
    #     to create a charge with wrong config. (Data-only fix at billing go-live.)
    if not plan.razorpay_plan_id or not plan.total_count:
        logger.error(
            "Plan %r not configured for billing (razorpay_plan_id/total_count "
            "missing) — refusing checkout (pre-billing fail-safe).",
            plan_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="plan_not_configured_for_billing",
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
            asyncio.to_thread(
                _create_razorpay_subscription,
                plan.razorpay_plan_id,
                plan.total_count,
                user_id,
            ),
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
