"""
Integration tests for the billing module (Stage 2 Step 7).

Covers:
  - GET /billing/plans returns active plans (public).
  - POST /billing/checkout: 401 anon, 400 missing Idempotency-Key,
    success creates a Razorpay subscription with user_id from the SESSION,
    and is idempotent (same key → same response, Razorpay called once).
  - POST /billing/webhook (re-mounted) processes a valid event.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid

import pytest

from dhanradar.models.billing import Plan
from tests.conftest import extract_cookie, make_auth_headers

pytestmark = pytest.mark.integration


class _FakeSubscriptionAPI:
    def __init__(self, counter):
        self._counter = counter

    def create(self, data):
        self._counter["calls"] += 1
        self._counter["last_notes"] = data.get("notes")
        self._counter["last_plan"] = data.get("plan_id")
        return {"id": f"sub_{uuid.uuid4().hex[:10]}"}


class _FakeClient:
    def __init__(self, *a, **k):
        # counter is injected via the module-level holder below
        self.subscription = _FakeSubscriptionAPI(_COUNTER)


_COUNTER = {"calls": 0, "last_notes": None, "last_plan": None}


@pytest.fixture()
def patch_razorpay(monkeypatch):
    _COUNTER.update({"calls": 0, "last_notes": None, "last_plan": None})
    import dhanradar.billing.service as svc
    monkeypatch.setattr(svc.razorpay, "Client", _FakeClient)
    return _COUNTER


async def _seed_plan(db_session, plan_id="pro_monthly", price=39900) -> None:
    # B7/B8: a billing-ready plan carries the REAL Razorpay plan id + per-plan
    # total_count. Without them, create_checkout fails safe (503) — so the
    # success-path tests must seed them (mirrors production catalog seeding).
    db_session.add(
        Plan(
            id=plan_id,
            name="Pro Monthly",
            price_inr=price,
            interval="month",
            features=["a"],
            razorpay_plan_id=f"plan_{plan_id}",
            total_count=12,
        )
    )
    await db_session.commit()


async def _signup(async_client) -> tuple[str, str]:
    email = f"bill_{uuid.uuid4().hex[:8]}@example.com"
    r = await async_client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "BillingPass42!"}
    )
    assert r.status_code == 201, r.text
    return str(r.json()["user"]["id"]), extract_cookie(r, "__Host-access")


async def test_plans_public_lists_active(async_client, db_session):
    await _seed_plan(db_session)
    r = await async_client.get("/api/v1/billing/plans")
    assert r.status_code == 200, r.text
    ids = [p["id"] for p in r.json()]
    assert "pro_monthly" in ids


async def test_checkout_requires_auth(async_client, db_session, patch_razorpay):
    await _seed_plan(db_session)
    r = await async_client.post(
        "/api/v1/billing/checkout",
        json={"plan_id": "pro_monthly"},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert r.status_code == 401, r.text
    assert patch_razorpay["calls"] == 0


async def test_checkout_requires_idempotency_key(async_client, db_session, patch_razorpay):
    await _seed_plan(db_session)
    _, access = await _signup(async_client)
    r = await async_client.post(
        "/api/v1/billing/checkout",
        json={"plan_id": "pro_monthly"},
        headers=make_auth_headers(access_token=access),
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "idempotency_key_required"
    assert patch_razorpay["calls"] == 0


async def test_checkout_success_and_idempotent(async_client, db_session, patch_razorpay):
    await _seed_plan(db_session)
    user_id, access = await _signup(async_client)
    key = str(uuid.uuid4())
    headers = {**make_auth_headers(access_token=access), "Idempotency-Key": key}

    r1 = await async_client.post(
        "/api/v1/billing/checkout", json={"plan_id": "pro_monthly"}, headers=headers
    )
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["amount_inr"] == 39900
    assert body1["order_id"].startswith("sub_")
    # user_id pinned from session, not body
    assert patch_razorpay["last_notes"] == {"user_id": user_id}
    assert patch_razorpay["calls"] == 1

    # Replay with the SAME key → same response, Razorpay NOT called again.
    r2 = await async_client.post(
        "/api/v1/billing/checkout", json={"plan_id": "pro_monthly"}, headers=headers
    )
    assert r2.status_code == 200, r2.text
    assert r2.json() == body1
    assert patch_razorpay["calls"] == 1, "idempotent replay must not re-create"


async def test_checkout_same_key_different_plan_conflict(async_client, db_session, patch_razorpay):
    """Reusing an Idempotency-Key with a different plan must 409 (not silently
    return the first plan's response, and not create a second subscription)."""
    await _seed_plan(db_session, plan_id="pro_monthly", price=39900)
    await _seed_plan(db_session, plan_id="pro_plus_annual", price=399900)
    _, access = await _signup(async_client)
    key = str(uuid.uuid4())
    h = {**make_auth_headers(access_token=access), "Idempotency-Key": key}

    r1 = await async_client.post("/api/v1/billing/checkout", json={"plan_id": "pro_monthly"}, headers=h)
    assert r1.status_code == 200, r1.text

    r2 = await async_client.post("/api/v1/billing/checkout", json={"plan_id": "pro_plus_annual"}, headers=h)
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"] == "idempotency_key_conflict"
    assert patch_razorpay["calls"] == 1, "conflicting replay must not create a 2nd subscription"


async def test_checkout_unknown_plan_404(async_client, db_session, patch_razorpay):
    _, access = await _signup(async_client)
    r = await async_client.post(
        "/api/v1/billing/checkout",
        json={"plan_id": "does_not_exist"},
        headers={**make_auth_headers(access_token=access), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "plan_not_found"
    assert patch_razorpay["calls"] == 0


async def test_webhook_remounted_at_billing(async_client, db_session):
    """The re-mounted /billing/webhook must reject a missing signature (400),
    proving it uses the same verify-before-parse handler."""
    r = await async_client.post(
        "/api/v1/billing/webhook",
        content=b'{"event":"subscription.activated"}',
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "missing_signature"


# ---------------------------------------------------------------------------
# B9 — gateway-failure no-double-charge guarantee
# ---------------------------------------------------------------------------

class _FailingSubscriptionAPI:
    """Counts calls and always raises — simulates a Razorpay outage/timeout."""

    def __init__(self, counter):
        self._counter = counter

    def create(self, data):
        self._counter["calls"] += 1
        raise RuntimeError("simulated gateway outage")


class _FailingClient:
    def __init__(self, *a, **k):
        self.subscription = _FailingSubscriptionAPI(_COUNTER)


@pytest.fixture()
def patch_razorpay_failing(monkeypatch):
    _COUNTER.update({"calls": 0, "last_notes": None, "last_plan": None})
    import dhanradar.billing.service as svc
    monkeypatch.setattr(svc.razorpay, "Client", _FailingClient)
    return _COUNTER


async def test_checkout_gateway_failure_502_then_retry_409_no_double_charge(
    async_client, db_session, patch_razorpay_failing
):
    """B9: when the gateway fails, the first attempt is 502 and the gateway was
    called exactly once; an immediate retry with the SAME Idempotency-Key is
    refused with 409 (lock held) WITHOUT a second gateway call — the
    no-double-charge guarantee — and advertises Retry-After."""
    await _seed_plan(db_session)
    _, access = await _signup(async_client)
    key = str(uuid.uuid4())
    headers = {**make_auth_headers(access_token=access), "Idempotency-Key": key}

    r1 = await async_client.post(
        "/api/v1/billing/checkout", json={"plan_id": "pro_monthly"}, headers=headers
    )
    assert r1.status_code == 502, r1.text
    assert r1.json()["detail"] == "payment_gateway_unavailable"
    assert patch_razorpay_failing["calls"] == 1

    r2 = await async_client.post(
        "/api/v1/billing/checkout", json={"plan_id": "pro_monthly"}, headers=headers
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"] == "checkout_in_progress"
    assert r2.headers.get("Retry-After") == "60"
    assert patch_razorpay_failing["calls"] == 1, "retry must NOT make a second gateway call"


# ---------------------------------------------------------------------------
# B9 — re-mounted webhook processes a VALID event (not just rejects bad sig)
# ---------------------------------------------------------------------------

def _wh_sig(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


async def test_webhook_remounted_processes_valid_event(async_client, db_session, monkeypatch):
    """B9: the re-mounted /billing/webhook must PROCESS a validly-signed event
    end-to-end (the plan's 'both paths' acceptance), not only reject a bad sig."""
    from sqlalchemy import select

    import dhanradar.subscriptions.service as sub_svc
    from dhanradar.config import settings
    from dhanradar.models.auth import User, UserTierEnum

    monkeypatch.setattr(
        sub_svc, "EXACT_PLAN_TIERS", {"plan_pro_monthly": UserTierEnum.pro}
    )

    user_id, _ = await _signup(async_client)
    payload = {
        "event": "subscription.activated",
        "payload": {
            "subscription": {
                "entity": {
                    "id": f"sub_{uuid.uuid4().hex[:8]}",
                    "plan_id": "plan_pro_monthly",
                    "status": "active",
                    "customer_id": "cust_TEST",
                    "current_start": 1700000000,
                    "current_end": 1702592000,
                    "notes": {"user_id": user_id},
                }
            }
        },
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = _wh_sig(settings.RAZORPAY_WEBHOOK_SECRET, body)

    r = await async_client.post(
        "/api/v1/billing/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": f"evt_{uuid.uuid4().hex}",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok"

    db_user = await db_session.scalar(select(User).where(User.id == uuid.UUID(user_id)))
    await db_session.refresh(db_user)
    assert db_user.tier == UserTierEnum.pro, f"Got {db_user.tier!r}"
