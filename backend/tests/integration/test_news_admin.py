"""
DhanRadar — Integration tests for admin news CRUD endpoints (B56-f4).

Covers:
  - 404 surface-hiding: all 4 routes return 404 for anonymous callers.
  - 404 surface-hiding: all 4 routes return 404 for authenticated non-admins.
  - Full lifecycle as admin:
      POST  → 201 draft (is_active=False).
      Item must be ABSENT from public GET /api/v1/news (draft is not served).
      PATCH {"is_active": true} → item NOW appears in public /news.
      PATCH a field edit (title) → 200 with updated field.
      Duplicate-url POST → 409 news_url_exists.
      Advisory-title POST → 400 invalid_news_item: advisory_title_rejected.
      PATCH malformed item_id → 404 (surface-hiding, not 422/500).
      DELETE → 204 and item gone from admin GET list.
  - GET admin list shows inactive items (no recency cutoff).

Infrastructure contract:
  - async_client, db_session, patch_redis, patch_settings_keys (from conftest).
  - monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id) to promote a user.
  - monkeypatch.setattr(_db_mod, "engine", db_session.bind) for own-session audit paths.
  - __Host- cookies extracted from raw Set-Cookie and re-injected manually.
"""

from __future__ import annotations

import uuid

import pytest

import dhanradar.db as _db_mod

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Teardown: truncate news.news_items between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _truncate_news(db_session):
    """Truncate news.news_items after each test so no state leaks across tests."""
    from sqlalchemy import text

    yield
    await db_session.rollback()
    await db_session.execute(text("TRUNCATE TABLE news.news_items RESTART IDENTITY CASCADE"))
    await db_session.commit()


# ---------------------------------------------------------------------------
# Helper: signup → (user_id, access_token)
# ---------------------------------------------------------------------------


async def _signup(client, email: str) -> tuple[str, str]:
    from tests.conftest import extract_cookie

    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "AdminPass42!"},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["user"]["id"]), extract_cookie(r, "__Host-access")


_NEWS_ADMIN_ROUTES = [
    ("GET", "/api/v1/admin/news"),
    ("POST", "/api/v1/admin/news"),
    ("PATCH", "/api/v1/admin/news/00000000-0000-0000-0000-000000000001"),
    ("DELETE", "/api/v1/admin/news/00000000-0000-0000-0000-000000000001"),
]


# ---------------------------------------------------------------------------
# 1. 404 for anonymous callers
# ---------------------------------------------------------------------------


