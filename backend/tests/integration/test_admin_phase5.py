"""
Integration tests for Admin Phase 5 — suspend / unsuspend feature.

Covers:
  - Non-admin (anonymous) → 404 on suspend / unsuspend endpoints.
  - Non-admin (authenticated, non-admin user) → 404 on both endpoints.
  - Admin suspend → 200 {ok: true, status: "suspended"}, user.suspended_at set.
  - Suspended user → 403 "account_suspended" on password login.
  - Suspend is idempotent: second suspend → 200 {status: "suspended"}, no error.
  - Admin unsuspend → 200 {ok: true, status: "active"}, user can log in again.
  - Unsuspend is idempotent: unsuspend an active user → 200 {status: "active"}.
  - Suspend unknown UUID → 404.

Infrastructure: async_client, db_session, monkeypatch.setattr(settings).
Mirrors test_admin_phase2.py patterns.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _signup(client, email: str, password: str = "AdminP5Test42!") -> tuple[str, str]:
    from tests.conftest import extract_cookie

    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["user"]["id"]), extract_cookie(r, "__Host-access")


# ---------------------------------------------------------------------------
# 1. Anonymous → 404 on suspend / unsuspend endpoints
# ---------------------------------------------------------------------------


async def test_suspend_404_for_anonymous(async_client):
    """No cookie → 404 on suspend/unsuspend endpoints (surface-hiding)."""
    fake_id = "00000000-0000-0000-0000-000000000001"
    for path in [
        f"/api/v1/admin/users/{fake_id}/suspend",
        f"/api/v1/admin/users/{fake_id}/unsuspend",
    ]:
        r = await async_client.post(path, json={})
        assert r.status_code == 404, (
            f"Expected 404 for anonymous on {path}, got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 2. Authenticated non-admin → 404 on both endpoints
# ---------------------------------------------------------------------------


async def test_suspend_404_for_non_admin(async_client, monkeypatch):
    """Non-admin user → 404 on suspend / unsuspend (surface-hiding)."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")

    _uid, access = await _signup(async_client, "nonadmin_suspend@example.com")
    headers = make_auth_headers(access_token=access)

    fake_id = "00000000-0000-0000-0000-000000000001"
    for path in [
        f"/api/v1/admin/users/{fake_id}/suspend",
        f"/api/v1/admin/users/{fake_id}/unsuspend",
    ]:
        r = await async_client.post(path, json={}, headers=headers)
        assert r.status_code == 404, (
            f"Expected 404 for non-admin on {path}, got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 3. Admin suspend → 200, status="suspended"
# ---------------------------------------------------------------------------


async def test_admin_suspend_returns_suspended_status(async_client, monkeypatch):
    """Admin can suspend a user; response has status='suspended'."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, admin_access = await _signup(async_client, "admin_suspend_op@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=admin_access)

    # Create target user
    target_id, _target_access = await _signup(async_client, "target_suspend@example.com")

    r = await async_client.post(
        f"/api/v1/admin/users/{target_id}/suspend",
        json={"reason": "test suspension"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["status"] == "suspended"


# ---------------------------------------------------------------------------
# 4. Suspended user gets 403 on password login
# ---------------------------------------------------------------------------


async def test_suspended_user_gets_403_on_login(async_client, monkeypatch, db_session):
    """After suspension, password login returns 403 'account_suspended'."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, admin_access = await _signup(async_client, "admin_suspend_block@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=admin_access)

    password = "SuspendTarget5!"
    target_id, _target_access = await _signup(
        async_client, "target_suspend_block@example.com", password=password
    )

    # Suspend the target user
    r = await async_client.post(
        f"/api/v1/admin/users/{target_id}/suspend",
        json={"reason": "block test"},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    # Attempt login — must get 403
    login_r = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "target_suspend_block@example.com", "password": password},
    )
    assert login_r.status_code == 403, (
        f"Expected 403 for suspended user login, got {login_r.status_code}: {login_r.text}"
    )
    assert login_r.json()["detail"] == "account_suspended"


# ---------------------------------------------------------------------------
# 5. Suspend is idempotent
# ---------------------------------------------------------------------------


