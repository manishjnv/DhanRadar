"""
DhanRadar — Misc queue tasks (notification delivery, housekeeping).

Routed to the 'misc' queue via celery_app.conf.task_routes.

`drain_notifications` is the celery-misc consumer (architecture Global §5): it pops
jobs LPUSH'd onto `notifications:queue:{telegram,email}` by
`notifications.service.publish_notification`, enforces opt-in + quiet-hours + the
per-channel daily rate cap, renders the (label-only, disclosure-injected) template,
delivers via the channel transport, logs the outcome, and retries transient
failures up to the per-channel cap (Telegram 3× — stale alerts have negative value).

The architecture specifies a BLPOP consumer; we run a bounded LPOP drain on a
1-minute Celery beat tick instead (Phase-6 deviation, documented in the feature
doc) — it fits the existing Celery infra without a bespoke long-running consumer
process and is delivery-latency-tolerant for educational alerts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from dhanradar.celery_app import celery_app
from dhanradar.notifications import channels, service
from dhanradar.notifications.schemas import NotificationJob
from dhanradar.notifications.templates import UnknownTemplate, render

logger = logging.getLogger(__name__)

_DELIVER_CHANNELS = ("telegram", "email")
_MAX_PER_TICK = 100  # safety bound per channel per drain


@celery_app.task(name="dhanradar.tasks.misc.send_notification")
def send_notification(user_id: str, channel: str, template_id: str, data: dict | None = None) -> str:
    """Convenience enqueue wrapper (the documented `publish_notification` interface).
    Domains may call this or LPUSH directly; the drain delivers."""
    from dhanradar.redis_client import get_redis

    async def _go() -> str:
        redis = get_redis()
        job = await service.publish_notification(redis, user_id, channel, template_id, data or {})
        return f"enqueued: {job.channel}/{job.template_id}"

    return asyncio.run(_go())


@celery_app.task(name="dhanradar.tasks.misc.drain_notifications")
def drain_notifications() -> str:
    """Beat-scheduled drain of both channel queues. Sync task wrapping the async
    pipeline (mirrors the MF worker pattern)."""
    return asyncio.run(_drain())


async def _drain() -> str:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from dhanradar.db import engine
    from dhanradar.redis_client import get_redis

    redis = get_redis()
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    now = service.now_ist_time()
    delivered = 0

    async with SessionLocal() as db:
        for channel in _DELIVER_CHANNELS:
            qkey = service.queue_key(channel)
            pending = min(await redis.llen(qkey), _MAX_PER_TICK)
            for _ in range(pending):
                raw = await redis.rpop(qkey)  # FIFO: publish LPUSHes head, drain pops tail
                if raw is None:
                    break
                try:
                    job = NotificationJob.model_validate_json(raw)
                except Exception:  # noqa: BLE001 — malformed payload, drop it
                    logger.warning("notify drain: malformed job dropped on %s", channel)
                    continue
                # Isolate each job: one job's DB/transport error must not sink the
                # whole tick or leave the shared session dirty for the next job.
                try:
                    if await _handle_job(db, redis, job, now):
                        delivered += 1
                except Exception:  # noqa: BLE001 — log opaque, roll back, keep draining
                    logger.exception("notify drain: job handling error on %s", channel)
                    await db.rollback()
    return f"drain: delivered {delivered}"


async def _handle_job(db: Any, redis: Any, job: NotificationJob, now: Any) -> bool:
    """Process one job. Returns True iff it was actually delivered.

    DPDP cross-border note (B31, deploy gate): this seam transmits user-specific
    PII (chat_id / email) + labels to NON-Indian processors (Telegram, Resend).
    The channel opt-in below is NOT a DPDP cross-border consent grant — a
    `RequireConsent`-equivalent purpose gate (analogous to the AI gateway's B20)
    must be enforced before these channels carry production traffic. Tracked in
    BLOCKERS.md (B31); the channels are token-gated off until then.
    """
    channel = job.channel
    prefs = await service.get_preferences(db, job.user_id)

    # 1. Opt-in gate — the user must have enabled this channel (fail-closed).
    if not prefs["channels_enabled"].get(channel):
        await service.log_delivery(db, job.user_id, channel, job.template_id, "failed", "channel_disabled")
        return False

    # 2. Quiet hours — defer NORMAL priority by re-queuing; HIGH bypasses.
    if job.priority != "high":
        start = service.parse_hhmm(prefs["quiet_hours_start"])
        end = service.parse_hhmm(prefs["quiet_hours_end"])
        if service.in_quiet_hours(now, start, end):
            # Re-enqueue at the HEAD (LPUSH); the drain pops the TAIL (RPOP) and
            # bounds each tick to the pre-loop length, so a re-queued job is NOT
            # re-processed this tick (no hot loop) and migrates toward the tail as
            # new jobs arrive — delivered once the user's quiet window lifts.
            await redis.lpush(service.queue_key(channel), job.model_dump_json())
            return False

    # 3. Daily rate cap.
    if await service.rate_cap_reached(redis, job.user_id, channel):
        await service.log_delivery(db, job.user_id, channel, job.template_id, "rate_capped", None)
        return False

    # 4. Render (label-only, disclosure-injected). Unknown template → drop, never
    #    deliver a malformed message.
    try:
        msg = render(job.template_id, job.data)
    except UnknownTemplate:
        await service.log_delivery(db, job.user_id, channel, job.template_id, "failed", "unknown_template")
        return False

    # 5. Resolve recipient + deliver.
    if channel == "telegram":
        result = await channels.deliver_telegram(prefs["telegram_chat_id"] or "", msg.text)
    else:  # email
        if not prefs["email_verified"]:
            await service.log_delivery(db, job.user_id, channel, job.template_id, "failed", "email_unverified")
            return False
        to = await _user_email(db, job.user_id)
        result = await channels.deliver_email(to or "", msg.subject, msg.html, msg.text)

    # 6. Outcome.
    if result.ok:
        await service.rate_cap_increment(redis, job.user_id, channel)
        await service.log_delivery(db, job.user_id, channel, job.template_id, "sent", None)
        return True

    if result.transient and (job.attempts + 1) < service.RETRY_CAPS.get(channel, 3):
        retry = job.model_copy(update={"attempts": job.attempts + 1})
        await redis.lpush(service.queue_key(channel), retry.model_dump_json())
        return False

    # Permanent, or transient retries exhausted.
    if channel == "email" and not result.transient:
        await _mark_email_unverified(db, job.user_id)  # bounce → require re-verify
    await service.log_delivery(db, job.user_id, channel, job.template_id, "failed", result.code)
    return False


async def _user_email(db: Any, user_id: str) -> str | None:
    from uuid import UUID

    from sqlalchemy import select

    from dhanradar.models.auth import User

    return await db.scalar(select(User.email).where(User.id == UUID(user_id)))


async def _mark_email_unverified(db: Any, user_id: str) -> None:
    from uuid import UUID

    from sqlalchemy import update

    from dhanradar.models.notifications import NotificationPreference

    await db.execute(
        update(NotificationPreference)
        .where(NotificationPreference.user_id == UUID(user_id))
        .values(email_verified=False)
    )
    await db.commit()
