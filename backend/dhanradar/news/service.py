"""
DhanRadar — News service: list, upsert, and ingest news items (B56 / B56-f4).

Two ingestion paths:
1. RSS ingestion (primary): `fetch_and_upsert_rss_news` fetches sanctioned RSS
   feeds via `news.rss`, HEAD-checks each URL, and upserts headline metadata only.
2. Admin-curated fallback: `get_curated_seed` / `upsert_curated_news` are
   retained as a belt-and-suspenders fallback when all RSS feeds fail.

Article body/excerpt is NEVER stored (copyright compliance, SEBI-safe).
The endpoint always degrades gracefully to 200 [] (never 500).

B56-f4: Admin CRUD helpers appended at the end of this module — see
"Admin CRUD (B56-f4)" section below.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta

import sqlalchemy.exc
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
# Curated items are MF-relevant reference links shown as a fallback when all
# RSS feeds return zero MF-relevant items.
#
# Design: `published_at` is intentionally NOT in the dict — it is set to
# `datetime.now(UTC)` at each upsert so these items always pass the 30-day
# recency filter (they are "always-fresh" featured content, not dated news).
# Update the URLs below whenever more-current content is available.
# ---------------------------------------------------------------------------
_CURATED_ITEMS: list[dict] = [
    {
        "scope": "market",
        "category": "mutual_funds",
        "title": "AMFI monthly SIP data — industry inflow statistics",
        "source": "AMFI",
        "canonical_url": "https://www.amfiindia.com/research-information/other-data/sip-data",
    },
    {
        "scope": "market",
        "category": "mutual_funds",
        "title": "AMFI AUM data — total assets under management by category",
        "source": "AMFI",
        "canonical_url": "https://www.amfiindia.com/research-information/other-data/mf-data",
    },
    {
        "scope": "market",
        "category": "regulation",
        "title": "SEBI Master Circular for Mutual Funds (latest)",
        "source": "SEBI",
        "canonical_url": "https://www.sebi.gov.in/legal/master-circulars/may-2024/master-circular-for-mutual-funds_83391.html",
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

    `published_at` is set to `datetime.now(UTC)` on each upsert so curated
    items always pass the 30-day recency filter and are visible as "featured"
    reference links even when no live RSS news is available.
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
            # published_at is always now — curated items are always-fresh featured links.
            published_at = now
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
                # B56-f4: is_active deliberately NOT in set_ — ingestion never
                # flips the publication state of an existing row (admin drafts
                # stay drafts; admin deactivation sticks). New rows still insert
                # active via .values().
                set_={
                    "title": title,
                    "source": source,
                    "scope": scope,
                    "category": category,
                    "published_at": published_at,
                    "fetched_at": now,
                    "updated_at": now,
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


async def get_recent_headlines(
    db: AsyncSession,
    *,
    hours: int = 48,
    limit: int = 30,
) -> list[str]:
    """Return active headline TITLES published within the last ``hours`` (newest
    first). Headline text only — never body/excerpt (the model stores none). Used
    as the input to the mood news-sentiment signal; returns [] when nothing recent.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=max(1, hours))
    result = await db.execute(
        select(NewsItemModel.title)
        .where(
            NewsItemModel.is_active.is_(True),
            NewsItemModel.published_at >= cutoff,
        )
        .order_by(NewsItemModel.published_at.desc())
        .limit(limit)
    )
    return [t for t in result.scalars().all() if t]


