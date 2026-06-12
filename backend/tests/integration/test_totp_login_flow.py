"""
Integration tests for standalone TOTP login (Feature 2).

Flow under test:
  signup → totp/setup → totp/verify (enrol) → logout
  → POST /auth/totp/login with current code → 200 + cookies
  → replay same code → 401
  → wrong code → 401
  → 5 wrong codes → locked → 401 (generic, not 429)
  → unknown email → 401 (same body)
  → SSO-only user (hashed_password=None) password login → 401

Infrastructure: same as test_auth_flow.py — Postgres + fakeredis + ephemeral RSA.
"""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import extract_cookie, make_auth_headers

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _signup(client, email: str = "totp_test@example.com", password: str = "ValidPass42!"):
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password},
    )
    access = extract_cookie(resp, "__Host-access")
    refresh = extract_cookie(resp, "__Host-refresh")
    return resp, access, refresh


async def _enrol_totp(client, access_token: str) -> str:
    """Setup + verify TOTP; returns the secret."""
    # Setup
    setup_resp = await client.post(
        "/api/v1/auth/totp/setup",
        headers=make_auth_headers(access_token=access_token),
    )
    assert setup_resp.status_code == 200, setup_resp.text
    secret = setup_resp.json()["secret"]

    # Verify (enrol)
    code = pyotp.TOTP(secret).now()
    verify_resp = await client.post(
        "/api/v1/auth/totp/verify",
        json={"code": code},
        headers=make_auth_headers(access_token=access_token),
    )
    assert verify_resp.status_code == 200, verify_resp.text
    return secret


async def _logout(client, access_token: str, refresh_token: str):
    return await client.post(
        "/api/v1/auth/logout",
        headers=make_auth_headers(access_token=access_token, refresh_token=refresh_token),
    )


# ---------------------------------------------------------------------------
# Happy path: full flow
# ---------------------------------------------------------------------------

async def test_totp_login_happy_path(async_client):
    """Enrol TOTP, log out, then log back in via /auth/totp/login."""
    email = "totp_happy@example.com"
    password = "HappyPass42!"

    _, access, refresh = await _signup(async_client, email, password)
    assert access is not None

    secret = await _enrol_totp(async_client, access)

    await _logout(async_client, access, refresh)

    code = pyotp.TOTP(secret).now()
    resp = await async_client.post(
        "/api/v1/auth/totp/login",
        json={"email": email, "code": code},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["message"] == "login_successful"
    assert body["user"]["email"] == email

    new_access = extract_cookie(resp, "__Host-access")
    new_refresh = extract_cookie(resp, "__Host-refresh")
    assert new_access is not None, "Expected __Host-access cookie after TOTP login"
    assert new_refresh is not None, "Expected __Host-refresh cookie after TOTP login"


# ---------------------------------------------------------------------------
# Replay guard
# ---------------------------------------------------------------------------

async def test_totp_login_replay_rejected(async_client):
    """Replaying the same TOTP code immediately must return 401."""
    email = "totp_replay@example.com"
    _, access, refresh = await _signup(async_client, email)
    secret = await _enrol_totp(async_client, access)
    await _logout(async_client, access, refresh)

    code = pyotp.TOTP(secret).now()

    # First use — must succeed.
    first = await async_client.post(
        "/api/v1/auth/totp/login",
        json={"email": email, "code": code},
    )
    assert first.status_code == 200, first.text

    # Immediate replay — must fail.
    second = await async_client.post(
        "/api/v1/auth/totp/login",
        json={"email": email, "code": code},
    )
    assert second.status_code == 401, second.text
    assert second.json()["detail"] == "invalid_credentials"


# ---------------------------------------------------------------------------
# Wrong code
# ---------------------------------------------------------------------------

async def test_totp_login_wrong_code_401(async_client):
    """A wrong code must return 401 with detail='invalid_credentials'."""
    email = "totp_wrong@example.com"
    _, access, refresh = await _signup(async_client, email)
    await _enrol_totp(async_client, access)
    await _logout(async_client, access, refresh)

    resp = await async_client.post(
        "/api/v1/auth/totp/login",
        json={"email": email, "code": "000000"},
    )
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"] == "invalid_credentials"


# ---------------------------------------------------------------------------
# Brute-force lock (5 wrong codes → still 401, not 429)
# ---------------------------------------------------------------------------

async def test_totp_login_brute_force_lock_stays_generic(async_client):
    """
    5 wrong codes lock the account.  The 6th attempt must still return 401
    (not 429) — a 429 on this unauthenticated surface would leak that the
    account exists and is enrolled.

    Each request comes from a DISTINCT IP: the per-account lock (keyed on
    user.id) is the control under test here, and it only becomes observable to
    a *distributed* attacker — a single IP would hit the per-IP rate limiter
    (5/60s) and get a 429 on the 6th request before the account-lock branch
    runs.  Varying the IP keeps the per-IP limiter under its threshold so the
    account lock is what answers the 6th attempt.
    """
    email = "totp_lock@example.com"

    _, access, refresh = await _signup(async_client, email)
    await _enrol_totp(async_client, access)
    await _logout(async_client, access, refresh)

    for i in range(5):
        r = await async_client.post(
            "/api/v1/auth/totp/login",
            json={"email": email, "code": "000000"},
            headers={"CF-Connecting-IP": f"203.0.113.{10 + i}"},
        )
        assert r.status_code == 401, r.text

    # 6th attempt, fresh IP — per-IP limiter is clear, but the account is now
    # locked; the lock must answer with a generic 401, never a 429.
    locked = await async_client.post(
        "/api/v1/auth/totp/login",
        json={"email": email, "code": "111111"},
        headers={"CF-Connecting-IP": "203.0.113.99"},
    )
    assert locked.status_code == 401, locked.text
    assert locked.json()["detail"] == "invalid_credentials"


# ---------------------------------------------------------------------------
# Unknown email — indistinguishable from wrong code
# ---------------------------------------------------------------------------

async def test_totp_login_unknown_email_same_body(async_client):
    """An unknown email must return 401 with the same body as a wrong code."""
    resp = await async_client.post(
        "/api/v1/auth/totp/login",
        json={"email": "nobody@example.com", "code": "123456"},
    )
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"] == "invalid_credentials"


# ---------------------------------------------------------------------------
# SSO-only user cannot log in with a password
# ---------------------------------------------------------------------------

async def test_sso_only_user_password_login_rejected(async_client, db_session):
    """
    A user with hashed_password=None (SSO-only) must not be authenticable via
    POST /auth/login — the response must be 401 invalid_credentials.
    """
    from sqlalchemy import update as sa_update

    from dhanradar.models.auth import User

    # Create a normal user first.
    email = "sso_only@example.com"
    password = "SSOOnly42!!"
    _, access, _ = await _signup(async_client, email, password)
    assert access is not None

    # Forcibly null out hashed_password to simulate SSO-only.
    await db_session.execute(
        sa_update(User)
        .where(User.email == email)
        .values(hashed_password=None)
    )
    await db_session.commit()

    # Attempt password login — must be rejected with the generic 401.
    resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"] == "invalid_credentials"


# ---------------------------------------------------------------------------
# Not-enrolled user
# ---------------------------------------------------------------------------

async def test_totp_login_not_enrolled_401(async_client):
    """A user who never set up TOTP must get generic 401."""
    email = "not_enrolled@example.com"
    await _signup(async_client, email)

    resp = await async_client.post(
        "/api/v1/auth/totp/login",
        json={"email": email, "code": "123456"},
    )
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"] == "invalid_credentials"
