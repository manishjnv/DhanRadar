"""
Integration tests for auth.user_activity_log (migration 0045).

Covers:
  (1) A password login creates a user_activity_log row with method='password'.
  (2) GET /admin/users/{user_id} returns login_history with the event.
  (3) GET /admin/users/activity returns recent events with email field.
  (4) GET /admin/users/activity is 404 for anonymous and non-admin callers.

These tests require a live Postgres DB (CI only — skipped locally).
They run in the integration pytest mark group and use the shared async_client
+ db_session fixtures from conftest.py.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers (mirrors test_admin_phase2.py patterns)
# ---------------------------------------------------------------------------


async def _signup(client, email: str) -> tuple[str, str]:
    from tests.conftest import extract_cookie

    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "ActivityLogTest42!"},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["user"]["id"]), extract_cookie(r, "__Host-access")


async def _login(client, email: str) -> str:
    from tests.conftest import extract_cookie

    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "ActivityLogTest42!"},
    )
    assert r.status_code == 200, r.text
    return extract_cookie(r, "__Host-access")


# ---------------------------------------------------------------------------
# (1) Login creates a user_activity_log row
# ---------------------------------------------------------------------------


async def test_password_login_creates_activity_log_row(async_client, db_session):
    """After a successful password login, auth.user_activity_log has a row
    with event_type='login' and method='password' for that user."""
    from uuid import UUID

    from dhanradar.models.auth import UserActivityLog

    email = "actlog_login@example.com"
    user_id_str, _ = await _signup(async_client, email)
    uid = UUID(user_id_str)

    # Perform a genuine login (not signup — signup doesn't call record_login)
    await _login(async_client, email)

    rows = (
        await db_session.execute(
            select(UserActivityLog)
            .where(UserActivityLog.user_id == uid)
            .order_by(UserActivityLog.occurred_at.desc())
        )
    ).scalars().all()

    assert len(rows) >= 1, "Expected at least one activity log row after login"
    latest = rows[0]
    assert latest.event_type == "login"
    assert latest.method == "password"


# ---------------------------------------------------------------------------
# (2) GET /admin/users/{user_id} returns login_history with the event
# ---------------------------------------------------------------------------


async def test_user_detail_login_history_populated(async_client, db_session, monkeypatch):
    """GET /admin/users/{user_id} must return login_history with at least one
    entry after the user has logged in."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    email = "actlog_detail@example.com"
    user_id_str, _ = await _signup(async_client, email)

    # Make caller an admin
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id_str)
    admin_access = await _login(async_client, email)
    headers = make_auth_headers(access_token=admin_access)

    r = await async_client.get(
        f"/api/v1/admin/users/{user_id_str}", headers=headers
    )
    assert r.status_code == 200, r.text
    body = r.json()

    assert "login_history" in body
    assert isinstance(body["login_history"], list)
    assert len(body["login_history"]) >= 1, (
        "Expected at least one login_history entry after login"
    )
    entry = body["login_history"][0]
    assert entry["event_type"] == "login"
    assert entry["method"] == "password"
    assert "occurred_at" in entry


# ---------------------------------------------------------------------------
# (3) GET /admin/users/activity returns recent events with email
# ---------------------------------------------------------------------------


async def test_recent_activity_feed(async_client, monkeypatch):
    """GET /admin/users/activity returns a list of ActivityEventRow objects
    including user_id, email, event_type, method, occurred_at."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    email = "actlog_feed@example.com"
    user_id_str, _ = await _signup(async_client, email)

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id_str)
    admin_access = await _login(async_client, email)
    headers = make_auth_headers(access_token=admin_access)

    r = await async_client.get("/api/v1/admin/users/activity", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1, "Expected at least one activity row"

    # Find a row for this user
    my_rows = [row for row in rows if row["user_id"] == user_id_str]
    assert my_rows, f"No activity row found for {user_id_str} in {rows}"

    row = my_rows[0]
    assert row["email"] == email
    assert row["event_type"] == "login"
    assert row["method"] == "password"
    assert "occurred_at" in row


# ---------------------------------------------------------------------------
# (4) /admin/users/activity is 404 for anonymous and non-admin
# ---------------------------------------------------------------------------


async def test_activity_endpoint_404_for_anonymous(async_client):
    """No auth cookie → 404 (surface-hiding)."""
    r = await async_client.get("/api/v1/admin/users/activity")
    assert r.status_code == 404, r.text


async def test_activity_endpoint_404_for_non_admin(async_client, monkeypatch):
    """Authenticated non-admin → 404."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")
    email = "actlog_nonadmin@example.com"
    _, access = await _signup(async_client, email)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/users/activity", headers=headers)
    assert r.status_code == 404, r.text
