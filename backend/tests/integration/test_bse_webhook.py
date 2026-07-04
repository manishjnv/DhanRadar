"""
Integration tests for POST /api/v1/bse/webhook (BSE Star MF 2.0 receiver).

Infrastructure contract (same as test_webhook.py):
  - `async_client` (httpx.AsyncClient via ASGITransport).
  - DB = compose `dhanradar-postgres` via db_session; truncated between tests.
  - Redis = fakeredis via patch_redis.

JOSE scheme under test (API doc §6.1.7)
---------------------------------------
A real BSE webhook body is  JWS( signed by BSE's private key )  whose payload is
JWE( encrypted to OUR public key ). The receiver verifies the JWS with BSE's PUBLIC
key, then decrypts the JWE with OUR PRIVATE key.

Tests generate two throwaway RSA keypairs:
  * "bse"  — signs the JWS; its PUBLIC half is configured as BSE_WEBHOOK_PUBLIC_KEY.
  * "ours" — receives the JWE; its PRIVATE half is configured as BSE_PRIVATE_KEY.
`_build_webhook` mirrors BSE's ctEncrypt pseudocode so valid bodies pass and we can
craft invalid ones (wrong signer, tampered body).
"""

from __future__ import annotations

import json
import uuid

import pytest
from joserfc import jwe, jws
from joserfc.jwk import RSAKey
from sqlalchemy import select

from dhanradar.config import settings
from dhanradar.models.bse import BSEWebhookEvent

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Throwaway keypairs (generated once for the module).
# ---------------------------------------------------------------------------
_BSE_KEY = RSAKey.generate_key(2048)     # BSE signs with this (private); we verify with its public
_OUR_KEY = RSAKey.generate_key(2048)     # BSE encrypts to this (public); we decrypt with its private
_OTHER_KEY = RSAKey.generate_key(2048)   # an attacker / wrong signer

_BSE_PUB_PEM = _BSE_KEY.as_pem(private=False).decode("utf-8")
_OUR_PRIV_PEM = _OUR_KEY.as_pem(private=True).decode("utf-8")


