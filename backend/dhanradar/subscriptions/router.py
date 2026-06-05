"""
DhanRadar — Subscriptions API router.

Endpoints:
  POST /api/v1/subscriptions/webhook   (Razorpay webhook receiver)

Security invariant (invariant #6 from spec):
  - Raw request body bytes are read FIRST via `await request.body()`.
  - `X-Razorpay-Signature` header is extracted.
  - `razorpay.utility.verify_webhook_signature(body_str, sig, secret)` is
    called BEFORE any JSON parsing.
  - Only on verified signature: parse body as JSON and delegate to service.
  - If signature check raises → 400, no further processing.

This ordering is critical: JSON parsing before sig verify is a known
anti-pattern (Phase-0 anti-pattern per spec) that can allow deserialization
attacks on unverified payloads.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Annotated

import razorpay
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.config import settings
from dhanradar.db import get_db
from dhanradar.redis_client import get_redis
from dhanradar.subscriptions import service as sub_svc

# A verified Razorpay webhook body stays signature-valid forever, so a captured
# event could be replayed to (e.g.) re-grant a paid tier after cancellation.
# Dedup on Razorpay's event id (header) — first delivery wins, replays are
# acknowledged 200 but not reprocessed. 7-day window covers Razorpay retries.
_EVENT_DEDUP_PREFIX = "auth:rzp_evt:"
_EVENT_DEDUP_TTL = 7 * 86400

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Razorpay subscription webhook receiver",
)
async def razorpay_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    Receive and process Razorpay subscription lifecycle events.

    Step 1: Read raw bytes.
    Step 2: Extract X-Razorpay-Signature header.
    Step 3: Verify signature on raw bytes BEFORE parsing JSON.
    Step 4 (only on valid sig): parse JSON, delegate to service.
    """
    # Step 1 — raw body (must happen before any body() consumption elsewhere)
    raw_body: bytes = await request.body()

    # Step 2 — signature header
    signature: str | None = request.headers.get("X-Razorpay-Signature")
    if not signature:
        logger.warning("Razorpay webhook: missing X-Razorpay-Signature header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing_signature",
        )

    # Step 3 — signature verification on RAW bytes (not parsed JSON)
    try:
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        client.utility.verify_webhook_signature(
            raw_body.decode("utf-8"),
            signature,
            settings.RAZORPAY_WEBHOOK_SECRET,
        )
    except Exception as exc:  # razorpay raises SignatureVerificationError
        logger.warning("Razorpay webhook: signature verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_signature",
        )

    # Step 4 — parse JSON only after verified
    try:
        event_data: dict = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        logger.error("Razorpay webhook: invalid JSON after sig verify: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_json",
        )

    # Step 5 — replay/idempotency guard (only after signature verified).
    # Prefer Razorpay's event id header; fall back to a hash of the verified
    # body so a replay is still caught even if the header is absent.
    event_id = request.headers.get("X-Razorpay-Event-Id") or hashlib.sha256(
        raw_body
    ).hexdigest()
    redis = get_redis()
    is_first = await redis.set(
        f"{_EVENT_DEDUP_PREFIX}{event_id}", "1", nx=True, ex=_EVENT_DEDUP_TTL
    )
    if not is_first:
        logger.info("Razorpay webhook: duplicate event %s ignored", event_id)
        return {"status": "duplicate_ignored"}

    # Delegate to service using the request-scoped session (Depends(get_db)),
    # so the test override applies and the session stays on the request's loop.
    await sub_svc.handle_subscription_event(event_data, db)

    return {"status": "ok"}
