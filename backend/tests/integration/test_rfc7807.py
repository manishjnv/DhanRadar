"""
Integration tests for the RFC7807 problem+json error contract (Stage 2 Step 5).

Asserts:
  - Unknown route → 404 problem+json with {type,title,status,request_id} + instance.
  - X-Request-ID response header is present and echoes an inbound id.
  - Validation error → 422 problem with type=validation_error.
  - Backward-compat: the webhook 400 still exposes detail == "missing_signature".
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


async def test_unknown_route_is_problem_json(async_client):
    resp = await async_client.get("/api/v1/this-route-does-not-exist")
    assert resp.status_code == 404, resp.text
    assert resp.headers.get("content-type", "").startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == 404
    assert body["type"].startswith("https://dhanradar.com/errors/")
    assert body["title"]
    assert body["request_id"]
    assert body.get("instance") == "/api/v1/this-route-does-not-exist"


async def test_request_id_header_echoed(async_client):
    rid = f"test-{uuid.uuid4().hex}"
    resp = await async_client.get(
        "/api/v1/this-route-does-not-exist",
        headers={"X-Request-ID": rid},
    )
    assert resp.headers.get("X-Request-ID") == rid
    assert resp.json()["request_id"] == rid


async def test_validation_error_is_problem_422(async_client):
    # signup with a malformed body (missing password) → 422 validation problem
    resp = await async_client.post("/api/v1/auth/signup", json={"email": "x@y.com"})
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["status"] == 422
    assert body["type"].endswith("/validation_error")
    assert "errors" in body
    # never echo the raw input value back
    for e in body["errors"]:
        assert "input" not in e


async def test_webhook_missing_signature_detail_preserved(async_client):
    # Backward-compat: detail machine code must survive the RFC7807 wrapping.
    resp = await async_client.post(
        "/api/v1/subscriptions/webhook",
        content=b'{"event":"subscription.activated"}',
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["detail"] == "missing_signature"
    assert body["status"] == 400
    assert body["request_id"]
