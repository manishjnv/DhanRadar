"""
DhanRadar — Signal daily alert task.

Runs at 09:15 IST on trading days (weekdays only for MVP; NSE holiday list deferred to Phase 4).
Queries all users with alerts_on=True, computes the current signal state using mock market data
(Phase 1/2 stub values; replaced with live data in Phase 4), and creates a notification row
for each triggered user — but only if no unread notification exists in the last 20 hours.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog

from dhanradar.celery_app import celery_app

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Market data — Phase 1/2 stub values (same as mood/router.py stubs).
# Phase 4 replaces these with live Yahoo Finance / NSE fetches.
# ---------------------------------------------------------------------------
_MOCK_VIX = 18.5
_MOCK_AD_RATIO = 1.24
_MOCK_NIFTY_CHANGE_PCT = 0.0


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


@celery_app.task(name="dhanradar.tasks.signal_alerts.daily_signal_alert")
def daily_signal_alert() -> str:
    """Create in-app notifications for users whose signal is triggered.

    Skips weekends. Idempotency: one unread notification per user per 20 hours.
    """
    from sqlalchemy import select

    from dhanradar.db import task_session
    from dhanradar.signal import service
    from dhanradar.signal.models import SignalRules

    async def _go() -> str:
        now_utc = datetime.now(UTC)
        # Skip weekends (Mon=0, Fri=4)
        if now_utc.weekday() >= 5:
            return "signal_alert: skipped (weekend)"

        signal_state = _compute_signal_state(
            _MOCK_NIFTY_CHANGE_PCT, _MOCK_VIX, _MOCK_AD_RATIO
        )

        if signal_state != "triggered":
            return f"signal_alert: state={signal_state}, no notifications sent"

        sent = 0
        async with task_session() as db:
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

        log.info("signal_alert.done", sent=sent)
        return f"signal_alert: sent={sent}"

    return asyncio.run(_go())
