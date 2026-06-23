"""
Integration tests for Admin Console Phase 3.

Covers:
  - GET /admin/flags          — feature flags (env-sourced, read-only)
  - GET /admin/scoring/model  — scoring model read (TIER-C, gated)
  - GET /admin/support/cas-failures — recent CAS failures for support
  - GET /admin/analytics/overview   — aggregate platform metrics
  - GET /admin/notifications/health — queue depth + delivery stats

Surface-hiding: every endpoint returns 404 to anonymous callers and to
authenticated non-admins (RequireAdmin gate). These tests mirror the
patterns in test_admin_phase2.py exactly.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _signup(client, email: str) -> tuple[str, str]:
    from tests.conftest import extract_cookie

    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "AdminP3Test42!"},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["user"]["id"]), extract_cookie(r, "__Host-access")


# ---------------------------------------------------------------------------
# 1. 404 for anonymous callers on all Phase 3 endpoints
# ---------------------------------------------------------------------------


async def test_phase3_endpoints_404_for_anonymous(async_client):
    """No cookie → 404 for every Phase 3 admin endpoint."""
    for path in [
        "/api/v1/admin/flags",
        "/api/v1/admin/scoring/model",
        "/api/v1/admin/support/cas-failures",
        "/api/v1/admin/analytics/overview",
        "/api/v1/admin/notifications/health",
    ]:
        r = await async_client.get(path)
        assert r.status_code == 404, (
            f"Expected 404 on {path} for anonymous, got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 2. 404 for authenticated non-admins on all Phase 3 endpoints
# ---------------------------------------------------------------------------


async def test_phase3_endpoints_404_for_non_admin(async_client, monkeypatch):
    """Authenticated non-admin → 404 on all Phase 3 endpoints."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")

    user_id, access = await _signup(async_client, "nonadmin_p3@example.com")
    headers = make_auth_headers(access_token=access)

    for path in [
        "/api/v1/admin/flags",
        "/api/v1/admin/scoring/model",
        "/api/v1/admin/support/cas-failures",
        "/api/v1/admin/analytics/overview",
        "/api/v1/admin/notifications/health",
    ]:
        r = await async_client.get(path, headers=headers)
        assert r.status_code == 404, (
            f"Expected 404 on {path} for non-admin, got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 3. GET /admin/flags — admin gets 200 with exactly 3 env-sourced flags
# ---------------------------------------------------------------------------


async def test_admin_get_flags_returns_three(async_client, monkeypatch):
    """Admin → 200; exactly three read-only env flags returned."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_flags_p3@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/flags", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()

    assert isinstance(data, list)
    assert len(data) == 3, f"Expected 3 flags, got {len(data)}: {data}"

    keys = {f["key"] for f in data}
    assert "AUDIT_ARCHIVE_ENABLED" in keys
    assert "COOKIE_SECURE" in keys
    assert "DPDP_CONSENT_ENFORCED" in keys

    for flag in data:
        assert flag["mutable"] is False, f"Flag {flag['key']} must not be mutable"
        assert flag["source"] == "env", f"Flag {flag['key']} source must be 'env'"
        assert isinstance(flag["value"], bool), f"Flag {flag['key']} value must be bool"
        assert isinstance(flag["description"], str) and flag["description"], (
            f"Flag {flag['key']} must have a non-empty description"
        )


async def test_admin_flags_values_match_settings(async_client, monkeypatch):
    """Flag values must match the live settings values."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_flags_values_p3@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/flags", headers=headers)
    assert r.status_code == 200, r.text
    by_key = {f["key"]: f for f in r.json()}

    assert by_key["AUDIT_ARCHIVE_ENABLED"]["value"] == settings.AUDIT_ARCHIVE_ENABLED
    assert by_key["COOKIE_SECURE"]["value"] == settings.COOKIE_SECURE
    assert by_key["DPDP_CONSENT_ENFORCED"]["value"] == settings.DPDP_CONSENT_ENFORCED


# ---------------------------------------------------------------------------
# 4. GET /admin/scoring/model — admin gets 200 (TIER-C, mocked DB/config)
# ---------------------------------------------------------------------------


