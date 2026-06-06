"""
Integration tests for the reusable, non-route consent primitive (B20/B31
foundation): `dhanradar.deps.consent_granted` / `assert_consent` and the
`cross_border_transfer` DPDP purpose.

The whole point of this primitive is that it FAILS CLOSED on every path, so the
tests assert exactly that: only an explicit grant returns True; everything else
(missing, false, malformed, unknown user, bad id, revoked) returns False.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import update

from dhanradar.deps import (
    _CONSENT_PURPOSES,
    ConsentRequiredError,
    assert_consent,
    consent_granted,
)
from dhanradar.models.auth import User

pytestmark = pytest.mark.integration

PURPOSE = "cross_border_ai"


async def _signup(async_client) -> str:
    email = f"consent_{uuid.uuid4().hex[:8]}@example.com"
    r = await async_client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "ConsentPass42!"}
    )
    assert r.status_code == 201, r.text
    return r.json()["user"]["id"]


async def _set_consents(db_session, user_id: str, consents) -> None:
    await db_session.execute(
        update(User).where(User.id == uuid.UUID(user_id)).values(dpdp_consents=consents)
    )
    await db_session.commit()


def test_cross_border_purposes_registered():
    # Per-processor (no bundling, DPDP specific-consent) — distinct AI + notify grants.
    assert "cross_border_ai" in _CONSENT_PURPOSES
    assert "cross_border_notify" in _CONSENT_PURPOSES


async def test_granted_true_form(async_client, db_session):
    uid = await _signup(async_client)
    await _set_consents(db_session, uid, {PURPOSE: True})
    assert await consent_granted(uid, PURPOSE, db_session) is True
    await assert_consent(uid, PURPOSE, db_session)  # must NOT raise


async def test_granted_dict_form(async_client, db_session):
    uid = await _signup(async_client)
    await _set_consents(db_session, uid, {PURPOSE: {"granted": True, "ts": "2026"}})
    assert await consent_granted(uid, PURPOSE, db_session) is True


async def test_not_granted_missing_fails_closed(async_client, db_session):
    uid = await _signup(async_client)  # default dpdp_consents — no grant
    assert await consent_granted(uid, PURPOSE, db_session) is False
    with pytest.raises(ConsentRequiredError):
        await assert_consent(uid, PURPOSE, db_session)


async def test_revoke_is_honoured_immediately(async_client, db_session):
    uid = await _signup(async_client)
    await _set_consents(db_session, uid, {PURPOSE: True})
    assert await consent_granted(uid, PURPOSE, db_session) is True
    await _set_consents(db_session, uid, {PURPOSE: False})
    assert await consent_granted(uid, PURPOSE, db_session) is False


async def test_malformed_grant_fails_closed(async_client, db_session):
    uid = await _signup(async_client)
    await _set_consents(db_session, uid, {PURPOSE: "yes"})  # not True / not {granted:true}
    assert await consent_granted(uid, PURPOSE, db_session) is False


async def test_granted_false_dict_fails_closed(async_client, db_session):
    # Pins the `granted is True` strictness — a {"granted": false} dict must deny.
    uid = await _signup(async_client)
    await _set_consents(db_session, uid, {PURPOSE: {"granted": False}})
    assert await consent_granted(uid, PURPOSE, db_session) is False


async def test_unknown_user_fails_closed(db_session):
    ghost = str(uuid.uuid4())
    assert await consent_granted(ghost, PURPOSE, db_session) is False
    with pytest.raises(ConsentRequiredError):
        await assert_consent(ghost, PURPOSE, db_session)


async def test_bad_user_id_fails_closed(db_session):
    assert await consent_granted("not-a-uuid", PURPOSE, db_session) is False
    assert await consent_granted(None, PURPOSE, db_session) is False  # type: ignore[arg-type]


async def test_unknown_purpose_raises(db_session):
    # Purpose validation happens BEFORE any DB access (a programming error must
    # fail loud at dev time, not silently fail open).
    with pytest.raises(ValueError):
        await consent_granted("x", "not_a_real_purpose", db_session)
