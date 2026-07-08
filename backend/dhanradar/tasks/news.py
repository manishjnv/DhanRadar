"""
DhanRadar — News queue tasks (B56 live RSS fix).

Routed to the 'news' queue via celery_app.conf.task_routes.
`refresh_market_news` runs every 30 min and:
  1. Fetches sanctioned RSS feeds (RBI press releases / notifications) via
     news.rss — HEAD-checks each URL at ingest so dead links never reach the UI.
  2. Falls back to the admin-curated seed when all RSS feeds return 0 items,
     so the endpoint always has something to serve.
  3. Any failure is caught and logged so the worker never crashes and the
     GET /api/v1/news endpoint always reads last persisted rows (graceful degrade).
"""

from __future__ import annotations

import asyncio
import logging

from dhanradar.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="dhanradar.tasks.news.refresh_market_news")
def refresh_market_news() -> str:
    """Fetch live RSS headlines and upsert into news.news_items.

    Primary path: sanctioned RSS feeds (RBI press releases / notifications).
    Fallback: admin-curated seed when RSS returns 0 items.
    Best-effort: exceptions are caught and logged; worker never crashes;
    the GET /api/v1/news endpoint continues serving last-persisted rows.
    """
    from dhanradar.db import TaskSessionLocal
    from dhanradar.news import service
    from dhanradar.tasks.ingestion_run import ingestion_run, is_source_paused

    _SOURCE = "rbi_rss"
    _TASK_NAME = "dhanradar.tasks.news.refresh_market_news"

    async def _go() -> str:
        if await is_source_paused(_SOURCE):
            return "news: skipped (paused)"

        async with ingestion_run(_TASK_NAME, _SOURCE) as (run_id, stats):
            async with TaskSessionLocal() as db:
                # Each sanctioned source runs in its own try so one failing source
                # never blocks the other (RSS feeds are IP-blocked from KVM4; GDELT is
                # VPS-reachable — they fail independently). GDELT is ADDITIVE.
                rss_count = 0
                gdelt_count = 0
                rss_ok = False
                gdelt_ok = False

                try:
                    rss_count = await service.fetch_and_upsert_rss_news(db)
                    rss_ok = True
                except Exception:
                    logger.exception("news: RSS ingest failed (isolated) — continuing")
                    await db.rollback()

                try:
                    gdelt_count = await service.fetch_and_upsert_gdelt_news(db)
                    gdelt_ok = True
                except Exception:
                    logger.exception("news: GDELT ingest failed (isolated) — continuing")
                    await db.rollback()

                total = rss_count + gdelt_count
                stats.fetched = total
                stats.written = total
                stats.reachable = rss_ok or gdelt_ok
                if not rss_ok:
                    stats.failed += 1
                if not gdelt_ok:
                    stats.failed += 1

                if total > 0:
                    return f"news: upserted {rss_count} RSS + {gdelt_count} GDELT items"

                # Both live sources empty — fall back to curated seed so the feed is
                # never empty.
                logger.warning("news: RSS+GDELT returned 0 items — falling back to curated seed")
                stats.last_error = "rss_and_gdelt_zero_items"
                stats.status_override = "partial"
                try:
                    count = await service.upsert_curated_news(db)
                    return f"news: live empty, upserted {count} curated fallback items"
                except Exception:
                    logger.exception("news: refresh failed; last persisted rows untouched")
                    await db.rollback()
                    stats.status_override = "failed"
                    return "news: refresh failed (see logs)"

    return asyncio.run(_go())

