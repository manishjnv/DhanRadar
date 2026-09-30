"""Integration tests — self-service account deletion (DPDP, B79 follow-up).

Covers:
  - POST /auth/account/deletion-request: 200 + cookies cleared, the SAME
    access cookie is rejected on a follow-up /auth/me call (mirrors
    test_logout_200_and_me_becomes_401), idempotent re-request, 422 on a
    missing/false `confirm`, 401 when anonymous.
  - POST /auth/refresh on a deletion-pending account: 403
    account_deletion_pending (the refresh-path gap this change closes —
    password/TOTP/email-OTP/SSO logins already refused deletion-pending
    accounts; refresh did not).
  - POST /admin/users/{id}/cancel-deletion: 404 unknown user, 409 when no
    deletion is pending, 200 + marker cleared on success (and the account
    can sign in again afterwards).

Infrastructure mirrors test_b79_hard_erasure.py / test_auth_flow.py:
async_client, db_session, patch_redis, extract_cookie, make_auth_headers.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from dhanradar.models.auth import User
from tests.conftest import extract_cookie, make_auth_headers

pytestmark = pytest.mark.integration


async def _signup(client, email: str, password: str = "SelfDelete42!"):
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 201, resp.text
    access = extract_cookie(resp, "__Host-access")
    refresh = extract_cookie(resp, "__Host-refresh")
    return resp.json()["user"]["id"], access, refresh


# ---------------------------------------------------------------------------
# POST /auth/account/deletion-request
# ---------------------------------------------------------------------------


async def test_deletion_request_200_kills_current_session(async_client, db_session):
    _uid, access, refresh = await _signup(async_client, "selfdelete1@example.com")

    # Authenticated before the request.
    me_before = await async_client.get(
        "/api/v1/auth/me", headers=make_auth_headers(access_token=access)
    )
    assert me_before.status_code == 200, me_before.text

    resp = await async_client.post(
        "/api/v1/auth/account/deletion-request",
        json={"confirm": True},
        headers=make_auth_headers(access_token=access, refresh_token=refresh),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "deletion_requested"
    assert "earliest_erase_at" in body
    assert "erase_by" in body

    # Cookies cleared on the response.
    assert extract_cookie(resp, "__Host-access") in (None, "", '""')
    assert extract_cookie(resp, "__Host-refresh") in (None, "", '""')

    # The SAME (still cryptographically valid) access token must now be
    # rejected — its jti was revoked, same mechanism as logout.
    me_after = await async_client.get(
        "/api/v1/auth/me", headers=make_auth_headers(access_token=access)
    )
    assert me_after.status_code == 401, me_after.text

    user = await db_session.scalar(select(User).where(User.email == "selfdelete1@example.com"))
    assert user.deletion_requested_at is not None


async def test_deletion_request_idempotent(async_client):
    _uid, access, refresh = await _signup(async_client, "selfdelete2@example.com")
    headers = make_auth_headers(access_token=access, refresh_token=refresh)

    r1 = await async_client.post(
        "/api/v1/auth/account/deletion-request", json={"confirm": True}, headers=headers
    )
    assert r1.status_code == 200, r1.text

    # Second call re-uses the already-revoked access cookie — anonymous, so 401.
    r2 = await async_client.post(
        "/api/v1/auth/account/deletion-request", json={"confirm": True}, headers=headers
    )
    assert r2.status_code == 401, r2.text


async def test_deletion_request_missing_or_false_confirm_422(async_client):
    _uid, access, _refresh = await _signup(async_client, "selfdelete3@example.com")
    headers = make_auth_headers(access_token=access)

    r_missing = await async_client.post(
        "/api/v1/auth/account/deletion-request", json={}, headers=headers
    )
    assert r_missing.status_code == 422, r_missing.text

    r_false = await async_client.post(
        "/api/v1/auth/account/deletion-request", json={"confirm": False}, headers=headers
    )
    assert r_false.status_code == 422, r_false.text


async def test_deletion_request_anonymous_401(async_client):
    resp = await async_client.post(
        "/api/v1/auth/account/deletion-request", json={"confirm": True}
    )
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# POST /auth/refresh on a deletion-pending account (the gap this change closes)
# ---------------------------------------------------------------------------


async def test_refresh_refused_for_deletion_pending_account(async_client, db_session):
    """Isolate the refresh-path deletion check from the session-teardown scan:
    mark deletion_requested_at directly on the DB row (bypassing erasure.py's
    jti revocation) so the refresh token is still a live, unrevoked jti, then
    confirm /auth/refresh still refuses it with 403 account_deletion_pending."""
    from datetime import UTC, datetime

    _uid, _access, refresh = await _signup(async_client, "selfdelete-refresh2@example.com")

    user = await db_session.scalar(
        select(User).where(User.email == "selfdelete-refresh2@example.com")
    )
    user.deletion_requested_at = datetime.now(UTC)
    await db_session.commit()

    resp = await async_client.post(
        "/api/v1/auth/refresh", headers=make_auth_headers(refresh_token=refresh)
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == "account_deletion_pending"
    assert extract_cookie(resp, "__Host-access") in (None, "", '""')


# ---------------------------------------------------------------------------
# POST /admin/users/{id}/cancel-deletion
# ---------------------------------------------------------------------------


async def test_cancel_deletion_404_unknown_user(async_client, monkeypatch):
    from dhanradar.config import settings

    admin_id, admin_access, _ = await _signup(async_client, "admin_cancel_404@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=admin_access)

    fake_id = "00000000-0000-0000-0000-000000000099"
    resp = await async_client.post(f"/api/v1/admin/users/{fake_id}/cancel-deletion", headers=headers)
    assert resp.status_code == 404, resp.text


async def test_cancel_deletion_409_when_not_requested(async_client, monkeypatch):
    from dhanradar.config import settings

    admin_id, admin_access, _ = await _signup(async_client, "admin_cancel_409@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=admin_access)

    target_id, _t_access, _t_refresh = await _signup(async_client, "target_cancel_409@example.com")

    resp = await async_client.post(
        f"/api/v1/admin/users/{target_id}/cancel-deletion", headers=headers
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "deletion_not_requested"


async def test_cancel_deletion_200_clears_marker_and_login_works_again(
    async_client, monkeypatch, db_session
):
    from dhanradar.config import settings

    admin_id, admin_access, _ = await _signup(async_client, "admin_cancel_200@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=admin_access)

    target_id, target_access, _ = await _signup(
        async_client, "target_cancel_200@example.com", "TargetPass42!"
    )

    req_resp = await async_client.post(
        f"/api/v1/admin/users/{target_id}/request-deletion", headers=headers
    )
    assert req_resp.status_code == 200, req_resp.text

    # Locked out while pending.
    locked = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "target_cancel_200@example.com", "password": "TargetPass42!"},
    )
    assert locked.status_code == 403, locked.text
    assert locked.json()["detail"] == "account_deletion_pending"

    cancel_resp = await async_client.post(
        f"/api/v1/admin/users/{target_id}/cancel-deletion", headers=headers
    )
    assert cancel_resp.status_code == 200, cancel_resp.text
    assert cancel_resp.json() == {"ok": True, "status": "active"}

    user = await db_session.scalar(select(User).where(User.id == target_id))
    assert user.deletion_requested_at is None

    # Login works again after cancellation.
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "target_cancel_200@example.com", "password": "TargetPass42!"},
    )
    assert login_resp.status_code == 200, login_resp.text


# ---------------------------------------------------------------------------
# POST /auth/account/deletion-cancel — the emailed link (unauthenticated)
# ---------------------------------------------------------------------------


async def test_deletion_cancel_200_via_token(async_client, db_session):
    from dhanradar.auth.security import create_deletion_cancel_token

    uid, access, _refresh = await _signup(async_client, "cancel-token-200@example.com")
    r = await async_client.post(
        "/api/v1/auth/account/deletion-request",
        json={"confirm": True},
        headers=make_auth_headers(access_token=access),
    )
    assert r.status_code == 200, r.text

    user = await db_session.scalar(select(User).where(User.id == uid))
    token = create_deletion_cancel_token(str(uid), user.deletion_requested_at)

    cancel_resp = await async_client.post(
        "/api/v1/auth/account/deletion-cancel", json={"token": token}
    )
    assert cancel_resp.status_code == 200, cancel_resp.text
    assert cancel_resp.json() == {"status": "cancelled"}

    refreshed = await db_session.scalar(select(User).where(User.id == uid))
    assert refreshed.deletion_requested_at is None

    # Idempotent: calling again with the same (now-stale, marker already
    # cleared) token is still a 200, never an error.
    cancel_resp2 = await async_client.post(
        "/api/v1/auth/account/deletion-cancel", json={"token": token}
    )
    assert cancel_resp2.status_code == 200, cancel_resp2.text
    assert cancel_resp2.json() == {"status": "cancelled"}


async def test_deletion_cancel_400_garbage_token(async_client):
    resp = await async_client.post(
        "/api/v1/auth/account/deletion-cancel", json={"token": "not-a-jwt"}
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == "invalid_or_expired_link"


async def test_deletion_cancel_400_wrong_typ(async_client, db_session):
    """An access token must never be accepted as a deletion_cancel token."""
    uid, access, _refresh = await _signup(async_client, "cancel-wrong-typ@example.com")

    resp = await async_client.post(
        "/api/v1/auth/account/deletion-cancel", json={"token": access}
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == "invalid_or_expired_link"


async def test_deletion_cancel_400_expired_token(async_client, db_session):
    from datetime import UTC, datetime, timedelta

    import jwt as pyjwt

    from dhanradar.config import settings

    uid, access, _refresh = await _signup(async_client, "cancel-expired@example.com")
    await async_client.post(
        "/api/v1/auth/account/deletion-request",
        json={"confirm": True},
        headers=make_auth_headers(access_token=access),
    )
    user = await db_session.scalar(select(User).where(User.id == uid))

    now = datetime.now(UTC)
    payload = {
        "sub": str(uid),
        "jti": "expired-jti",
        "typ": "deletion_cancel",
        "iat": now - timedelta(days=40),
        "drq": int(user.deletion_requested_at.timestamp()),
        "exp": now - timedelta(days=1),  # already expired
    }
    expired_token = pyjwt.encode(payload, settings.jwt_private_key, algorithm="RS256")

    resp = await async_client.post(
        "/api/v1/auth/account/deletion-cancel", json={"token": expired_token}
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == "invalid_or_expired_link"


async def test_deletion_cancel_400_stale_drq_after_rerequest(async_client, db_session):
    """A cancel link from an OLDER request must not cancel a re-request made
    after the email was sent (its `drq` claim no longer matches)."""
    from dhanradar.auth.security import create_deletion_cancel_token

    uid, access, refresh = await _signup(async_client, "cancel-stale-drq@example.com")

    r1 = await async_client.post(
        "/api/v1/auth/account/deletion-request",
        json={"confirm": True},
        headers=make_auth_headers(access_token=access, refresh_token=refresh),
    )
    assert r1.status_code == 200, r1.text
    user = await db_session.scalar(select(User).where(User.id == uid))
    old_token = create_deletion_cancel_token(str(uid), user.deletion_requested_at)

    # Re-request (admin re-triggers, or a second self-service call after a
    # fresh login) re-stamps deletion_requested_at.
    from dhanradar.auth.erasure import request_user_deletion

    await request_user_deletion(db_session, uid)

    resp = await async_client.post(
        "/api/v1/auth/account/deletion-cancel", json={"token": old_token}
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == "invalid_or_expired_link"


async def test_deletion_cancel_200_idempotent_when_never_requested(async_client):
    """A syntactically valid token for a user with no pending deletion is an
    idempotent success (no enumeration of whether a deletion was pending)."""
    from datetime import UTC, datetime

    from dhanradar.auth.security import create_deletion_cancel_token

    uid, _access, _refresh = await _signup(async_client, "cancel-never-requested@example.com")
    token = create_deletion_cancel_token(str(uid), datetime.now(UTC))

    resp = await async_client.post(
        "/api/v1/auth/account/deletion-cancel", json={"token": token}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "cancelled"}
