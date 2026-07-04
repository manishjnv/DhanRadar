"""
DhanRadar — BSE Star MF 2.0 webhook API router.

  POST /api/v1/bse/webhook   (public — authenticated by JOSE signature, not a cookie)

Failsafe store-and-forward receiver:

  raw body
   → (optional) BSE source-IP allowlist
   → VERIFY JWS (BSE public key) + DECRYPT JWE (our private key)   [verify-before-parse]
   → parse JSON → normalize event
   → persist durably (DB UNIQUE(request_id) = idempotency)         [commit BEFORE ack]
   → enqueue async processing (only for a newly-inserted event)
   → return webhook_ack {status:"success", data:{id}, messages:[]}

The handler does the minimum and ACKs only AFTER the row is committed; all business
processing is off-row in Celery, so a processing fault never becomes a non-200 (which
would trigger BSE retries). Bad/absent signature → 400; keys unconfigured → 503;
persistence failure → 503 (BSE retries). HTTP success is any 2xx; the app-level
result is the body `status` (API doc §6.1.2).

Unsigned plaintext fallback (verified 2026-07-04): BSE Star MF's UAT pushes webhooks
as UNSIGNED plain JSON — their webhook doc defines no JOSE/signature for the callback
channel (§6.1.7 encryption is the request/response API channel, not webhooks). We
accept an unsigned body ONLY when the dedicated `BSE_WEBHOOK_ALLOW_PLAINTEXT` flag is
True AND the request comes from an allowlisted BSE source IP (CF-Connecting-IP,
edge-set, unforgeable through the tunnel). That source-IP allowlist IS the
authentication in place of a signature, so an EMPTY allowlist accepts NO plaintext
(fail-closed). The flag is deliberately separate from BSE_ENV so an unrelated ops
change can't re-arm it; keep it False wherever BSE signs. The stored event is a HINT only —
the async processor is inert at UAT (no transactional side effects).
"""

from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.bse import service
from dhanradar.bse.schemas import ParsedEvent, WebhookAck, WebhookAckData
from dhanradar.bse.security import (
    BSEKeyNotConfigured,
    BSEWebhookSecurityError,
    verify_and_decrypt,
)
from dhanradar.config import settings
from dhanradar.db import get_db
from dhanradar.ratelimit import RateLimit
from dhanradar.tasks.bse import process_webhook_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bse", tags=["bse"])

# Guard against BSE retry storms; the JOSE signature is the real authentication.
_rl_webhook = RateLimit(max_requests=300, window_seconds=60)

# Hard cap on the webhook body before any (CPU-heavy) JOSE work — a BSE event JSON,
# even JOSE-wrapped, is small. Bounds a memory/CPU DoS via an oversized POST.
_MAX_BODY_BYTES = 256 * 1024


def _check_source_ip(request: Request) -> None:
    """Optional defence-in-depth: reject if BSE_WEBHOOK_SOURCE_IPS is configured and
    the (Cloudflare-trusted) client IP is not in it. No-op when the allowlist is empty."""
    allow = settings.bse_webhook_source_ips
    if not allow:
        return
    client_ip = RateLimit._get_client_ip(request)
    if client_ip not in allow:
        logger.warning("bse.webhook: source IP %s not in allowlist", client_ip)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ip_not_allowed")


