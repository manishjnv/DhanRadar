"""
DhanRadar — Notification service: queue, quiet-hours, rate caps, preferences.

Delivery transport lives in `channels.py`; share-cards in `sharecard.py`. This
module owns the orchestration glue and the pure, unit-testable policy functions:

  * `publish_notification` — LPUSH a `NotificationJob` onto
    `notifications:queue:{channel}` (architecture Global §5 interface, Redis LPUSH).
  * `in_quiet_hours` — pure window check (handles midnight wrap).
  * rate-cap counter helpers — `notif:rate:{user}:{channel}:{date}` (86400s TTL).
  * preferences read/upsert against `notify.notification_preferences`.
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Any, Optional
from zoneinfo import ZoneInfo

from dhanradar.notifications.schemas import NotificationJob

_IST = ZoneInfo("Asia/Kolkata")

# Redis queue keys (no TTL — a worker-down window must not lose jobs, architecture
# "queue persists, no TTL").
QUEUE_PREFIX = "notifications:queue:"

# Per-channel daily delivery caps (architecture: 3 Telegram/day, 1 email digest/day).
RATE_CAPS: dict[str, int] = {"telegram": 3, "email": 1}
_RATE_TTL = 86400  # one day; key also encodes the date so it self-rolls

# Per-channel transient-failure retry cap. Telegram: 3 (stale alerts have negative
# value — do not retry forever). Email: 2.
RETRY_CAPS: dict[str, int] = {"telegram": 3, "email": 2}


def queue_key(channel: str) -> str:
    return f"{QUEUE_PREFIX}{channel}"


def rate_key(user_id: str, channel: str, day: str) -> str:
    return f"notif:rate:{user_id}:{channel}:{day}"


# ---------------------------------------------------------------------------
# Publish (the documented interface) — LPUSH a job onto the channel queue.
# ---------------------------------------------------------------------------

async def publish_notification(
    redis: Any,
    user_id: str,
    channel: str,
    template_id: str,
    data: Optional[dict] = None,
    priority: str = "normal",
) -> NotificationJob:
    """Enqueue one notification. Returns the job (also LPUSH'd as JSON). The drain
    task (`tasks.misc.drain_notifications`) pops and delivers it."""
    job = NotificationJob(
        user_id=user_id,
        channel=channel,  # type: ignore[arg-type]  — validated by the model
        template_id=template_id,
        data=data or {},
        priority=priority,  # type: ignore[arg-type]
    )
    await redis.lpush(queue_key(channel), job.model_dump_json())
    return job


# ---------------------------------------------------------------------------
# Quiet hours — pure window check (IST wall-clock), handles midnight wrap.
# ---------------------------------------------------------------------------

def in_quiet_hours(current: time, start: Optional[time], end: Optional[time]) -> bool:
    """True if `current` falls in [start, end). A null start/end → no quiet hours.
    Supports a wrapping window (e.g. 22:00–07:00). Equal start==end → empty window
    (never quiet), the safe reading (we would rather deliver than silently swallow)."""
    if start is None or end is None or start == end:
        return False
    if start < end:
        return start <= current < end
    # Wraps past midnight: quiet if at/after start OR before end.
    return current >= start or current < end


def now_ist_time() -> time:
    """Current wall-clock time in IST (the project tz). Factored out so the drain
    is testable by monkeypatching this single seam."""
    return datetime.now(_IST).timetz().replace(tzinfo=None)


def today_ist_str() -> str:
    return datetime.now(_IST).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Rate caps — per (user, channel, day). INCR + first-write EXPIRE.
# ---------------------------------------------------------------------------

async def rate_cap_reached(redis: Any, user_id: str, channel: str) -> bool:
    """Read-only check: True if today's count is already at/over the channel cap."""
    cap = RATE_CAPS.get(channel)
    if cap is None:
        return False
    raw = await redis.get(rate_key(user_id, channel, today_ist_str()))
    return raw is not None and int(raw) >= cap


async def rate_cap_increment(redis: Any, user_id: str, channel: str) -> int:
    """Atomically count one successful delivery; set the TTL on first write so the
    key self-expires (the date in the key is the real roll, TTL is just GC)."""
    key = rate_key(user_id, channel, today_ist_str())
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, _RATE_TTL)
    return count