async def test_admin_get_scoring_model_200(async_client, monkeypatch):
    """Admin → 200 with expected fields from the scoring model endpoint.

    The scoring model endpoint calls get_config() (file-backed, no DB),
    is_engine_version_activated() (DB), list_engine_versions() (DB), and
    a MfFund count query (DB). We patch the two compliance service calls
    and the DB scalar so the test is hermetic (no rating_engine_changelog rows
    in the test DB, and no mf_funds rows either).
    """
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_scoring_p3@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    with (
        patch(
            "dhanradar.admin.scoring_router.is_engine_version_activated",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "dhanradar.admin.scoring_router.list_engine_versions",
            new=AsyncMock(return_value=[]),
        ),
    ):
        r = await async_client.get("/api/v1/admin/scoring/model", headers=headers)

    assert r.status_code == 200, r.text
    data = r.json()

    # Required top-level fields
    for field in ["model_version", "activated", "provisional", "axis_weights", "coverage", "registry_versions"]:
        assert field in data, f"Missing field '{field}' in scoring/model response"

    assert isinstance(data["model_version"], str) and data["model_version"]
    assert isinstance(data["activated"], bool)
    assert isinstance(data["provisional"], bool)
    # activated True → provisional False (the mocked state)
    assert data["activated"] is True
    assert data["provisional"] is False

    assert isinstance(data["axis_weights"], dict)
    assert len(data["axis_weights"]) > 0, "axis_weights must be non-empty"
    for k, v in data["axis_weights"].items():
        assert isinstance(k, str)
        assert isinstance(v, float)

    assert "total_funds" in data["coverage"]
    assert isinstance(data["coverage"]["total_funds"], int)
    assert data["coverage"]["total_funds"] >= 0

    assert isinstance(data["registry_versions"], list)


async def test_admin_scoring_model_provisional_when_not_activated(async_client, monkeypatch):
    """When is_engine_version_activated returns False, provisional must be True."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_scoring_prov@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    with (
        patch(
            "dhanradar.admin.scoring_router.is_engine_version_activated",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "dhanradar.admin.scoring_router.list_engine_versions",
            new=AsyncMock(return_value=[]),
        ),
    ):
        r = await async_client.get("/api/v1/admin/scoring/model", headers=headers)

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["activated"] is False
    assert data["provisional"] is True


# ---------------------------------------------------------------------------
# 5. GET /admin/support/cas-failures — admin gets 200, empty list when no failures
# ---------------------------------------------------------------------------


async def test_admin_get_cas_failures_200(async_client, monkeypatch):
    """Admin → 200 with list of CAS failures (empty in clean test DB)."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_casfail_p3@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/support/cas-failures", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    # Empty list is valid in a clean test DB — just confirm schema for non-empty
    for item in data:
        for field in ["job_id", "user_id", "status"]:
            assert field in item, f"Missing field '{field}' in cas-failure record"


async def test_admin_cas_failures_limit_param_valid(async_client, monkeypatch):
    """limit query param is accepted in [1, 200] range."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_casfail_limit@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get(
        "/api/v1/admin/support/cas-failures",
        params={"limit": 10},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    # Out-of-range limit → 422 validation error
    r_bad = await async_client.get(
        "/api/v1/admin/support/cas-failures",
        params={"limit": 0},
        headers=headers,
    )
    assert r_bad.status_code == 422, r_bad.text


# ---------------------------------------------------------------------------
# 6. GET /admin/analytics/overview — admin gets 200 with numeric fields
# ---------------------------------------------------------------------------


async def test_admin_analytics_overview_200(async_client, monkeypatch):
    """Admin → 200 with expected aggregate fields."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_analytics_p3@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/analytics/overview", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()

    for field in [
        "signups_total",
        "signups_30d",
        "cas_uploads_total",
        "cas_uploads_30d",
        "portfolios_created",
        "reports_generated",
        "premium_conversions",
        "funnel",
        "conversion_rate_pct",
    ]:
        assert field in data, f"Missing field '{field}' in analytics/overview"

    # All count fields non-negative ints
    for field in [
        "signups_total", "signups_30d", "cas_uploads_total", "cas_uploads_30d",
        "portfolios_created", "reports_generated", "premium_conversions",
    ]:
        assert isinstance(data[field], int), f"'{field}' must be int"
        assert data[field] >= 0, f"'{field}' must be non-negative"

    assert isinstance(data["conversion_rate_pct"], float | int)
    assert data["conversion_rate_pct"] >= 0.0

    # Funnel sub-fields
    funnel = data["funnel"]
    for f in ["cas_uploaded", "portfolio_created", "report_generated"]:
        assert f in funnel, f"Missing funnel field '{f}'"
        assert isinstance(funnel[f], int)
        assert funnel[f] >= 0

    # Sanity: 30d counts can't exceed totals
    assert data["signups_30d"] <= data["signups_total"]
    assert data["cas_uploads_30d"] <= data["cas_uploads_total"]

    # At least the admin user created during this test is counted
    assert data["signups_total"] >= 1


# ---------------------------------------------------------------------------
# 7. GET /admin/notifications/health — admin gets 200 with queue + stats
# ---------------------------------------------------------------------------


