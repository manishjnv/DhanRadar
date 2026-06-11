"""
Integration tests for the Concept-Explainer endpoints (C1).

Infrastructure contract (canonical fixtures — see tests/conftest.py):
  - async_client     — httpx.AsyncClient over ASGITransport(app); no lifespan.
  - db_session       — function-scoped AsyncSession; conftest truncates auth/billing.
  - patch_redis      — fakeredis.aioredis.FakeRedis; flushed between tests.
  - patch_settings_keys — ephemeral RSA keypair; COOKIE_SECURE=False.

Both routes are PUBLIC-READ (no auth, anonymous returns 200). Each test seeds
`concepts.concept_explainers` via `seed_concepts(db_session)` before the HTTP
call; an autouse teardown fixture (same-connection pattern as _truncate_education)
truncates the table after each test.

Covered:
  1. list happy         — seed → GET /learn/concepts → 200; concepts non-empty;
                          required fields present; anonymous (no auth cookie).
  2. category filter    — GET /learn/concepts?category=Risk%20%26%20return → every
                          returned concept has category "Risk & return".
  3. unknown category   — GET /learn/concepts?category=no-such → 200 with an EMPTY
                          list (not an error; filter simply matches nothing).
  4. get-by-slug happy  — GET /learn/concepts/compounding → 200; body_md non-empty;
                          disclosure bundle present.
  5. bad slug → 404     — GET /learn/concepts/no-such-concept → 404 RFC7807
                          problem+json with detail "concept_not_found".
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Teardown: truncate concepts table between tests (same-connection pattern).
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _truncate_concepts(db_session):
    """Truncate concepts.concept_explainers after each test using db_session's
    OWN connection to avoid the TRUNCATE deadlock (see test_education.py)."""
    yield
    await db_session.rollback()  # drop any open read txn so TRUNCATE is clean
    await db_session.execute(
        text("TRUNCATE TABLE concepts.concept_explainers RESTART IDENTITY CASCADE")
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# 1. List happy path — anonymous, disclosure bundle, required fields
# ---------------------------------------------------------------------------


async def test_list_concepts_happy_anonymous(async_client, db_session):
    """After seeding, GET /learn/concepts returns 200 with a non-empty concepts
    list; each item has slug/title/summary/category; disclosure bundle present;
    works with no auth cookie set at all (anonymous-allowed)."""
    from dhanradar.concepts.seed import seed_concepts

    await seed_concepts(db_session)

    # No Cookie header — fully anonymous request.
    r = await async_client.get("/api/v1/learn/concepts")
    assert r.status_code == 200, r.text

    body = r.json()
    assert "concepts" in body, f"Missing 'concepts' key: {body.keys()}"
    concepts = body["concepts"]
    assert len(concepts) >= 8, f"Expected the 8 seeded concepts, got {len(concepts)}"

    for c in concepts:
        assert "slug" in c, f"Missing 'slug' in concept: {c}"
        assert "title" in c, f"Missing 'title' in concept: {c}"
        assert "summary" in c, f"Missing 'summary' in concept: {c}"
        assert "category" in c, f"Missing 'category' in concept: {c}"

    # Disclosure bundle (non-neg #9)
    assert body.get("disclosure"), "'disclosure' must be non-empty"
    assert body.get("not_advice"), "'not_advice' must be non-empty"
    assert body.get("disclaimer_version"), "'disclaimer_version' must be non-empty"


# ---------------------------------------------------------------------------
# 2. Category filter
# ---------------------------------------------------------------------------


async def test_list_concepts_category_filter(async_client, db_session):
    """GET /learn/concepts?category=Risk%20%26%20return → 200; every returned
    concept has category 'Risk & return'. Other categories must not appear."""
    from dhanradar.concepts.seed import seed_concepts

    await seed_concepts(db_session)

    r = await async_client.get("/api/v1/learn/concepts", params={"category": "Risk & return"})
    assert r.status_code == 200, r.text

    body = r.json()
    concepts = body["concepts"]
    assert len(concepts) > 0, "Expected at least one 'Risk & return' concept after seeding"

    for c in concepts:
        assert c["category"] == "Risk & return", (
            f"Expected category='Risk & return', got {c['category']!r} (slug={c['slug']!r})"
        )


# ---------------------------------------------------------------------------
# 3. Unknown category → 200 with empty list (not an error)
# ---------------------------------------------------------------------------


async def test_list_concepts_unknown_category_empty_200(async_client, db_session):
    """GET /learn/concepts?category=no-such-category → 200 with concepts == [].
    An unmatched filter is an empty result, never an error."""
    from dhanradar.concepts.seed import seed_concepts

    await seed_concepts(db_session)

    r = await async_client.get(
        "/api/v1/learn/concepts", params={"category": "no-such-category"}
    )
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["concepts"] == [], f"Expected empty list, got {body['concepts']!r}"

    # Disclosure bundle still present on the empty result (non-neg #9)
    assert body.get("disclosure"), "'disclosure' must be non-empty even when list is empty"
    assert body.get("not_advice"), "'not_advice' must be non-empty even when list is empty"


# ---------------------------------------------------------------------------
# 4. Get-by-slug happy path
# ---------------------------------------------------------------------------


async def test_get_concept_by_slug_happy(async_client, db_session):
    """GET /learn/concepts/compounding → 200; body_md non-empty; disclosure
    bundle present (slug is confirmed in content.py)."""
    from dhanradar.concepts.seed import seed_concepts

    await seed_concepts(db_session)

    r = await async_client.get("/api/v1/learn/concepts/compounding")
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["slug"] == "compounding"
    assert body.get("body_md"), "'body_md' must be non-empty"
    assert body.get("title"), "'title' must be non-empty"
    assert body.get("summary"), "'summary' must be non-empty"
    assert body.get("category"), "'category' must be non-empty"
    assert "updated_at" in body, "'updated_at' must be present"

    # Disclosure bundle (non-neg #9)
    assert body.get("disclosure"), "'disclosure' must be non-empty"
    assert body.get("not_advice"), "'not_advice' must be non-empty"
    assert body.get("disclaimer_version"), "'disclaimer_version' must be non-empty"


# ---------------------------------------------------------------------------
# 5. Bad slug → RFC7807 404
# ---------------------------------------------------------------------------


async def test_get_concept_bad_slug_404(async_client, db_session):
    """GET /learn/concepts/no-such-concept → 404 RFC7807 problem+json with
    detail=='concept_not_found'."""
    from dhanradar.concepts.seed import seed_concepts

    await seed_concepts(db_session)

    r = await async_client.get("/api/v1/learn/concepts/no-such-concept")
    assert r.status_code == 404, r.text

    body = r.json()

    # RFC 7807 envelope fields
    assert "detail" in body, f"RFC7807 'detail' missing from 404 body: {body}"
    assert body["detail"] == "concept_not_found", (
        f"Expected detail='concept_not_found', got {body['detail']!r}"
    )

    # FastAPI wraps HTTPException with at minimum `detail`; additional RFC7807
    # fields (type/title/status/request_id) are added by the global handler.
    if "status" in body:
        assert body["status"] == 404, f"Expected status==404, got {body['status']}"
