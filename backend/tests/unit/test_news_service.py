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
from unittest.mock import AsyncMock, patch

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
