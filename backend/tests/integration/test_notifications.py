"""
Integration tests for the notification module (Phase 6, architecture Global §5).

Covers:
  - GET /notifications/preferences: 401 anonymous; 200 defaults for a fresh user.
  - POST /notifications/preferences: partial update persists; extra keys → 422;
    invalid quiet_hours → 422.
  - POST /notifications/test: 402 for free tier; 400 when telegram_chat_id unset;
    200 + Redis enqueue for a pro user who has set telegram_chat_id.
  - DRAIN end-to-end: publish → _drain() → fake deliver_telegram called with the
    correct chat_id; rendered text contains NOT_ADVICE disclosure; queue emptied.
  - QUIET-HOURS defer: normal-priority job is re-queued (not delivered) when the
    current IST time falls in the user's quiet window.

Infrastructure contract (same as test_billing / test_auth_flow):
  - async_client  — httpx.AsyncClient over ASGITransport; no lifespan.
  - db_session    — function-scoped AsyncSession; truncates between tests.
  - patch_redis / fake_redis — fakeredis.aioredis.FakeRedis; flushed between tests.
  - patch_settings_keys     — ephemeral RSA keypair; COOKIE_SECURE=False.
  - ASGITransport does NOT run lifespan; get_db and redis are overridden.
  - __Host- cookies are extracted from raw Set-Cookie and re-injected manually.
"""

from __future__ import annotations

import datetime
import uuid as _uuid

import pytest
from sqlalchemy import update

from dhanradar.models.auth import User, UserTierEnum
from tests.conftest import extract_cookie, make_auth_headers

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helper: signup, return (user_id, access_token)
# ---------------------------------------------------------------------------


async def _signup(client, email: str) -> tuple[str, str]:
    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "NotifPass42!"},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["user"]["id"]), extract_cookie(r, "__Host-access")


async def _make_pro(db_session, user_id: str) -> None:
    """Elevate a user to pro directly in the test DB.

    Tier resolution in the app reads Redis cache first, then falls back to the
    DB.  The fake_redis is empty for every test, so the DB value is authoritative.
    """
    await db_session.execute(
        update(User)
        .where(User.id == _uuid.UUID(user_id))
        .values(tier=UserTierEnum.pro)
    )
    await db_session.commit()


