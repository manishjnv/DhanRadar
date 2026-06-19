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
from datetime import UTC, datetime, timedelta
from typing import Any

import razorpay
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.config import settings
from dhanradar.core.logging import hash_user_ref
from dhanradar.models.auth import Subscription, User
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
    # `is None` (not falsy): only an UNSET field is "not configured". Razorpay
    # rejects total_count < 1 itself, so we don't second-guess a real value here.
    if plan.razorpay_plan_id is None or plan.total_count is None:
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
        # A lock is held: either a genuinely concurrent request, or a prior
        # attempt that failed at the gateway (the lock is held for _LOCK_TTL so a
        # transient failure isn't immediately retried into a double-charge, B9).
        # Advertise remaining TTL so the client doesn't over-wait.
        remaining = await redis.ttl(lock_key)
        retry_after = str(remaining) if remaining > 0 else str(_LOCK_TTL)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="checkout_in_progress",
            headers={"Retry-After": retry_after},
        )

    # 4. Create the Razorpay subscription. user_id is pinned in notes from the
    #    SESSION. Run in a thread with a hard timeout < _LOCK_TTL so the call
    #    cannot block the event loop or outlive the lock (double-charge guard).
    #    Uses plan.razorpay_plan_id (the REAL dashboard id, B7) + plan.total_count
    #    (per-plan, B8) — gated by the §2b fail-safe above.
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
    except (TimeoutError, Exception) as exc:  # gateway error or timeout
        # Lock is intentionally NOT released here: it expires with _LOCK_TTL so
        # an immediate retry is blocked (409) rather than risking a duplicate.
        # user_ref hashed (never the raw user_id in logs); exc is regex-scrubbed
        # by the redaction processor for any embedded key/email/PAN.
        logger.error(
            "Razorpay subscription.create failed for user_ref=%s: %s",
            hash_user_ref(str(user_id)), exc,
        )
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


# ---------------------------------------------------------------------------
# Admin read helpers (Phase 2 — billing overview & subscription reads)
# Module isolation: billing MRR/sub logic lives here; routers orchestrate only.
# NO mutations — read-only.
# ---------------------------------------------------------------------------

# Razorpay statuses treated as "active paying"
_ACTIVE_STATUSES = frozenset({"active", "authenticated"})
# Statuses treated as "past-due / pending payment"
_PAST_DUE_STATUSES = frozenset({"halted", "pending"})
# Statuses treated as churned
_CHURN_STATUSES = frozenset({"cancelled", "expired", "completed"})


async def compute_billing_overview(db: AsyncSession) -> dict[str, Any]:
    """Compute MRR, ARPU, active subscriptions, past-due, and trials.

    MRR normalisation:
      month    → price_inr × 1
      year     → price_inr ÷ 12
      lifetime → excluded (not a recurring charge)

    Joins auth.subscriptions to billing.plans on plan_id (nullable FK).
    Rows with no plan_id joined (plan_id IS NULL) contribute 0 to MRR.
    """
    now = datetime.now(UTC)

    # --- active subscriptions & MRR via ORM join ---
    # Left-join Subscription → Plan on plan_id so rows without a catalog link are
    # still counted (they just contribute 0 to MRR).
    result = await db.execute(
        select(Subscription, Plan)
        .outerjoin(Plan, Subscription.plan_id == Plan.id)
        .where(Subscription.status.in_(_ACTIVE_STATUSES))
    )
    rows = result.all()

    active_subscriptions = len(rows)
    mrr: float = 0.0
    for sub, plan in rows:
        if plan is None:
            continue
        if plan.interval == "month":
            mrr += float(plan.price_inr)
        elif plan.interval == "year":
            mrr += float(plan.price_inr) / 12.0
        # lifetime → excluded from MRR (non-recurring)

    arpu_inr: float = mrr / active_subscriptions if active_subscriptions > 0 else 0.0

    # --- past-due count ---
    past_due = await db.scalar(
        select(func.count()).select_from(Subscription).where(
            Subscription.status.in_(_PAST_DUE_STATUSES)
        )
    ) or 0

    # --- trials: users with pro_access_until > now (time-window grant, not a sub) ---
    trials = await db.scalar(
        select(func.count()).select_from(User).where(User.pro_access_until > now)
    ) or 0

    return {
        "mrr_inr": round(mrr, 2),
        "arpu_inr": round(arpu_inr, 2),
        "active_subscriptions": active_subscriptions,
        "past_due": int(past_due),
        "trials": int(trials),
    }


