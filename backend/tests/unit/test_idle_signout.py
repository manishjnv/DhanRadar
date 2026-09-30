"""Unit tests for the 15-min-idle sign-out server-side hard cutoff.

Covers:
  (1) store_refresh_jti persists the jti with the sliding IDLE_TTL, not the
      full REFRESH_TTL.
  (2) Missing key + stale `issued_at` (idle window elapsed) -> 401
      session_idle_timeout, NO security event fired.
  (3) Missing key + fresh `issued_at` (idle window has not elapsed) -> 401
      token_reuse_detected, security event fired (unchanged reuse path).
  (4) Normal rotation (key present) still works regardless of issued_at.

Runs fully in-process with fakeredis (patch_redis fixture) — no Postgres.
"""

from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from dhanradar.auth import service as svc
from dhanradar.config import settings


async def test_store_refresh_jti_uses_idle_ttl(patch_redis):
    uid = str(uuid.uuid4())
    jti = str(uuid.uuid4())
    await svc.store_refresh_jti(jti, uid)

    ttl = await patch_redis.ttl(f"{svc.REFRESH_KEY_PREFIX}{jti}")
    assert 0 < ttl <= svc.IDLE_TTL
    assert svc.IDLE_TTL == settings.SESSION_IDLE_TIMEOUT_MIN * 60


async def test_expired_key_stale_iat_is_idle_timeout_not_reuse(patch_redis, monkeypatch):
    fake_event = AsyncMock()
    monkeypatch.setattr(svc, "record_security_event", fake_event)

    uid = str(uuid.uuid4())
    old_jti = str(uuid.uuid4())
    # Never stored (simulating natural TTL expiry) + issued long before the
    # idle window — this must read as idle timeout, not reuse.
    stale_iat = int(time.time()) - (settings.SESSION_IDLE_TIMEOUT_MIN * 60) - 60

    with pytest.raises(HTTPException) as exc_info:
        await svc.rotate_refresh_token(old_jti, uid, stale_iat)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "session_idle_timeout"
    # Logged under its own low-key type — never as a reuse alarm.
    fake_event.assert_called_once()
    assert fake_event.call_args.kwargs["event_type"] == "refresh_idle_expired"


async def test_missing_key_fresh_iat_is_still_reuse_detected(patch_redis, monkeypatch):
    fake_event = AsyncMock()
    monkeypatch.setattr(svc, "record_security_event", fake_event)

    uid = str(uuid.uuid4())
    old_jti = str(uuid.uuid4())
    # Never stored, but issued just now — cannot be an idle-window expiry.
    fresh_iat = int(time.time())

    with pytest.raises(HTTPException) as exc_info:
        await svc.rotate_refresh_token(old_jti, uid, fresh_iat)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "token_reuse_detected"
    fake_event.assert_called_once()
    assert fake_event.call_args.kwargs["event_type"] == "refresh_reuse_detected"


async def test_normal_rotation_still_works(patch_redis):
    uid = str(uuid.uuid4())
    old_jti = str(uuid.uuid4())
    await svc.store_refresh_jti(old_jti, uid)

    access, _, refresh, new_jti = await svc.rotate_refresh_token(
        old_jti, uid, int(time.time())
    )
    assert access
    assert refresh
    assert new_jti != old_jti


async def test_rotation_keeps_absolute_cap_from_sign_in(patch_redis):
    """A rotation must not restart the 7-day clock: `sst` and `exp` stay
    anchored to the original sign-in."""
    from dhanradar.auth.security import decode_token

    uid = str(uuid.uuid4())
    old_jti = str(uuid.uuid4())
    await svc.store_refresh_jti(old_jti, uid)
    signed_in = int(time.time()) - 3 * 86400  # session started 3 days ago

    _, _, refresh, _ = await svc.rotate_refresh_token(
        old_jti, uid, int(time.time()), session_start=signed_in
    )
    payload = decode_token(refresh, expected_typ="refresh")
    assert payload["sst"] == signed_in
    assert payload["exp"] == signed_in + settings.REFRESH_TTL_DAYS * 86400
