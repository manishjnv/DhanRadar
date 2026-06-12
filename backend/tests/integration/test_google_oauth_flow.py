"""
Integration tests for Google SSO flow (Feature 1).

Network steps (exchange_code_with_verifier, verify_id_token) are monkeypatched.
Redis state, DB user creation, and cookie issuance are exercised against real
fakeredis and Postgres.

Test matrix:
  - /google/start when unconfigured → 503
  - /google/start when configured → 302 with required params + Redis state stored
  - /google/callback with unknown state → 302 to /login?error=google_auth_failed
  - /google/callback happy path (new user) → 303 to /dashboard + cookies set
  - /google/callback existing password user, same email → REJECTED with
    account_exists_use_password (auto-link forbidden: local emails unverified)
  - /google/callback deletion_requested_at user → redirect with account_deletion_pending
  - /google/callback email_verified=False claims → error redirect
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from tests.conftest import extract_cookie

pytestmark = pytest.mark.integration

# Fake Google credentials used in all configured tests.
_FAKE_CLIENT_ID = "test-client-id.apps.googleusercontent.com"
_FAKE_CLIENT_SECRET = "test-client-secret"  # noqa: S105 — obviously fake
_FAKE_REDIRECT_URI = "http://test/api/v1/auth/google/callback"

# Fake Google identity
_FAKE_SUB = "google-sub-123456789"
_FAKE_EMAIL = "googleuser@example.com"


def _fake_claims(
    sub: str = _FAKE_SUB,
    email: str = _FAKE_EMAIL,
    email_verified: bool = True,
    nonce: str | None = None,
) -> dict[str, Any]:
    claims: dict[str, Any] = {
        "sub": sub,
        "email": email,
        "email_verified": email_verified,
        "iss": "https://accounts.google.com",
    }
    if nonce is not None:
        claims["nonce"] = nonce
    return claims


def _patch_settings(**kwargs):
    """Context manager: patch settings attributes for a single test."""
    import contextlib

    from dhanradar.config import settings

    @contextlib.contextmanager
    def _ctx():
        original = {k: getattr(settings, k) for k in kwargs}
        for k, v in kwargs.items():
            object.__setattr__(settings, k, v)
        try:
            yield
        finally:
            for k, v in original.items():
                object.__setattr__(settings, k, v)

    return _ctx()


def _google_settings():
    return _patch_settings(
        GOOGLE_CLIENT_ID=_FAKE_CLIENT_ID,
        GOOGLE_CLIENT_SECRET=_FAKE_CLIENT_SECRET,
        GOOGLE_REDIRECT_URI=_FAKE_REDIRECT_URI,
    )


# ---------------------------------------------------------------------------
# /google/start — unconfigured → 503
# ---------------------------------------------------------------------------

async def test_google_start_unconfigured_503(async_client):
    """Without GOOGLE_CLIENT_ID etc., /google/start must return 503."""
    # Ensure the settings are None (they are by default in test env).
    with _patch_settings(GOOGLE_CLIENT_ID=None, GOOGLE_CLIENT_SECRET=None, GOOGLE_REDIRECT_URI=None):
        resp = await async_client.get("/api/v1/auth/google/start")
    assert resp.status_code == 503, resp.text
    assert resp.json()["detail"] == "google_sso_not_configured"


# ---------------------------------------------------------------------------
# /google/start — configured → 302 with required params + Redis state
# ---------------------------------------------------------------------------

async def test_google_start_configured_302(async_client, fake_redis, monkeypatch):
    """Configured /google/start must redirect to Google with state/challenge/nonce."""
    monkeypatch.setattr("dhanradar.redis_client._client", fake_redis)
    monkeypatch.setattr("dhanradar.redis_client.get_redis", lambda: fake_redis)

    with _google_settings():
        resp = await async_client.get(
            "/api/v1/auth/google/start",
            follow_redirects=False,
        )

    assert resp.status_code == 302, resp.text
    location = resp.headers["location"]
    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth"), location

    parsed = urlparse(location)
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

    assert "state" in params and len(params["state"]) > 0
    assert "nonce" in params and len(params["nonce"]) > 0
    assert "code_challenge" in params and len(params["code_challenge"]) > 0
    assert params["code_challenge_method"] == "S256"
    assert params["client_id"] == _FAKE_CLIENT_ID
    assert params["redirect_uri"] == _FAKE_REDIRECT_URI

    # Redis state must be stored.
    state_key = f"auth:oauth_state:{params['state']}"
    raw = await fake_redis.get(state_key)
    assert raw is not None, "OAuth state not stored in Redis"
    data = json.loads(raw)
    assert data["nonce"] == params["nonce"]
    assert "code_verifier" in data


# ---------------------------------------------------------------------------
# /google/callback — unknown state → error redirect
# ---------------------------------------------------------------------------

async def test_google_callback_unknown_state_redirects(async_client):
    """A callback with an unrecognised state must redirect to the error URL."""
    with _google_settings():
        resp = await async_client.get(
            "/api/v1/auth/google/callback",
            params={"state": "nonexistent-state", "code": "some-code"},
            follow_redirects=False,
        )
    assert resp.status_code == 302, resp.text
    assert "google_auth_failed" in resp.headers["location"]


# ---------------------------------------------------------------------------
# /google/callback — happy path (new user created, 303 to /dashboard + cookies)
# ---------------------------------------------------------------------------

async def test_google_callback_happy_path_new_user(async_client, fake_redis, monkeypatch):
    """
    Full happy path: stored state → exchange_code_with_verifier → verify_id_token
    → new user created → 303 redirect to /dashboard with auth cookies set.
    """
    monkeypatch.setattr("dhanradar.redis_client._client", fake_redis)
    monkeypatch.setattr("dhanradar.redis_client.get_redis", lambda: fake_redis)

    # Pre-plant state in Redis.
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    state_payload = json.dumps({"nonce": nonce, "code_verifier": code_verifier, "next": "/dashboard"})
    await fake_redis.set(f"auth:oauth_state:{state}", state_payload, ex=600)

    claims = _fake_claims(nonce=nonce)

    with _google_settings():
        with patch(
            "dhanradar.auth.google.exchange_code_with_verifier",
            new=AsyncMock(return_value={"id_token": "fake.id.token"}),
        ), patch(
            "dhanradar.auth.google.verify_id_token",
            new=AsyncMock(return_value=claims),
        ):
            resp = await async_client.get(
                "/api/v1/auth/google/callback",
                params={"state": state, "code": "google-auth-code"},
                follow_redirects=False,
            )

    assert resp.status_code == 303, resp.text
    assert resp.headers["location"] == "/dashboard"

    access = extract_cookie(resp, "__Host-access")
    refresh = extract_cookie(resp, "__Host-refresh")
    assert access is not None, "Expected __Host-access cookie after Google SSO login"
    assert refresh is not None, "Expected __Host-refresh cookie after Google SSO login"


# ---------------------------------------------------------------------------
# /google/callback — existing password user, same email → REJECTED (no auto-link)
# ---------------------------------------------------------------------------

async def test_google_callback_password_account_not_autolinked(async_client, fake_redis, monkeypatch, db_session):
    """
    A Google sign-in whose email matches an existing PASSWORD account must be
    rejected with account_exists_use_password — never auto-linked.  DhanRadar
    does not verify local emails, so silently linking would let an attacker who
    controls the address on Google's side take over the local account
    (Tier-B security review finding).
    """
    monkeypatch.setattr("dhanradar.redis_client._client", fake_redis)
    monkeypatch.setattr("dhanradar.redis_client.get_redis", lambda: fake_redis)

    email = "existing_user@example.com"

    # Create a password-based user first.
    signup_resp = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "ExistingPass42!"},
    )
    assert signup_resp.status_code == 201, signup_resp.text

    # Pre-plant OAuth state.
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    state_payload = json.dumps({"nonce": nonce, "code_verifier": code_verifier, "next": "/dashboard"})
    await fake_redis.set(f"auth:oauth_state:{state}", state_payload, ex=600)

    claims = _fake_claims(sub=_FAKE_SUB, email=email, nonce=nonce)

    with _google_settings():
        with patch(
            "dhanradar.auth.google.exchange_code_with_verifier",
            new=AsyncMock(return_value={"id_token": "fake.id.token"}),
        ), patch(
            "dhanradar.auth.google.verify_id_token",
            new=AsyncMock(return_value=claims),
        ):
            resp = await async_client.get(
                "/api/v1/auth/google/callback",
                params={"state": state, "code": "google-auth-code"},
                follow_redirects=False,
            )

    assert resp.status_code == 302, resp.text
    assert resp.headers["location"] == "/login?error=account_exists_use_password"

    # No session cookies may be issued on the rejection path.
    assert extract_cookie(resp, "__Host-access") is None
    assert extract_cookie(resp, "__Host-refresh") is None

    # Verify google_sub was NOT persisted.
    from sqlalchemy import select

    from dhanradar.models.auth import User

    user = await db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    assert user.google_sub is None


# ---------------------------------------------------------------------------
# /google/callback — deletion_requested_at set → account_deletion_pending redirect
# ---------------------------------------------------------------------------

async def test_google_callback_deletion_pending_redirect(
    async_client, fake_redis, monkeypatch, db_session
):
    """A user with deletion_requested_at set must be redirected to the deletion-pending URL."""
    monkeypatch.setattr("dhanradar.redis_client._client", fake_redis)
    monkeypatch.setattr("dhanradar.redis_client.get_redis", lambda: fake_redis)

    email = "deletion@example.com"
    signup_resp = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "DeletionPass42!"},
    )
    assert signup_resp.status_code == 201, signup_resp.text

    # Mark the user as pending deletion.
    from sqlalchemy import update as sa_update

    from dhanradar.models.auth import User

    await db_session.execute(
        sa_update(User)
        .where(User.email == email)
        .values(deletion_requested_at=datetime.now(UTC))
    )
    await db_session.commit()

    # Pre-plant state.
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    state_payload = json.dumps(
        {"nonce": nonce, "code_verifier": secrets.token_urlsafe(64), "next": "/dashboard"}
    )
    await fake_redis.set(f"auth:oauth_state:{state}", state_payload, ex=600)

    claims = _fake_claims(sub=_FAKE_SUB, email=email, nonce=nonce)

    with _google_settings():
        with patch(
            "dhanradar.auth.google.exchange_code_with_verifier",
            new=AsyncMock(return_value={"id_token": "fake.id.token"}),
        ), patch(
            "dhanradar.auth.google.verify_id_token",
            new=AsyncMock(return_value=claims),
        ):
            resp = await async_client.get(
                "/api/v1/auth/google/callback",
                params={"state": state, "code": "some-code"},
                follow_redirects=False,
            )

    assert resp.status_code == 302, resp.text
    assert "account_deletion_pending" in resp.headers["location"]


# ---------------------------------------------------------------------------
# /google/callback — email_verified=False → error redirect
# ---------------------------------------------------------------------------

async def test_google_callback_unverified_email_redirects(
    async_client, fake_redis, monkeypatch
):
    """Claims with email_verified=False must trigger the error redirect."""
    monkeypatch.setattr("dhanradar.redis_client._client", fake_redis)
    monkeypatch.setattr("dhanradar.redis_client.get_redis", lambda: fake_redis)

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    state_payload = json.dumps(
        {"nonce": nonce, "code_verifier": secrets.token_urlsafe(64), "next": "/dashboard"}
    )
    await fake_redis.set(f"auth:oauth_state:{state}", state_payload, ex=600)

    unverified_claims = _fake_claims(nonce=nonce, email_verified=False)

    with _google_settings():
        with patch(
            "dhanradar.auth.google.exchange_code_with_verifier",
            new=AsyncMock(return_value={"id_token": "fake.id.token"}),
        ), patch(
            "dhanradar.auth.google.verify_id_token",
            new=AsyncMock(return_value=unverified_claims),
        ):
            resp = await async_client.get(
                "/api/v1/auth/google/callback",
                params={"state": state, "code": "some-code"},
                follow_redirects=False,
            )

    assert resp.status_code == 302, resp.text
    assert "google_auth_failed" in resp.headers["location"]
