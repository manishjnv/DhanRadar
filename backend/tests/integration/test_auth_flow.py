"""
Integration tests for the full auth flow.

Infrastructure contract
-----------------------
- Uses `async_client` fixture (httpx.AsyncClient via ASGITransport, no lifespan).
- DB = compose service `dhanradar-postgres` via the `db_session` / `db_engine`
  fixtures; tables are truncated between tests.
- Redis = fakeredis via `patch_redis` (injected by `async_client`).
- RSA keys = ephemeral in-process keypair via `patch_settings_keys`
  (also injected by `async_client`).

__Host- cookie limitation
--------------------------
httpx.AsyncClient on http:// silently drops cookies whose name starts with
"__Host-" (RFC 6265bis compliance, same as browsers). This is a test-harness
limitation, not an app bug. All tests extract cookies from the raw Set-Cookie
header using `extract_cookie()` from conftest, then re-inject them via an
explicit Cookie header using `make_auth_headers()`.

Rate-limit tests
----------------
Rate limiting is driven by the `CF-Connecting-IP` header, not by timing.
All 6 rapid requests use the same fixed IP header. fakeredis incr/expire
semantics match real Redis, so the fixed-window counter increments correctly.
No `time.sleep` is used.
"""

from __future__ import annotations

import pytest

from tests.conftest import extract_cookie, make_auth_headers

# All tests in this file are integration tests needing Postgres + fakeredis.
pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helper: perform a full signup and return (user_id, access_token, refresh_token)
# ---------------------------------------------------------------------------

async def _signup(client, email: str = "test@example.com", password: str = "ValidPass42!"):
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password},
    )
    access = extract_cookie(resp, "__Host-access")
    refresh = extract_cookie(resp, "__Host-refresh")
    return resp, access, refresh


async def _login(client, email: str, password: str):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    access = extract_cookie(resp, "__Host-access")
    refresh = extract_cookie(resp, "__Host-refresh")
    return resp, access, refresh


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------


async def test_signup_201_sets_auth_cookies(async_client):
    """Successful signup must return 201 and set both auth cookies."""
    resp, access, refresh = await _signup(async_client)

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["message"] == "account_created"
    assert "user" in body
    assert body["user"]["email"] == "test@example.com"
    assert body["user"]["tier"] == "free"

    assert access is not None, "Missing __Host-access cookie in Set-Cookie header"
    assert refresh is not None, "Missing __Host-refresh cookie in Set-Cookie header"


async def test_signup_duplicate_email_409(async_client):
    """Signing up with an already-registered email must return 409."""
    await _signup(async_client, email="dup@example.com")
    resp2, _, _ = await _signup(async_client, email="dup@example.com")

    assert resp2.status_code == 409, resp2.text
    assert resp2.json()["detail"] == "email_already_registered"


async def test_signup_email_case_insensitive_dedup(async_client):
    """Email normalisation: 'User@Example.COM' and 'user@example.com' are the same."""
    _, _, _ = await _signup(async_client, email="CaseTest@Example.COM")
    resp2, _, _ = await _signup(async_client, email="casetest@example.com")
    assert resp2.status_code == 409, resp2.text


async def test_signup_short_password_422(async_client):
    """Password shorter than 10 characters must be rejected at schema level."""
    resp = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": "short@example.com", "password": "Short1!"},
    )
    assert resp.status_code == 422, resp.text


async def test_signup_long_password_422(async_client):
    """Password longer than 128 characters must be rejected."""
    long_pw = "A" * 129 + "1!"
    resp = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": "long@example.com", "password": long_pw},
    )
    assert resp.status_code == 422, resp.text


async def test_signup_exactly_10_char_password_201(async_client):
    """Password of exactly 10 characters (the minimum) must be accepted."""
    resp = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": "min10@example.com", "password": "Exactly10!"},
    )
    assert resp.status_code == 201, resp.text


async def test_signup_exactly_128_char_password_201(async_client):
    """Password of exactly 128 characters (the maximum) must be accepted."""
    max_pw = "Aa1!" + "x" * 124  # 4 + 124 = 128 chars
    resp = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": "max128@example.com", "password": max_pw},
    )
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


async def test_login_wrong_password_401(async_client):
    """Wrong password must return 401 with detail='invalid_credentials'."""
    await _signup(async_client, email="logintest@example.com")
    resp, _, _ = await _login(async_client, "logintest@example.com", "WrongPass99!")
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"] == "invalid_credentials"


async def test_login_unknown_email_401_same_body(async_client):
    """
    Unknown email must return 401 with the SAME body as wrong-password to
    prevent user enumeration.
    """
    resp, _, _ = await _login(async_client, "nobody@example.com", "SomePass123!")
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"] == "invalid_credentials"


async def test_login_correct_credentials_200_with_cookies(async_client):
    """Correct credentials must return 200 and set auth cookies."""
    await _signup(async_client, email="goodlogin@example.com", password="GoodPass42!")
    resp, access, refresh = await _login(async_client, "goodlogin@example.com", "GoodPass42!")

    assert resp.status_code == 200, resp.text
    assert resp.json()["message"] == "login_successful"
    assert access is not None, "Missing __Host-access cookie"
    assert refresh is not None, "Missing __Host-refresh cookie"


# ---------------------------------------------------------------------------
# /auth/me
# ---------------------------------------------------------------------------


async def test_me_anonymous_no_cookies_401(async_client):
    """GET /auth/me without any cookie must return 401."""
    resp = await async_client.get("/api/v1/auth/me")
    assert resp.status_code == 401, resp.text


