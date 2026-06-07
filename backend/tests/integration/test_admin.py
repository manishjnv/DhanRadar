"""
Integration tests for the Admin compliance module (B26).

Covers:
  - 404 surface-hiding for anonymous callers (no cookie).
  - 404 surface-hiding for authenticated non-admins.
  - POST /admin/disclaimers → 201 (create INACTIVE); single-active invariant via activate.
  - POST /admin/disclaimers/{version}/activate → 200; snapshot_status skipped_r2_unconfigured.
  - activate unknown version → 404.
  - create duplicate version → 409.
  - GET /admin/audit/label-churn → insufficient_data when audit table empty.
  - GET /admin/audit/label-churn → pending_publish + requires_human_review=True when >5% churn.

Infrastructure contract:
  - async_client, db_session, patch_redis, patch_settings_keys (from conftest).
  - monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id) to promote a user to admin.
  - monkeypatch.setattr(_db_mod, "engine", db_session.bind) for own-session service paths.
  - __Host- cookies extracted from raw Set-Cookie and re-injected manually.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

import dhanradar.db as _db_mod
from dhanradar.models.compliance import AiRecommendationAudit, Disclaimer

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Teardown: truncate all compliance + audit tables between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _truncate_admin(db_session):
    """Truncate compliance tables after each test — same-connection pattern as
    test_compliance._truncate_compliance to avoid cross-connection lock deadlocks."""
    yield
    await db_session.rollback()
    await db_session.execute(
        text(
            "TRUNCATE TABLE "
            "compliance.rating_engine_changelog, "
            "compliance.ai_low_confidence_log, "
            "compliance.ai_recommendation_audit, "
            "compliance.disclaimers "
            "RESTART IDENTITY CASCADE"
        )
    )
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


# ---------------------------------------------------------------------------
# 1. 404 for anonymous callers
# ---------------------------------------------------------------------------


async def test_admin_endpoints_404_for_anonymous(async_client):
    """No cookie → 404 for POST /disclaimers and GET /audit/label-churn."""
    r = await async_client.post(
        "/api/v1/admin/disclaimers",
        json={"version": "2026-07-01.v1", "content": "test"},
    )
    assert r.status_code == 404, r.text

    r = await async_client.get("/api/v1/admin/audit/label-churn")
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 2. 404 for authenticated non-admins
# ---------------------------------------------------------------------------


async def test_admin_endpoints_404_for_non_admin(async_client, monkeypatch):
    """Authenticated non-admin (empty allowlist) → 404."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")

    user_id, access = await _signup(async_client, "nonadmin@example.com")
    headers = make_auth_headers(access_token=access)

    r = await async_client.post(
        "/api/v1/admin/disclaimers",
        json={"version": "2026-07-01.v1", "content": "test"},
        headers=headers,
    )
    assert r.status_code == 404, r.text

    r = await async_client.get("/api/v1/admin/audit/label-churn", headers=headers)
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 3. Create then activate disclaimer (single-active invariant)
# ---------------------------------------------------------------------------


async def test_create_then_activate_disclaimer(
    async_client, db_session, monkeypatch, patch_redis
):
    """Create v2 INACTIVE; activate it; old v1 must become inactive."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_activate@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    assert settings.admin_user_ids == frozenset({user_id})
    monkeypatch.setattr(_db_mod, "engine", db_session.bind)
    headers = make_auth_headers(access_token=access)

    # Seed an existing active v1 disclaimer directly.
    v1 = Disclaimer(
        version="2026-06-06.v1",
        type="ai_recommendation",
        content="Old disclaimer.",
        active=True,
    )
    db_session.add(v1)
    await db_session.commit()

    # POST create v2 → 201, active=False.
    r = await async_client.post(
        "/api/v1/admin/disclaimers",
        json={"version": "2026-07-01.v2", "content": "Educational only — not advice."},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["version"] == "2026-07-01.v2"
    assert body["active"] is False

    # POST activate v2 → 200, active=True.
    r = await async_client.post(
        "/api/v1/admin/disclaimers/2026-07-01.v2/activate",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["active"] is True
    assert body["version"] == "2026-07-01.v2"
    # R2 not configured in tests → skipped.
    assert body["snapshot_status"] == "skipped_r2_unconfigured"
    assert body["snapshot_key"] is None

    # Verify single-active invariant: v1 must now be inactive.
    await db_session.expire_all()
    from sqlalchemy import select
    rows = (await db_session.scalars(select(Disclaimer))).all()
    by_version = {r.version: r for r in rows}
    assert by_version["2026-07-01.v2"].active is True
    assert by_version["2026-06-06.v1"].active is False


# ---------------------------------------------------------------------------
# 4. Activate unknown version → 404
# ---------------------------------------------------------------------------


async def test_activate_unknown_version_404(async_client, monkeypatch, patch_redis):
    """Activating a non-existent version returns 404 disclaimer_not_found."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_notfound@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.post(
        "/api/v1/admin/disclaimers/9999-does-not-exist.v0/activate",
        headers=headers,
    )
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "disclaimer_not_found"


