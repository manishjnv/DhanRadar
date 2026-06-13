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
    """Compute + publish the current twice-daily market-mood snapshot.

    Builds a minimal macro adapter (NseMacroProvider), fetches the best-effort
    signal subset, then calls compute_and_store.  Signal fetch failure is caught
    and degrades gracefully to the all-None (data_unavailable) path.
    """
    from dhanradar.ai_gateway.gateway import OpenRouterGateway
    from dhanradar.market_data.adapter import MarketDataAdapter
    from dhanradar.market_data.config import load_ladders
    from dhanradar.market_data.providers.macro import NseMacroProvider
    from dhanradar.market_data.providers.yahoo import YahooMacroProvider
    from dhanradar.mood import service
    from dhanradar.mood.commentary import generate_mood_commentary
    from dhanradar.mood.signals import fetch_mood_inputs

    async def _go() -> str:
        now_ist = datetime.now(_IST)

        # Build the macro adapter: Yahoo primary (server-reachable), NSE fallback.
        # Ladder order lives in market_data config (MACRO_SIGNAL).
        adapter = MarketDataAdapter(
            providers={
                "yahoo_macro": YahooMacroProvider(),
                "nse_macro": NseMacroProvider(),
            },
            ladders=load_ladders(),
        )

        # Fetch signals best-effort; any failure returns the all-None dict.
        try:
            inputs = await fetch_mood_inputs(adapter)
        except Exception:  # noqa: BLE001 — never let signal fetch crash the task
            inputs = service.default_fetch_inputs()

        # B35-e: AI commentary generator (governed gateway consumer). Awaited by the
        # service ONLY when the snapshot's commentary_allowed gate is set (>= 7 signals,
        # confidence >= 0.40); best-effort — None on any gateway/budget/low-confidence
        # path leaves the snapshot published with its regime label and no commentary.
        result = await service.compute_and_store(
            snapshot_date=now_ist.date(),
            snapshot_time=now_ist,
            fetch=lambda: inputs,
            generate_commentary=lambda r: generate_mood_commentary(
                OpenRouterGateway(), result=r
            ),
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