async def list_subscriptions(
    db: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return subscriptions with user email and plan price.

    Left-joins auth.subscriptions → auth.users (for email) and billing.plans
    (for price_inr) on plan_id. Filters by raw Razorpay status string if given.
    """
    stmt = (
        select(Subscription, User, Plan)
        .join(User, Subscription.user_id == User.id)
        .outerjoin(Plan, Subscription.plan_id == Plan.id)
    )
    if status is not None:
        stmt = stmt.where(Subscription.status == status)
    stmt = stmt.order_by(Subscription.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(stmt)
    rows = result.all()

    out = []
    for sub, user, plan in rows:
        out.append({
            "email": user.email,
            "plan": sub.plan,
            "status": sub.status,
            "current_period_end": sub.current_period_end,
            "price_inr": plan.price_inr if plan is not None else None,
        })
    return out


async def get_user_subscription(db: AsyncSession, user_id: str) -> dict[str, Any] | None:
    """Return the most recent subscription for a user, or None."""
    from uuid import UUID

    try:
        uid = UUID(str(user_id))
    except (ValueError, TypeError):
        return None

    result = await db.execute(
        select(Subscription, Plan)
        .outerjoin(Plan, Subscription.plan_id == Plan.id)
        .where(Subscription.user_id == uid)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    row = result.first()
    if row is None:
        return None

    sub, plan = row
    return {
        "id": str(sub.id),
        "plan": sub.plan,
        "status": sub.status,
        "current_period_start": sub.current_period_start,
        "current_period_end": sub.current_period_end,
        "price_inr": plan.price_inr if plan is not None else None,
        "created_at": sub.created_at,
        "updated_at": sub.updated_at,
    }


async def subscription_metrics(db: AsyncSession) -> dict[str, Any]:
    """Return premium_count, trials, renewals_30d, churn_30d.

    renewals_30d and churn_30d are best-effort (derived from updated_at /
    current_period_start — no dedicated webhook-event table exists yet).
    """
    now = datetime.now(UTC)
    cutoff_30d = now - timedelta(days=30)

    # premium_count: active-status subs
    premium_count = await db.scalar(
        select(func.count()).select_from(Subscription).where(
            Subscription.status.in_(_ACTIVE_STATUSES)
        )
    ) or 0

    # trials: users with pro_access_until > now
    trials = await db.scalar(
        select(func.count()).select_from(User).where(User.pro_access_until > now)
    ) or 0

    # renewals_30d: subs where current_period_start is within last 30 days
    # (best-effort proxy for renewal — no dedicated billing-cycle table)
    renewals_30d = await db.scalar(
        select(func.count()).select_from(Subscription).where(
            Subscription.current_period_start >= cutoff_30d
        )
    ) or 0

    # churn_30d: subs with churn status AND updated_at in last 30 days
    # (best-effort — updated_at is the closest signal; no webhook-event table)
    churn_30d = await db.scalar(
        select(func.count()).select_from(Subscription).where(
            Subscription.status.in_(_CHURN_STATUSES),
            Subscription.updated_at >= cutoff_30d,
        )
    ) or 0

    return {
        "premium_count": int(premium_count),
        "trials": int(trials),
        "renewals_30d": int(renewals_30d),
        # churn_30d is best-effort: derived from updated_at on cancelled/expired/completed
        # subs in the last 30 days. No structured churn-event table exists yet.
        "churn_30d": int(churn_30d),
    }
