"""
DhanRadar — Signal alert and automation tasks (Phase 3+).

daily_signal_alert  — 09:15 IST weekdays; notify users whose thresholds are met.
market_data_refresh — every 15 min, Mon–Fri 09:00–16:00 IST; pre-warm VIX + breadth cache.
auto_log_no_action  — 21:00 IST weekdays; auto-journal "skipped" for triggered/watch days.
sip_reminder        — 09:00 IST daily; SIP reminder notification on the 1st of each month.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, date, datetime, timedelta

import structlog

from dhanradar.celery_app import celery_app

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Signal state computation — mirrors the frontend computeSignalState() logic.
# ---------------------------------------------------------------------------

def _nifty_score(pct: float) -> int:
    if pct > 0:
        return 0
    if pct > -2:
        return 1
    if pct > -5:
        return 2
    if pct > -8:
        return 3
    return 4


def _vix_score(vix: float) -> int:
    if vix < 15:
        return 0
    if vix < 17:
        return 1
    if vix < 19:
        return 2
    if vix < 22:
        return 3
    return 4


def _breadth_score(ad: float) -> int:
    if ad > 1.5:
        return 0
    if ad > 1.2:
        return 1
    if ad > 0.8:
        return 2
    if ad > 0.5:
        return 3
    return 4


def _compute_signal_state(nifty_pct: float, vix: float, ad_ratio: float) -> str:
    weighted = (
        _nifty_score(nifty_pct) * 0.20
        + _vix_score(vix) * 0.40
        + _breadth_score(ad_ratio) * 0.40
    )
    if weighted >= 3.0:
        return "triggered"
    if weighted >= 2.0:
        return "watch"
    return "no_signal"


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

_FALLBACK_VIX = 18.5
_FALLBACK_AD_RATIO = 1.24
_FALLBACK_NIFTY_PCT = 0.0


async def _read_market_cache() -> tuple[float, float, float]:
    """Read (nifty_pct, vix, ad_ratio) from Redis; fall back to defaults on miss/error."""
    from dhanradar.redis_client import get_redis
    redis = get_redis()

    vix = _FALLBACK_VIX
    ad_ratio = _FALLBACK_AD_RATIO
    nifty_pct = _FALLBACK_NIFTY_PCT

    try:
        raw = await redis.get("signal:vix:last")
        if raw:
            data = json.loads(raw if isinstance(raw, str) else raw.decode())
            vix = float(data.get("value", _FALLBACK_VIX))
    except Exception:  # noqa: BLE001
        pass

    try:
        raw = await redis.get("signal:breadth:last")
        if raw:
            data = json.loads(raw if isinstance(raw, str) else raw.decode())
            ad_ratio = float(data.get("ad_ratio", _FALLBACK_AD_RATIO))
            nifty_pct = float(data.get("nifty_change_pct", _FALLBACK_NIFTY_PCT))
    except Exception:  # noqa: BLE001
        pass

    return nifty_pct, vix, ad_ratio


async def _vix_cache_age_secs() -> float | None:
    """Return age in seconds of the VIX cache entry, or None if absent/unparseable."""
    from dhanradar.redis_client import get_redis
    try:
        raw = await get_redis().get("signal:vix:last")
        if not raw:
            return None
        data = json.loads(raw if isinstance(raw, str) else raw.decode())
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        return (datetime.now(UTC) - fetched_at).total_seconds()
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Task 0 (existing, now uses live cache)
# ---------------------------------------------------------------------------

@celery_app.task(name="dhanradar.tasks.signal_alerts.daily_signal_alert")
def daily_signal_alert() -> str:
    """Create in-app notifications for users whose signal is triggered.

    Skips weekends. Idempotency: one unread notification per user per 20 hours.
    Phase 4: reads live VIX + breadth from Redis cache (pre-warmed by market_data_refresh).
    """
    from sqlalchemy import select

    from dhanradar.db import (
        admin_task_session,  # B81: cross-user scan (all users' signal_*) → BYPASSRLS
    )
    from dhanradar.signal import service
    from dhanradar.signal.models import SignalRules

    async def _go() -> str:
        now_utc = datetime.now(UTC)
        if now_utc.weekday() >= 5:
            return "signal_alert: skipped (weekend)"

        nifty_pct, vix, ad_ratio = await _read_market_cache()
        signal_state = _compute_signal_state(nifty_pct, vix, ad_ratio)

        if signal_state != "triggered":
            return f"signal_alert: state={signal_state}, no notifications sent"

        sent = 0
        async with admin_task_session() as db:
            stmt = select(SignalRules).where(SignalRules.alerts_on.is_(True))
            result = await db.execute(stmt)
            users_with_alerts = list(result.scalars().all())

            for rules_row in users_with_alerts:
                user_id = str(rules_row.user_id)
                already_notified = await service.has_recent_notification(db, user_id)
                if already_notified:
                    continue
                await service.create_notification(
                    db,
                    user_id,
                    message=(
                        "Signal triggered — your thresholds are met. "
                        "Check /signal before your trading session."
                    ),
                    signal_state="triggered",
                )
                sent += 1
            await db.commit()

        log.info("signal_alert.done", sent=sent, vix=vix, ad_ratio=ad_ratio)
        return f"signal_alert: sent={sent}"

    return asyncio.run(_go())


# ---------------------------------------------------------------------------
# Task 1 — market_data_refresh (Part C)
# ---------------------------------------------------------------------------

@celery_app.task(name="dhanradar.tasks.signal_alerts.market_data_refresh")
def market_data_refresh() -> str:
    """Pre-warm VIX + breadth Redis cache. Scheduled every 15 min, Mon–Fri 09:00–16:00 IST."""
    import time as _t

    from dhanradar.mood import service as mood_service
    from dhanradar.tasks.ingestion_run import ingestion_run, is_source_paused

    _SOURCE = "yahoo_finance"
    _TASK_NAME = "dhanradar.tasks.signal_alerts.market_data_refresh"

    async def _go() -> str:
        if await is_source_paused(_SOURCE):
            return "market_refresh: skipped (paused)"

        start = _t.monotonic()
        async with ingestion_run(_TASK_NAME, _SOURCE) as (run_id, stats):
            try:
                vix_out = await mood_service.get_vix()
                breadth_out = await mood_service.get_breadth()
                elapsed_ms = round((_t.monotonic() - start) * 1000)
                stats.fetched = 2
                stats.written = 2
                log.info(
                    "signal.market_refresh",
                    vix=vix_out.value,
                    ad_ratio=breadth_out.ad_ratio,
                    duration_ms=elapsed_ms,
                )
                return f"market_refresh: vix={vix_out.value} ad_ratio={breadth_out.ad_ratio}"
            except Exception as exc:  # noqa: BLE001
                stats.reachable = False
                stats.status_override = "failed"
                stats.last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
                log.warning("signal.market_refresh_error", exc_type=type(exc).__name__)
                return f"market_refresh: error={type(exc).__name__}"

    return asyncio.run(_go())


# ---------------------------------------------------------------------------
# Task 2 — auto_log_no_action (Part C)
# ---------------------------------------------------------------------------

@celery_app.task(name="dhanradar.tasks.signal_alerts.auto_log_no_action")
def auto_log_no_action() -> str:
    """Auto-insert a 'skipped' journal entry for users with no action on triggered/watch days.

    Scheduled 21:00 IST Mon–Fri. Only runs when market cache is fresh (< 2h old).
    """
    from sqlalchemy import and_, func, select

    from dhanradar.db import (
        admin_task_session,  # B81: cross-user scan (all users' signal_*) → BYPASSRLS
    )
    from dhanradar.signal.models import SignalJournal, SignalRules

    async def _go() -> str:
        now_utc = datetime.now(UTC)
        if now_utc.weekday() >= 5:
            return "auto_log: skipped (weekend)"

        # Guard: only run when cache is fresh enough to trust the signal state
        cache_age = await _vix_cache_age_secs()
        if cache_age is None:
            log.info("auto_log: skipped — no VIX cache")
            return "auto_log: skipped (no cache)"
        if cache_age > 7200:
            log.info("auto_log: skipped — VIX cache stale", age_secs=cache_age)
            return "auto_log: skipped (stale cache)"

        nifty_pct, vix, ad_ratio = await _read_market_cache()
        signal_state = _compute_signal_state(nifty_pct, vix, ad_ratio)

        if signal_state == "no_signal":
            return "auto_log: skipped (no_signal day)"

        market_snapshot = {
            "nifty_pct": nifty_pct,
            "vix_level": vix,
            "breadth_ratio": ad_ratio,
        }
        today = date.today()
        inserted = 0

        async with admin_task_session() as db:
            result = await db.execute(select(SignalRules))
            all_rules = list(result.scalars().all())

            for rules_row in all_rules:
                user_id = rules_row.user_id
                existing_count = await db.scalar(
                    select(func.count()).select_from(SignalJournal).where(
                        and_(
                            SignalJournal.user_id == user_id,
                            SignalJournal.date == today,
                        )
                    )
                )
                if existing_count:
                    continue

                entry = SignalJournal(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    date=today,
                    decision="skipped",
                    amount=None,
                    emotion=[],
                    notes="(auto-logged)",
                    market_snapshot=market_snapshot,
                    signal_state=signal_state,
                    fomo_avoided=False,
                    premature=False,
                    created_at=datetime.now(UTC),
                )
                db.add(entry)
                inserted += 1

            await db.commit()

        log.info("auto_log.done", inserted=inserted, signal_state=signal_state)
        return f"auto_log: inserted={inserted}"

    return asyncio.run(_go())


# ---------------------------------------------------------------------------
# Task 3 — sip_reminder (Part C)
# ---------------------------------------------------------------------------

@celery_app.task(name="dhanradar.tasks.signal_alerts.sip_reminder")
def sip_reminder() -> str:
    """Insert a SIP reminder notification on the 1st of each month.

    Guard: no reminder inserted if one already exists in the last 25 days.
    Phase 5+ will pull the real SIP date from the user's CAS upload.
    """
    from sqlalchemy import and_, func, select

    from dhanradar.db import (
        admin_task_session,  # B81: cross-user scan (all users' signal_*) → BYPASSRLS
    )
    from dhanradar.signal import service
    from dhanradar.signal.models import SignalNotification, SignalRules

    async def _go() -> str:
        now_utc = datetime.now(UTC)
        cutoff = now_utc - timedelta(days=25)
        sent = 0

        async with admin_task_session() as db:
            result = await db.execute(select(SignalRules))
            all_rules = list(result.scalars().all())

            for rules_row in all_rules:
                uid = rules_row.user_id

                # Use user's SIP day from CAS if known; fall back to 1st of month
                target_day: int = rules_row.sip_day if rules_row.sip_day else 1
                if now_utc.day != target_day:
                    continue

                existing = await db.scalar(
                    select(func.count()).select_from(SignalNotification).where(
                        and_(
                            SignalNotification.user_id == uid,
                            SignalNotification.message.like("SIP reminder%"),
                            SignalNotification.created_at >= cutoff,
                        )
                    )
                )
                if existing:
                    continue

                await service.create_notification(
                    db,
                    str(uid),
                    message=(
                        "SIP reminder — your monthly SIP date may be today. "
                        "Keep your automated investment running regardless of market conditions."
                    ),
                    signal_state="no_signal",
                )
                sent += 1

            await db.commit()

        log.info("sip_reminder.done", sent=sent)
        return f"sip_reminder: sent={sent}"

    return asyncio.run(_go())


# ---------------------------------------------------------------------------
# Task 4 — check_achievements (Part B)
# ---------------------------------------------------------------------------

# Achievement slugs matching the 6 milestones defined in frontend/src/components/signal/Achievements.tsx.
_ACHIEVEMENTS: list[tuple[str, str]] = [
    ("disciplined",      "Disciplined Investor — 90 non-premature deployments"),
    ("bear-hunter",      "Bear Market Hunter — deployed when VIX > 20"),
    ("patience",         "Patience Master — avoided FOMO 3+ times"),
    ("crash-collector",  "Crash Collector — deployed when Nifty dropped ≥15%"),
    ("long-term",        "Long-Term Legend — placeholder (future milestone)"),
    ("survivor",         "Market Survivor — deployed when VIX > 25"),
]


def _evaluate_achievements(entries: list) -> set[str]:
    earned: set[str] = set()

    disciplined_count = sum(1 for e in entries if not e.premature)
    if disciplined_count >= 90:
        earned.add("disciplined")

    fomo_avoided = sum(1 for e in entries if e.fomo_avoided)
    if fomo_avoided >= 3:
        earned.add("patience")

    for e in entries:
        if e.decision != "deployed":
            continue
        snapshot: dict = e.market_snapshot or {}
        vix = snapshot.get("vix_level") or 0.0
        nifty = snapshot.get("nifty_pct") or 0.0
        if vix > 20:
            earned.add("bear-hunter")
        if vix > 25:
            earned.add("survivor")
        if nifty <= -15:
            earned.add("crash-collector")

    # long-term is a placeholder — never unlocked automatically
    return earned


@celery_app.task(name="dhanradar.tasks.signal_alerts.check_achievements")
def check_achievements() -> str:
    """Evaluate achievement conditions for all users; unlock newly earned achievements.

    Scheduled nightly at 22:00 IST. Idempotent — only adds achievements that are not
    already in earned_achievements[].
    """
    from sqlalchemy import select

    from dhanradar.db import (
        admin_task_session,  # B81: cross-user scan (all users' signal_*) → BYPASSRLS
    )
    from dhanradar.signal import service
    from dhanradar.signal.models import SignalRules

    async def _go() -> str:
        unlocked_total = 0

        async with admin_task_session() as db:
            result = await db.execute(select(SignalRules))
            all_rules = list(result.scalars().all())

            for rules_row in all_rules:
                uid = rules_row.user_id
                user_id_str = str(uid)

                journal_rows = await service.get_journal(db, user_id_str, limit=500)

                newly_earned = _evaluate_achievements(entries=journal_rows)

                existing = set(rules_row.earned_achievements or [])
                new_unlocks = newly_earned - existing
                if not new_unlocks:
                    continue

                rules_row.earned_achievements = list(existing | new_unlocks)

                # Notify for each new unlock
                slug_to_label = dict(_ACHIEVEMENTS)
                for slug in new_unlocks:
                    label = slug_to_label.get(slug, slug)
                    await service.create_notification(
                        db,
                        user_id_str,
                        message=f"Achievement unlocked: {label}",
                        signal_state="no_signal",
                    )
                    unlocked_total += 1

            await db.commit()

        log.info("check_achievements.done", unlocked=unlocked_total)
        return f"check_achievements: unlocked={unlocked_total}"

    return asyncio.run(_go())
