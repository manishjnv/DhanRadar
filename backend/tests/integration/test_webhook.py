"""
Integration tests for POST /api/v1/subscriptions/webhook.

Infrastructure contract
-----------------------
- Uses `async_client` fixture (httpx.AsyncClient via ASGITransport).
- DB = compose `dhanradar-postgres` via db_session; truncated between tests.
- Redis = fakeredis via patch_redis.

Signature scheme
----------------
Razorpay uses HMAC-SHA256. The helper `_make_sig(secret, body)` produces the
value that must appear in the `X-Razorpay-Signature` header:

    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

The router calls `razorpay.Client(...).utility.verify_webhook_signature(body_str, sig, secret)`.
Internally, the razorpay SDK does the same HMAC-SHA256 and compares with the
provided signature. Our helper produces an identical result so valid payloads
pass and we can also craft invalid ones by mutating the body after signing.

Razorpay credentials used in tests
-----------------------------------
RAZORPAY_KEY_ID / KEY_SECRET / WEBHOOK_SECRET are set to deterministic test
values in conftest.py before any dhanradar module is imported. See conftest.py
preamble for the exact values. Here we read them from settings.

Dedup / idempotency
--------------------
The router stores `auth:rzp_evt:{event_id}` in Redis (7-day TTL).
Replaying the same body+headers within a test (fakeredis is flushed between
tests) returns {"status": "duplicate_ignored"}.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid

import pytest
from sqlalchemy import select, text

from dhanradar.models.auth import User, UserTierEnum
from tests.conftest import extract_cookie, make_auth_headers

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sig(secret: str, body: bytes) -> str:
    """Compute the Razorpay webhook HMAC-SHA256 signature."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _webhook_body(
    event: str,
    plan_id: str,
    sub_status: str,
    user_id: str,
    rzp_sub_id: str = "sub_TEST001",
    current_start: int = 1700000000,
    current_end: int = 1702592000,
) -> bytes:
    """Build a minimal Razorpay subscription event payload."""
    payload = {
        "event": event,
        "payload": {
            "subscription": {
                "entity": {
                    "id": rzp_sub_id,
                    "plan_id": plan_id,
                    "status": sub_status,
                    "customer_id": "cust_TEST001",
                    "current_start": current_start,
                    "current_end": current_end,
                    "notes": {
                        "user_id": user_id,
                    },
                }
            }
        },
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


async def _create_user(async_client) -> tuple[str, str, str]:
    """
    Sign up a test user and return (user_id, access_token, refresh_token).
    """
    email = f"webhook_{uuid.uuid4().hex[:8]}@example.com"
    resp = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "WebhookPass42!"},
    )
    assert resp.status_code == 201, resp.text
    user_id = str(resp.json()["user"]["id"])
    access = extract_cookie(resp, "__Host-access")
    refresh = extract_cookie(resp, "__Host-refresh")
    return user_id, access, refresh


def _razorpay_secret() -> str:
    from dhanradar.config import settings
    return settings.RAZORPAY_WEBHOOK_SECRET


# ---------------------------------------------------------------------------
# Missing / bad signature → 400
# ---------------------------------------------------------------------------


async def test_webhook_missing_signature_400(async_client):
    """A request with no X-Razorpay-Signature header must be rejected with 400."""
    body = b'{"event": "subscription.activated"}'
    resp = await async_client.post(
        "/api/v1/subscriptions/webhook",
        content=body,
        headers={"Content-Type": "application/json"},
        # No X-Razorpay-Signature
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == "missing_signature"


async def test_webhook_bad_signature_400(async_client):
    """A request with an incorrect signature must be rejected with 400."""
    body = b'{"event": "subscription.activated"}'
    resp = await async_client.post(
        "/api/v1/subscriptions/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": "deadbeef" * 8,  # 64 hex chars, wrong value
        },
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == "invalid_signature"


async def test_webhook_body_tampered_after_signing_400(async_client):
    """
    Sign the original body, then send a different body with the same signature.
    Must be rejected — the HMAC is over the original body bytes.
    """
    secret = _razorpay_secret()
    original_body = b'{"event": "subscription.activated"}'
    sig = _make_sig(secret, original_body)

    tampered_body = b'{"event": "subscription.cancelled"}'  # different body

    resp = await async_client.post(
        "/api/v1/subscriptions/webhook",
        content=tampered_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
        },
    )
    assert resp.status_code == 400, resp.text