async def test_me_after_login_returns_email(async_client):
    """GET /auth/me with a valid access cookie must return 200 with email."""
    await _signup(async_client, email="metest@example.com", password="MePass42!!!!")
    _, access, _ = await _login(async_client, "metest@example.com", "MePass42!!!!")

    resp = await async_client.get(
        "/api/v1/auth/me",
        headers=make_auth_headers(access_token=access),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["email"] == "metest@example.com"


async def test_me_with_garbage_token_401(async_client):
    """A malformed access token must yield 401 from /auth/me."""
    resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Cookie": "__Host-access=not.a.real.jwt"},
    )
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# Refresh rotation + reuse detection
# ---------------------------------------------------------------------------


async def test_refresh_rotates_cookie(async_client):
    """
    POST /auth/refresh must return 200 and set a NEW refresh cookie value
    that differs from the original.
    """
    await _signup(async_client, email="refresh@example.com", password="RefreshPass42!")
    _, access_before, refresh_before = await _login(
        async_client, "refresh@example.com", "RefreshPass42!"
    )

    assert refresh_before is not None

    resp = await async_client.post(
        "/api/v1/auth/refresh",
        headers=make_auth_headers(refresh_token=refresh_before),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["message"] == "tokens_rotated"

    refresh_after = extract_cookie(resp, "__Host-refresh")
    assert refresh_after is not None, "No new refresh cookie set after rotation"
    assert refresh_after != refresh_before, "Refresh token must change after rotation"


async def test_refresh_reuse_detected_401(async_client):
    """
    Replaying the OLD refresh token immediately after rotation must return 401
    with detail='token_reuse_detected'.
    """
    await _signup(async_client, email="reuse@example.com", password="ReusePass42!!!")
    _, _, old_refresh = await _login(async_client, "reuse@example.com", "ReusePass42!!!")

    # First rotation — consumes old_refresh, issues a new one.
    rotate_resp = await async_client.post(
        "/api/v1/auth/refresh",
        headers=make_auth_headers(refresh_token=old_refresh),
    )
    assert rotate_resp.status_code == 200, rotate_resp.text

    # Replay old_refresh — must be rejected.
    replay_resp = await async_client.post(
        "/api/v1/auth/refresh",
        headers=make_auth_headers(refresh_token=old_refresh),
    )
    assert replay_resp.status_code == 401, replay_resp.text
    assert replay_resp.json()["detail"] == "token_reuse_detected"


async def test_refresh_without_cookie_401(async_client):
    """POST /auth/refresh with no cookie must return 401."""
    resp = await async_client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# Logout — cookie clear + access-jti denylist
# ---------------------------------------------------------------------------


async def test_logout_200_and_me_becomes_401(async_client):
    """
    After logout:
    1. POST /auth/logout returns 200.
    2. GET /auth/me with the revoked access cookie returns 401.

    This exercises the access-jti denylist: the access token is still
    cryptographically valid (not expired) but its jti has been revoked in Redis.
    """
    await _signup(async_client, email="logout@example.com", password="LogoutPass42!!")
    _, access, refresh = await _login(async_client, "logout@example.com", "LogoutPass42!!")

    # Verify we are authenticated before logout.
    me_before = await async_client.get(
        "/api/v1/auth/me",
        headers=make_auth_headers(access_token=access),
    )
    assert me_before.status_code == 200, me_before.text

    # Logout.
    logout_resp = await async_client.post(
        "/api/v1/auth/logout",
        headers=make_auth_headers(access_token=access, refresh_token=refresh),
    )
    assert logout_resp.status_code == 200, logout_resp.text
    assert logout_resp.json()["message"] == "logged_out"

    # The same (still cryptographically valid) access token must now yield 401
    # because its jti has been added to the Redis denylist.
    me_after = await async_client.get(
        "/api/v1/auth/me",
        headers=make_auth_headers(access_token=access),
    )
    assert me_after.status_code == 401, (
        "Expected 401 after logout (jti denylist), got "
        f"{me_after.status_code}: {me_after.text}"
    )


async def test_logout_without_cookies_200(async_client):
    """Logout without any cookies must still return 200 (idempotent)."""
    resp = await async_client.post("/api/v1/auth/logout")
    assert resp.status_code == 200, resp.text


async def test_refresh_after_logout_401(async_client):
    """The old refresh token must be rejected after logout."""
    await _signup(async_client, email="logout2@example.com", password="LogoutPass99!!")
    _, access, refresh = await _login(async_client, "logout2@example.com", "LogoutPass99!!")

    await async_client.post(
        "/api/v1/auth/logout",
        headers=make_auth_headers(access_token=access, refresh_token=refresh),
    )

    # Attempt to refresh with the now-revoked refresh token.
    resp = await async_client.post(
        "/api/v1/auth/refresh",
        headers=make_auth_headers(refresh_token=refresh),
    )
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"] == "token_reuse_detected"


# ---------------------------------------------------------------------------
# Rate limiting: 6 rapid login attempts → at least one 429
# ---------------------------------------------------------------------------


async def test_login_rate_limit_6_requests_yields_429(async_client):
    """
    Send 6 login requests from the same CF-Connecting-IP within one window.
    The limit is 5/60s, so at least the 6th must be 429.

    No time.sleep used — the fixed-window counter in fakeredis increments on
    each call; timing is irrelevant.
    """
    fixed_ip = "203.0.113.42"  # TEST-NET-3, guaranteed not to be a real IP.
    headers = {"CF-Connecting-IP": fixed_ip}

    statuses = []
    for _ in range(6):
        resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "ratelimit@example.com", "password": "WrongPass"},
            headers=headers,
        )
        statuses.append(resp.status_code)

    assert 429 in statuses, (
        f"Expected at least one 429 in 6 rapid login attempts, got: {statuses}"
    )