def _plaintext_webhook_allowed(request: Request, raw_body: bytes) -> bool:
    """Escape hatch for BSE's UNSIGNED plain-JSON webhooks (UAT delivers plaintext).

    Three INDEPENDENT fail-closed gates — returns True only when ALL hold (else the
    caller requires full JOSE):
      1. `BSE_WEBHOOK_ALLOW_PLAINTEXT` is explicitly True — a dedicated opt-in flag,
         deliberately NOT `BSE_ENV`, so an unrelated ops change can't re-arm this;
      2. a non-empty source-IP allowlist is configured AND the trusted client IP
         (CF-Connecting-IP, edge-set/unforgeable through the tunnel) is in it — this
         is the authentication that replaces the missing signature, so an empty
         allowlist yields False;
      3. the body is a JSON object (starts with `{`), not a JOSE compact string
         (whose base64url alphabet excludes `{`, so genuine JOSE never misroutes).

    (2) is also enforced by `_check_source_ip` (403 for off-allowlist IPs once the
    allowlist is set); this predicate re-checks it so plaintext acceptance can NEVER
    depend on an empty/absent allowlist.
    """
    if not settings.BSE_WEBHOOK_ALLOW_PLAINTEXT:
        return False
    allow = settings.bse_webhook_source_ips
    if not allow:
        return False
    if RateLimit._get_client_ip(request) not in allow:
        return False
    return raw_body.lstrip()[:1] == b"{"


@router.post(
    "/webhook",
    response_model=WebhookAck,
    status_code=status.HTTP_200_OK,
    summary="BSE Star MF 2.0 webhook receiver (JOSE-verified, store-and-forward)",
)
async def bse_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _rl: Annotated[None, Depends(_rl_webhook)] = None,
) -> WebhookAck:
    # Step 0 — size guard (Content-Length is attacker-controlled, so re-check the
    # actual body too), then read the raw body (the JOSE compact string).
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > _MAX_BODY_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="payload_too_large"
        )
    raw_body: bytes = await request.body()
    if len(raw_body) > _MAX_BODY_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="payload_too_large"
        )

    # Step 1 — optional source-IP allowlist (defence-in-depth on the JOSE path;
    # MANDATORY gate for the UAT plaintext fallback in Step 2).
    _check_source_ip(request)

    # Step 2 — obtain the clear-text event bytes.
    #   * Normal path: BSE signs+encrypts (JOSE) → verify-before-parse.
    #   * UAT plaintext fallback: BSE UAT pushes UNSIGNED plain JSON; accept ONLY
    #     from an allowlisted uat source IP (see `_plaintext_webhook_allowed`).
    if _plaintext_webhook_allowed(request, raw_body):
        clear_bytes = raw_body
        logger.warning(
            "bse.webhook: accepting UNSIGNED plaintext event (BSE_ENV=uat, "
            "allowlisted source IP %s) — stored as a HINT, processor inert",
            RateLimit._get_client_ip(request),
        )
    else:
        try:
            clear_bytes = verify_and_decrypt(raw_body)
        except BSEKeyNotConfigured as exc:
            logger.error("bse.webhook: keys not configured: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="bse_keys_unconfigured"
            )
        except BSEWebhookSecurityError as exc:
            logger.warning("bse.webhook: signature/decrypt failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_signature"
            )

    # Step 3 — parse JSON (only after verified + decrypted).
    try:
        payload = json.loads(clear_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.error("bse.webhook: invalid JSON after decrypt: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_json")

    # Step 4 — normalize the event envelope. ValueError covers pydantic
    # ValidationError (its subclass) so a malformed envelope is a 400, never a 500.
    try:
        parsed = ParsedEvent.from_payload(payload)
    except (KeyError, TypeError, ValueError) as exc:
        logger.error("bse.webhook: malformed event envelope: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="malformed_event")

    # Step 5 — durably persist BEFORE acking (idempotent on request_id).
    ack_id = service.generate_ack_id()
    try:
        new_id = await service.persist_event(db, parsed, payload, ack_id)
    except Exception as exc:  # noqa: BLE001 — persistence failure must 5xx so BSE retries
        logger.exception("bse.webhook: persistence failed request_id=%s: %s", parsed.request_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="persist_failed"
        )

    # Step 6 — enqueue async processing ONLY for a newly inserted event.
    if new_id is not None:
        process_webhook_event.delay(new_id)
    else:
        logger.info("bse.webhook: duplicate request_id=%s acknowledged", parsed.request_id)

    # Step 7 — webhook_ack (always — duplicate or new — so BSE stops retrying).
    return WebhookAck(data=WebhookAckData(id=ack_id))
