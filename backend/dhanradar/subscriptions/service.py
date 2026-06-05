"""
DhanRadar — Subscriptions service.

Handles Razorpay webhook processing after signature verification:
  1. Upsert auth.subscriptions row.
  2. Recompute users.tier from active subscription state.
  3. Flush auth:tier:{user_id} Redis cache.

Tier mapping (B2 fail-safe): tier is taken ONLY from the exact
EXACT_PLAN_TIERS map (populate with the real Razorpay dashboard plan_ids
before launch). An unmapped active plan grants NO paid tier (free + error);
inactive / cancelled / expired → free. No substring guessing.

All SQL via parameterized ORM — no f-string interpolation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.auth.service import flush_tier_cache
from dhanradar.models.auth import Subscription, User, UserTierEnum

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier derivation from plan name / status
# ---------------------------------------------------------------------------

# Exact Razorpay plan_id → tier map. PRE-BILLING BLOCKER: this MUST be
# populated with the real plan_ids created in the Razorpay dashboard before
# billing goes live. The substring fallback below is a foot-gun (e.g. a plan
# id like "promo_2026" contains "pro") and must NOT be relied on in
# production — it exists only so the webhook is testable pre-billing and
# emits a loud warning whenever it is hit.
EXACT_PLAN_TIERS: dict[str, UserTierEnum] = {
    # "plan_XXXXXXXXXXXX": UserTierEnum.pro,
    # "plan_YYYYYYYYYYYY": UserTierEnum.pro_plus,
    # "plan_ZZZZZZZZZZZZ": UserTierEnum.founder_lifetime,
}

_ACTIVE_STATUSES = {"active", "authenticated"}


def _derive_tier(plan: str, status: str) -> UserTierEnum:
    """
    Derive a UserTierEnum from the Razorpay plan identifier and status.

    Active states that upgrade the tier: "active", "authenticated".
    Anything else (cancelled, completed, expired, halted) → free.

    FAIL-SAFE (B2): tier comes ONLY from the exact EXACT_PLAN_TIERS map. An
    unmapped plan_id grants NO paid tier (returns free) and logs an error — it
    never guesses. The previous substring heuristic was a privilege foot-gun
    (a plan id like "promo_2026" contains "pro").
    """
    if status.lower() not in _ACTIVE_STATUSES:
        return UserTierEnum.free

    exact = EXACT_PLAN_TIERS.get(plan)
    if exact is not None:
        return exact

    logger.error(
        "Razorpay plan_id %r not in EXACT_PLAN_TIERS — granting NO paid tier "
        "(fail-safe). Populate EXACT_PLAN_TIERS with the real dashboard "
        "plan_ids before billing go-live (B2).",
        plan,
    )
    return UserTierEnum.free


# ---------------------------------------------------------------------------
# Webhook event processor
# ---------------------------------------------------------------------------

async def handle_subscription_event(
    event_data: dict[str, Any],
    db: AsyncSession,
) -> None:
    """
    Process a verified Razorpay subscription event payload.

    Called ONLY after `razorpay.utility.verify_webhook_signature` has passed
    in the router.  Safe to parse JSON here because signature is already valid.

    Supported events: subscription.activated, subscription.updated,
    subscription.cancelled, subscription.completed, subscription.halted,
    subscription.authenticated.  Unknown events are logged and skipped.
    """
    event_type: str = event_data.get("event", "")
    payload: dict = event_data.get("payload", {})
    subscription_payload: dict = payload.get("subscription", {}).get("entity", {})

    if not subscription_payload:
        logger.warning("Razorpay webhook: missing subscription entity in payload")
        return

    rzp_sub_id: Optional[str] = subscription_payload.get("id")
    plan_id: Optional[str] = subscription_payload.get("plan_id", "")
    sub_status: str = subscription_payload.get("status", "")
    customer_id: Optional[str] = subscription_payload.get("customer_id")
    notes: dict = subscription_payload.get("notes", {})

    # We store user_id in subscription notes during checkout creation.
    # Razorpay notes is a dict; we look for "user_id" key.
    user_id_str: Optional[str] = notes.get("user_id") if isinstance(notes, dict) else None

    if not rzp_sub_id or not user_id_str:
        logger.warning(
            "Razorpay webhook: missing rzp_sub_id or user_id in notes; "
            "event=%s rzp_sub_id=%s user_id_note=%s",
            event_type, rzp_sub_id, user_id_str,
        )
        return

    try:
        user_uuid = UUID(user_id_str)
    except ValueError:
        logger.error("Razorpay webhook: invalid user_id UUID in notes: %s", user_id_str)
        return

    # Timestamps from Razorpay are Unix epoch integers.
    def _ts(val: Any) -> Optional[datetime]:
        if val is None:
            return None
        try:
            return datetime.fromtimestamp(int(val), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None

    current_start = _ts(subscription_payload.get("current_start"))
    current_end = _ts(subscription_payload.get("current_end"))
    new_tier = _derive_tier(plan_id or "", sub_status)

    # --- Upsert subscription row (parameterized ORM) ---
    # Use PostgreSQL INSERT ... ON CONFLICT DO UPDATE for atomic upsert.
    stmt = (
        pg_insert(Subscription)
        .values(
            user_id=user_uuid,
            razorpay_subscription_id=rzp_sub_id,
            plan=plan_id or "",
            status=sub_status,
            current_period_start=current_start,
            current_period_end=current_end,
        )
        .on_conflict_do_update(
            index_elements=["razorpay_subscription_id"],
            set_={
                "plan": plan_id or "",
                "status": sub_status,
                "current_period_start": current_start,
                "current_period_end": current_end,
                "updated_at": datetime.now(timezone.utc),
            },
        )
    )
    await db.execute(stmt)

    # --- Update users.tier ---
    user: Optional[User] = await db.scalar(
        select(User).where(User.id == user_uuid)
    )
    if user is None:
        logger.error("Razorpay webhook: user %s not found in DB", user_uuid)
        await db.rollback()
        return

    user.tier = new_tier
    await db.commit()

    # --- Flush Redis tier cache so next request sees new tier immediately ---
    await flush_tier_cache(str(user_uuid))

    logger.info(
        "Razorpay webhook processed: event=%s user=%s tier=%s",
        event_type, user_uuid, new_tier.value,
    )
