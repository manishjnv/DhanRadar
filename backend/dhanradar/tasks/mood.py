"""
DhanRadar — Mood queue tasks.

Routed to the 'mood' queue via celery_app.conf.task_routes.
`compute_mood_snapshot` is the twice-daily Mood Compass pipeline (beat 09:00 &
16:00 IST). Sync task wrapping the async service (mirrors the MF worker pattern).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from dhanradar.celery_app import celery_app

_IST = ZoneInfo("Asia/Kolkata")


@celery_app.task(name="dhanradar.tasks.mood.compute_mood_snapshot")
def compute_mood_snapshot() -> str:
    """Compute + publish the current twice-daily market-mood snapshot."""
    from dhanradar.mood import service

    async def _go() -> str:
        now_ist = datetime.now(_IST)
        result = await service.compute_and_store(
            snapshot_date=now_ist.date(), snapshot_time=now_ist
        )
        if result is None:
            return "mood: skipped (all inputs missing)"
        return f"mood: {result.regime} ({result.inputs_available}/11 inputs, {result.data_quality})"

    return asyncio.run(_go())


@celery_app.task(name="dhanradar.tasks.mood.run_sentiment_analysis")
def run_sentiment_analysis(symbol: str | None = None) -> str:
    """
    Stub: run sentiment analysis for market news / social signals.
    TODO: implement OpenRouter-powered sentiment pipeline (AI Enrichment module).
    """
    return f"sentiment_analysis: stub — symbol={symbol!r} not yet implemented"