async def test_suspend_is_idempotent(async_client, monkeypatch):
    """Suspending an already-suspended user returns 200 {status: 'suspended'}."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, admin_access = await _signup(async_client, "admin_idem_suspend@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=admin_access)

    target_id, _ = await _signup(async_client, "target_idem_suspend@example.com")

    # First suspend
    r1 = await async_client.post(
        f"/api/v1/admin/users/{target_id}/suspend",
        json={},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    # Second suspend — idempotent
    r2 = await async_client.post(
        f"/api/v1/admin/users/{target_id}/suspend",
        json={"reason": "duplicate call"},
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "suspended"


# ---------------------------------------------------------------------------
# 6. Admin unsuspend → 200, user can log in again
# ---------------------------------------------------------------------------


async def test_admin_unsuspend_restores_active(async_client, monkeypatch):
    """After unsuspend, user can log in successfully."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, admin_access = await _signup(async_client, "admin_unsuspend_op@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=admin_access)

    password = "UnsuspendMe5!"
    target_id, _ = await _signup(
        async_client, "target_unsuspend@example.com", password=password
    )

    # Suspend first
    r_susp = await async_client.post(
        f"/api/v1/admin/users/{target_id}/suspend",
        json={},
        headers=headers,
    )
    assert r_susp.status_code == 200, r_susp.text

    # Unsuspend
    r_unsusp = await async_client.post(
        f"/api/v1/admin/users/{target_id}/unsuspend",
        json={},
        headers=headers,
    )
    assert r_unsusp.status_code == 200, r_unsusp.text
    body = r_unsusp.json()
    assert body["ok"] is True
    assert body["status"] == "active"

    # Login should now succeed
    login_r = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "target_unsuspend@example.com", "password": password},
    )
    assert login_r.status_code == 200, (
        f"Expected 200 after unsuspend, got {login_r.status_code}: {login_r.text}"
    )


# ---------------------------------------------------------------------------
# 7. Unsuspend is idempotent (unsuspend an active user)
# ---------------------------------------------------------------------------


async def test_unsuspend_is_idempotent(async_client, monkeypatch):
    """Unsuspending an active (never-suspended) user returns 200 {status: 'active'}."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, admin_access = await _signup(async_client, "admin_idem_unsusp@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=admin_access)

    target_id, _ = await _signup(async_client, "target_idem_unsusp@example.com")

    r = await async_client.post(
        f"/api/v1/admin/users/{target_id}/unsuspend",
        json={},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"


# ---------------------------------------------------------------------------
# 8. Suspend unknown UUID → 404
# ---------------------------------------------------------------------------


async def test_suspend_unknown_user_404(async_client, monkeypatch):
    """Suspending a UUID that doesn't exist returns 404."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, admin_access = await _signup(async_client, "admin_404_suspend@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=admin_access)

    fake_id = "00000000-0000-0000-0000-000000000099"
    r = await async_client.post(
        f"/api/v1/admin/users/{fake_id}/suspend",
        json={},
        headers=headers,
    )
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# CF-Connecting-IP note
#
# All new signup/login calls below pass a unique CF-Connecting-IP header so
# multiple tests in the same module do not collide on the per-IP 5/60s signup
# rate-limit. The existing phase5 tests use sequential emails which are
# distinct, but they do NOT set CF-Connecting-IP; if the IP-keyed limiter
# triggers before the email-keyed one, those older tests will start failing.
# The new tests here set distinct IPs ("10.5.x.y") to ensure isolation.
#
# make_auth_headers() does NOT set CF-Connecting-IP (it only builds Cookie
# headers), so the header is injected explicitly in each signup/login POST
# below.
# ---------------------------------------------------------------------------


async def _signup_with_ip(
    client,
    email: str,
    password: str = "AdminP5Test42!",
    ip_suffix: int = 1,
) -> tuple[str, str]:
    """Signup helper that injects a unique CF-Connecting-IP to avoid per-IP rate limits."""
    from tests.conftest import extract_cookie

    ip = f"10.5.0.{ip_suffix}"
    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password},
        headers={"CF-Connecting-IP": ip},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["user"]["id"]), extract_cookie(r, "__Host-access")


# ---------------------------------------------------------------------------
# 9. Refund idempotency
# ---------------------------------------------------------------------------


