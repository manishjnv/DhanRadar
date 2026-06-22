"""
Integration tests for the Admin Ops router (Admin Console Phase 1).

Covers:
  - 404 surface-hiding for anonymous callers on all new ops endpoints.
  - 404 surface-hiding for authenticated non-admins.
  - GET /admin/health → 200 for admin; fields present.
  - GET /admin/sources → 200 for admin; returns a list.
  - GET /admin/tasks → 200 for admin; returns a list with known task keys.
  - GET /admin/runs → 200 for admin; empty list when table is empty.
  - GET /admin/runs/{run_id} → 404 for non-existent run_id.
  - GET /admin/quality → 200 for admin; empty list when table is empty.
  - GET /auth/me → is_admin=True for admin user; is_admin=False for non-admin.

Infrastructure: async_client, db_session, patch_redis, monkeypatch.setattr(settings).

NOTE: POST /sources/{source_key}/sync and POST /tasks/{task_name}/trigger are NOT
tested here — they call celery_app.send_task() which requires a broker. They are
covered by manual smoke tests and the existing celery task-registration unit tests.
POST /sources/pause|resume and /tasks/pause|resume use fake_redis (patch_redis).
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
        json={"email": email, "password": "AdminOps42!"},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["user"]["id"]), extract_cookie(r, "__Host-access")


# ---------------------------------------------------------------------------
# 1. 404 for anonymous callers on all new ops endpoints
# ---------------------------------------------------------------------------


async def test_ops_endpoints_404_for_anonymous(async_client):
    """No cookie → 404 for every new admin ops endpoint."""
    for path in [
        "/api/v1/admin/health",
        "/api/v1/admin/alerts",
        "/api/v1/admin/sources",
        "/api/v1/admin/tasks",
        "/api/v1/admin/runs",
        "/api/v1/admin/quality",
    ]:
        r = await async_client.get(path)
        assert r.status_code == 404, f"Expected 404 on {path}, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# 2. 404 for authenticated non-admins
# ---------------------------------------------------------------------------


async def test_ops_endpoints_404_for_non_admin(async_client, monkeypatch):
    """Authenticated non-admin → 404 on all ops endpoints."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")

    user_id, access = await _signup(async_client, "nonadmin_ops@example.com")
    headers = make_auth_headers(access_token=access)

    for path in [
        "/api/v1/admin/health",
        "/api/v1/admin/alerts",
        "/api/v1/admin/sources",
        "/api/v1/admin/tasks",
        "/api/v1/admin/runs",
        "/api/v1/admin/quality",
    ]:
        r = await async_client.get(path, headers=headers)
        assert r.status_code == 404, f"Expected 404 on {path}, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# 3. GET /admin/health — admin gets 200 with expected fields
# ---------------------------------------------------------------------------


async def test_health_200_for_admin(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_health@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/health", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    # All required fields must be present
    assert "sources_healthy" in body
    assert "sources_total" in body
    assert "last_nav_sync" in body
    assert "total_schemes" in body
    assert "active_users" in body
    assert "premium_users" in body
    assert "advice_boundary_breaches_today" in body
    assert "low_groundedness_flags_7d" in body
    assert isinstance(body["recent_failures"], list)
    assert isinstance(body["recent_signups"], list)
    assert isinstance(body["recent_alerts"], list)

    # Deferred signals must be 0 (TODO in ops_router.py)
    assert body["advice_boundary_breaches_today"] == 0
    assert body["low_groundedness_flags_7d"] == 0


# ---------------------------------------------------------------------------
# 3b. GET /admin/alerts — admin gets 200 with a derived-alerts envelope
# ---------------------------------------------------------------------------


async def test_alerts_200_for_admin(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_alerts@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/alerts", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["alerts"], list)
    assert body["count"] == len(body["alerts"])
    # With no mood snapshot computed in the test DB, the 'mood_missing' alert fires.
    keys = {a["key"] for a in body["alerts"]}
    assert "mood_missing" in keys
    for a in body["alerts"]:
        assert a["severity"] in {"critical", "warning", "info"}
        assert a["title"] and a["detail"]


# ---------------------------------------------------------------------------
# 4. GET /admin/sources — admin gets 200 with a non-empty list
# ---------------------------------------------------------------------------


async def test_sources_200_for_admin(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_sources@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/sources", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    assert len(body) > 0

    # Each entry has the required fields
    entry = body[0]
    for field in ["source_key", "name", "tier", "description", "method",
                  "schedule_display", "cost", "last_success_at", "last_records",
                  "status", "paused"]:
        assert field in entry, f"Missing field {field} in source entry"

    # AMFI NAV should always be in the catalog
    source_keys = [e["source_key"] for e in body]
    assert "amfi_nav" in source_keys


# ---------------------------------------------------------------------------
# 5. GET /admin/tasks — admin gets 200 with known task names
# ---------------------------------------------------------------------------


async def test_tasks_200_for_admin(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_tasks@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/tasks", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    assert len(body) > 0

    task_names = [t["task_name"] for t in body]
    assert "dhanradar.tasks.mf.nav_daily_fetch" in task_names
    assert "dhanradar.tasks.mf.mf_metrics_refresh" in task_names


# ---------------------------------------------------------------------------
# 6. GET /admin/runs — admin gets 200; empty list when table is empty
# ---------------------------------------------------------------------------


async def test_runs_200_empty_for_admin(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_runs@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/runs", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == []


# ---------------------------------------------------------------------------
# 7. GET /admin/runs/{run_id} — 404 for non-existent run_id
# ---------------------------------------------------------------------------


async def test_run_detail_404_for_missing(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_run_detail@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/runs/999999999", headers=headers)
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "run_not_found"


# ---------------------------------------------------------------------------
# 8. GET /admin/quality — admin gets 200; empty list when table is empty
# ---------------------------------------------------------------------------


async def test_quality_200_empty_for_admin(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_quality@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/quality", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == []


# ---------------------------------------------------------------------------
# 9. Source pause/resume via Redis — 200 for admin; 404 for unknown source
# ---------------------------------------------------------------------------


async def test_source_pause_resume(async_client, monkeypatch, patch_redis):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_pause@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.post("/api/v1/admin/sources/amfi_nav/pause", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    r = await async_client.post("/api/v1/admin/sources/amfi_nav/resume", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


async def test_source_pause_404_unknown(async_client, monkeypatch, patch_redis):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_pause_unk@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.post("/api/v1/admin/sources/nonexistent_source/pause", headers=headers)
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 10. GET /auth/me — is_admin field
# ---------------------------------------------------------------------------


async def test_me_is_admin_true_for_admin(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_me_true@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["user"]["is_admin"] is True


async def test_me_is_admin_false_for_non_admin(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "nonadmin_me@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")  # empty allowlist
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["user"]["is_admin"] is False