async def _grant_cross_border_notify(db_session, user_id: str) -> None:
    """Grant the DPDP cross-border notification consent (B31) so the deliver seam
    will transmit to the non-Indian processors (Telegram/Resend)."""
    await db_session.execute(
        update(User)
        .where(User.id == _uuid.UUID(user_id))
        .values(dpdp_consents={"cross_border_notify": True})
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# 1. GET preferences — anonymous → 401
# ---------------------------------------------------------------------------


async def test_get_preferences_anonymous_401(async_client):
    """An unauthenticated GET must return 401."""
    r = await async_client.get("/api/v1/notifications/preferences")
    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# 2. GET preferences — fresh user → 200 with default fields
# ---------------------------------------------------------------------------


async def test_get_preferences_defaults(async_client, db_session):
    """A freshly signed-up user has no preference row yet; the API must return
    default values: channels_enabled == {} and email_verified == False."""
    email = f"notif_defaults_{_uuid.uuid4().hex[:8]}@example.com"
    _, access = await _signup(async_client, email)

    r = await async_client.get(
        "/api/v1/notifications/preferences",
        headers=make_auth_headers(access_token=access),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["channels_enabled"] == {}
    assert body["email_verified"] is False
    assert body["telegram_chat_id"] is None
    assert body["quiet_hours_start"] is None
    assert body["quiet_hours_end"] is None


# ---------------------------------------------------------------------------
# 3. POST preferences — partial update persists; GET reflects the new values
# ---------------------------------------------------------------------------


async def test_post_preferences_partial_update_persists(async_client, db_session):
    """POST sets telegram_chat_id, channels_enabled, and quiet hours; a subsequent
    GET must echo all four values exactly."""
    email = f"notif_update_{_uuid.uuid4().hex[:8]}@example.com"
    _, access = await _signup(async_client, email)
    headers = make_auth_headers(access_token=access)

    r = await async_client.post(
        "/api/v1/notifications/preferences",
        json={
            "telegram_chat_id": "123456789",
            "channels_enabled": {"telegram": True},
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "07:00",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["telegram_chat_id"] == "123456789"
    assert body["channels_enabled"] == {"telegram": True}
    assert body["quiet_hours_start"] == "22:00"
    assert body["quiet_hours_end"] == "07:00"

    # GET must return the same values
    r2 = await async_client.get("/api/v1/notifications/preferences", headers=headers)
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["telegram_chat_id"] == "123456789"
    assert body2["channels_enabled"] == {"telegram": True}
    assert body2["quiet_hours_start"] == "22:00"
    assert body2["quiet_hours_end"] == "07:00"


# ---------------------------------------------------------------------------
# 4. POST preferences — extra key → 422; invalid quiet_hours → 422
# ---------------------------------------------------------------------------


async def test_post_preferences_extra_key_422(async_client, db_session):
    """An unknown extra key in the body must be rejected with 422 (extra=forbid)."""
    email = f"notif_extra_{_uuid.uuid4().hex[:8]}@example.com"
    _, access = await _signup(async_client, email)

    r = await async_client.post(
        "/api/v1/notifications/preferences",
        json={"telegram_chat_id": "999", "unknown_field": "boom"},
        headers=make_auth_headers(access_token=access),
    )
    assert r.status_code == 422, r.text


async def test_post_preferences_invalid_quiet_hours_422(async_client, db_session):
    """Malformed quiet_hours_start must be rejected with 422 at the API edge."""
    email = f"notif_qh_{_uuid.uuid4().hex[:8]}@example.com"
    _, access = await _signup(async_client, email)

    r = await async_client.post(
        "/api/v1/notifications/preferences",
        json={"quiet_hours_start": "99:99"},
        headers=make_auth_headers(access_token=access),
    )
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# 5. POST /notifications/test — free user → 402
# ---------------------------------------------------------------------------


async def test_test_notification_free_user_402(async_client, db_session):
    """A free-tier user must receive 402 (tier gate) from /notifications/test."""
    email = f"notif_free_{_uuid.uuid4().hex[:8]}@example.com"
    _, access = await _signup(async_client, email)

    r = await async_client.post(
        "/api/v1/notifications/test",
        json={"channel": "telegram"},
        headers=make_auth_headers(access_token=access),
    )
    assert r.status_code == 402, r.text


# ---------------------------------------------------------------------------
# 6. POST /notifications/test — pro, no telegram_chat_id → 400
# ---------------------------------------------------------------------------


async def test_test_notification_pro_no_chat_id_400(async_client, db_session):
    """A pro user who has not set telegram_chat_id must get 400 telegram_not_set."""
    email = f"notif_pro_no_tg_{_uuid.uuid4().hex[:8]}@example.com"
    user_id, access = await _signup(async_client, email)
    await _make_pro(db_session, user_id)

    r = await async_client.post(
        "/api/v1/notifications/test",
        json={"channel": "telegram"},
        headers=make_auth_headers(access_token=access),
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "telegram_not_set"


# ---------------------------------------------------------------------------
# 7. POST /notifications/test — pro, chat_id set → 200 + Redis enqueue
# ---------------------------------------------------------------------------


async def test_test_notification_pro_enqueues(async_client, db_session, fake_redis):
    """A pro user with telegram_chat_id set must get 200 enqueued=True; exactly one
    job must be LPUSH'd onto notifications:queue:telegram."""
    email = f"notif_pro_tg_{_uuid.uuid4().hex[:8]}@example.com"
    user_id, access = await _signup(async_client, email)
    await _make_pro(db_session, user_id)

    # Set telegram_chat_id via the preferences endpoint
    await async_client.post(
        "/api/v1/notifications/preferences",
        json={"telegram_chat_id": "777888999"},
        headers=make_auth_headers(access_token=access),
    )

    r = await async_client.post(
        "/api/v1/notifications/test",
        json={"channel": "telegram"},
        headers=make_auth_headers(access_token=access),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enqueued"] is True
    assert body["channel"] == "telegram"

    assert await fake_redis.llen("notifications:queue:telegram") == 1


# ---------------------------------------------------------------------------
# 8. DRAIN end-to-end
# ---------------------------------------------------------------------------


async def test_drain_delivers_to_fake_telegram(
    async_client, db_session, fake_redis, monkeypatch
):
    """Full drain pipeline:
    1. Sign up a pro user, set prefs (telegram_chat_id + channels_enabled).
    2. Monkeypatch deliver_telegram so no network is hit.
    3. Publish a high-priority test_ping job.
    4. Run _drain() directly (uses the test DB engine via monkeypatch + the
       patched fake_redis from conftest).
    5. Assert the fake was called once with the correct chat_id, the delivered
       text contains NOT_ADVICE, and the queue is now empty.
    """
    import dhanradar.db as _db_mod
    import dhanradar.tasks.misc as misc
    from dhanradar.notifications import service
    from dhanradar.notifications.channels import DeliveryResult
    from dhanradar.redis_client import get_redis
    from dhanradar.scoring.engine.schemas import NOT_ADVICE

    # Patch the module-level engine inside dhanradar.db so that _drain()'s
    # async_sessionmaker(engine, ...) binds to the test DB, not the app DB.
    monkeypatch.setattr(_db_mod, "engine", db_session.bind)

    # Sign up + promote + set prefs
    email = f"notif_drain_{_uuid.uuid4().hex[:8]}@example.com"
    user_id, access = await _signup(async_client, email)
    await _make_pro(db_session, user_id)
    await _grant_cross_border_notify(db_session, user_id)  # B31 deploy-gate

    await async_client.post(
        "/api/v1/notifications/preferences",
        json={
            "telegram_chat_id": "555",
            "channels_enabled": {"telegram": True},
        },
        headers=make_auth_headers(access_token=access),
    )
    # Commit so _drain's separate AsyncSession can see the row.
    await db_session.commit()

    # Monkeypatch the Telegram transport
    sent: list[tuple[str, str]] = []

    async def _fake_tg(chat_id: str, text: str, *, client=None) -> DeliveryResult:
        sent.append((chat_id, text))
        return DeliveryResult(ok=True, transient=False, code="ok")

    monkeypatch.setattr(misc.channels, "deliver_telegram", _fake_tg)

    # Publish a job
    await service.publish_notification(
        get_redis(), user_id, "telegram", "test_ping", data={}, priority="high"
    )

    # Run the drain
    await misc._drain()

    assert len(sent) == 1, f"Expected 1 delivery, got {len(sent)}"
    assert sent[0][0] == "555", f"Wrong chat_id: {sent[0][0]!r}"
    assert NOT_ADVICE in sent[0][1], "Delivered text must contain NOT_ADVICE disclosure"
    assert await get_redis().llen("notifications:queue:telegram") == 0, "Queue should be empty after drain"


# ---------------------------------------------------------------------------
# 9. QUIET-HOURS defer — normal priority job is NOT delivered during quiet window
# ---------------------------------------------------------------------------


async def test_drain_quiet_hours_defers_normal_job(
    async_client, db_session, fake_redis, monkeypatch
):
    """When the current IST time falls inside the user's quiet window, a normal-
    priority job must be re-queued (not delivered) and deliver_telegram must NOT
    be called."""
    import dhanradar.db as _db_mod
    import dhanradar.tasks.misc as misc
    from dhanradar.notifications import service
    from dhanradar.notifications.channels import DeliveryResult
    from dhanradar.redis_client import get_redis

    # Redirect _drain to the test engine
    monkeypatch.setattr(_db_mod, "engine", db_session.bind)

    # Sign up + promote + set prefs: quiet 00:00–23:59 (always quiet)
    email = f"notif_quiet_{_uuid.uuid4().hex[:8]}@example.com"
    user_id, access = await _signup(async_client, email)
    await _make_pro(db_session, user_id)
    await _grant_cross_border_notify(db_session, user_id)  # B31: reach the quiet path

    await async_client.post(
        "/api/v1/notifications/preferences",
        json={
            "telegram_chat_id": "555",
            "channels_enabled": {"telegram": True},
            "quiet_hours_start": "00:00",
            "quiet_hours_end": "23:59",
        },
        headers=make_auth_headers(access_token=access),
    )
    await db_session.commit()

    # Freeze IST time inside the quiet window
    monkeypatch.setattr(misc.service, "now_ist_time", lambda: datetime.time(12, 0))

    # Recorder for deliver_telegram — must NOT be called
    delivered: list[tuple[str, str]] = []

    async def _recording_tg(chat_id: str, text: str, *, client=None) -> DeliveryResult:
        delivered.append((chat_id, text))
        return DeliveryResult(ok=True, transient=False, code="ok")

    monkeypatch.setattr(misc.channels, "deliver_telegram", _recording_tg)

    # Publish a NORMAL priority job
    await service.publish_notification(
        get_redis(), user_id, "telegram", "test_ping", data={}, priority="normal"
    )

    await misc._drain()

    assert len(delivered) == 0, "deliver_telegram must NOT be called during quiet hours"
    assert await get_redis().llen("notifications:queue:telegram") == 1, (
        "Deferred job must still be on the queue after quiet-hours deferral"
    )


# ---------------------------------------------------------------------------
# 10. B31 — no cross-border consent ⇒ deliver seam refuses (fail-closed)
# ---------------------------------------------------------------------------


async def test_drain_skips_without_cross_border_consent(
    async_client, db_session, fake_redis, monkeypatch
):
    """B31 (deploy gate): a pro user with the channel enabled + chat_id set but
    WITHOUT `cross_border_notify` consent must have NOTHING delivered — the
    Telegram transport is never invoked, and the blocked job is dropped (not
    re-queued)."""
    import dhanradar.db as _db_mod
    import dhanradar.tasks.misc as misc
    from dhanradar.notifications import service
    from dhanradar.notifications.channels import DeliveryResult
    from dhanradar.redis_client import get_redis

    monkeypatch.setattr(_db_mod, "engine", db_session.bind)

    email = f"notif_noconsent_{_uuid.uuid4().hex[:8]}@example.com"
    user_id, access = await _signup(async_client, email)
    await _make_pro(db_session, user_id)
    # Deliberately NO _grant_cross_border_notify — the cross-border grant is absent.

    await async_client.post(
        "/api/v1/notifications/preferences",
        json={"telegram_chat_id": "555", "channels_enabled": {"telegram": True}},
        headers=make_auth_headers(access_token=access),
    )
    await db_session.commit()

    called: list[tuple[str, str]] = []

    async def _must_not_call(chat_id: str, text: str, *, client=None) -> DeliveryResult:
        called.append((chat_id, text))
        return DeliveryResult(ok=True, transient=False, code="ok")

    monkeypatch.setattr(misc.channels, "deliver_telegram", _must_not_call)

    await service.publish_notification(
        get_redis(), user_id, "telegram", "test_ping", data={}, priority="high"
    )
    await misc._drain()

    assert called == [], "B31: no cross_border_notify consent → Telegram must NOT be invoked"
    assert await get_redis().llen("notifications:queue:telegram") == 0, (
        "Blocked job must be dropped (not re-queued)"
    )