# ---------------------------------------------------------------------------
# Preferences — read / upsert against notify.notification_preferences.
# ---------------------------------------------------------------------------

def _fmt_time(t: Optional[time]) -> Optional[str]:
    return t.strftime("%H:%M") if t is not None else None


def parse_hhmm(s: Optional[str]) -> Optional[time]:
    """Parse an 'HH:MM' string (or None) to a `time`. Public — the drain uses it."""
    if not s:
        return None
    hh, mm = s.split(":")
    return time(int(hh), int(mm))


# Back-compat internal alias.
_parse_time = parse_hhmm


async def get_preferences(db: Any, user_id: str) -> dict:
    """Return the user's preferences as a plain dict (defaults if no row yet)."""
    from uuid import UUID

    from sqlalchemy import select

    from dhanradar.models.notifications import NotificationPreference

    row = await db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == UUID(user_id))
    )
    if row is None:
        return {
            "telegram_chat_id": None,
            "email_verified": False,
            "whatsapp_number": None,
            "quiet_hours_start": None,
            "quiet_hours_end": None,
            "channels_enabled": {},
        }
    return {
        "telegram_chat_id": row.telegram_chat_id,
        "email_verified": row.email_verified,
        "whatsapp_number": row.whatsapp_number,
        "quiet_hours_start": _fmt_time(row.quiet_hours_start),
        "quiet_hours_end": _fmt_time(row.quiet_hours_end),
        "channels_enabled": dict(row.channels_enabled or {}),
    }


async def upsert_preferences(db: Any, user_id: str, fields: dict) -> dict:
    """Partial upsert: only keys present in `fields` are written. Returns the new
    full preference dict. `quiet_hours_*` come in as 'HH:MM' strings."""
    from uuid import UUID

    from sqlalchemy import func, select
    from sqlalchemy.dialects.postgresql import insert

    from dhanradar.models.notifications import NotificationPreference

    uid = UUID(user_id)
    values: dict = {"user_id": uid}
    update_set: dict = {}
    for key in ("telegram_chat_id", "whatsapp_number", "channels_enabled"):
        if key in fields:
            values[key] = fields[key]
            update_set[key] = fields[key]
    for key in ("quiet_hours_start", "quiet_hours_end"):
        if key in fields:
            parsed = _parse_time(fields[key])
            values[key] = parsed
            update_set[key] = parsed

    if update_set:
        update_set["updated_at"] = func.now()
        stmt = insert(NotificationPreference).values(**values).on_conflict_do_update(
            index_elements=["user_id"], set_=update_set
        )
        await db.execute(stmt)
        await db.commit()
    else:
        # Nothing to write, but ensure a row exists so reads are stable.
        exists = await db.scalar(
            select(NotificationPreference.user_id).where(NotificationPreference.user_id == uid)
        )
        if exists is None:
            await db.execute(insert(NotificationPreference).values(user_id=uid).on_conflict_do_nothing())
            await db.commit()

    return await get_preferences(db, user_id)


async def log_delivery(
    db: Any, user_id: str, channel: str, template_id: str, status: str, error_text: Optional[str] = None
) -> None:
    """Append one row to notify.notification_log. `error_text` must be an OPAQUE
    code (never a raw provider body/PII)."""
    from uuid import UUID

    from dhanradar.models.notifications import NotificationLog

    db.add(
        NotificationLog(
            user_id=UUID(user_id),
            channel=channel,
            template_id=template_id,
            status=status,
            error_text=(error_text[:500] if error_text else None),
        )
    )
    await db.commit()
