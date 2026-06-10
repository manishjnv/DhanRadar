"""
DhanRadar — News service: list, upsert, and ingest news items (B56).

Two ingestion paths:
1. RSS ingestion (primary): `fetch_and_upsert_rss_news` fetches sanctioned RSS
   feeds via `news.rss`, HEAD-checks each URL, and upserts headline metadata only.
2. Admin-curated fallback: `get_curated_seed` / `upsert_curated_news` are
   retained as a belt-and-suspenders fallback when all RSS feeds fail.

Article body/excerpt is NEVER stored (copyright compliance, SEBI-safe).
The endpoint always degrades gracefully to 200 [] (never 500).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.config import settings
from dhanradar.models.news import NewsItem as NewsItemModel
from dhanradar.news.schemas import NewsItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Admin-curated seed source (no external fetch; update out-of-band)
# ---------------------------------------------------------------------------
# Each entry: scope, category, title, source, canonical_url, published_at
# The beat task upserts these every 30 min best-effort.  Only headline + link
# are stored; article body/excerpt is never persisted.
# ---------------------------------------------------------------------------
_CURATED_ITEMS: list[dict] = [
    {
        "scope": "market",
        "category": "regulation",
        "title": "SEBI circular on mutual fund categorisation — March 2024",
        "source": "SEBI",
        "canonical_url": "https://www.sebi.gov.in/legal/circulars/mar-2024/circulars.html",
        "published_at": datetime(2024, 3, 1, tzinfo=UTC),
    },
    {
        "scope": "market",
        "category": "mutual_funds",
        "title": "AMFI monthly data: SIP inflows update — April 2024",
        "source": "AMFI",
        "canonical_url": "https://www.amfiindia.com/research-information/other-data/sip-data",
        "published_at": datetime(2024, 4, 9, tzinfo=UTC),
    },
    {
        "scope": "market",
        "category": "macro",
        "title": "RBI monetary policy April 2024 — repo rate decision",
        "source": "RBI",
        "canonical_url": "https://www.rbi.org.in/scripts/bs_pressreleasedisplay.aspx?prid=57558",
        "published_at": datetime(2024, 4, 5, tzinfo=UTC),
    },
]


def get_curated_seed() -> list[dict]:
    """Return the admin-curated headline list.  No network I/O."""
    return list(_CURATED_ITEMS)


async def upsert_curated_news(db: AsyncSession) -> int:
    """Upsert admin-curated items into news.news_items.

    Uses INSERT … ON CONFLICT (canonical_url) DO UPDATE so repeated runs are
    idempotent.  Returns the count of rows processed.  Any individual item
    that fails validation is skipped (malformed items never crash the task).
    Exceptions from get_curated_seed() propagate to the caller (task catches
    them so the endpoint always reads last persisted rows).
    """
    items = get_curated_seed()
    now = datetime.now(UTC)
    upserted = 0

    for raw in items:
        try:
            title = str(raw["title"]).strip()
            source = str(raw["source"]).strip()
            canonical_url = str(raw["canonical_url"]).strip()
            scope = str(raw.get("scope", "market")).strip()
            category = str(raw.get("category", "market")).strip()
            published_at = raw["published_at"]
            if not title or not source or not canonical_url:
                logger.warning(
                    "news.upsert: skipping malformed item url=%r", canonical_url
                )
                continue
        except (KeyError, TypeError, ValueError):
            logger.warning("news.upsert: skipping malformed item", exc_info=True)
            continue

        stmt = (
            pg_insert(NewsItemModel)
            .values(
                scope=scope,
                category=category,
                title=title,
                source=source,
                canonical_url=canonical_url,
                published_at=published_at,
                provenance_source="admin_curated",
                fetched_at=now,
                is_active=True,
            )
            .on_conflict_do_update(
                index_elements=["canonical_url"],
                set_={
                    "title": title,
                    "source": source,
                    "scope": scope,
                    "category": category,
                    "published_at": published_at,
                    "fetched_at": now,
                    "is_active": True,
                },
            )
        )
        await db.execute(stmt)
        upserted += 1

    await db.commit()
    return upserted


async def list_news(
    db: AsyncSession,
    *,
    scope: str = "market",
    limit: int = 20,
) -> list[NewsItem]:
    """Return active news items within the recency window, ordered by published_at DESC.

    Recency window: NEWS_MAX_AGE_DAYS (default 30) from config.
    Staleness warning: logs when the newest served item is older than
    NEWS_STALENESS_WARN_HOURS — observable signal for feed health.
    Always returns 200 [] when no rows exist — never 404.
    """
    cutoff = datetime.now(UTC) - timedelta(days=settings.NEWS_MAX_AGE_DAYS)

    result = await db.execute(
        select(NewsItemModel)
        .where(
            NewsItemModel.scope == scope,
            NewsItemModel.is_active.is_(True),
            NewsItemModel.published_at >= cutoff,
        )
        .order_by(NewsItemModel.published_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()

    # Staleness observability — warn when the freshest served item is old.
    if rows:
        newest_age_h = (datetime.now(UTC) - rows[0].published_at).total_seconds() / 3600
        if newest_age_h > settings.NEWS_STALENESS_WARN_HOURS:
            logger.warning(
                "news.staleness: newest served item is %.1fh old (threshold=%dh) — "
                "RSS feed may be stale or all ingest cycles failed",
                newest_age_h,
                settings.NEWS_STALENESS_WARN_HOURS,
            )

    return [
        NewsItem(
            title=row.title,
            source=row.source,
            url=row.canonical_url,
            published_at=row.published_at,
            category=row.category,
        )
        for row in rows
    ]


async def fetch_and_upsert_rss_news(db: AsyncSession) -> int:
    """Fetch sanctioned RSS feeds and upsert live headline items into news.news_items.

    Primary ingestion path (replaces admin-curated seed).  Returns the count of
    items upserted.  Any feed failure is gracefully isolated (fetch_all_feeds
    returns [] for a bad feed, never raises).  Returns 0 when all feeds fail
    so the caller can fall back to the curated seed.

    Dedup is enforced at the DB level via ON CONFLICT (canonical_url) DO UPDATE.
    URL liveness was already checked by rss.fetch_feed before items reach here.
    """
    from dhanradar.news.rss import fetch_all_feeds

    items = await fetch_all_feeds()
    if not items:
        logger.warning("news.service: all RSS feeds returned 0 items")
        return 0

    now = datetime.now(UTC)
    upserted = 0

    for raw in items:
        try:
            title = str(raw["title"]).strip()
            source = str(raw["source"]).strip()
            canonical_url = str(raw["canonical_url"]).strip()
            scope = str(raw.get("scope", "market")).strip()
            category = str(raw.get("category", "market")).strip()
            published_at: datetime = raw["published_at"]
            provenance_source = str(raw.get("provenance_source", "rss")).strip()

            if not title or not source or not canonical_url:
                logger.warning(
                    "news.service.rss: skipping malformed item url=%r", canonical_url
                )
                continue
        except (KeyError, TypeError, ValueError):
            logger.warning("news.service.rss: skipping malformed item", exc_info=True)
            continue

        stmt = (
            pg_insert(NewsItemModel)
            .values(
                scope=scope,
                category=category,
                title=title,
                source=source,
                canonical_url=canonical_url,
                published_at=published_at,
                provenance_source=provenance_source,
                fetched_at=now,
                is_active=True,
            )
            .on_conflict_do_update(
                index_elements=["canonical_url"],
                set_={
                    "title": title,
                    "source": source,
                    "scope": scope,
                    "category": category,
                    "published_at": published_at,
                    "provenance_source": provenance_source,
                    "fetched_at": now,
                    "is_active": True,
                },
            )
        )
        await db.execute(stmt)
        upserted += 1

    await db.commit()
    logger.info("news.service.rss: upserted %d items", upserted)
    return upserted