async def test_refund_idempotency(async_client, monkeypatch):
    """Refund endpoint:
      - First POST → 200 (refund issued, _create_razorpay_refund called once).
      - Second POST same key+amount → 200 (idempotent replay, _create_razorpay_refund NOT called again).
      - Same key, different amount → 409 idempotency_key_conflict.
      - Missing Idempotency-Key header → 400 idempotency_key_required.
    """
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, admin_access = await _signup_with_ip(
        async_client, "admin_refund_idem@example.com", ip_suffix=10
    )
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=admin_access)

    # Monkeypatch the Razorpay call; record how many times it is invoked.
    call_count = {"n": 0}

    def _fake_razorpay_refund(payment_id: str, amount_paise: int, admin_id: str) -> dict:
        call_count["n"] += 1
        return {"id": "rfnd_test"}

    import dhanradar.billing.service as billing_svc

    monkeypatch.setattr(billing_svc, "_create_razorpay_refund", _fake_razorpay_refund)

    payment_id = "pay_p5_idem_001"
    idem_key = "p5-idem-refund-k1"
    body = {"razorpay_payment_id": payment_id, "amount_inr": 100}

    # First call — must succeed and invoke _create_razorpay_refund exactly once.
    r1 = await async_client.post(
        "/api/v1/admin/billing/refund",
        json=body,
        headers={**headers, "Idempotency-Key": idem_key},
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["status"] == "refunded"
    assert call_count["n"] == 1, (
        f"Expected _create_razorpay_refund called once, got {call_count['n']}"
    )

    # Second call — same key + same amount → idempotent replay; must NOT call again.
    r2 = await async_client.post(
        "/api/v1/admin/billing/refund",
        json=body,
        headers={**headers, "Idempotency-Key": idem_key},
    )
    assert r2.status_code == 200, r2.text
    assert call_count["n"] == 1, (
        f"Idempotent replay must not call _create_razorpay_refund again; "
        f"got {call_count['n']} calls"
    )

    # Same key, different amount → 409 idempotency_key_conflict.
    body_diff_amount = {"razorpay_payment_id": payment_id, "amount_inr": 200}
    r3 = await async_client.post(
        "/api/v1/admin/billing/refund",
        json=body_diff_amount,
        headers={**headers, "Idempotency-Key": idem_key},
    )
    assert r3.status_code == 409, r3.text
    assert r3.json()["detail"] == "idempotency_key_conflict"

    # Missing Idempotency-Key header → 400 idempotency_key_required.
    r4 = await async_client.post(
        "/api/v1/admin/billing/refund",
        json=body,
        headers=headers,  # no Idempotency-Key
    )
    assert r4.status_code == 400, r4.text
    assert r4.json()["detail"] == "idempotency_key_required"


# ---------------------------------------------------------------------------
# 10. Reset-access endpoint
# ---------------------------------------------------------------------------


async def test_reset_access(async_client, monkeypatch):
    """POST /admin/users/{id}/reset-access:
      - Admin → 200 {ok: true}.
      - Non-admin → 404.
      - Unknown UUID → 404.
    """
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, admin_access = await _signup_with_ip(
        async_client, "admin_reset_access@example.com", ip_suffix=20
    )
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    admin_headers = make_auth_headers(access_token=admin_access)

    # Create a target user who will have their access reset.
    target_id, target_access = await _signup_with_ip(
        async_client, "target_reset_access@example.com", ip_suffix=21
    )

    # Admin can reset a real user.
    r = await async_client.post(
        f"/api/v1/admin/users/{target_id}/reset-access",
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True

    # Non-admin (the target user themselves) → 404.
    non_admin_headers = make_auth_headers(access_token=target_access)
    r_nonadmin = await async_client.post(
        f"/api/v1/admin/users/{target_id}/reset-access",
        headers=non_admin_headers,
    )
    assert r_nonadmin.status_code == 404, r_nonadmin.text

    # Unknown UUID → 404.
    fake_id = "00000000-0000-0000-0000-000000000088"
    r_unknown = await async_client.post(
        f"/api/v1/admin/users/{fake_id}/reset-access",
        headers=admin_headers,
    )
    assert r_unknown.status_code == 404, r_unknown.text


# ---------------------------------------------------------------------------
# 11. Plan change (comp / tier-override)
# ---------------------------------------------------------------------------


async def test_plan_change(async_client, monkeypatch):
    """POST /admin/billing/users/{id}/plan:
      - Admin + valid tier → 200, tier updated.
      - Invalid tier value → 422 invalid_tier.
      - Unknown user UUID → 404.
    """
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, admin_access = await _signup_with_ip(
        async_client, "admin_plan_change@example.com", ip_suffix=30
    )
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    admin_headers = make_auth_headers(access_token=admin_access)

    target_id, _target_access = await _signup_with_ip(
        async_client, "target_plan_change@example.com", ip_suffix=31
    )

    # Admin sets target to "pro" tier.
    r = await async_client.post(
        f"/api/v1/admin/billing/users/{target_id}/plan",
        json={"tier": "pro", "reason": "comp grant"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["tier"] == "pro"

    # Invalid tier value → 422.
    r_bad_tier = await async_client.post(
        f"/api/v1/admin/billing/users/{target_id}/plan",
        json={"tier": "nonsense", "reason": "test bad tier"},
        headers=admin_headers,
    )
    assert r_bad_tier.status_code == 422, r_bad_tier.text
    assert r_bad_tier.json()["detail"] == "invalid_tier"

    # Unknown user UUID → 404.
    fake_id = "00000000-0000-0000-0000-000000000077"
    r_unknown = await async_client.post(
        f"/api/v1/admin/billing/users/{fake_id}/plan",
        json={"tier": "pro", "reason": "does not exist"},
        headers=admin_headers,
    )
    assert r_unknown.status_code == 404, r_unknown.text


# ---------------------------------------------------------------------------
# 12. Broadcast — confirmation, advisory-language, and idempotency guards
# ---------------------------------------------------------------------------


async def test_broadcast_confirm_and_advisory(async_client, monkeypatch):
    """POST /admin/notifications/broadcast guards:
      - confirm:false → 400 confirmation_required.
      - Missing Idempotency-Key (with confirm:true) → 400 idempotency_key_required.
      - Advisory word in body → 422 advisory_language_forbidden.
      - confirm:true + valid key + clean copy → 200 ok:true.

    Monkeypatches:
      - dhanradar.notifications.service.post_public_card  → async returning True
      - dhanradar.notifications.service.broadcast_available → returning True
      - dhanradar.notifications.service.in_quiet_hours → returning False
        (so the test is deterministic regardless of wall-clock IST time)
    """
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, admin_access = await _signup_with_ip(
        async_client, "admin_broadcast_p5@example.com", ip_suffix=40
    )
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    admin_headers = make_auth_headers(access_token=admin_access)

    import dhanradar.notifications.service as notify_svc

    # Monkeypatch post_public_card → always delivers successfully.
    async def _fake_post_public_card(text: str) -> bool:
        return True

    monkeypatch.setattr(notify_svc, "post_public_card", _fake_post_public_card)

    # Monkeypatch broadcast_available → True (channel is configured).
    monkeypatch.setattr(notify_svc, "broadcast_available", lambda: True)

    # Monkeypatch in_quiet_hours → False (not in quiet hours regardless of time).
    monkeypatch.setattr(notify_svc, "in_quiet_hours", lambda *args, **kwargs: False)

    idem_key = "p5-broadcast-test-k1"

    # Guard 1: confirm:false (no Idempotency-Key yet, but confirm gate fires first
    # in the router). The router checks Idempotency-Key first, then confirm — so
    # we supply the key here to test the confirm gate specifically.
    r_no_confirm = await async_client.post(
        "/api/v1/admin/notifications/broadcast",
        json={"title": "Hello", "body": "World update", "channel": "telegram_public", "confirm": False},
        headers={**admin_headers, "Idempotency-Key": idem_key},
    )
    assert r_no_confirm.status_code == 400, r_no_confirm.text
    assert r_no_confirm.json()["detail"] == "confirmation_required"

    # Guard 2: confirm:true but missing Idempotency-Key → 400 (key is checked first in router).
    r_no_key = await async_client.post(
        "/api/v1/admin/notifications/broadcast",
        json={"title": "Hello", "body": "World update", "channel": "telegram_public", "confirm": True},
        headers=admin_headers,  # no Idempotency-Key
    )
    assert r_no_key.status_code == 400, r_no_key.text
    assert r_no_key.json()["detail"] == "idempotency_key_required"

    # Guard 3: advisory word in body → 422 advisory_language_forbidden.
    # "sell" is one of the banned verbs in platform_router._ADVISORY_VERBS.
    r_advisory = await async_client.post(
        "/api/v1/admin/notifications/broadcast",
        json={
            "title": "Market note",
            "body": "you should sell now",
            "channel": "telegram_public",
            "confirm": True,
        },
        headers={**admin_headers, "Idempotency-Key": idem_key + "-adv"},
    )
    assert r_advisory.status_code == 422, r_advisory.text
    assert r_advisory.json()["detail"] == "advisory_language_forbidden"

    # Happy path: confirm:true + unique key + clean copy → 200.
    r_ok = await async_client.post(
        "/api/v1/admin/notifications/broadcast",
        json={
            "title": "Platform update",
            "body": "Scheduled maintenance complete. All systems operational.",
            "channel": "telegram_public",
            "confirm": True,
        },
        headers={**admin_headers, "Idempotency-Key": idem_key},
    )
    assert r_ok.status_code == 200, r_ok.text
    body = r_ok.json()
    assert body["ok"] is True
