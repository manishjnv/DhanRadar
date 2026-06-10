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

    async def _go() -> str:
        async with TaskSessionLocal() as db:
            try:
                count = await service.fetch_and_upsert_rss_news(db)
                if count > 0:
                    return f"news: upserted {count} RSS items"

                # RSS returned 0 — fall back to curated seed so the feed is never empty.
                logger.warning(
                    "news: RSS returned 0 items — falling back to curated seed"
                )
                count = await service.upsert_curated_news(db)
                return f"news: RSS empty, upserted {count} curated fallback items"

            except Exception:
                logger.exception(
                    "news: refresh failed; last persisted rows untouched"
                )
                return "news: refresh failed (see logs)"

    return asyncio.run(_go())

