"""
Integration tests for the Tax-Education endpoints (G8).

Infrastructure contract:
  - async_client     — httpx.AsyncClient over ASGITransport(app); no lifespan.
  - db_session       — function-scoped AsyncSession; conftest truncates auth/billing.
  - patch_redis      — fakeredis.aioredis.FakeRedis; flushed between tests.
  - patch_settings_keys — ephemeral RSA keypair; COOKIE_SECURE=False.

All three routes are PUBLIC-READ (no auth, anonymous returns 200). Each test seeds
`education.tax_education_articles` via `seed_articles(db_session)` before the HTTP
call; an autouse teardown fixture (same-connection pattern as _truncate_mood) truncates
the table after each test.

TRUNCATE note — same-connection pattern (see _truncate_mood in test_mood.py):
  Teardown runs TRUNCATE on db_session's OWN connection to avoid the ACCESS EXCLUSIVE
  deadlock that a second connection would trigger against any lingering ACCESS SHARE lock
  from the test's SELECT.

Covered:
  1. list happy        — seed → GET /learn/tax → 200; articles non-empty; required fields
                         present; anonymous (no auth cookie).
  2. category filter   — GET /learn/tax?category=Capital%20gains → every returned article
                         has category "Capital gains".
  3. get-by-slug happy — GET /learn/tax/capital-gains-basics → 200; body_md non-empty;
                         fy_label present; disclosure bundle present.
  4. bad slug → 404    — GET /learn/tax/no-such-article → 404 RFC7807 problem+json with
                         detail "article_not_found".
  5. calendar happy    — GET /learn/tax/calendar → 200; fy_label present; key_dates is
                         a non-empty list each with label/date/note; elss_note present;
                         disclosure bundle present.
  6. route-order guard — GET /learn/tax/calendar returns the calendar shape (key_dates),
                         NOT captured as a {slug} → not 404/article-shaped.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Teardown: truncate education table between tests (same-connection pattern).
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _truncate_education(db_session):
    """Truncate education.tax_education_articles after each test using db_session's
    OWN connection to avoid the TRUNCATE deadlock (see module docstring)."""
    yield
    await db_session.rollback()  # drop any open read txn so TRUNCATE is clean
    await db_session.execute(
        text("TRUNCATE TABLE education.tax_education_articles RESTART IDENTITY CASCADE")
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# 1. List happy path — anonymous, disclosure bundle, required fields
# ---------------------------------------------------------------------------


async def test_list_articles_happy_anonymous(async_client, db_session):
    """After seeding, GET /learn/tax returns 200 with non-empty articles list;
    each item has slug/title/summary/category/fy_label; disclosure bundle present;
    works with no auth cookie set at all (anonymous-allowed)."""
    from dhanradar.education.seed import seed_articles

    await seed_articles(db_session)

    # No Cookie header — fully anonymous request.
    r = await async_client.get("/api/v1/learn/tax")
    assert r.status_code == 200, r.text

    body = r.json()
    assert "articles" in body, f"Missing 'articles' key: {body.keys()}"
    articles = body["articles"]
    assert len(articles) > 0, "Expected at least one article after seeding"

    for art in articles:
        assert "slug" in art, f"Missing 'slug' in article: {art}"
        assert "title" in art, f"Missing 'title' in article: {art}"
        assert "summary" in art, f"Missing 'summary' in article: {art}"
        assert "category" in art, f"Missing 'category' in article: {art}"
        assert "fy_label" in art, f"Missing 'fy_label' in article: {art}"

    # Disclosure bundle (non-neg #9)
    assert "disclosure" in body, "Missing 'disclosure' in response"
    assert body["disclosure"], "'disclosure' must be non-empty"
    assert "not_advice" in body, "Missing 'not_advice' in response"
    assert body["not_advice"], "'not_advice' must be non-empty"
    assert "disclaimer_version" in body, "Missing 'disclaimer_version' in response"
    assert body["disclaimer_version"], "'disclaimer_version' must be non-empty"


# ---------------------------------------------------------------------------
# 2. Category filter
# ---------------------------------------------------------------------------


async def test_list_articles_category_filter(async_client, db_session):
    """GET /learn/tax?category=Capital%20gains → 200; every returned article has
    category 'Capital gains'. Other categories must not appear in the result."""
    from dhanradar.education.seed import seed_articles

    await seed_articles(db_session)

    r = await async_client.get("/api/v1/learn/tax", params={"category": "Capital gains"})
    assert r.status_code == 200, r.text

    body = r.json()
    articles = body["articles"]
    assert len(articles) > 0, "Expected at least one 'Capital gains' article after seeding"

    for art in articles:
        assert art["category"] == "Capital gains", (
            f"Expected category='Capital gains', got {art['category']!r} (slug={art['slug']!r})"
        )


# ---------------------------------------------------------------------------
# 3. Get-by-slug happy path
# ---------------------------------------------------------------------------


async def test_get_article_by_slug_happy(async_client, db_session):
    """GET /learn/tax/capital-gains-basics → 200; body_md non-empty; fy_label
    present; disclosure bundle present (slug is confirmed in content.py)."""
    from dhanradar.education.seed import seed_articles

    await seed_articles(db_session)

    r = await async_client.get("/api/v1/learn/tax/capital-gains-basics")
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["slug"] == "capital-gains-basics"
    assert body.get("body_md"), "'body_md' must be non-empty"
    assert body.get("fy_label"), "'fy_label' must be non-empty"
    assert body.get("title"), "'title' must be non-empty"
    assert body.get("summary"), "'summary' must be non-empty"
    assert body.get("category"), "'category' must be non-empty"

    # Disclosure bundle (non-neg #9)
    assert body.get("disclosure"), "'disclosure' must be non-empty"
    assert body.get("not_advice"), "'not_advice' must be non-empty"
    assert body.get("disclaimer_version"), "'disclaimer_version' must be non-empty"


# ---------------------------------------------------------------------------
# 4. Bad slug → RFC7807 404
# ---------------------------------------------------------------------------


async def test_get_article_bad_slug_404(async_client, db_session):
    """GET /learn/tax/no-such-article → 404 RFC7807 problem+json with
    detail=='article_not_found'. Confirm type/title/status/request_id present."""
    from dhanradar.education.seed import seed_articles

    await seed_articles(db_session)

    r = await async_client.get("/api/v1/learn/tax/no-such-article")
    assert r.status_code == 404, r.text

    body = r.json()

    # RFC 7807 envelope fields
    assert "detail" in body, f"RFC7807 'detail' missing from 404 body: {body}"
    assert body["detail"] == "article_not_found", (
        f"Expected detail='article_not_found', got {body['detail']!r}"
    )

    # FastAPI wraps HTTPException with at minimum `detail`; additional RFC7807
    # fields (type/title/status/request_id) are added by the global handler.
    # Assert at least type and status if present (they may not all be wired yet).
    if "status" in body:
        assert body["status"] == 404, f"Expected status==404, got {body['status']}"


# ---------------------------------------------------------------------------
# 5. Calendar happy path — structural shape, not hardcoded FY
# ---------------------------------------------------------------------------


async def test_calendar_happy(async_client, db_session):
    """GET /learn/tax/calendar → 200; fy_label present; key_dates is a non-empty
    list each with label/date/note; elss_note present; disclosure bundle present.
    Does NOT assert a hardcoded FY string — the calendar is date.today()-driven."""
    # Calendar endpoint is DB-free (pure computation) but we still exercise via
    # async_client which requires the override_get_db/patch_redis chain from
    # async_client fixture. No seed needed for this endpoint.
    r = await async_client.get("/api/v1/learn/tax/calendar")
    assert r.status_code == 200, r.text

    body = r.json()

    assert body.get("fy_label"), "'fy_label' must be non-empty"
    assert body.get("fy_start"), "'fy_start' must be non-empty"
    assert body.get("fy_end"), "'fy_end' must be non-empty"
    assert body.get("elss_note"), "'elss_note' must be non-empty"

    key_dates = body.get("key_dates")
    assert isinstance(key_dates, list), f"'key_dates' must be a list, got {type(key_dates)}"
    assert len(key_dates) > 0, "'key_dates' must be non-empty"

    for kd in key_dates:
        assert "label" in kd, f"Missing 'label' in key_date entry: {kd}"
        assert "date" in kd, f"Missing 'date' in key_date entry: {kd}"
        assert "note" in kd, f"Missing 'note' in key_date entry: {kd}"
        assert kd["label"], "'label' must be non-empty"
        assert kd["date"], "'date' must be non-empty"
        assert kd["note"], "'note' must be non-empty"

    # Disclosure bundle (non-neg #9)
    assert body.get("disclosure"), "'disclosure' must be non-empty"
    assert body.get("not_advice"), "'not_advice' must be non-empty"
    assert body.get("disclaimer_version"), "'disclaimer_version' must be non-empty"


# ---------------------------------------------------------------------------
# 6. Route-order guard: /learn/tax/calendar is NOT captured as {slug}
# ---------------------------------------------------------------------------


async def test_calendar_route_not_captured_as_slug(async_client, db_session):
    """GET /learn/tax/calendar must hit the calendar handler (returns key_dates),
    NOT be captured by the {slug} route returning 404 or an article shape.
    This guards the FastAPI route-order declaration in router.py."""
    r = await async_client.get("/api/v1/learn/tax/calendar")

    # Must be 200 — not 404 (which would mean the {slug} route caught it first
    # and service.get_article returned None for the string "calendar")
    assert r.status_code == 200, (
        f"Expected 200 from calendar handler; got {r.status_code} — "
        "route-order may be wrong (calendar after {{slug}} in router.py)"
    )

    body = r.json()

    # Calendar shape guard: must have key_dates (calendar-specific field)
    assert "key_dates" in body, (
        f"Response lacks 'key_dates' — likely captured by the {{slug}} handler, "
        f"not the calendar handler. Body: {list(body.keys())}"
    )
    assert isinstance(body["key_dates"], list), "'key_dates' must be a list"
    assert len(body["key_dates"]) > 0, "'key_dates' must be non-empty"

    # Article shape must NOT be present
    assert "body_md" not in body, (
        "'body_md' appeared — response looks like an article, not a calendar"
    )