# ---------------------------------------------------------------------------
# Valid signature — subscription.activated → tier upgraded
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _map_test_plans(monkeypatch):
    """B2: tier is now derived ONLY from EXACT_PLAN_TIERS (the substring
    heuristic was removed as a privilege foot-gun). Populate the map with the
    test plan_ids, mirroring how production is seeded with real dashboard ids."""
    import dhanradar.subscriptions.service as sub_svc

    monkeypatch.setattr(
        sub_svc,
        "EXACT_PLAN_TIERS",
        {
            "plan_pro_monthly": UserTierEnum.pro,
            "dhanradar_pro_plus_annual": UserTierEnum.pro_plus,
        },
    )


async def test_webhook_activated_upgrades_tier_to_pro(async_client, db_session):
    """
    A valid subscription.activated event with plan_id containing 'pro' must:
    1. Return 200 {"status": "ok"}.
    2. Update the user's tier in Postgres to 'pro'.
    3. Flush (or update) the auth:tier:{uid} Redis cache.
    """
    user_id, _, _ = await _create_user(async_client)
    secret = _razorpay_secret()

    body = _webhook_body(
        event="subscription.activated",
        plan_id="plan_pro_monthly",       # substring "pro" → UserTierEnum.pro
        sub_status="active",
        user_id=user_id,
        rzp_sub_id=f"sub_{uuid.uuid4().hex[:8]}",
    )
    sig = _make_sig(secret, body)
    event_id = f"evt_{uuid.uuid4().hex}"

    resp = await async_client.post(
        "/api/v1/subscriptions/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": event_id,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ok"

    # Verify tier updated in DB.
    db_user = await db_session.scalar(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    assert db_user is not None
    assert db_user.tier == UserTierEnum.pro, (
        f"Expected tier=pro, got {db_user.tier!r}"
    )


async def test_webhook_activated_upgrades_tier_to_pro_plus(async_client, db_session):
    """
    A valid subscription.activated event with plan_id containing 'pro_plus'
    must upgrade the user to pro_plus.
    """
    user_id, _, _ = await _create_user(async_client)
    secret = _razorpay_secret()

    body = _webhook_body(
        event="subscription.activated",
        plan_id="dhanradar_pro_plus_annual",
        sub_status="active",
        user_id=user_id,
        rzp_sub_id=f"sub_{uuid.uuid4().hex[:8]}",
    )
    sig = _make_sig(secret, body)
    event_id = f"evt_{uuid.uuid4().hex}"

    resp = await async_client.post(
        "/api/v1/subscriptions/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": event_id,
        },
    )
    assert resp.status_code == 200, resp.text

    db_user = await db_session.scalar(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    # db_session may have stale state; expire and refresh.
    await db_session.refresh(db_user)
    assert db_user.tier == UserTierEnum.pro_plus, f"Got {db_user.tier!r}"


async def test_webhook_cancelled_downgrades_to_free(async_client, db_session):
    """
    A subscription.cancelled event (status="cancelled") must drop the user
    back to free tier regardless of the plan_id.
    """
    user_id, _, _ = await _create_user(async_client)
    secret = _razorpay_secret()

    body = _webhook_body(
        event="subscription.cancelled",
        plan_id="plan_pro_monthly",
        sub_status="cancelled",            # non-active → free
        user_id=user_id,
        rzp_sub_id=f"sub_{uuid.uuid4().hex[:8]}",
    )
    sig = _make_sig(secret, body)

    resp = await async_client.post(
        "/api/v1/subscriptions/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": f"evt_{uuid.uuid4().hex}",
        },
    )
    assert resp.status_code == 200, resp.text

    db_user = await db_session.scalar(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    await db_session.refresh(db_user)
    assert db_user.tier == UserTierEnum.free, f"Got {db_user.tier!r}"


# ---------------------------------------------------------------------------
# Idempotency: replay same body+signature+event_id → 200 duplicate_ignored
# ---------------------------------------------------------------------------


async def test_webhook_replay_duplicate_ignored(async_client, db_session):
    """
    Replaying the exact same event (same body, same signature, same
    X-Razorpay-Event-Id) must return {"status": "duplicate_ignored"} and
    leave the DB unchanged.

    First delivery upgrades to pro; second delivery of the same event
    must not reprocess (and must not re-upgrade — DB already has pro).
    """
    user_id, _, _ = await _create_user(async_client)
    secret = _razorpay_secret()
    event_id = f"evt_{uuid.uuid4().hex}"
    rzp_sub_id = f"sub_{uuid.uuid4().hex[:8]}"

    body = _webhook_body(
        event="subscription.activated",
        plan_id="plan_pro_monthly",
        sub_status="active",
        user_id=user_id,
        rzp_sub_id=rzp_sub_id,
    )
    sig = _make_sig(secret, body)

    common_headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": sig,
        "X-Razorpay-Event-Id": event_id,
    }

    # First delivery.
    resp1 = await async_client.post(
        "/api/v1/subscriptions/webhook",
        content=body,
        headers=common_headers,
    )
    assert resp1.status_code == 200, resp1.text
    assert resp1.json()["status"] == "ok"

    # Replay.
    resp2 = await async_client.post(
        "/api/v1/subscriptions/webhook",
        content=body,
        headers=common_headers,
    )
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["status"] == "duplicate_ignored", resp2.text

    # DB tier must still be pro (second delivery did not change anything).
    db_user = await db_session.scalar(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    await db_session.refresh(db_user)
    assert db_user.tier == UserTierEnum.pro


async def test_webhook_different_event_ids_processed_separately(async_client, db_session):
    """
    Two deliveries with the same body but DIFFERENT event IDs must each be
    processed. (Razorpay retries with a new event id — this is not a replay.)
    """
    user_id, _, _ = await _create_user(async_client)
    secret = _razorpay_secret()

    body = _webhook_body(
        event="subscription.activated",
        plan_id="plan_pro_monthly",
        sub_status="active",
        user_id=user_id,
        rzp_sub_id=f"sub_{uuid.uuid4().hex[:8]}",
    )
    sig = _make_sig(secret, body)

    resp1 = await async_client.post(
        "/api/v1/subscriptions/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": f"evt_{uuid.uuid4().hex}",  # unique ID
        },
    )
    assert resp1.status_code == 200, resp1.text
    assert resp1.json()["status"] == "ok"

    resp2 = await async_client.post(
        "/api/v1/subscriptions/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": f"evt_{uuid.uuid4().hex}",  # different ID
        },
    )
    # Both are processed (upsert is idempotent at DB level too).
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Missing user_id in notes — webhook must not 500
# ---------------------------------------------------------------------------