# ---------------------------------------------------------------------------
# 5. Create conflict → 409
# ---------------------------------------------------------------------------


async def test_create_conflict_409(async_client, monkeypatch, patch_redis):
    """Creating the same version twice returns 409 on the second request."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_conflict@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    payload = {"version": "2026-07-01.v3", "content": "Educational only — not advice."}

    r = await async_client.post("/api/v1/admin/disclaimers", json=payload, headers=headers)
    assert r.status_code == 201, r.text

    r = await async_client.post("/api/v1/admin/disclaimers", json=payload, headers=headers)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "disclaimer_version_exists"


# ---------------------------------------------------------------------------
# 6. Label churn — insufficient_data (empty audit table)
# ---------------------------------------------------------------------------


async def test_label_churn_insufficient_data(async_client, monkeypatch, patch_redis):
    """Empty audit table → 200, decision='insufficient_data', requires_human_review=False."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_churn_empty@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/audit/label-churn", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["decision"] == "insufficient_data"
    assert body["requires_human_review"] is False


# ---------------------------------------------------------------------------
# 7. Label churn — hold when >5% churn
# ---------------------------------------------------------------------------


async def test_label_churn_hold_over_threshold(
    async_client, db_session, monkeypatch, patch_redis
):
    """Seed 20 users on day1 as on_track; 3 switch to off_track on day2 (15% churn)
    → decision='pending_publish', requires_human_review=True."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_churn_hold@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    monkeypatch.setattr(_db_mod, "engine", db_session.bind)
    headers = make_auth_headers(access_token=access)

    day1 = datetime(2026, 6, 5, 10, 0, 0, tzinfo=timezone.utc)
    day2 = datetime(2026, 6, 6, 10, 0, 0, tzinfo=timezone.utc)

    # 20 distinct users; all on_track on day1.
    user_ids = [uuid.uuid4() for _ in range(20)]
    for uid in user_ids:
        db_session.add(
            AiRecommendationAudit(
                served_at=day1,
                user_id=uid,
                recommendation_type="educational_label",
                label="on_track",
                content_hash="a" * 64,
                disclaimer_version="2026-06-06.v1",
                surface="mf_report",
            )
        )

    # day2: same 20 users; 3 switch to off_track (15% churn).
    for i, uid in enumerate(user_ids):
        label = "off_track" if i < 3 else "on_track"
        db_session.add(
            AiRecommendationAudit(
                served_at=day2,
                user_id=uid,
                recommendation_type="educational_label",
                label=label,
                content_hash="b" * 64,
                disclaimer_version="2026-06-06.v1",
                surface="mf_report",
            )
        )

    await db_session.commit()

    r = await async_client.get("/api/v1/admin/audit/label-churn", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["decision"] == "pending_publish", body
    assert body["requires_human_review"] is True
    assert body["universe"] == 20
    assert body["changed"] == 3


# ---------------------------------------------------------------------------
# 8. Partial-unique index: two active disclaimers of one type are rejected
# ---------------------------------------------------------------------------


async def test_two_active_same_type_rejected_by_index(db_session):
    """`uq_disclaimer_active_per_type` must reject a second active row of the same
    type at the DB level (single-active invariant enforced atomically)."""
    import sqlalchemy.exc

    db_session.add(
        Disclaimer(version="2026-06-06.v1", type="ai_recommendation", content="A", active=True)
    )
    await db_session.commit()

    db_session.add(
        Disclaimer(version="2026-07-01.v2", type="ai_recommendation", content="B", active=True)
    )
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await db_session.flush()
    await db_session.rollback()


# ---------------------------------------------------------------------------
# 9. Input-validation 400s through the admin router
# ---------------------------------------------------------------------------


async def test_create_content_too_long_400(async_client, monkeypatch, patch_redis):
    """An oversized disclaimer body is rejected with 400 (admin-only DoS bound)."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_toolong@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.post(
        "/api/v1/admin/disclaimers",
        json={"version": "2026-07-01.v9", "content": "x" * 70000},
        headers=headers,
    )
    assert r.status_code == 400, r.text
    assert "invalid_disclaimer" in r.json()["detail"]


async def test_label_churn_invalid_type_400(async_client, monkeypatch, patch_redis):
    """A non-allowlisted recommendation_type returns 400, not a fail-open 200."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_badtype@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get(
        "/api/v1/admin/audit/label-churn?recommendation_type=buy_sell",
        headers=headers,
    )
    assert r.status_code == 400, r.text
    assert "invalid_recommendation_type" in r.json()["detail"]