async def _upsert_news_items(
    db: AsyncSession,
    items: list[dict],
    *,
    default_provenance: str = "rss",
) -> int:
    """Shared upsert for live ingestion sources (RSS, GDELT, …).

    Upserts headline metadata via INSERT … ON CONFLICT (canonical_url) DO UPDATE
    so repeated runs are idempotent (dedup is enforced at the DB level). Each
    item's own ``provenance_source`` is honoured; ``default_provenance`` is used
    only when an item omits it. Malformed items (empty required fields) are
    skipped and never crash the batch. Returns the count submitted to the DB.

    B56-f4: ``is_active`` is deliberately NOT in the DO UPDATE set — automated
    ingestion never flips the publication state of an existing row (only admins
    change is_active). New rows still insert active.
    """
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
            provenance_source = str(raw.get("provenance_source", default_provenance)).strip()

            if not title or not source or not canonical_url:
                logger.warning(
                    "news.service.upsert: skipping malformed item url=%r", canonical_url
                )
                continue
        except (KeyError, TypeError, ValueError):
            logger.warning("news.service.upsert: skipping malformed item", exc_info=True)
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
                # B56-f4: is_active deliberately NOT in set_ — automated ingestion
                # never flips the publication state of an existing row (only admins
                # change is_active). New rows still insert active.
                set_={
                    "title": title,
                    "source": source,
                    "scope": scope,
                    "category": category,
                    "published_at": published_at,
                    "provenance_source": provenance_source,
                    "fetched_at": now,
                    "updated_at": now,
                },
            )
        )
        await db.execute(stmt)
        upserted += 1

    await db.commit()
    return upserted


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

    upserted = await _upsert_news_items(db, items, default_provenance="rss")
    logger.info("news.service.rss: upserted %d items", upserted)
    return upserted


async def fetch_and_upsert_gdelt_news(db: AsyncSession) -> int:
    """Fetch sanctioned GDELT DOC 2.0 headlines and upsert them into news.news_items.

    ADDITIVE sanctioned source (B56-f5) — runs ALONGSIDE the RSS path, never
    replacing it or the curated fallback. Headline metadata + canonical link only;
    GDELT's V2Tone / sentiment is discarded at fetch time (stack-lock). Reuses the
    shared ``_upsert_news_items`` ON CONFLICT (canonical_url) DO UPDATE path, so a
    repeated canonical_url updates the existing row rather than duplicating it.
    Returns 0 (no raise) when GDELT yields nothing — graceful degrade.
    """
    from dhanradar.news.gdelt import fetch_gdelt_news

    items = await fetch_gdelt_news()
    if not items:
        logger.warning("news.service.gdelt: GDELT returned 0 items")
        return 0

    upserted = await _upsert_news_items(db, items, default_provenance="gdelt")
    logger.info("news.service.gdelt: upserted %d items", upserted)
    return upserted


# ---------------------------------------------------------------------------
# Admin CRUD (B56-f4) — RequireAdmin-gated operations workflow
# ---------------------------------------------------------------------------
# These helpers replace the hand-edited curated seed as the operator workflow
# for managing news.news_items rows.  All validation is centralised here so
# the admin_router remains a thin translation layer.
# ---------------------------------------------------------------------------


class DuplicateUrlError(Exception):
    """Raised when a canonical_url collides with an existing row."""


# Defense-in-depth advisory screen over admin-entered titles before they reach
# a public surface (non-neg #1). Mirrors mood/service.py:65-67 exactly —
# the core SEBI-advisory verb set; the versioned, domain-signed taxonomy lives
# with the AI gateway (B23). Admin-entered titles are user-facing, so this
# screen applies here just as it does to AI-generated commentary.
_ADVISORY_RE = re.compile(
    r"\b(strong[\s_]?buy|strong[\s_]?sell|buy|sell|hold|switch|avoid|caution)\b",
    re.IGNORECASE,
)


def _validate_fields(**fields: str | None) -> None:  # noqa: C901 — deliberately flat
    """Apply shared validation rules to the provided string fields.

    Rules (applied to every non-None field):
      - Strip whitespace; if result is empty → ValueError("empty_field: <name>").
      - canonical_url must start with http:// or https://.
      - title must not match _ADVISORY_RE (SEBI non-advisory, non-neg #1).

    Raises ValueError with a short machine-readable code so callers can
    surface it as a 400 detail without leaking internal paths.
    """
    for name, value in fields.items():
        if value is None:
            continue
        stripped = str(value).strip()
        if not stripped:
            raise ValueError(f"empty_field: {name}")
        if name == "canonical_url":
            if not (stripped.startswith("http://") or stripped.startswith("https://")):
                raise ValueError("invalid_url")
        if name == "title" and _ADVISORY_RE.search(stripped):
            raise ValueError("advisory_title_rejected")


