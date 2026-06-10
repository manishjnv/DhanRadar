"""
DhanRadar — News queue tasks (B56).

Routed to the 'news' queue via celery_app.conf.task_routes.
`refresh_market_news` runs every 30 min and upserts admin-curated items into
news.news_items.  Any failure is caught and logged so the worker never crashes
and the endpoint always reads last persisted rows (graceful degrade).
"""

from __future__ import annotations

import asyncio
import logging

from dhanradar.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="dhanradar.tasks.news.refresh_market_news")
def refresh_market_news() -> str:
    """Upsert admin-curated news headlines into news.news_items.

    Best-effort: exceptions are caught and logged so worker failure does not
    crash this task or break the GET /api/v1/news endpoint.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from dhanradar.db import engine
    from dhanradar.news import service

    async def _go() -> str:
        SessionLocal = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )
        async with SessionLocal() as db:
            try:
                count = await service.upsert_curated_news(db)
                return f"news: upserted {count} curated items"
            except Exception:
                logger.exception(
                    "news: upsert_curated_news failed; last persisted rows untouched"
                )
                return "news: upsert failed (see logs)"

    return asyncio.run(_go())