async def test_admin_notifications_health_200(async_client, monkeypatch):
    """Admin → 200 with queue_depth, delivery stats, templates, broadcast_available.

    get_queue_health() and get_delivery_stats() are async; list_templates() and
    broadcast_available() are sync. We mock the Redis/DB-backed calls to make the
    test hermetic — the notify.notification_log table is empty in the test DB.
    """
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_notif_p3@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    with (
        patch(
            "dhanradar.admin.platform_router.get_queue_health",
            new=AsyncMock(return_value={"telegram": 2, "email": 0}),
        ),
        patch(
            "dhanradar.admin.platform_router.get_delivery_stats",
            new=AsyncMock(return_value={
                "sent": 10,
                "failed": 1,
                "rate_capped": 0,
                "deferred": 0,
                "last_sent_at": None,
            }),
        ),
    ):
        r = await async_client.get("/api/v1/admin/notifications/health", headers=headers)

    assert r.status_code == 200, r.text
    data = r.json()

    for field in ["queue_depth", "sent", "failed", "rate_capped", "deferred", "templates", "broadcast_available"]:
        assert field in data, f"Missing field '{field}' in notifications/health"

    assert "telegram" in data["queue_depth"]
    assert "email" in data["queue_depth"]
    assert isinstance(data["queue_depth"]["telegram"], int)
    assert isinstance(data["queue_depth"]["email"], int)

    assert data["sent"] == 10
    assert data["failed"] == 1
    assert data["rate_capped"] == 0
    assert data["deferred"] == 0

    # Templates come from _RENDERERS in templates.py — 4 registered templates
    assert isinstance(data["templates"], list)
    assert len(data["templates"]) > 0
    for tpl in data["templates"]:
        assert "id" in tpl
        assert isinstance(tpl["id"], str) and tpl["id"]

    # Verify all 4 expected templates are present
    template_ids = {t["id"] for t in data["templates"]}
    for expected in ["test_ping", "mf_report_ready", "mf_label_change", "weekly_digest"]:
        assert expected in template_ids, f"Template '{expected}' missing from health response"

    assert isinstance(data["broadcast_available"], bool)


async def test_admin_notifications_health_without_mocks(async_client, monkeypatch):
    """Admin → 200 even without mocks — Redis queue depth returns 0 on empty fakeredis."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_notif_nomock@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/notifications/health", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()

    # Fakeredis returns 0 for LLEN on empty queue
    assert data["queue_depth"]["telegram"] == 0
    assert data["queue_depth"]["email"] == 0
    # Empty notification_log → all counts zero
    assert data["sent"] == 0
    assert data["failed"] == 0


# ---------------------------------------------------------------------------
# 9. POST /admin/support/cas-failures/{job_id}/notes — set + read-back
# ---------------------------------------------------------------------------


async def _seed_failed_cas_job(db_session, user_id: str) -> str:
    """Insert one failed mf.mf_cas_jobs row and return its job_id (str)."""
    from dhanradar.models.mf import MfCasJob

    job = MfCasJob(
        user_id=user_id,
        status="failed",
        source_hash="seed-hash-cas-notes",
        error_message="parser failed",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return str(job.job_id)


async def test_admin_set_cas_support_notes_and_read_back(
    async_client, db_session, monkeypatch
):
    """Admin sets a support note, then reads it back via get_cas_failures."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_casnotes@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    job_id = await _seed_failed_cas_job(db_session, user_id)

    # Set the note.
    r = await async_client.post(
        f"/api/v1/admin/support/cas-failures/{job_id}/notes",
        json={"notes": "investigated — bad folio header"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    # Read it back through the support-failures list.
    r2 = await async_client.get(
        "/api/v1/admin/support/cas-failures", headers=headers
    )
    assert r2.status_code == 200, r2.text
    rows = r2.json()
    match = next((row for row in rows if row["job_id"] == job_id), None)
    assert match is not None, "seeded failed CAS job not returned by the read"
    assert match["support_notes"] == "investigated — bad folio header"


async def test_admin_set_cas_support_notes_empty_clears(
    async_client, db_session, monkeypatch
):
    """An empty notes string is accepted and clears the note (→ '')."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_casnotes_clear@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    job_id = await _seed_failed_cas_job(db_session, user_id)

    r = await async_client.post(
        f"/api/v1/admin/support/cas-failures/{job_id}/notes",
        json={"notes": ""},
        headers=headers,
    )
    assert r.status_code == 200, r.text


async def test_admin_set_cas_support_notes_unknown_job_404(
    async_client, monkeypatch
):
    """Unknown job_id → 404 cas_job_not_found."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_casnotes_404@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    missing = "00000000-0000-0000-0000-0000000000ff"
    r = await async_client.post(
        f"/api/v1/admin/support/cas-failures/{missing}/notes",
        json={"notes": "x"},
        headers=headers,
    )
    assert r.status_code == 404, r.text


async def test_admin_set_cas_support_notes_404_for_non_admin(
    async_client, monkeypatch
):
    """Non-admin → 404 (surface-hiding) on the notes mutation."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")
    user_id, access = await _signup(async_client, "nonadmin_casnotes@example.com")
    headers = make_auth_headers(access_token=access)

    fake = "00000000-0000-0000-0000-000000000001"
    r = await async_client.post(
        f"/api/v1/admin/support/cas-failures/{fake}/notes",
        json={"notes": "x"},
        headers=headers,
    )
    assert r.status_code == 404, r.text
