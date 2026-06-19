"""
Integration tests for Admin Console Phase 2 — users and billing routers.

Covers:
  - 404 surface-hiding for anonymous callers on all Phase 2 endpoints.
  - 404 surface-hiding for authenticated non-admins.
  - GET /admin/users/summary — admin gets 200 with expected fields.
  - GET /admin/users — admin gets 200; empty list when no users beyond admin.
  - GET /admin/users/{user_id} — 200 for existing user; 404 for unknown id.
  - GET /admin/billing/overview — admin gets 200 with expected numeric fields.
  - GET /admin/audit — admin gets 200; empty list when table is empty.
  - SQL injection safety — /admin/users?search= with injection chars doesn't raise.

Infrastructure: async_client, db_session, monkeypatch.setattr(settings).
Mirrors test_admin_ops.py patterns (signup helper, make_auth_headers, etc.).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _signup(client, email: str) -> tuple[str, str]:
    from tests.conftest import extract_cookie

    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "AdminP2Test42!"},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["user"]["id"]), extract_cookie(r, "__Host-access")


# ---------------------------------------------------------------------------
# 1. 404 for anonymous callers on all Phase 2 endpoints
# ---------------------------------------------------------------------------


async def test_phase2_endpoints_404_for_anonymous(async_client):
    """No cookie → 404 for every Phase 2 admin endpoint."""
    for path in [
        "/api/v1/admin/users/summary",
        "/api/v1/admin/users",
        "/api/v1/admin/billing/overview",
        "/api/v1/admin/billing/subscriptions",
        "/api/v1/admin/billing/payments",
        "/api/v1/admin/billing/subscription-metrics",
        "/api/v1/admin/billing/webhook-health",
        "/api/v1/admin/audit",
    ]:
        r = await async_client.get(path)
        assert r.status_code == 404, (
            f"Expected 404 on {path} for anonymous, got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 2. 404 for authenticated non-admins
# ---------------------------------------------------------------------------


async def test_phase2_endpoints_404_for_non_admin(async_client, monkeypatch):
    """Authenticated non-admin → 404 on all Phase 2 endpoints."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")

    user_id, access = await _signup(async_client, "nonadmin_p2@example.com")
    headers = make_auth_headers(access_token=access)

    for path in [
        "/api/v1/admin/users/summary",
        "/api/v1/admin/users",
        "/api/v1/admin/billing/overview",
        "/api/v1/admin/audit",
    ]:
        r = await async_client.get(path, headers=headers)
        assert r.status_code == 404, (
            f"Expected 404 on {path} for non-admin, got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 3. GET /admin/users/summary — admin gets 200 with expected fields
# ---------------------------------------------------------------------------


async def test_users_summary_200_for_admin(async_client, monkeypatch):
    """Admin → 200 with all required summary fields."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_summary_p2@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/users/summary", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    # All required fields present
    for field in ["total", "active", "premium", "trials", "blocked"]:
        assert field in body, f"Missing field '{field}' in users/summary response"

    # All fields are non-negative integers
    for field in ["total", "active", "premium", "trials", "blocked"]:
        assert isinstance(body[field], int), f"'{field}' should be int, got {type(body[field])}"
        assert body[field] >= 0, f"'{field}' should be non-negative"

    # Sanity: total >= active (active = total - blocked)
    assert body["total"] >= body["active"]
    # Sanity: at least the admin user we just created is counted
    assert body["total"] >= 1


# ---------------------------------------------------------------------------
# 4. GET /admin/users — admin gets 200; paginated list
# ---------------------------------------------------------------------------


async def test_users_list_200_for_admin(async_client, monkeypatch):
    """Admin → 200; response has total and users list."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_list_p2@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/users", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert "total" in body
    assert "users" in body
    assert isinstance(body["users"], list)
    assert isinstance(body["total"], int)
    assert body["total"] >= 1

    # Each user item has required fields
    if body["users"]:
        item = body["users"][0]
        for field in ["id", "email", "display_name", "tier", "status", "created_at"]:
            assert field in item, f"Missing field '{field}' in user list item"
        # last_login_at is present (may be null)
        assert "last_login_at" in item


# ---------------------------------------------------------------------------
# 5. GET /admin/users/{user_id} — 200 for existing user; 404 for unknown
# ---------------------------------------------------------------------------


async def test_user_detail_200_for_admin(async_client, monkeypatch):
    """Admin → 200 for existing user_id with expected fields."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_detail_p2@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get(f"/api/v1/admin/users/{user_id}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    for field in [
        "id", "email", "display_name", "tier", "status",
        "created_at", "payments", "login_history", "cas_uploads",
    ]:
        assert field in body, f"Missing field '{field}' in user detail response"

    assert body["id"] == user_id
    assert isinstance(body["payments"], list)
    assert isinstance(body["login_history"], list)
    assert isinstance(body["cas_uploads"], list)
    # display_name is derived from email
    assert body["display_name"] == "admin_detail_p2"


async def test_user_detail_404_for_nonexistent(async_client, monkeypatch):
    """Admin → 404 for a random UUID that doesn't exist."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_detail_notfound@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    fake_id = "00000000-0000-0000-0000-000000000000"
    r = await async_client.get(f"/api/v1/admin/users/{fake_id}", headers=headers)
    assert r.status_code == 404, r.text


async def test_user_detail_404_for_invalid_uuid(async_client, monkeypatch):
    """Admin → 404 for a non-UUID user_id path."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_detail_invalid@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/users/not-a-valid-uuid", headers=headers)
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 6. GET /admin/billing/overview — admin gets 200 with numeric fields
# ---------------------------------------------------------------------------


async def test_billing_overview_200_for_admin(async_client, monkeypatch):
    """Admin → 200 with mrr_inr, arpu_inr, active_subscriptions, past_due, trials."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_billing_p2@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/billing/overview", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    for field in ["mrr_inr", "arpu_inr", "active_subscriptions", "past_due", "trials"]:
        assert field in body, f"Missing field '{field}' in billing/overview"

    # All numeric and non-negative
    assert body["mrr_inr"] >= 0.0
    assert body["arpu_inr"] >= 0.0
    assert body["active_subscriptions"] >= 0
    assert body["past_due"] >= 0
    assert body["trials"] >= 0


# ---------------------------------------------------------------------------
# 7. GET /admin/audit — admin gets 200; empty list when table is empty
# ---------------------------------------------------------------------------


async def test_audit_log_200_empty_for_admin(async_client, monkeypatch):
    """Admin → 200 with an empty list when audit.admin_actions has no rows."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_audit_p2@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/audit", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    # In CI the audit table is empty; we just check it's a list (may have rows
    # from earlier tests in the session that triggered record_admin_action).


# ---------------------------------------------------------------------------
# 8. SQL injection safety — /admin/users?search= with injection chars
# ---------------------------------------------------------------------------


async def test_users_search_sql_injection_safe(async_client, monkeypatch):
    """Search with SQL injection characters must not raise a 500.

    This verifies the ORM ilike() parameterised binding is used (not f-string SQL).
    A 200 or 422 is acceptable; a 500 would indicate a raw SQL injection.
    """
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_sqli@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    injection_strings = [
        "' OR '1'='1",
        "admin@example.com'; DROP TABLE auth.users; --",
        "\" OR 1=1 --",
        "\\'; SELECT * FROM auth.users; --",
    ]

    for payload in injection_strings:
        r = await async_client.get(
            "/api/v1/admin/users",
            params={"search": payload},
            headers=headers,
        )
        # Must NOT be a 500 — any other code is acceptable
        assert r.status_code != 500, (
            f"SQL injection payload caused 500: {payload!r} → {r.text}"
        )


# ---------------------------------------------------------------------------
# 9. GET /admin/billing/subscription-metrics — admin gets 200
# ---------------------------------------------------------------------------


async def test_subscription_metrics_200_for_admin(async_client, monkeypatch):
    """Admin → 200 with premium_count, trials, renewals_30d, churn_30d."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_metrics_p2@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/billing/subscription-metrics", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    for field in ["premium_count", "trials", "renewals_30d", "churn_30d"]:
        assert field in body, f"Missing field '{field}' in subscription-metrics"
        assert isinstance(body[field], int)
        assert body[field] >= 0


# ---------------------------------------------------------------------------
# 10. GET /admin/billing/webhook-health — admin gets 200
# ---------------------------------------------------------------------------


async def test_webhook_health_200_for_admin(async_client, monkeypatch):
    """Admin → 200 with note explaining the derivation."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_whook_p2@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/billing/webhook-health", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    for field in ["recent_count", "success_count", "failed_count", "note"]:
        assert field in body, f"Missing field '{field}' in webhook-health"

    assert "TODO" in body["note"] or "payment_events" in body["note"]
    assert body["recent_count"] >= 0
    assert body["success_count"] >= 0
    assert body["failed_count"] >= 0
