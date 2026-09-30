"""
Unit tests for the public Contact-Us enquiry router (no DB, no network).

Mocks `dhanradar.contact.router.deliver_email` directly (module-level import,
not the `channels` module) and uses the shared `patch_redis` fixture so the
RateLimit dependency runs against fakeredis.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.testclient import TestClient

from dhanradar.contact import router as contact_router_module
from dhanradar.contact.router import router as contact_router
from dhanradar.deps import UserContext, current_user_or_anonymous
from dhanradar.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from dhanradar.notifications.channels import DeliveryResult

VALID_BODY = {
    "name": "Asha Rao",
    "email": "asha@example.com",
    "topic": "general",
    "message": "Hello, I have a question about my portfolio report.",
}


def _make_app(*, anonymous: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(contact_router, prefix="/api/v1")
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    async def _override_user() -> UserContext:
        if anonymous:
            return UserContext()
        return UserContext(user_id="11111111-1111-1111-1111-111111111111", is_anonymous=False)

    app.dependency_overrides[current_user_or_anonymous] = _override_user
    return app


@pytest.fixture(autouse=True)
def _redis(patch_redis):
    """Every test in this module hits the RateLimit dependency; back it with
    fakeredis for all of them, not just tests that request a named fixture."""
    return patch_redis


def _mock_deliver_ok(monkeypatch) -> list[dict]:
    calls: list[dict] = []

    async def _fake(**kwargs):
        calls.append(kwargs)
        return DeliveryResult(ok=True, transient=False, code="ok")

    monkeypatch.setattr(contact_router_module, "deliver_email", _fake)
    monkeypatch.setattr(contact_router_module, "email_configured", lambda: True)
    return calls


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_valid_submission_sends_and_returns_202(monkeypatch):
    calls = _mock_deliver_ok(monkeypatch)
    resp = TestClient(_make_app()).post("/api/v1/contact", json=VALID_BODY)
    assert resp.status_code == 202, resp.text
    assert resp.json() == {"status": "received"}
    assert len(calls) == 1
    kw = calls[0]
    assert kw["to"] == "connect@dhanradar.com"
    assert kw["reply_to"] == "asha@example.com"
    assert "Asha Rao" in kw["subject"]


def test_html_and_name_are_escaped(monkeypatch):
    calls = _mock_deliver_ok(monkeypatch)
    body = dict(VALID_BODY)
    body["name"] = "<script>alert(1)</script>"
    body["message"] = "Hi <script>alert(2)</script> please help, this is my message."
    resp = TestClient(_make_app()).post("/api/v1/contact", json=body)
    assert resp.status_code == 202, resp.text
    html_body = calls[0]["html"]
    assert "<script>" not in html_body
    assert "&lt;script&gt;" in html_body


def test_signed_in_flag_reflected_in_body(monkeypatch):
    calls = _mock_deliver_ok(monkeypatch)
    resp = TestClient(_make_app(anonymous=False)).post("/api/v1/contact", json=VALID_BODY)
    assert resp.status_code == 202, resp.text
    assert "Signed in: True" in calls[0]["text"]


# ---------------------------------------------------------------------------
# Honeypot
# ---------------------------------------------------------------------------


def test_honeypot_filled_returns_202_but_does_not_send(monkeypatch):
    calls = _mock_deliver_ok(monkeypatch)
    body = dict(VALID_BODY)
    body["website"] = "https://spam.example"
    resp = TestClient(_make_app()).post("/api/v1/contact", json=body)
    assert resp.status_code == 202, resp.text
    assert resp.json() == {"status": "received"}
    assert calls == []


# ---------------------------------------------------------------------------
# Validation (422)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "override",
    [
        {"email": "not-an-email"},
        {"message": "short"},
        {"name": "x" * 101},
        {"name": "Bad\nName"},
        {"topic": "not_a_real_topic"},
    ],
)
def test_invalid_fields_yield_422(monkeypatch, override):
    _mock_deliver_ok(monkeypatch)
    body = dict(VALID_BODY)
    body.update(override)
    resp = TestClient(_make_app()).post("/api/v1/contact", json=body)
    assert resp.status_code == 422, resp.text


def test_extra_field_yields_422(monkeypatch):
    _mock_deliver_ok(monkeypatch)
    body = dict(VALID_BODY)
    body["extra_field"] = "nope"
    resp = TestClient(_make_app()).post("/api/v1/contact", json=body)
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# Delivery failure / unconfigured (503)
# ---------------------------------------------------------------------------


def test_delivery_failure_returns_503(monkeypatch):
    async def _fake_fail(**kwargs):
        return DeliveryResult(ok=False, transient=True, code="http_500")

    monkeypatch.setattr(contact_router_module, "deliver_email", _fake_fail)
    monkeypatch.setattr(contact_router_module, "email_configured", lambda: True)
    resp = TestClient(_make_app()).post("/api/v1/contact", json=VALID_BODY)
    assert resp.status_code == 503, resp.text
    assert resp.json()["detail"] == "contact_unavailable"


def test_no_provider_configured_returns_503(monkeypatch):
    called = False

    async def _fake(**kwargs):
        nonlocal called
        called = True
        return DeliveryResult(ok=True, transient=False, code="ok")

    monkeypatch.setattr(contact_router_module, "deliver_email", _fake)
    monkeypatch.setattr(contact_router_module, "email_configured", lambda: False)
    resp = TestClient(_make_app()).post("/api/v1/contact", json=VALID_BODY)
    assert resp.status_code == 503, resp.text
    assert resp.json()["detail"] == "contact_unavailable"
    assert called is False


# ---------------------------------------------------------------------------
# Rate limit
# ---------------------------------------------------------------------------


def test_rate_limit_4th_request_yields_429(monkeypatch):
    _mock_deliver_ok(monkeypatch)
    client = TestClient(_make_app())
    headers = {"CF-Connecting-IP": "203.0.113.99"}
    statuses = []
    for _ in range(4):
        resp = client.post("/api/v1/contact", json=VALID_BODY, headers=headers)
        statuses.append(resp.status_code)
    assert statuses == [202, 202, 202, 429], statuses


def test_daily_cap_blocks_after_limit(monkeypatch):
    """Site-wide cap protects the shared email quota (login codes) from a many-IP flood."""
    calls = _mock_deliver_ok(monkeypatch)
    monkeypatch.setattr(contact_router_module, "_DAILY_CAP", 2)
    client = TestClient(_make_app())
    statuses = [
        client.post(
            "/api/v1/contact", json=VALID_BODY, headers={"CF-Connecting-IP": f"198.51.100.{i}"}
        ).status_code
        for i in range(3)
    ]
    assert statuses == [202, 202, 503], statuses
    assert len(calls) == 2
