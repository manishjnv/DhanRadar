"""
Integration tests for the News module (B56).

Infrastructure contract (same as test_mood / test_compliance):
  - async_client      — httpx.AsyncClient over ASGITransport(app); no lifespan.
  - db_session        — function-scoped AsyncSession; conftest truncates
                        auth/billing; this module truncates news.news_items.
  - override_get_db   — routes FastAPI's get_db to the test session.
  - patch_redis / patch_settings_keys — standard fakes from conftest.

Covered:
  1. happy-path: seed one row → GET /api/v1/news returns 200 list with
     {title, source, url, published_at, category} fields.
  2. empty-source: no rows → GET returns 200 [].
  3. bad-params: limit=0 → 422 RFC7807 problem+json.
  4. bad-params: limit=51 (above max) → 422.
  5. scope filter: rows for a different scope are excluded from default query.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from dhanradar.models.news import NewsItem as NewsItemModel

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Teardown: truncate news.news_items after each test (same-connection pattern).
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _truncate_news(db_session):
    yield
    await db_session.rollback()
    await db_session.execute(
        text("TRUNCATE TABLE news.news_items RESTART IDENTITY CASCADE")
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(
    *,
    title: str = "Test headline",
    source: str = "SEBI",
    canonical_url: str = "https://sebi.gov.in/test",
    category: str = "regulation",
    scope: str = "market",
    published_at: datetime | None = None,
) -> NewsItemModel:
    return NewsItemModel(
        scope=scope,
        category=category,
        title=title,
        source=source,
        canonical_url=canonical_url,
        published_at=published_at or datetime(2024, 6, 1, tzinfo=UTC),
        provenance_source="admin_curated",
        fetched_at=datetime.now(UTC),
        is_active=True,
    )


# ---------------------------------------------------------------------------
# 1. happy-path: seeded row → 200 with expected fields
# ---------------------------------------------------------------------------


async def test_get_news_happy_path(async_client, db_session):
    """Seed one news item; GET /api/v1/news returns 200 with the item fields."""
    row = _make_row(
        title="SEBI circular on MF categorisation",
        source="SEBI",
        canonical_url="https://sebi.gov.in/happy",
        category="regulation",
    )
    db_session.add(row)
    await db_session.commit()

    r = await async_client.get("/api/v1/news")
    assert r.status_code == 200, r.text

    items = r.json()
    assert isinstance(items, list)
    assert len(items) >= 1

    item = items[0]
    assert item["title"] == "SEBI circular on MF categorisation"
    assert item["source"] == "SEBI"
    assert item["url"] == "https://sebi.gov.in/happy"
    assert item["category"] == "regulation"
    assert "published_at" in item
    # Verify body/excerpt never leaks
    assert "body" not in item
    assert "excerpt" not in item
    assert "content" not in item


# ---------------------------------------------------------------------------
# 2. empty-source: no rows → 200 []
# ---------------------------------------------------------------------------


async def test_get_news_empty_returns_200_list(async_client, db_session):
    """When no news rows exist, GET returns 200 with an empty list (never 404)."""
    r = await async_client.get("/api/v1/news")
    assert r.status_code == 200, r.text
    assert r.json() == []


# ---------------------------------------------------------------------------
# 3 & 4. bad params → 422 RFC7807
# ---------------------------------------------------------------------------


async def test_get_news_limit_zero_returns_422(async_client, db_session):
    """limit=0 is below the minimum (ge=1); must return 422."""
    r = await async_client.get("/api/v1/news?limit=0")
    assert r.status_code == 422, r.text
    assert r.headers.get("content-type", "").startswith("application/problem+json")
    body = r.json()
    assert body.get("type") == "https://dhanradar.com/errors/validation_error"


async def test_get_news_limit_too_high_returns_422(async_client, db_session):
    """limit=51 exceeds the maximum (le=50); must return 422."""
    r = await async_client.get("/api/v1/news?limit=51")
    assert r.status_code == 422, r.text
    assert r.headers.get("content-type", "").startswith("application/problem+json")
    body = r.json()
    assert body.get("type") == "https://dhanradar.com/errors/validation_error"


# ---------------------------------------------------------------------------
# 5. scope filter excludes other-scope rows
# ---------------------------------------------------------------------------


async def test_get_news_scope_filter(async_client, db_session):
    """Rows with scope='etf' are excluded from the default scope=market query."""
    db_session.add(
        _make_row(
            title="Market row",
            canonical_url="https://sebi.gov.in/market-row",
            scope="market",
        )
    )
    db_session.add(
        _make_row(
            title="ETF row",
            canonical_url="https://sebi.gov.in/etf-row",
            scope="etf",
        )
    )
    await db_session.commit()

    r = await async_client.get("/api/v1/news?scope=market")
    assert r.status_code == 200
    titles = [item["title"] for item in r.json()]
    assert "Market row" in titles
    assert "ETF row" not in titles


async def test_refresh_failure_preserves_cached_rows(async_client, db_session, monkeypatch):
    """Beat refresh failure must not break reads; endpoint still serves last persisted rows."""
    db_session.add(
        _make_row(
            title="Cached row",
            canonical_url="https://sebi.gov.in/cached-row",
            scope="market",
        )
    )
    await db_session.commit()

    from dhanradar.tasks.news import refresh_market_news

    def _raise_seed_failure():
        raise RuntimeError("curated source unavailable")

    monkeypatch.setattr("dhanradar.news.service.get_curated_seed", _raise_seed_failure)

    result = refresh_market_news()
    assert "failed" in result.lower()

    r = await async_client.get("/api/v1/news?scope=market&limit=5")
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 1
    assert items[0]["title"] == "Cached row"


# ---------------------------------------------------------------------------
# 6. recency filter: item older than NEWS_MAX_AGE_DAYS is excluded from list
# ---------------------------------------------------------------------------


async def test_get_news_recency_filter_excludes_old_items(async_client, db_session):
    """Items with published_at older than NEWS_MAX_AGE_DAYS are excluded from results.

    Seeds one fresh item (today) and one stale item (1 year ago).  Only the
    fresh item should appear in the response.
    """
    from datetime import timedelta

    from dhanradar.config import settings

    now = datetime.now(UTC)
    fresh_time = now - timedelta(days=1)
    stale_time = now - timedelta(days=settings.NEWS_MAX_AGE_DAYS + 10)

    db_session.add(
        _make_row(
            title="Fresh item",
            canonical_url="https://rbi.org.in/fresh",
            published_at=fresh_time,
        )
    )
    db_session.add(
        _make_row(
            title="Stale item",
            canonical_url="https://rbi.org.in/stale",
            published_at=stale_time,
        )
    )
    await db_session.commit()

    r = await async_client.get("/api/v1/news?scope=market&limit=10")
    assert r.status_code == 200, r.text

    titles = [item["title"] for item in r.json()]
    assert "Fresh item" in titles, "Fresh item must be served"
    assert "Stale item" not in titles, "Stale item must be excluded by recency filter"
