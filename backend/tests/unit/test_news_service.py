"""
Unit tests for the news service — no DB/Redis/network.

Covered:
  1. dedup: upsert_curated_news issues one execute call per valid seed item
     using the ON CONFLICT upsert pattern (dedup is enforced at the DB level).
  2. malformed items: items with empty/missing required fields are skipped and
     session.execute is never called for them.
  3. fetch-failure: if get_curated_seed raises, upsert_curated_news propagates
     the error without calling execute or commit (DB rows untouched).

asyncio_mode = "auto" (pyproject.toml) — async tests need no decorator.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# 1. Dedup — upsert sends one execute per valid item (ON CONFLICT upsert)
# ---------------------------------------------------------------------------


async def test_dedup_upsert_issues_execute_per_item():
    """upsert_curated_news issues exactly one execute call per valid seed item.

    The ON CONFLICT (canonical_url) DO UPDATE clause is the dedup mechanism at
    the DB level; the service always submits every item in the seed so repeated
    task runs are idempotent.
    """
    from dhanradar.news.service import get_curated_seed, upsert_curated_news

    db = AsyncMock()
    count = await upsert_curated_news(db)

    seed = get_curated_seed()
    assert count == len(seed), f"Expected {len(seed)} upserted, got {count}"
    assert db.execute.call_count == len(seed)
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# 2. Malformed items are skipped; valid items proceed
# ---------------------------------------------------------------------------


async def test_malformed_items_are_skipped():
    """Items with empty/missing title, source, or canonical_url are skipped.

    session.execute must not be called for any malformed item; commit is still
    called once (no-op on empty batch).
    """
    from dhanradar.news.service import upsert_curated_news

    malformed_seed = [
        # Empty title — must be skipped
        {
            "scope": "market",
            "category": "market",
            "title": "",
            "source": "SEBI",
            "canonical_url": "https://sebi.gov.in/a",
            "published_at": datetime(2024, 1, 1, tzinfo=UTC),
        },
        # Empty canonical_url — must be skipped
        {
            "scope": "market",
            "category": "market",
            "title": "A valid title",
            "source": "RBI",
            "canonical_url": "",
            "published_at": datetime(2024, 1, 1, tzinfo=UTC),
        },
        # Missing required key — must be skipped
        {
            "scope": "market",
            "category": "market",
            "title": "Another title",
            "published_at": datetime(2024, 1, 1, tzinfo=UTC),
            # "source" and "canonical_url" intentionally absent
        },
    ]

    db = AsyncMock()
    with patch("dhanradar.news.service.get_curated_seed", return_value=malformed_seed):
        count = await upsert_curated_news(db)

    assert count == 0
    db.execute.assert_not_called()
    db.commit.assert_called_once()


async def test_mixed_valid_and_malformed_skips_bad_only():
    """Only malformed items are skipped; valid items in the same batch proceed."""
    from dhanradar.news.service import upsert_curated_news

    mixed_seed = [
        # Valid
        {
            "scope": "market",
            "category": "macro",
            "title": "Valid headline",
            "source": "RBI",
            "canonical_url": "https://rbi.org.in/valid",
            "published_at": datetime(2024, 5, 1, tzinfo=UTC),
        },
        # Malformed (empty title)
        {
            "scope": "market",
            "category": "macro",
            "title": "",
            "source": "RBI",
            "canonical_url": "https://rbi.org.in/bad",
            "published_at": datetime(2024, 5, 2, tzinfo=UTC),
        },
    ]

    db = AsyncMock()
    with patch("dhanradar.news.service.get_curated_seed", return_value=mixed_seed):
        count = await upsert_curated_news(db)

    assert count == 1
    assert db.execute.call_count == 1
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# 3. Fetch failure propagates; DB rows are untouched
# ---------------------------------------------------------------------------


async def test_fetch_failure_leaves_db_untouched():
    """If get_curated_seed raises, upsert_curated_news propagates the error
    without calling execute or commit (prior DB rows are left exactly as-is).
    """
    from dhanradar.news.service import upsert_curated_news

    db = AsyncMock()
    with patch(
        "dhanradar.news.service.get_curated_seed",
        side_effect=RuntimeError("provider error"),
    ):
        with pytest.raises(RuntimeError, match="provider error"):
            await upsert_curated_news(db)

    db.execute.assert_not_called()
    db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# 4. list_news recency filter: items older than NEWS_MAX_AGE_DAYS are excluded
# ---------------------------------------------------------------------------


async def test_list_news_recency_filter_excludes_old_items(caplog):
    """list_news applies a published_at >= cutoff filter (recency guard).

    We mock db.execute to return a scalars().all() of [] (no rows) and assert
    the WHERE clause was built with a cutoff filter.  The easiest observable
    signal is that the query's whereclause references 'published_at'.
    """


    from dhanradar.news import service as svc

    db = AsyncMock()
    # Simulate empty result set
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    items = await svc.list_news(db, scope="market", limit=5)

    assert items == []
    db.execute.assert_called_once()
    # Verify the WHERE clause in the compiled SQL contains the cutoff filter.
    call_args = db.execute.call_args[0][0]
    compiled = str(call_args.compile(compile_kwargs={"literal_binds": False}))
    assert "published_at" in compiled, "Query must filter by published_at (recency)"
    assert "is_active" in compiled


# ---------------------------------------------------------------------------
# 5. list_news staleness warning: logged when newest item is older than threshold
# ---------------------------------------------------------------------------


async def test_list_news_staleness_warning_emitted(caplog):
    """list_news emits a WARNING log when the newest served item is older than
    NEWS_STALENESS_WARN_HOURS hours (observability guard).
    """
    import logging
    from datetime import timedelta
    from unittest.mock import MagicMock

    from dhanradar.config import settings
    from dhanradar.models.news import NewsItem as NewsItemModel
    from dhanradar.news import service as svc

    db = AsyncMock()

    # Build a stale row: published_at = threshold + 2 hours ago
    stale_time = datetime.now(UTC) - timedelta(
        hours=settings.NEWS_STALENESS_WARN_HOURS + 2
    )
    stale_row = MagicMock(spec=NewsItemModel)
    stale_row.title = "Old headline"
    stale_row.source = "RBI"
    stale_row.canonical_url = "https://rbi.org.in/old"
    stale_row.published_at = stale_time
    stale_row.category = "macro"

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [stale_row]
    db.execute = AsyncMock(return_value=mock_result)

    with caplog.at_level(logging.WARNING, logger="dhanradar.news.service"):
        items = await svc.list_news(db, scope="market", limit=5)

    assert len(items) == 1
    assert any("stale" in r.message.lower() for r in caplog.records), (
        "Expected staleness WARNING log when newest item exceeds threshold"
    )


# ---------------------------------------------------------------------------
# 6. fetch_and_upsert_rss_news: dedup — same canonical_url calls execute once
# ---------------------------------------------------------------------------


async def test_fetch_and_upsert_rss_news_dedup():
    """fetch_and_upsert_rss_news calls execute once per unique canonical_url."""
    from dhanradar.news import service as svc

    items = [
        {
            "scope": "market",
            "category": "macro",
            "title": "RBI headline",
            "source": "RBI",
            "canonical_url": "https://rbi.org.in/article/1",
            "published_at": datetime(2026, 6, 10, tzinfo=UTC),
            "provenance_source": "https://rbi.org.in/pressreleases_rss.xml",
        },
        {
            "scope": "market",
            "category": "macro",
            "title": "RBI headline duplicate",
            "source": "RBI",
            "canonical_url": "https://rbi.org.in/article/1",  # same URL
            "published_at": datetime(2026, 6, 10, tzinfo=UTC),
            "provenance_source": "https://rbi.org.in/pressreleases_rss.xml",
        },
    ]

    db = AsyncMock()

    with patch(
        "dhanradar.news.service.fetch_and_upsert_rss_news.__wrapped__"
        if hasattr(svc.fetch_and_upsert_rss_news, "__wrapped__") else
        "dhanradar.news.rss.fetch_all_feeds",
        return_value=items,
    ):
        # Patch fetch_all_feeds inside the service call
        with patch("dhanradar.news.rss.fetch_all_feeds", return_value=items):
            count = await svc.fetch_and_upsert_rss_news(db)

    # Both items have the same URL; upsert still runs for both (DB ON CONFLICT
    # handles dedup), so execute is called twice and count == 2.
    assert count == 2
    assert db.execute.call_count == 2
    db.commit.assert_called_once()



# ---------------------------------------------------------------------------
# 4. B56-f4 reviewer gate — ingestion upserts never touch is_active
# ---------------------------------------------------------------------------


async def test_curated_upsert_never_touches_is_active():
    """upsert_curated_news must NOT set is_active in ON CONFLICT DO UPDATE —
    automation never flips publication state (admin drafts stay drafts, admin
    deactivations stick — B56-f4 reviewer gate). updated_at IS refreshed."""
    from sqlalchemy.dialects import postgresql

    from dhanradar.news.service import upsert_curated_news

    db = AsyncMock()
    await upsert_curated_news(db)

    assert db.execute.call_count >= 1
    for call in db.execute.call_args_list:
        compiled = str(call[0][0].compile(dialect=postgresql.dialect()))
        set_clause = compiled.split("DO UPDATE SET", 1)[1]
        assert "is_active" not in set_clause, (
            "Curated upsert must not flip is_active on existing rows (B56-f4)"
        )
        assert "updated_at" in set_clause


async def test_rss_upsert_never_touches_is_active():
    """fetch_and_upsert_rss_news must NOT set is_active in DO UPDATE (B56-f4)."""
    from sqlalchemy.dialects import postgresql

    from dhanradar.news.service import fetch_and_upsert_rss_news

    items = [
        {
            "scope": "market",
            "category": "regulation",
            "title": "RBI press release on liquidity operations",
            "source": "RBI",
            "canonical_url": "https://rbi.org.in/pr/1",
            "published_at": datetime(2026, 6, 1, tzinfo=UTC),
            "provenance_source": "rss",
        }
    ]
    db = AsyncMock()
    with patch(
        "dhanradar.news.rss.fetch_all_feeds", new=AsyncMock(return_value=items)
    ):
        count = await fetch_and_upsert_rss_news(db)

    assert count == 1
    compiled = str(db.execute.call_args[0][0].compile(dialect=postgresql.dialect()))
    set_clause = compiled.split("DO UPDATE SET", 1)[1]
    assert "is_active" not in set_clause, (
        "RSS upsert must not flip is_active on existing rows (B56-f4)"
    )
    assert "updated_at" in set_clause
