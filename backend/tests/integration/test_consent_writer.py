"""Integration tests for the B44 DPDP consent grant/revoke writer.

Tests verify the full HTTP surface (GET /consent, POST /consent/grant,
POST /consent/revoke) plus the DB state they produce.  Every assertion is
intentionally explicit so a future regression in the REVOKE CONTRACT
(deps.py:211-213 — revoke MUST write granted:false, never a 'revoked' key)
is caught by test (c).

Fixtures required: async_client, db_session (from conftest.py).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from dhanradar.deps import consent_granted

pytestmark = pytest.mark.integration

ALL_PURPOSES = [
    "mf_analytics",
    "ai_insights",
    "marketing",
    "portfolio_sync",
    "behavioral_nudges",
    "cross_border_ai",
    "cross_border_notify",
]

_CONSENT_VERSION = "2026-06-01"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _signup(async_client) -> tuple[str, str]:
    """Sign up a unique user; return (user_id, access_token)."""
    email = f"writer_{uuid.uuid4().hex[:8]}@example.com"
    r = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "ConsentWriter42!"},
    )
    assert r.status_code == 201, r.text
    uid = r.json()["user"]["id"]
    from tests.conftest import extract_cookie  # noqa: PLC0415
    access = extract_cookie(r, "__Host-access")
    return uid, access


def _auth(access: str) -> dict:
    from tests.conftest import make_auth_headers  # noqa: PLC0415
    return make_auth_headers(access)


async def _get_raw_consents(db_session, user_id: str) -> dict:
    """Read dpdp_consents JSONB column directly (bypass ORM caching)."""
    row = await db_session.execute(
        text("SELECT dpdp_consents FROM auth.users WHERE id = :uid"),
        {"uid": user_id},
    )
    return row.scalar_one()


async def _get_consent_version(db_session, user_id: str) -> str | None:
    row = await db_session.execute(
        text("SELECT dpdp_consent_version FROM auth.users WHERE id = :uid"),
        {"uid": user_id},
    )
    return row.scalar_one()


async def _count_audit_rows(db_session, user_id: str, action: str | None = None) -> int:
    if action:
        row = await db_session.execute(
            text(
                "SELECT COUNT(*) FROM consent.consent_audit_log "
                "WHERE user_id = :uid AND action = :action"
            ),
            {"uid": uuid.UUID(user_id), "action": action},
        )
    else:
        row = await db_session.execute(
            text(
                "SELECT COUNT(*) FROM consent.consent_audit_log WHERE user_id = :uid"
            ),
            {"uid": uuid.UUID(user_id)},
        )
    return row.scalar_one()


# ---------------------------------------------------------------------------
# (a) GET /consent — all purposes False for a new user
# ---------------------------------------------------------------------------

async def test_get_consent_initial_state(async_client, db_session):
    uid, access = await _signup(async_client)

    r = await async_client.get("/api/v1/consent", headers=_auth(access))
    assert r.status_code == 200, r.text
    body = r.json()

    assert "consents" in body
    assert "consent_version" in body
    assert body["consent_version"] == _CONSENT_VERSION

    # Every canonical purpose must be present and False
    for purpose in ALL_PURPOSES:
        assert purpose in body["consents"], f"Missing purpose: {purpose}"
        assert body["consents"][purpose] is False, f"Expected False for {purpose}"


# ---------------------------------------------------------------------------
# (b) POST /consent/grant — DB state, reader, audit row
# ---------------------------------------------------------------------------

async def test_grant_writes_correct_db_state(async_client, db_session):
    uid, access = await _signup(async_client)

    r = await async_client.post(
        "/api/v1/consent/grant",
        json={"purposes": ["mf_analytics"]},
        headers=_auth(access),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["consents"]["mf_analytics"] is True

    # Reader sees grant
    assert await consent_granted(uid, "mf_analytics", db_session) is True

    # Raw JSONB has correct shape
    raw = await _get_raw_consents(db_session, uid)
    mfa = raw["mf_analytics"]
    assert isinstance(mfa, dict), "Expected dict write format"
    assert mfa["granted"] is True
    assert "ts" in mfa
    assert "version" in mfa

    # Exactly one audit row
    count = await _count_audit_rows(db_session, uid, "grant")
    assert count == 1

    # consent_version set on user
    ver = await _get_consent_version(db_session, uid)
    assert ver == _CONSENT_VERSION


# ---------------------------------------------------------------------------
# (c) POST /consent/revoke — revoke contract: granted:false, no 'revoked' key
# ---------------------------------------------------------------------------

async def test_revoke_writes_granted_false_not_revoked_key(async_client, db_session):
    uid, access = await _signup(async_client)

    # Grant first
    await async_client.post(
        "/api/v1/consent/grant",
        json={"purposes": ["mf_analytics"]},
        headers=_auth(access),
    )

    # Now revoke
    r = await async_client.post(
        "/api/v1/consent/revoke",
        json={"purposes": ["mf_analytics"]},
        headers=_auth(access),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["consents"]["mf_analytics"] is False

    # Reader sees revoke
    assert await consent_granted(uid, "mf_analytics", db_session) is False

    # REVOKE CONTRACT pin: raw value MUST be {"granted": false, ...}
    # It MUST NOT contain a "revoked" key (reader ignores "revoked" → fail-open trap)
    raw = await _get_raw_consents(db_session, uid)
    mfa = raw["mf_analytics"]
    assert isinstance(mfa, dict), "Expected dict write format after revoke"
    assert mfa["granted"] is False, "Revoke MUST write granted:false"
    assert "revoked" not in mfa, "Revoke MUST NOT add a 'revoked' key (fail-open trap)"

    # Revoke audit row exists
    count = await _count_audit_rows(db_session, uid, "revoke")
    assert count == 1


# ---------------------------------------------------------------------------
# (d) Sibling clobber prevention — grant one, grant another, first unchanged
# ---------------------------------------------------------------------------

async def test_grant_does_not_clobber_sibling_purposes(async_client, db_session):
    uid, access = await _signup(async_client)

    await async_client.post(
        "/api/v1/consent/grant",
        json={"purposes": ["mf_analytics"]},
        headers=_auth(access),
    )
    await async_client.post(
        "/api/v1/consent/grant",
        json={"purposes": ["cross_border_ai"]},
        headers=_auth(access),
    )

    r = await async_client.get("/api/v1/consent", headers=_auth(access))
    consents = r.json()["consents"]
    assert consents["mf_analytics"] is True, "mf_analytics was clobbered"
    assert consents["cross_border_ai"] is True


# ---------------------------------------------------------------------------
# (e) Anonymous (no cookie) → 401 not_authenticated
# ---------------------------------------------------------------------------

async def test_anonymous_get_consent_401(async_client, db_session):
    r = await async_client.get("/api/v1/consent")
    assert r.status_code == 401
    assert r.json().get("detail") == "not_authenticated"


async def test_anonymous_grant_401(async_client, db_session):
    r = await async_client.post(
        "/api/v1/consent/grant", json={"purposes": ["mf_analytics"]}
    )
    assert r.status_code == 401
    assert r.json().get("detail") == "not_authenticated"


async def test_anonymous_revoke_401(async_client, db_session):
    r = await async_client.post(
        "/api/v1/consent/revoke", json={"purposes": ["mf_analytics"]}
    )
    assert r.status_code == 401
    assert r.json().get("detail") == "not_authenticated"


# ---------------------------------------------------------------------------
# (f) Validation: unknown purpose → 422; empty list → 422
# ---------------------------------------------------------------------------

async def test_grant_unknown_purpose_422(async_client, db_session):
    uid, access = await _signup(async_client)
    r = await async_client.post(
        "/api/v1/consent/grant",
        json={"purposes": ["not_a_purpose"]},
        headers=_auth(access),
    )
    assert r.status_code == 422


async def test_grant_empty_list_422(async_client, db_session):
    uid, access = await _signup(async_client)
    r = await async_client.post(
        "/api/v1/consent/grant",
        json={"purposes": []},
        headers=_auth(access),
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# (g) Idempotency-Key: same key → one audit row; different key → second row
# ---------------------------------------------------------------------------

async def test_idempotency_key_deduplicates_audit(async_client, db_session):
    uid, access = await _signup(async_client)
    idem_key = f"idem-{uuid.uuid4().hex}"

    # First request with the key
    r1 = await async_client.post(
        "/api/v1/consent/grant",
        json={"purposes": ["mf_analytics"]},
        headers={**_auth(access), "Idempotency-Key": idem_key},
    )
    assert r1.status_code == 200

    # Replay with SAME key — must be idempotent (no new audit row)
    r2 = await async_client.post(
        "/api/v1/consent/grant",
        json={"purposes": ["mf_analytics"]},
        headers={**_auth(access), "Idempotency-Key": idem_key},
    )
    assert r2.status_code == 200

    count_after_replay = await _count_audit_rows(db_session, uid, "grant")
    assert count_after_replay == 1, "Replay with same Idempotency-Key MUST NOT add audit rows"

    # New key → second write goes through
    r3 = await async_client.post(
        "/api/v1/consent/grant",
        json={"purposes": ["mf_analytics"]},
        headers={**_auth(access), "Idempotency-Key": f"different-{uuid.uuid4().hex}"},
    )
    assert r3.status_code == 200

    count_after_new_key = await _count_audit_rows(db_session, uid, "grant")
    assert count_after_new_key == 2, "Different Idempotency-Key MUST produce a new audit row"


# ---------------------------------------------------------------------------
# (g2) Idempotency-Key is scoped per action — reusing a grant's key for a
#      revoke must NOT be swallowed as a replay (fail-open regression guard).
# ---------------------------------------------------------------------------

async def test_same_idempotency_key_across_grant_then_revoke_still_revokes(
    async_client, db_session
):
    uid, access = await _signup(async_client)
    shared_key = f"shared-{uuid.uuid4().hex}"

    # Grant with the shared key.
    r1 = await async_client.post(
        "/api/v1/consent/grant",
        json={"purposes": ["mf_analytics"]},
        headers={**_auth(access), "Idempotency-Key": shared_key},
    )
    assert r1.status_code == 200
    assert await consent_granted(uid, "mf_analytics", db_session) is True

    # Revoke with the SAME key — must take effect, not be skipped as a replay.
    r2 = await async_client.post(
        "/api/v1/consent/revoke",
        json={"purposes": ["mf_analytics"]},
        headers={**_auth(access), "Idempotency-Key": shared_key},
    )
    assert r2.status_code == 200
    assert r2.json()["consents"]["mf_analytics"] is False
    assert await consent_granted(uid, "mf_analytics", db_session) is False


# ---------------------------------------------------------------------------
# (h) dpdp_consent_version is set after a grant
# ---------------------------------------------------------------------------

async def test_consent_version_set_after_grant(async_client, db_session):
    uid, access = await _signup(async_client)

    await async_client.post(
        "/api/v1/consent/grant",
        json={"purposes": ["mf_analytics"]},
        headers=_auth(access),
    )

    ver = await _get_consent_version(db_session, uid)
    assert ver == _CONSENT_VERSION, f"Expected {_CONSENT_VERSION!r}, got {ver!r}"


# ---------------------------------------------------------------------------
# (i) Multi-purpose single call writes exactly one audit row per purpose
# ---------------------------------------------------------------------------

async def test_multi_purpose_grant_writes_one_audit_row_each(async_client, db_session):
    uid, access = await _signup(async_client)

    r = await async_client.post(
        "/api/v1/consent/grant",
        json={"purposes": ["mf_analytics", "ai_insights"]},
        headers=_auth(access),
    )
    assert r.status_code == 200, r.text
    consents = r.json()["consents"]
    assert consents["mf_analytics"] is True
    assert consents["ai_insights"] is True

    # Exactly two grant audit rows — one per purpose, no more, no fewer.
    assert await _count_audit_rows(db_session, uid, "grant") == 2


# ---------------------------------------------------------------------------
# (k) B48 — consent ENFORCEMENT: a gated data-processing route refuses a user
#     who has not granted the purpose. Fail-closed 403, never fail-open.
#     This proves the production posture (settings.consent_bypassed is False);
#     in production ENV=production forces that, see
#     tests/unit/test_b48_consent_prod_guard.py for the boot-guard mechanism.
# ---------------------------------------------------------------------------

async def test_consent_gated_route_refuses_without_grant(async_client, db_session):
    from dhanradar.config import settings

    # Premise: the gate must be ON for this assertion to mean anything. The
    # default test env (ENV=development, DPDP_CONSENT_ENFORCED=True) and
    # production both yield consent_bypassed=False. If a dev box has flipped the
    # B48 kill-switch, the premise does not hold — surface that explicitly
    # rather than passing vacuously.
    assert settings.consent_bypassed is False, (
        "consent gate is bypassed in this env (B48 kill-switch on); "
        "cannot assert production enforcement here"
    )

    uid, access = await _signup(async_client)  # fresh user — NO consent grant

    # The MF CAS-upload route is consent-gated (RequireConsent('mf_analytics'))
    # immediately after the 401 auth check. A real (dummy) multipart file is
    # required so the request reaches the handler body where the gate fires.
    r = await async_client.post(
        "/api/v1/mf/upload/cas",
        headers=_auth(access),
        files={"file": ("cas.pdf", b"%PDF-1.4 dummy", "application/pdf")},
    )
    assert r.status_code == 403, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "consent_required"
    assert detail["purpose"] == "mf_analytics"


# ---------------------------------------------------------------------------
# (j) Deleted-mid-session user → 401, and NO false audit row is written
#     (Finding 1: a 0-row UPDATE must not commit a forensic record of a
#     consent change that never happened).
# ---------------------------------------------------------------------------

async def test_grant_for_deleted_user_fails_closed_no_audit(async_client, db_session):
    uid, access = await _signup(async_client)

    # Delete the user row (account deletion / DPDP erasure) while the JWT is
    # still valid. consent_audit_log has no FK, so it is unaffected by the delete.
    await db_session.execute(
        text("DELETE FROM auth.users WHERE id = :uid"), {"uid": uuid.UUID(uid)}
    )
    await db_session.commit()

    r = await async_client.post(
        "/api/v1/consent/grant",
        json={"purposes": ["mf_analytics"]},
        headers=_auth(access),
    )
    assert r.status_code == 401
    assert r.json().get("detail") == "user_not_found"

    # No audit row may have been committed for the no-op write.
    assert await _count_audit_rows(db_session, uid) == 0
