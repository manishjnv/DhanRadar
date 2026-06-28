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
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

import dhanradar.db as _db_mod
from dhanradar.models.compliance import AiRecommendationAudit, Disclaimer

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Teardown: truncate all compliance + audit tables between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_activation_cache():
    """The scoring activation registry uses a process-global positive memo
    (`activation._activated_cache`). The DB is truncated between tests but that set
    is not — clear it before each test so no activated-version state leaks across
    tests (removes order-dependence; production activation is monotonic so the memo
    is correct there)."""
    from dhanradar.scoring.engine import activation

    activation._activated_cache.clear()
    yield
    activation._activated_cache.clear()


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
    db_session.expire_all()  # sync on AsyncSession — must NOT be awaited
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

    day1 = datetime(2026, 6, 5, 10, 0, 0, tzinfo=UTC)
    day2 = datetime(2026, 6, 6, 10, 0, 0, tzinfo=UTC)

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


# ---------------------------------------------------------------------------
# B6/B28 — scoring activation gate integration tests
# ---------------------------------------------------------------------------


async def test_scoring_activate_404_for_non_admin(async_client, monkeypatch):
    """Empty allowlist: authenticated non-admin → 404 (surface-hiding)."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")

    user_id, access = await _signup(async_client, "activate_nonadmin@example.com")
    headers = make_auth_headers(access_token=access)

    r = await async_client.post(
        "/api/v1/admin/scoring/v1/activate",
        json={"backtest_passed": False},
        headers=headers,
    )
    assert r.status_code == 404, r.text


async def test_scoring_activate_backtest_not_passed_422(
    async_client, db_session, monkeypatch
):
    """Admin posting backtest_passed=false → 422 backtest_not_passed."""
    from dhanradar.config import settings
    from dhanradar.scoring.engine.config import get_config
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "activate_nobacktest@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    monkeypatch.setattr(_db_mod, "engine", db_session.bind)
    headers = make_auth_headers(access_token=access)

    # Only the currently loaded config version is activatable — derive it so a
    # model_version bump (e.g. v1 → v1.1) doesn't 404 this test.
    ver = get_config().model_version
    r = await async_client.post(
        f"/api/v1/admin/scoring/{ver}/activate",
        json={"backtest_passed": False},
        headers=headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["detail"] == "backtest_not_passed"


async def test_scoring_activate_happy_path(
    async_client, db_session, monkeypatch
):
    """Admin activates the loaded config version with backtest_passed=true → 200
    with full registry row; subsequent GET /status shows registry_activated=True,
    provisional=False."""
    from dhanradar.config import settings
    from dhanradar.scoring.engine import activation as _activation
    from dhanradar.scoring.engine.config import get_config
    from tests.conftest import make_auth_headers

    _activation._activated_cache.clear()

    user_id, access = await _signup(async_client, "activate_happy@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    monkeypatch.setattr(_db_mod, "engine", db_session.bind)
    headers = make_auth_headers(access_token=access)

    ver = get_config().model_version
    r = await async_client.post(
        f"/api/v1/admin/scoring/{ver}/activate",
        json={"backtest_passed": True},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["activated"] is True
    assert body["two_person_ok"] is True
    assert body["approved_by"] == user_id
    # created_by is sourced from the active config (changes per model version) — assert
    # the endpoint surfaces it, not a frozen literal (v1.2 = "claude-builder (B66-f1 pt2)").
    assert body["created_by"] == get_config().created_by
    assert body["model_version"] == ver

    # Clear memo so status check goes to DB.
    _activation._activated_cache.clear()

    r = await async_client.get(
        f"/api/v1/admin/scoring/{ver}/status",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    status_body = r.json()
    assert status_body["registry_activated"] is True
    assert status_body["effective_activated"] is True
    assert status_body["provisional"] is False


async def test_scoring_activate_unknown_version_404(
    async_client, monkeypatch
):
    """POSTing an unknown model_version → 404 model_version_not_found."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "activate_badver@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.post(
        "/api/v1/admin/scoring/v9/activate",
        json={"backtest_passed": True},
        headers=headers,
    )
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "model_version_not_found"


async def test_scoring_activate_double_activation_409(
    async_client, db_session, monkeypatch
):
    """Activating the same model_version twice → second request returns 409
    model_already_activated."""
    from dhanradar.config import settings
    from dhanradar.scoring.engine import activation as _activation
    from tests.conftest import make_auth_headers

    _activation._activated_cache.clear()

    user_id, access = await _signup(async_client, "activate_double@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    monkeypatch.setattr(_db_mod, "engine", db_session.bind)
    headers = make_auth_headers(access_token=access)

    from dhanradar.scoring.engine.config import get_config

    ver = get_config().model_version

    # First activation — must succeed.
    r = await async_client.post(
        f"/api/v1/admin/scoring/{ver}/activate",
        json={"backtest_passed": True},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    # Clear memo so second attempt hits the DB guard (not the local cache).
    _activation._activated_cache.clear()

    # Second activation — must return 409.
    r = await async_client.post(
        f"/api/v1/admin/scoring/{ver}/activate",
        json={"backtest_passed": True},
        headers=headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "model_already_activated"


async def test_two_activated_changelog_rows_rejected_by_index(db_session):
    """`uq_engine_changelog_activated_per_version` must reject a second activated=true
    row for the same model_version (the race-safe single-activation-record backstop)."""
    import sqlalchemy.exc

    from dhanradar.models.compliance import RatingEngineChangelog

    db_session.add(
        RatingEngineChangelog(
            model_version="v1", created_by="architecture-review",
            approved_by="admin-a", two_person_ok=True, activated=True,
        )
    )
    await db_session.commit()

    db_session.add(
        RatingEngineChangelog(
            model_version="v1", created_by="architecture-review",
            approved_by="admin-b", two_person_ok=True, activated=True,
        )
    )
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_scoring_status_provisional_before_activation(
    async_client, db_session, monkeypatch
):
    """Before any registry activation, status must show registry_activated=False and
    provisional=True — even though the shipped file flag is True (B6/B28 activation,
    2026-06-11; v1.1 follows the same shape). The gate (registry), not the file
    flag, governs `provisional`."""
    from dhanradar.config import settings
    from dhanradar.scoring.engine.config import get_config
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "status_provisional@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    ver = get_config().model_version
    r = await async_client.get(f"/api/v1/admin/scoring/{ver}/status", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["registry_activated"] is False
    assert body["file_activated"] is True  # ranking_configs_v1.json ships activated:true
    assert body["provisional"] is True  # registry empty in this test DB → still provisional