async def test_news_admin_404_for_anonymous(async_client):
    """All 4 admin/news routes return 404 for callers with no cookie."""
    for method, path in _NEWS_ADMIN_ROUTES:
        r = await getattr(async_client, method.lower())(path)
        assert r.status_code == 404, (
            f"{method} {path} should be 404 for anonymous; got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 2. 404 for authenticated non-admins
# ---------------------------------------------------------------------------


async def test_news_admin_404_for_non_admin(async_client, monkeypatch):
    """Authenticated non-admin (empty ADMIN_USER_IDS) → 404 on all 4 routes."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")

    _, access = await _signup(async_client, "nonadmin_news@example.com")
    headers = make_auth_headers(access_token=access)

    for method, path in _NEWS_ADMIN_ROUTES:
        r = await getattr(async_client, method.lower())(path, headers=headers)
        assert r.status_code == 404, (
            f"{method} {path} should be 404 for non-admin; got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 3. Full admin lifecycle
# ---------------------------------------------------------------------------


async def test_news_admin_full_lifecycle(
    async_client, db_session, monkeypatch, patch_redis
):
    """
    Full lifecycle:
      POST  → 201 draft
      Item absent from public /news (draft, is_active=False)
      PATCH is_active=true → item appears in public /news
      PATCH title change → reflected in response
      Duplicate POST → 409
      Advisory POST → 400
      Malformed item_id PATCH → 404
      DELETE → 204
      Item gone from admin GET list
    """
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_news_lifecycle@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    monkeypatch.setattr(_db_mod, "engine", db_session.bind)
    headers = make_auth_headers(access_token=access)

    payload = {
        "title": "AMFI monthly SIP data hits record high",
        "source": "AMFI",
        "canonical_url": "https://amfiindia.com/sip-lifecycle-test",
        "category": "mutual_funds",
        "scope": "market",
    }

    # --- POST → 201 draft ---
    r = await async_client.post("/api/v1/admin/news", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    body = r.json()
    item_id = body["id"]
    assert body["is_active"] is False, "New item must be a draft"
    assert body["provenance_source"] == "admin_curated"
    assert body["title"] == payload["title"]

    # --- Draft absent from public /news ---
    r_pub = await async_client.get("/api/v1/news?scope=market&limit=50")
    assert r_pub.status_code == 200
    pub_urls = [item["url"] for item in r_pub.json()]
    assert payload["canonical_url"] not in pub_urls, (
        "Draft (is_active=False) must NOT appear in public /news"
    )

    # --- PATCH is_active=True → appears in public /news ---
    r = await async_client.patch(
        f"/api/v1/admin/news/{item_id}",
        json={"is_active": True},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is True

    r_pub = await async_client.get("/api/v1/news?scope=market&limit=50")
    pub_urls = [item["url"] for item in r_pub.json()]
    assert payload["canonical_url"] in pub_urls, (
        "Published item (is_active=True) must appear in public /news"
    )

    # --- PATCH title edit ---
    r = await async_client.patch(
        f"/api/v1/admin/news/{item_id}",
        json={"title": "AMFI SIP data: updated headline"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "AMFI SIP data: updated headline"

    # --- PATCH is_active=false → withdrawn from public /news (re-draft) ---
    r = await async_client.patch(
        f"/api/v1/admin/news/{item_id}",
        json={"is_active": False},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False

    r_pub = await async_client.get("/api/v1/news?scope=market&limit=50")
    pub_urls = [item["url"] for item in r_pub.json()]
    assert payload["canonical_url"] not in pub_urls, (
        "Withdrawn item (is_active=False) must disappear from public /news"
    )

    # Re-publish so the remaining lifecycle steps run against a live item.
    r = await async_client.patch(
        f"/api/v1/admin/news/{item_id}",
        json={"is_active": True},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    # --- Duplicate URL POST → 409 ---
    r = await async_client.post("/api/v1/admin/news", json=payload, headers=headers)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "news_url_exists"

    # --- Advisory title POST → 400 ---
    advisory_payload = {**payload, "canonical_url": "https://amfiindia.com/advisory", "title": "Buy these 5 funds now"}
    r = await async_client.post("/api/v1/admin/news", json=advisory_payload, headers=headers)
    assert r.status_code == 400, r.text
    assert "advisory_title_rejected" in r.json()["detail"]

    # --- Malformed item_id PATCH → 404 (not 422) ---
    r = await async_client.patch(
        "/api/v1/admin/news/not-a-uuid",
        json={"title": "Ignored"},
        headers=headers,
    )
    assert r.status_code == 404, r.text

    # --- Malformed item_id DELETE → 404 (not 422) ---
    r = await async_client.delete("/api/v1/admin/news/not-a-uuid", headers=headers)
    assert r.status_code == 404, r.text

    # --- DELETE → 204 ---
    r = await async_client.delete(f"/api/v1/admin/news/{item_id}", headers=headers)
    assert r.status_code == 204, r.text

    # --- Item gone from admin list ---
    r = await async_client.get("/api/v1/admin/news", headers=headers)
    assert r.status_code == 200, r.text
    ids_in_list = [item["id"] for item in r.json()]
    assert item_id not in ids_in_list, "Deleted item must not appear in admin list"


# ---------------------------------------------------------------------------
# 4. Admin list shows inactive items (no recency cutoff)
# ---------------------------------------------------------------------------


async def test_admin_list_shows_inactive_items(
    async_client, db_session, monkeypatch, patch_redis
):
    """Admin GET list returns inactive drafts that the public endpoint would never serve."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_news_list@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    monkeypatch.setattr(_db_mod, "engine", db_session.bind)
    headers = make_auth_headers(access_token=access)

    # Create a draft item.
    r = await async_client.post(
        "/api/v1/admin/news",
        json={
            "title": "Draft item — not yet published",
            "source": "SEBI",
            "canonical_url": "https://sebi.gov.in/draft-test-item",
            "category": "regulation",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    item_id = r.json()["id"]

    # Verify it is NOT in the public feed.
    r_pub = await async_client.get("/api/v1/news?scope=market")
    pub_urls = [i["url"] for i in r_pub.json()]
    assert "https://sebi.gov.in/draft-test-item" not in pub_urls

    # Verify it IS in the admin list.
    r_admin = await async_client.get("/api/v1/admin/news", headers=headers)
    assert r_admin.status_code == 200, r_admin.text
    admin_ids = [i["id"] for i in r_admin.json()]
    assert item_id in admin_ids, "Draft item must appear in admin list"


# ---------------------------------------------------------------------------
# 5. Empty-body PATCH → 400 no_fields_to_update
# ---------------------------------------------------------------------------


async def test_patch_empty_body_400(async_client, db_session, monkeypatch, patch_redis):
    """A PATCH with no fields set must return 400 no_fields_to_update."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_news_empty_patch@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    monkeypatch.setattr(_db_mod, "engine", db_session.bind)
    headers = make_auth_headers(access_token=access)

    r = await async_client.post(
        "/api/v1/admin/news",
        json={
            "title": "Valid item",
            "source": "AMFI",
            "canonical_url": "https://amfiindia.com/empty-patch-test",
            "category": "mutual_funds",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    item_id = r.json()["id"]

    r = await async_client.patch(
        f"/api/v1/admin/news/{item_id}", json={}, headers=headers
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "no_fields_to_update"

    # Explicit null must be a 400 null_field — not an IntegrityError-mislabelled
    # 409 from the NOT-NULL constraint.
    r = await async_client.patch(
        f"/api/v1/admin/news/{item_id}", json={"title": None}, headers=headers
    )
    assert r.status_code == 400, r.text
    assert "null_field" in r.json()["detail"]


# ---------------------------------------------------------------------------
# 6. PATCH non-existent item_id → 404
# ---------------------------------------------------------------------------


async def test_patch_nonexistent_item_404(async_client, monkeypatch, patch_redis):
    """PATCH with a valid UUID that does not exist in DB → 404 news_item_not_found."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_news_patch_404@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    fake_id = str(uuid.uuid4())
    r = await async_client.patch(
        f"/api/v1/admin/news/{fake_id}",
        json={"title": "Does not matter"},
        headers=headers,
    )
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "news_item_not_found"
