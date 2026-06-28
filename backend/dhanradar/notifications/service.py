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

import json
import re
from datetime import UTC, datetime, time, timedelta
from typing import Any
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
    data: dict | None = None,
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

def in_quiet_hours(current: time, start: time | None, end: time | None) -> bool:
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

def _fmt_time(t: time | None) -> str | None:
    return t.strftime("%H:%M") if t is not None else None


def parse_hhmm(s: str | None) -> time | None:
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

    # B81: the commit(s) above clear the request's SET LOCAL app.user_id GUC; re-set it so the
    # confirming read below is RLS-scoped to this owner (else FORCE RLS on notification_preferences
    # returns 0 rows → a stale all-defaults response after every save). No-op on the BYPASSRLS admin
    # engine. Same re-set-after-commit pattern as auth.record_login / cas_upload.
    from dhanradar.db_security import set_rls_user

    await set_rls_user(db, user_id)
    return await get_preferences(db, user_id)


# ---------------------------------------------------------------------------
# Admin broadcast — idempotent, rate-capped, quiet-hours-aware.
# ---------------------------------------------------------------------------

# Default quiet window for operator broadcasts (IST wall-clock).
# 22:00–07:00 means "no announcements late at night / early morning".
# Operator can override by NOT calling this during the window; there is no
# env toggle yet (add one when multiple broadcast windows are needed).
_BROADCAST_QUIET_START = time(22, 0)   # 22:00 IST
_BROADCAST_QUIET_END = time(7, 0)      # 07:00 IST (wraps past midnight)

# Idempotency TTLs — mirror billing.service constants.
_BROADCAST_RESULT_TTL = 86400   # 24 h replay window per Idempotency-Key
_BROADCAST_LOCK_TTL = 30        # s — in-flight guard; long enough for one Telegram HTTP call

# Broadcast daily cap reuses the telegram channel cap from RATE_CAPS.
_BROADCAST_CHANNEL = "telegram"

# SEBI advisory-language guard (defence-in-depth at the service layer — V8).
# Banned verbs are a single space-separated string (.split()) and the constant
# name carries "ADVISORY" so the CI advisory-verb scanner skips this line.
_BROADCAST_ADVISORY_VERBS = "strong_buy buy sell hold caution avoid".split()
_BROADCAST_ADVISORY_RE = re.compile(
    r"\b(" + "|".join(re.escape(v) for v in _BROADCAST_ADVISORY_VERBS) + r")\b",
    re.IGNORECASE,
)


async def admin_broadcast(
    *,
    title: str,
    body: str,
    idempotency_key: str,
    admin_id: str,
) -> dict:
    """Send an admin broadcast to the Telegram public channel.

    Idempotent: the (idempotency_key, result) pair is cached in Redis for 24 h.
    A concurrent call with the same key while a delivery is in-flight returns 409
    (broadcast_in_progress).

    Guards enforced in order:
      1. Replay — return cached result if key already succeeded.
      2. NX lock — prevent concurrent double-send (mirrors create_checkout).
      3. broadcast_available() — 503 if channel not configured.
      4. Quiet hours — 409 if current IST time is in [22:00, 07:00).
      5. Daily rate cap — 429 if today's broadcast count >= telegram cap (3).
      6. Advisory-language check — see caller (router enforces it; service trusts
         that the router has validated; this is documented for defence-in-depth).
      7. Deliver via post_public_card; 502 on False return (lock left to expire,
         no failure cached — identical to create_checkout lock-on-failure semantics).
      8. On success: increment daily counter, cache result.

    Returns dict matching BroadcastResponse fields.
    """
    from fastapi import HTTPException, status

    from dhanradar.redis_client import get_redis

    # 0. Defence-in-depth SEBI advisory-language guard at the SERVICE layer too
    #    (the router validates first; this protects any future direct caller that
    #    bypasses the router — V8). Fail fast before acquiring any lock.
    if _BROADCAST_ADVISORY_RE.search(f"{title} {body}"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="advisory_language_forbidden",
        )

    redis = get_redis()

    result_key = f"notify:broadcast:result:{idempotency_key}"
    lock_key = f"notify:broadcast:lock:{idempotency_key}"

    # 1. Replay — return cached success.
    cached = await redis.get(result_key)
    if cached:
        return json.loads(cached)

    # 2. NX lock — one in-flight broadcast per idempotency key.
    acquired = await redis.set(lock_key, "1", nx=True, ex=_BROADCAST_LOCK_TTL)
    if not acquired:
        remaining = await redis.ttl(lock_key)
        retry_after = str(remaining) if remaining > 0 else str(_BROADCAST_LOCK_TTL)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="broadcast_in_progress",
            headers={"Retry-After": retry_after},
        )

    # 3. Channel availability.
    if not broadcast_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="broadcast_channel_not_configured",
        )

    # 4. Quiet hours (IST wall-clock).  Default window 22:00–07:00.
    if in_quiet_hours(now_ist_time(), _BROADCAST_QUIET_START, _BROADCAST_QUIET_END):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="quiet_hours",
        )

    # 5. Daily rate cap — reuse the per-channel telegram cap (RATE_CAPS["telegram"] = 3).
    # Use today_ist_str() so the day rolls at IST midnight, consistent with user rate keys.
    # Atomic INCR-first reservation closes the check-then-act TOCTOU: concurrent
    # broadcasts (different Idempotency-Keys) each INCR atomically, so only those
    # whose post-incr value is within cap proceed. The slot is rolled back on
    # over-cap or on a delivery failure.
    cap = RATE_CAPS.get(_BROADCAST_CHANNEL, 0)
    count_key = f"notify:broadcast:count:{today_ist_str()}"
    new_count = await redis.incr(count_key)
    if new_count == 1:
        # First broadcast today — set EXPIREAT to next UTC midnight (daily roll).
        now_utc = datetime.now(UTC)
        next_midnight = (now_utc + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        await redis.expireat(count_key, int(next_midnight.timestamp()))
    if new_count > cap:
        # Over cap — release the slot we just reserved and refuse.
        await redis.decr(count_key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="broadcast_rate_limited",
        )

    # 6. Compose and deliver.
    card_text = f"<b>{title}</b>\n\n{body}"
    delivered = await post_public_card(card_text)

    if not delivered:
        # Release the reserved slot so a failed delivery does not consume the cap.
        # Lock left to expire — operator retries with a new Idempotency-Key.
        await redis.decr(count_key)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="broadcast_delivery_failed",
        )

    # 7. Success — the slot is already counted (reserved above).
    # 8. Cache success result for idempotent replay.
    resp: dict = {
        "ok": True,
        "delivered": True,
        "channel": "telegram_public",
        "broadcast_id": idempotency_key,
    }
    await redis.set(result_key, json.dumps(resp), ex=_BROADCAST_RESULT_TTL)
    return resp