async def test_webhook_missing_user_id_in_notes_200(async_client):
    """
    A valid signature but no 'user_id' in subscription.notes must be
    handled gracefully (logged, not 500). The router returns 200 because
    the service logs and returns rather than raising.
    """
    secret = _razorpay_secret()

    payload = {
        "event": "subscription.activated",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_NOUSERID",
                    "plan_id": "plan_pro",
                    "status": "active",
                    "customer_id": "cust_001",
                    # no 'notes' key
                }
            }
        },
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = _make_sig(secret, body)

    resp = await async_client.post(
        "/api/v1/subscriptions/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": f"evt_{uuid.uuid4().hex}",
        },
    )
    # Service logs and returns None (no exception), so router returns 200 {"status":"ok"}.
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# Tier cache flushed after webhook (indirectly via /auth/me tier field)
# ---------------------------------------------------------------------------


async def test_webhook_tier_visible_on_me_after_upgrade(async_client, db_session):
    """
    After a successful webhook upgrades a user to pro, GET /auth/me must
    reflect the new tier (cache flush was called).
    """
    user_id, access, _ = await _create_user(async_client)

    # Verify initial tier is 'free'.
    me_before = await async_client.get(
        "/api/v1/auth/me",
        headers=make_auth_headers(access_token=access),
    )
    assert me_before.status_code == 200, me_before.text
    assert me_before.json()["user"]["tier"] == "free"

    # Send upgrade webhook.
    secret = _razorpay_secret()
    body = _webhook_body(
        event="subscription.activated",
        plan_id="plan_pro_monthly",
        sub_status="active",
        user_id=user_id,
        rzp_sub_id=f"sub_{uuid.uuid4().hex[:8]}",
    )
    sig = _make_sig(secret, body)

    wh_resp = await async_client.post(
        "/api/v1/subscriptions/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": f"evt_{uuid.uuid4().hex}",
        },
    )
    assert wh_resp.status_code == 200, wh_resp.text

    # /auth/me must now show the updated tier because:
    # 1. The webhook flushed auth:tier:{uid} from fakeredis.
    # 2. current_user_or_anonymous calls resolve_tier_with_db which hits DB.
    # The tier returned by /auth/me comes from resolve_tier_with_db → DB read.
    me_after = await async_client.get(
        "/api/v1/auth/me",
        headers=make_auth_headers(access_token=access),
    )
    assert me_after.status_code == 200, me_after.text
    assert me_after.json()["user"]["tier"] == "pro", (
        f"Expected tier=pro after webhook upgrade, got: {me_after.json()}"
    )
