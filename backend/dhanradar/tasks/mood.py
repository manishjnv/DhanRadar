"""
DhanRadar — Mood queue tasks.

Routed to the 'mood' queue via celery_app.conf.task_routes.
`compute_mood_snapshot` is the twice-daily Mood Compass pipeline (beat 09:00 &
16:00 IST). Sync task wrapping the async service (mirrors the MF worker pattern).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from dhanradar.celery_app import celery_app

logger = logging.getLogger(__name__)
_IST = ZoneInfo("Asia/Kolkata")


class _PrefetchedAdapter:
    """Wraps a single pre-fetched MacroSignalReceived event so fetch_mood_inputs
    can consume it via the normal .fetch() interface without re-hitting the network.

    This is the mechanism that ensures the Upstox API is called AT MOST ONCE per
    snapshot run, regardless of how many times fetch_mood_inputs would otherwise
    invoke the provider internally.
    """

    def __init__(self, event: object) -> None:
        self._event = event

    async def fetch(self, _request: object) -> object:  # noqa: ANN001
        return self._event


@celery_app.task(name="dhanradar.tasks.mood.compute_mood_snapshot")
def compute_mood_snapshot() -> str:
    """Compute + publish the current twice-daily market-mood snapshot.

    Builds a minimal macro adapter (NseMacroProvider), fetches the best-effort
    signal subset, then calls compute_and_store.  Signal fetch failure is caught
    and degrades gracefully to the all-None (data_unavailable) path.

    Upstox Analytics (FII/DII/PCR) is token-gated:
      - When UPSTOX_ANALYTICS_TOKEN is set, the API is fetched EXACTLY ONCE inside
        an ingestion_run context (for health/ops tracking), then cached via
        service.cache_market_flows, and the resulting event is replayed into
        fetch_mood_inputs via _PrefetchedAdapter — no second network call.
      - When the token is absent, the existing no-token upstox_adapter path is used
        (provider returns no signals, INERT, no change in behaviour).
    """
    from dhanradar.ai_gateway.gateway import OpenRouterGateway
    from dhanradar.config import settings
    from dhanradar.market_data.adapter import MarketDataAdapter
    from dhanradar.market_data.config import DataKind, DataRequest, load_ladders
    from dhanradar.market_data.providers.macro import NseMacroProvider
    from dhanradar.market_data.providers.upstox import UpstoxAnalyticsProvider
    from dhanradar.market_data.providers.yahoo import YahooMacroProvider
    from dhanradar.mood import service
    from dhanradar.mood.commentary import generate_mood_commentary
    from dhanradar.mood.news_sentiment import fetch_news_sentiment
    from dhanradar.mood.signals import fetch_mood_inputs
    from dhanradar.tasks.ingestion_run import ingestion_run

    async def _go() -> str:
        now_ist = datetime.now(_IST)
        token = settings.UPSTOX_ANALYTICS_TOKEN

        # Build the macro adapter: Yahoo primary (server-reachable), NSE fallback.
        # Ladder order lives in market_data config (MACRO_SIGNAL).
        adapter = MarketDataAdapter(
            providers={
                "yahoo_macro": YahooMacroProvider(),
                "nse_macro": NseMacroProvider(),
            },
            ladders=load_ladders(),
        )

        # Upstox Analytics is ADDITIVE, not a ladder fallback: it supplies
        # fii_flows / dii_flows / put_call_ratio that Yahoo/NSE do not.
        # INERT until UPSTOX_ANALYTICS_TOKEN is set.
        upstox_adapter = MarketDataAdapter(
            providers={"upstox_analytics": UpstoxAnalyticsProvider()},
            ladders={DataKind.MACRO_SIGNAL: ["upstox_analytics"]},
        )

        # Token-gated: fetch Upstox ONCE, record the run in ingestion_runs, cache
        # raw flows, then replay the event via _PrefetchedAdapter so fetch_mood_inputs
        # never makes a second network call.  Any failure here falls back to the
        # no-token path (upstox_adapter, which returns no signals).
        upstox_event = None
        if token:
            try:
                async with ingestion_run(
                    "dhanradar.tasks.mood.compute_mood_snapshot", "upstox_analytics"
                ) as (run_id, stats):  # noqa: F841 — run_id unused here; stats mutated
                    # Catch INSIDE the run block so no raw exception propagates to
                    # ingestion_run's error_detail writer (which stores str(exc)). The
                    # token is a local here; even though the provider never raises and
                    # no path embeds the token in an exception string, this guarantees
                    # only a static, token-free reason is ever persisted (Tier-B 2026-06-22).
                    try:
                        upstox_event = await UpstoxAnalyticsProvider(token=token).fetch(
                            DataRequest(DataKind.MACRO_SIGNAL, {})
                        )
                        n = len(upstox_event.signals)
                        stats.fetched = 3  # three signals attempted: fii, dii, pcr
                        stats.written = n
                        if n == 0:
                            stats.reachable = False
                            stats.status_override = "failed"
                            stats.last_error = (
                                "upstox returned no signals (token invalid or API unreachable)"
                            )
                    except Exception:  # noqa: BLE001 — never surface a raw exception (not token-safe) to error_detail
                        logger.warning("mood: upstox fetch raised unexpectedly — recording soft failure")
                        upstox_event = None
                        stats.reachable = False
                        stats.status_override = "failed"
                        stats.last_error = "upstox fetch error (see task logs)"
                # OUTSIDE the run block: a cache hiccup must never mark the run failed.
                if upstox_event is not None and upstox_event.signals:
                    await service.cache_market_flows(upstox_event.signals)
            except Exception:  # noqa: BLE001 — health/flows recording must never crash the snapshot
                logger.warning("mood: upstox health/flows recording failed — continuing")
                upstox_event = None

        supplementals = (
            [_PrefetchedAdapter(upstox_event)]
            if upstox_event is not None
            else [upstox_adapter]
        )

        # Fetch signals best-effort; any failure returns the all-None dict.
        try:
            inputs = await fetch_mood_inputs(adapter, supplemental_adapters=supplementals)
        except Exception:  # noqa: BLE001 — never let signal fetch crash the task
            inputs = service.default_fetch_inputs()

        # 11th factor — news sentiment via the governed gateway (Phase 2). AI-derived,
        # so it is injected here rather than via the macro adapter. Best-effort: None on
        # no-headlines / gateway error / low-confidence / advisory rejection leaves the
        # signal absent and the engine degrades (never imputed). Feeds the server-side
        # score only — never the DOM.
        try:
            from dhanradar.db import TaskSessionLocal

            async with TaskSessionLocal() as news_db:
                inputs["news_sentiment"] = await fetch_news_sentiment(
                    OpenRouterGateway(), news_db
                )
        except Exception:  # noqa: BLE001 — signal fetch must never crash the task
            logger.warning("mood: news-sentiment signal fetch failed — signal absent")

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


@celery_app.task(name="dhanradar.tasks.mood.mood_history_snapshot")
def mood_history_snapshot() -> str:
    """Persist today's served regime into `mood.mood_regime_history` — enrichment
    item 4, the prerequisite for per-fund "performance by market phase"
    (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §10.8).

    PURE Redis cache consumer (mood worker discipline — see mood/service.py module
    docstring + memory 'mood-breadth-is-cache-consumer'): reads the already-published
    `mood:latest` key (written by `service._cache_latest` on every
    `compute_mood_snapshot` run) and writes ONE row. NEVER recomputes, NEVER
    live-fetches. Cache cold / unparseable / missing regime -> a structured warning
    and no row (fail-closed) -- never a task failure.

    Runs 16:05 IST, five minutes after `compute_mood_snapshot`'s 16:00 run has had
    time to refresh the cache. Idempotent: upserts on `snapshot_date`, so a re-run
    the same day still leaves exactly one row.
    """
    return asyncio.run(_mood_history_snapshot_async())


async def _mood_history_snapshot_async() -> str:
    import json

    from sqlalchemy.dialects.postgresql import insert

    from dhanradar.db import TaskSessionLocal
    from dhanradar.models.mood import MoodRegimeHistory
    from dhanradar.mood import service
    from dhanradar.redis_client import get_redis

    today = datetime.now(_IST).date()

    try:
        raw = await get_redis().get(service._LATEST_KEY)
    except Exception:  # noqa: BLE001 — Redis is a soft dependency here too
        logger.warning("mood_history_snapshot: redis read failed — skip (fail-closed)")
        return "mood_history_snapshot: skipped (redis error)"

    if not raw:
        logger.warning("mood_history_snapshot: mood:latest cache cold — skip (fail-closed)")
        return "mood_history_snapshot: skipped (cold cache)"

    try:
        cached = json.loads(raw if isinstance(raw, str) else raw.decode())
    except (ValueError, UnicodeDecodeError):
        logger.warning("mood_history_snapshot: mood:latest cache unparseable — skip (fail-closed)")
        return "mood_history_snapshot: skipped (unparseable cache)"

    regime = cached.get("regime")
    if not regime:
        logger.warning("mood_history_snapshot: mood:latest missing 'regime' — skip (fail-closed)")
        return "mood_history_snapshot: skipped (no regime in cache)"

    # score_inputs = exactly the component readings the cache already carries — no
    # recompute, no numeric mood_score (non-neg #2).
    score_inputs = {
        "confidence_band": cached.get("confidence_band"),
        "data_quality": cached.get("data_quality"),
        "contributing_factors": cached.get("contributing_factors", []),
        "contradicting_factors": cached.get("contradicting_factors", []),
    }

    values = dict(
        snapshot_date=today,
        regime=regime,
        score_inputs=score_inputs,
        as_of=datetime.now(_IST),
    )
    async with TaskSessionLocal() as db:
        stmt = insert(MoodRegimeHistory).values(**values).on_conflict_do_update(
            index_elements=["snapshot_date"],
            set_={k: values[k] for k in values if k != "snapshot_date"},
        )
        await db.execute(stmt)
        await db.commit()

    return f"mood_history_snapshot: {regime} for {today}"


@celery_app.task(name="dhanradar.tasks.mood.run_sentiment_analysis")
def run_sentiment_analysis(symbol: str | None = None) -> str:
    """
    Stub: run sentiment analysis for market news / social signals.
    TODO: implement OpenRouter-powered sentiment pipeline (AI Enrichment module).
    """
    return f"sentiment_analysis: stub — symbol={symbol!r} not yet implemented"