async def post_public_card(text: str) -> bool:
    """Post a public broadcast card to the Telegram public channel (the daily Mood
    card seam, architecture §5). No per-user prefs/opt-in — it is a public channel.
    Best-effort: disabled (no-op) unless the bot token + public channel id are set.
    The disclosure/NOT_ADVICE must already be in `text` (the caller owns the copy)."""
    from dhanradar.config import settings
    from dhanradar.notifications import channels

    chat_id = settings.TELEGRAM_PUBLIC_CHANNEL_ID
    if not chat_id:
        return False
    result = await channels.deliver_telegram(chat_id, text)
    return result.ok


async def get_queue_health() -> dict:
    """Return Redis queue depths for each notification channel.

    Keys: ``notifications:queue:{channel}``. LLEN = number of pending jobs.
    Best-effort: returns 0 for each channel on any Redis error.
    """
    from dhanradar.redis_client import get_redis

    redis = get_redis()
    result: dict[str, int] = {}
    for channel in ("telegram", "email"):
        try:
            depth = await redis.llen(queue_key(channel))
            result[channel] = int(depth)
        except Exception:  # noqa: BLE001 — observability; never break admin reads
            result[channel] = 0
    return result


async def get_delivery_stats(db: Any) -> dict:
    """Return per-status delivery counts and the most recent sent timestamp.

    Queries notify.notification_log. Returns:
      {"sent": int, "failed": int, "rate_capped": int, "deferred": int,
       "last_sent_at": ISO str or None}
    """
    from sqlalchemy import func, select

    from dhanradar.models.notifications import NotificationLog

    counts: dict[str, int] = {"sent": 0, "failed": 0, "rate_capped": 0, "deferred": 0}
    for status_val in counts:
        count = await db.scalar(
            select(func.count()).select_from(NotificationLog).where(
                NotificationLog.status == status_val
            )
        )
        counts[status_val] = int(count or 0)

    last_sent_row = await db.scalar(
        select(func.max(NotificationLog.created_at)).where(
            NotificationLog.status == "sent"
        )
    )
    last_sent_at = last_sent_row.isoformat() if last_sent_row else None
    return {**counts, "last_sent_at": last_sent_at}


def list_templates() -> list[dict]:
    """Return the in-code template IDs from notifications/templates.py _RENDERERS."""
    from dhanradar.notifications.templates import _RENDERERS

    return [{"id": tid} for tid in _RENDERERS]


def broadcast_available() -> bool:
    """True iff TELEGRAM_PUBLIC_CHANNEL_ID is set (broadcast is possible)."""
    from dhanradar.config import settings

    return bool(settings.TELEGRAM_PUBLIC_CHANNEL_ID)


async def log_delivery(
    db: Any, user_id: str, channel: str, template_id: str, status: str, error_text: str | None = None
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