async def create_news_item(
    db: AsyncSession,
    *,
    title: str,
    source: str,
    canonical_url: str,
    category: str,
    scope: str = "market",
    published_at: datetime | None = None,
) -> NewsItemModel:
    """Create a new news item as a draft (is_active=False).

    The item starts inactive — publication is a deliberate PATCH (reviewer
    gate).  provenance_source is always "admin_curated" for this path.

    Raises:
        ValueError:          field validation failure (empty, bad URL, advisory title).
        DuplicateUrlError:   canonical_url already exists in the table.
    """
    _validate_fields(
        title=title,
        source=source,
        canonical_url=canonical_url,
        category=category,
        scope=scope,
    )
    now = datetime.now(UTC)
    row = NewsItemModel(
        scope=scope.strip(),
        category=category,
        title=title.strip(),
        source=source.strip(),
        canonical_url=canonical_url.strip(),
        published_at=published_at if published_at is not None else now,
        provenance_source="admin_curated",
        fetched_at=now,
        is_active=False,
    )
    db.add(row)
    try:
        await db.flush()
        await db.commit()
    except sqlalchemy.exc.IntegrityError:
        await db.rollback()
        raise DuplicateUrlError(canonical_url)
    await db.refresh(row)
    return row


# Fields an admin may update via PATCH. The router schema already constrains
# this, but the service is the centralised validation layer (defense-in-depth
# against a future caller bypassing the schema).
_UPDATABLE_FIELDS = frozenset(
    {"title", "source", "canonical_url", "category", "scope", "published_at", "is_active"}
)
_STRING_FIELDS = frozenset({"title", "source", "canonical_url", "category", "scope"})


async def update_news_item(
    db: AsyncSession,
    item_id: str,
    **fields: object,
) -> NewsItemModel:
    """Apply partial updates to an existing news item.

    Only the provided keyword arguments are applied (partial update).  The
    same validation rules as create apply to any string field that is given.

    Raises:
        KeyError:            no row with item_id.
        ValueError:          unknown field, explicit null, or field validation
                             failure (empty, bad URL, advisory title).
        DuplicateUrlError:   canonical_url collision.
    """
    unknown = sorted(set(fields) - _UPDATABLE_FIELDS)
    if unknown:
        raise ValueError(f"unknown_field: {unknown[0]}")
    for name, value in fields.items():
        if value is None:
            # Every updatable column is NOT NULL — letting a null through would
            # surface as an IntegrityError mislabelled 409 news_url_exists.
            raise ValueError(f"null_field: {name}")

    result = await db.execute(select(NewsItemModel).where(NewsItemModel.id == item_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(item_id)

    # Validate the string fields that are being updated.
    str_fields_to_validate = {k: v for k, v in fields.items() if k in _STRING_FIELDS}
    if str_fields_to_validate:
        _validate_fields(**str_fields_to_validate)  # type: ignore[arg-type]

    for attr, value in fields.items():
        # Store string fields stripped, matching create_news_item.
        setattr(row, attr, value.strip() if attr in _STRING_FIELDS else value)  # type: ignore[union-attr]

    try:
        await db.flush()
        await db.commit()
    except sqlalchemy.exc.IntegrityError:
        await db.rollback()
        raise DuplicateUrlError(fields.get("canonical_url", ""))
    await db.refresh(row)
    return row


async def delete_news_item(db: AsyncSession, item_id: str) -> None:
    """Hard-delete a news item by id.

    Raises:
        KeyError: no row with item_id.
    """
    result = await db.execute(select(NewsItemModel).where(NewsItemModel.id == item_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(item_id)
    await db.delete(row)
    await db.commit()


async def admin_list_news(
    db: AsyncSession,
    *,
    scope: str | None = None,
    is_active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[NewsItemModel]:
    """Return news items for admin review — no recency cutoff, all provenance.

    Optional filters: scope, is_active.  Ordered published_at DESC.
    """
    stmt = select(NewsItemModel)
    if scope is not None:
        stmt = stmt.where(NewsItemModel.scope == scope)
    if is_active is not None:
        stmt = stmt.where(NewsItemModel.is_active.is_(is_active))
    stmt = stmt.order_by(NewsItemModel.published_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())