@pytest.fixture(autouse=True)
def _configure_bse_keys(monkeypatch):
    """Point the receiver at the test keypairs (BSE's public + our private)."""
    monkeypatch.setattr(settings, "BSE_WEBHOOK_PUBLIC_KEY", _BSE_PUB_PEM)
    monkeypatch.setattr(settings, "BSE_WEBHOOK_PUBLIC_KEY_FILE", "")
    monkeypatch.setattr(settings, "BSE_PRIVATE_KEY", _OUR_PRIV_PEM)
    monkeypatch.setattr(settings, "BSE_PRIVATE_KEY_FILE", "")
    monkeypatch.setattr(settings, "BSE_WEBHOOK_SOURCE_IPS", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_webhook(payload: dict, *, signer: RSAKey = _BSE_KEY, recipient: RSAKey = _OUR_KEY) -> bytes:
    """Build a JWS(JWE) compact body the way BSE does (ctEncrypt)."""
    clear = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    jwe_compact = jwe.encrypt_compact(
        {"alg": "RSA-OAEP-256", "enc": "A256GCM"},
        clear,
        recipient,
        algorithms=["RSA-OAEP-256", "A256GCM"],
    )
    signed = jws.serialize_compact({"alg": "RS256"}, jwe_compact, signer)
    return signed.encode("ascii") if isinstance(signed, str) else signed


def _event_payload(
    event_type: str = "ORDER",
    event: str = "match_pending",
    request_id: str | None = None,
    order_id: str = "ORD123",
) -> dict:
    return {
        "member": {"member_id": "63655"},
        "request_id": request_id or str(uuid.uuid4()),
        "investor": {"client_code": "CLNT00001"},
        "action": {
            "msgcode": 10001,
            "at": "2025-07-07 05:31:05 +0530 IST",
            "event_type": event_type,
            "event": event,
            "event_message": "",
            "order_id": order_id,
            "mem_ord_ref_id": "MEMREF1",
        },
    }


_JOSE_HEADERS = {"Content-Type": "application/jose"}


# ---------------------------------------------------------------------------
# Valid event → 200 webhook_ack + persisted + (one) enqueue
# ---------------------------------------------------------------------------

async def test_valid_webhook_acks_and_persists(async_client, db_session, monkeypatch):
    enqueued: list[str] = []
    import dhanradar.bse.router as bse_router
    monkeypatch.setattr(bse_router.process_webhook_event, "delay", lambda eid: enqueued.append(eid))

    payload = _event_payload()
    body = _build_webhook(payload)

    resp = await async_client.post("/api/v1/bse/webhook", content=body, headers=_JOSE_HEADERS)
    assert resp.status_code == 200, resp.text
    j = resp.json()
    assert j["status"] == "success"
    # webhook_ack id format: YYYYMMDD-[A-Za-z0-9]{8}
    ack_id = j["data"]["id"]
    date_part, _, suffix = ack_id.partition("-")
    assert len(date_part) == 8 and date_part.isdigit()
    assert len(suffix) == 8 and suffix.isalnum()
    assert j["messages"] == []

    row = await db_session.scalar(
        select(BSEWebhookEvent).where(BSEWebhookEvent.request_id == payload["request_id"])
    )
    assert row is not None
    assert row.event_type == "ORDER"
    assert row.event == "match_pending"
    assert row.order_id == "ORD123"
    assert row.client_code == "CLNT00001"
    assert row.status == "received"
    assert len(enqueued) == 1  # processed exactly once


# ---------------------------------------------------------------------------
# Bad signature (wrong signer) → 400, nothing persisted
# ---------------------------------------------------------------------------

async def test_wrong_signer_rejected_400(async_client, db_session, monkeypatch):
    enqueued: list[str] = []
    import dhanradar.bse.router as bse_router
    monkeypatch.setattr(bse_router.process_webhook_event, "delay", lambda eid: enqueued.append(eid))

    payload = _event_payload()
    body = _build_webhook(payload, signer=_OTHER_KEY)  # not BSE's key

    resp = await async_client.post("/api/v1/bse/webhook", content=body, headers=_JOSE_HEADERS)
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == "invalid_signature"

    row = await db_session.scalar(
        select(BSEWebhookEvent).where(BSEWebhookEvent.request_id == payload["request_id"])
    )
    assert row is None
    assert enqueued == []


async def test_garbage_body_rejected_400(async_client):
    resp = await async_client.post(
        "/api/v1/bse/webhook", content=b"not-a-jose-token", headers=_JOSE_HEADERS
    )
    assert resp.status_code == 400, resp.text


async def test_oversized_body_rejected_413(async_client):
    """A body over the size cap is refused BEFORE any JOSE work (DoS guard)."""
    big = b"x" * (256 * 1024 + 1)
    resp = await async_client.post("/api/v1/bse/webhook", content=big, headers=_JOSE_HEADERS)
    assert resp.status_code == 413, resp.text


async def test_malformed_envelope_after_decrypt_400(async_client):
    """A validly-signed+encrypted body whose JSON lacks the mandatory envelope
    (no action.event_type/event) is a 400, never a 500."""
    body = _build_webhook({"request_id": "r-malformed", "investor": {}})  # no 'action'
    resp = await async_client.post("/api/v1/bse/webhook", content=body, headers=_JOSE_HEADERS)
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == "malformed_event"


# ---------------------------------------------------------------------------
# Duplicate request_id → 200 ack, no second row, not re-enqueued
# ---------------------------------------------------------------------------

async def test_duplicate_request_id_not_reprocessed(async_client, db_session, monkeypatch):
    enqueued: list[str] = []
    import dhanradar.bse.router as bse_router
    monkeypatch.setattr(bse_router.process_webhook_event, "delay", lambda eid: enqueued.append(eid))

    rid = str(uuid.uuid4())
    # Two distinct signings of the same request_id (BSE retry).
    body1 = _build_webhook(_event_payload(request_id=rid))
    body2 = _build_webhook(_event_payload(request_id=rid))

    r1 = await async_client.post("/api/v1/bse/webhook", content=body1, headers=_JOSE_HEADERS)
    r2 = await async_client.post("/api/v1/bse/webhook", content=body2, headers=_JOSE_HEADERS)
    assert r1.status_code == 200 and r2.status_code == 200, (r1.text, r2.text)
    # Both return a valid ack so BSE stops retrying.
    assert r1.json()["status"] == "success" and r2.json()["status"] == "success"

    rows = (
        await db_session.scalars(
            select(BSEWebhookEvent).where(BSEWebhookEvent.request_id == rid)
        )
    ).all()
    assert len(rows) == 1  # idempotent at the DB layer
    assert len(enqueued) == 1  # processed only once


# ---------------------------------------------------------------------------
# Keys unconfigured → 503 (fail-closed)
# ---------------------------------------------------------------------------

async def test_unconfigured_keys_503(async_client, monkeypatch):
    monkeypatch.setattr(settings, "BSE_WEBHOOK_PUBLIC_KEY", "")
    monkeypatch.setattr(settings, "BSE_WEBHOOK_PUBLIC_KEY_FILE", "")
    monkeypatch.setattr(settings, "BSE_PRIVATE_KEY", "")
    monkeypatch.setattr(settings, "BSE_PRIVATE_KEY_FILE", "")

    body = _build_webhook(_event_payload())
    resp = await async_client.post("/api/v1/bse/webhook", content=body, headers=_JOSE_HEADERS)
    assert resp.status_code == 503, resp.text
    assert resp.json()["detail"] == "bse_keys_unconfigured"


# ---------------------------------------------------------------------------
# Unsigned plaintext fallback — BSE UAT pushes UNSIGNED plain JSON. Accept ONLY when
# BSE_WEBHOOK_ALLOW_PLAINTEXT is True AND CF-Connecting-IP is in a non-empty allowlist.
# ---------------------------------------------------------------------------

_BSE_IP = "203.199.49.100"
_PLAINTEXT_HEADERS = {"Content-Type": "application/json", "CF-Connecting-IP": _BSE_IP}


def _plaintext_body(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


async def test_plaintext_from_allowlisted_ip_accepted(async_client, db_session, monkeypatch):
    """Flag on + allowlisted source IP → unsigned plain JSON is accepted and stored."""
    monkeypatch.setattr(settings, "BSE_WEBHOOK_ALLOW_PLAINTEXT", True)
    monkeypatch.setattr(settings, "BSE_WEBHOOK_SOURCE_IPS", _BSE_IP)
    enqueued: list[str] = []
    import dhanradar.bse.router as bse_router
    monkeypatch.setattr(bse_router.process_webhook_event, "delay", lambda eid: enqueued.append(eid))

    payload = _event_payload(event_type="UCC", event="PENDING_AUTHENTICATION")
    resp = await async_client.post(
        "/api/v1/bse/webhook", content=_plaintext_body(payload), headers=_PLAINTEXT_HEADERS
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"

    row = await db_session.scalar(
        select(BSEWebhookEvent).where(BSEWebhookEvent.request_id == payload["request_id"])
    )
    assert row is not None
    assert row.event_type == "UCC"
    assert row.event == "PENDING_AUTHENTICATION"
    assert len(enqueued) == 1


async def test_plaintext_from_offallowlist_ip_403(async_client, db_session, monkeypatch):
    """Allowlist set but request IP not in it → 403 before any parsing; nothing stored."""
    monkeypatch.setattr(settings, "BSE_WEBHOOK_ALLOW_PLAINTEXT", True)
    monkeypatch.setattr(settings, "BSE_WEBHOOK_SOURCE_IPS", _BSE_IP)

    payload = _event_payload()
    resp = await async_client.post(
        "/api/v1/bse/webhook",
        content=_plaintext_body(payload),
        headers={"Content-Type": "application/json", "CF-Connecting-IP": "9.9.9.9"},
    )
    assert resp.status_code == 403, resp.text

    row = await db_session.scalar(
        select(BSEWebhookEvent).where(BSEWebhookEvent.request_id == payload["request_id"])
    )
    assert row is None


async def test_plaintext_flag_off_rejected_even_from_allowlisted_ip(async_client, db_session, monkeypatch):
    """Flag OFF (default) NEVER accepts plaintext — it falls through to JOSE and 400s."""
    monkeypatch.setattr(settings, "BSE_WEBHOOK_ALLOW_PLAINTEXT", False)
    monkeypatch.setattr(settings, "BSE_WEBHOOK_SOURCE_IPS", _BSE_IP)

    payload = _event_payload()
    resp = await async_client.post(
        "/api/v1/bse/webhook", content=_plaintext_body(payload), headers=_PLAINTEXT_HEADERS
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == "invalid_signature"

    row = await db_session.scalar(
        select(BSEWebhookEvent).where(BSEWebhookEvent.request_id == payload["request_id"])
    )
    assert row is None


async def test_flag_on_empty_allowlist_plaintext_stays_jose_strict(async_client, db_session, monkeypatch):
    """Fail-closed: flag on but NO source-IP allowlist → plaintext refused (JOSE required)."""
    monkeypatch.setattr(settings, "BSE_WEBHOOK_ALLOW_PLAINTEXT", True)
    monkeypatch.setattr(settings, "BSE_WEBHOOK_SOURCE_IPS", "")

    payload = _event_payload()
    resp = await async_client.post(
        "/api/v1/bse/webhook", content=_plaintext_body(payload), headers=_PLAINTEXT_HEADERS
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == "invalid_signature"

    row = await db_session.scalar(
        select(BSEWebhookEvent).where(BSEWebhookEvent.request_id == payload["request_id"])
    )
    assert row is None


async def test_jose_still_accepted_when_plaintext_enabled(async_client, db_session, monkeypatch):
    """Enabling the plaintext fallback must not break a genuine JOSE event."""
    monkeypatch.setattr(settings, "BSE_WEBHOOK_ALLOW_PLAINTEXT", True)
    monkeypatch.setattr(settings, "BSE_WEBHOOK_SOURCE_IPS", _BSE_IP)
    enqueued: list[str] = []
    import dhanradar.bse.router as bse_router
    monkeypatch.setattr(bse_router.process_webhook_event, "delay", lambda eid: enqueued.append(eid))

    payload = _event_payload()
    body = _build_webhook(payload)  # real JOSE (starts with base64, not '{')
    resp = await async_client.post(
        "/api/v1/bse/webhook",
        content=body,
        headers={**_JOSE_HEADERS, "CF-Connecting-IP": _BSE_IP},
    )
    assert resp.status_code == 200, resp.text
    row = await db_session.scalar(
        select(BSEWebhookEvent).where(BSEWebhookEvent.request_id == payload["request_id"])
    )
    assert row is not None
    assert len(enqueued) == 1


# ---------------------------------------------------------------------------
# Pure round-trip of the security primitive (no HTTP / DB)
# ---------------------------------------------------------------------------

def test_verify_and_decrypt_roundtrip(monkeypatch):
    from dhanradar.bse import security

    monkeypatch.setattr(settings, "BSE_WEBHOOK_PUBLIC_KEY", _BSE_PUB_PEM)
    monkeypatch.setattr(settings, "BSE_WEBHOOK_PUBLIC_KEY_FILE", "")
    monkeypatch.setattr(settings, "BSE_PRIVATE_KEY", _OUR_PRIV_PEM)
    monkeypatch.setattr(settings, "BSE_PRIVATE_KEY_FILE", "")

    payload = _event_payload(event_type="UCC", event="ACTIVE")
    body = _build_webhook(payload)
    clear = security.verify_and_decrypt(body)
    assert json.loads(clear)["action"]["event"] == "ACTIVE"

    # Tampered signature → BSEWebhookSecurityError
    with pytest.raises(security.BSEWebhookSecurityError):
        security.verify_and_decrypt(_build_webhook(payload, signer=_OTHER_KEY))
