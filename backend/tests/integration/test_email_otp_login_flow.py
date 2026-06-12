"""
Integration tests for the email-OTP login flow (Feature 3).

Flow under test:
  POST /auth/email-otp/request (202, code delivered to mock)
  POST /auth/email-otp/login with captured code → 200 + cookies
  POST /auth/email-otp/login with wrong code → 401
  5 wrong codes from distinct IPs → account locked → 6th attempt → 401 (not 429)
  unknown email request → 202 (silent)
  deletion-pending user → 202 (silent, no send)

Infrastructure: same as test_totp_login_flow.py — Postgres + fakeredis + ephemeral RSA.

CRITICAL TEST TRAP (mirrors TOTP integration test note):
  The per-IP rate limit (5/60s on /email-otp/login) equals the account-lock
  threshold (5).  A single-IP test hits the per-IP 429 before the account-lock
  generic-401 branch runs.  To exercise the lock's generic-401 the brute-force
  loop MUST vary CF-Connecting-IP per request (distributed-attacker model).
  This mirrors the identical trap in test_totp_login_flow.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.conftest import extract_cookie

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _signup(client, email: str, password: str = "ValidPass42!"):
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password},
    )
    access = extract_cookie(resp, "__Host-access")
    return resp, access


async def _request_otp(client, email: str, deliver_mock=None):
    """POST /auth/email-otp/request and return (response, captured_code)."""
    resp = await client.post(
        "/api/v1/auth/email-otp/request",
        json={"email": email},
    )
    code = None
    if deliver_mock is not None and deliver_mock.called:
        # The code is embedded in the text body as a 6-digit sequence.
        import re
        _, call_kwargs = deliver_mock.call_args
        text_body = call_kwargs.get("text", "")
        m = re.search(r"\b(\d{6})\b", text_body)
        if m:
            code = m.group(1)
    return resp, code


# ---------------------------------------------------------------------------
# Happy path: full request → login flow
# ---------------------------------------------------------------------------

async def test_email_otp_happy_path(async_client, monkeypatch):
    """
    Full flow: signup → request OTP (mocked delivery) → login with OTP → cookies set.
    """
    from dhanradar.config import settings
    from dhanradar.notifications.channels import DeliveryResult

    monkeypatch.setattr(settings, "RESEND_API_KEY", "test-resend-key")

    deliver_mock = AsyncMock(return_value=DeliveryResult(ok=True, transient=False, code="ok"))
    monkeypatch.setattr("dhanradar.notifications.channels.deliver_email", deliver_mock)

    email = "emailotp_happy@example.com"
    await _signup(async_client, email)

    resp, code = await _request_otp(async_client, email, deliver_mock)
    assert resp.status_code == 202, resp.text
    assert resp.json()["message"] == "otp_sent_if_account_exists"
    assert code is not None, "Should have captured the OTP from deliver_email args"

    # Login with the captured code.
    login_resp = await async_client.post(
        "/api/v1/auth/email-otp/login",
        json={"email": email, "code": code},
    )
    assert login_resp.status_code == 200, login_resp.text
    body = login_resp.json()
    assert body["message"] == "login_successful"
    assert body["user"]["email"] == email

    new_access = extract_cookie(login_resp, "__Host-access")
    new_refresh = extract_cookie(login_resp, "__Host-refresh")
    assert new_access is not None, "Expected __Host-access cookie after email OTP login"
    assert new_refresh is not None, "Expected __Host-refresh cookie after email OTP login"


# ---------------------------------------------------------------------------
# Wrong code → 401
# ---------------------------------------------------------------------------

async def test_email_otp_wrong_code_401(async_client, monkeypatch):
    from dhanradar.config import settings
    from dhanradar.notifications.channels import DeliveryResult

    monkeypatch.setattr(settings, "RESEND_API_KEY", "test-resend-key")
    deliver_mock = AsyncMock(return_value=DeliveryResult(ok=True, transient=False, code="ok"))
    monkeypatch.setattr("dhanradar.notifications.channels.deliver_email", deliver_mock)

    email = "emailotp_wrong@example.com"
    await _signup(async_client, email)
    await _request_otp(async_client, email, deliver_mock)

    resp = await async_client.post(
        "/api/v1/auth/email-otp/login",
        json={"email": email, "code": "000000"},
    )
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"] == "invalid_credentials"


# ---------------------------------------------------------------------------
# Brute-force lock (5 wrong codes → still 401, not 429)
# ---------------------------------------------------------------------------

async def test_email_otp_brute_force_lock_stays_generic(async_client, monkeypatch):
    """
    5 wrong codes from distinct IPs lock the account.  The 6th attempt must
    still return 401 (not 429) — per security invariant: a 429 on this
    unauthenticated surface would leak that the account exists.

    Each request uses a DISTINCT CF-Connecting-IP to keep the per-IP rate
    limiter below its own threshold.  This is the same pattern as
    test_totp_login_brute_force_lock_stays_generic.
    """
    from dhanradar.config import settings
    from dhanradar.notifications.channels import DeliveryResult

    monkeypatch.setattr(settings, "RESEND_API_KEY", "test-resend-key")
    deliver_mock = AsyncMock(return_value=DeliveryResult(ok=True, transient=False, code="ok"))
    monkeypatch.setattr("dhanradar.notifications.channels.deliver_email", deliver_mock)

    email = "emailotp_lock@example.com"
    await _signup(async_client, email)
    await _request_otp(async_client, email, deliver_mock)

    for i in range(5):
        r = await async_client.post(
            "/api/v1/auth/email-otp/login",
            json={"email": email, "code": "000000"},
            headers={"CF-Connecting-IP": f"203.0.113.{20 + i}"},
        )
        assert r.status_code == 401, r.text

    # 6th attempt from a fresh IP — per-IP limiter is clear, account is locked;
    # the lock must answer with a generic 401, never a 429.
    locked = await async_client.post(
        "/api/v1/auth/email-otp/login",
        json={"email": email, "code": "111111"},
        headers={"CF-Connecting-IP": "203.0.113.99"},
    )
    assert locked.status_code == 401, locked.text
    assert locked.json()["detail"] == "invalid_credentials"


# ---------------------------------------------------------------------------
# Unknown email request → 202 (identical to known account, no oracle)
# ---------------------------------------------------------------------------

async def test_email_otp_request_unknown_email_returns_202(async_client, monkeypatch):
    from dhanradar.config import settings
    from dhanradar.notifications.channels import DeliveryResult

    monkeypatch.setattr(settings, "RESEND_API_KEY", "test-resend-key")
    deliver_mock = AsyncMock(return_value=DeliveryResult(ok=True, transient=False, code="ok"))
    monkeypatch.setattr("dhanradar.notifications.channels.deliver_email", deliver_mock)

    resp = await async_client.post(
        "/api/v1/auth/email-otp/request",
        json={"email": "nobody_at_all@example.com"},
    )
    assert resp.status_code == 202, resp.text
    assert resp.json()["message"] == "otp_sent_if_account_exists"
    # No email must have been sent for an unknown account.
    assert deliver_mock.call_count == 0


# ---------------------------------------------------------------------------
# 503 when RESEND_API_KEY is not configured
# ---------------------------------------------------------------------------

async def test_email_otp_request_503_without_resend_key(async_client, monkeypatch):
    from dhanradar.config import settings

    monkeypatch.setattr(settings, "RESEND_API_KEY", "")

    resp = await async_client.post(
        "/api/v1/auth/email-otp/request",
        json={"email": "someuser@example.com"},
    )
    assert resp.status_code == 503, resp.text
    assert resp.json()["detail"] == "email_otp_not_configured"


# ---------------------------------------------------------------------------
# Unknown email login → 401 with same body as wrong-code (enumeration safety)
# ---------------------------------------------------------------------------

async def test_email_otp_login_unknown_email_same_body_as_wrong_code(
    async_client, monkeypatch
):
    from dhanradar.config import settings
    from dhanradar.notifications.channels import DeliveryResult

    monkeypatch.setattr(settings, "RESEND_API_KEY", "test-resend-key")
    deliver_mock = AsyncMock(return_value=DeliveryResult(ok=True, transient=False, code="ok"))
    monkeypatch.setattr("dhanradar.notifications.channels.deliver_email", deliver_mock)

    # Known account, wrong code.
    email = "emailotp_enum@example.com"
    await _signup(async_client, email)
    await _request_otp(async_client, email, deliver_mock)
    wrong = await async_client.post(
        "/api/v1/auth/email-otp/login",
        json={"email": email, "code": "000000"},
    )

    # Unknown account.
    unknown = await async_client.post(
        "/api/v1/auth/email-otp/login",
        json={"email": "nobody_login@example.com", "code": "000000"},
    )

    assert wrong.status_code == unknown.status_code
    assert wrong.json()["detail"] == unknown.json()["detail"]
