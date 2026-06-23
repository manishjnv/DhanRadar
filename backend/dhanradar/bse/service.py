"""
DhanRadar — BSE Star MF 2.0 webhook service layer.

Pure DB + helper logic for the webhook inbox. No FastAPI, no Celery imports here
(the router and task call into this), and no cross-module imports (isolation).

Failsafe contract:
  * `persist_event` does an INSERT ... ON CONFLICT (request_id) DO NOTHING and
    reports whether the row was newly inserted — so a retry/replay is a no-op at
    the DB layer even if the Redis dedup is bypassed.
  * `process_event` is the async processor (called from the Celery task). At the
    current UAT posture it is LOG + MARK PROCESSED only — it performs NO
    transactional side effects (no order execution). Transactional handling is a
    later, separately-reviewed slice gated on UAT validation.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.bse.schemas import ParsedEvent
from dhanradar.models.bse import (
    STATUS_PROCESSED,
    STATUS_RECEIVED,
    BSEWebhookEvent,
)

logger = logging.getLogger(__name__)

_ACK_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


def generate_ack_id() -> str:
    """Generate a webhook_ack id (API doc §7.3.72): `YYYYMMDD-[A-Za-z0-9]{8}`.

    Begins and ends alphanumeric (date digit … alnum), satisfying BSE's format."""
    today = datetime.now(UTC).strftime("%Y%m%d")
    suffix = "".join(secrets.choice(_ACK_ALPHABET) for _ in range(8))
    return f"{today}-{suffix}"


async def persist_event(
    db: AsyncSession,
    parsed: ParsedEvent,
    raw_payload: dict[str, Any],
    ack_id: str,
) -> str | None:
    """Durably store one verified+decrypted webhook event.

    Idempotency is the DB UNIQUE(request_id) via INSERT ... ON CONFLICT DO NOTHING —
    authoritative and failsafe (no lost-event window that a Redis-marker dedup would
    create if persistence then failed).

    Returns the new row id if inserted, or None if `request_id` already existed
    (duplicate — caller ACKs but must NOT re-enqueue). Commits the transaction.
    """
    stmt = (
        pg_insert(BSEWebhookEvent)
        .values(
            request_id=parsed.request_id,
            event_type=parsed.event_type,
            event=parsed.event,
            client_code=parsed.client_code,
            order_id=parsed.order_id,
            sxp_reg_num=parsed.sxp_reg_num,
            mandate_id=parsed.mandate_id,
            ack_id=ack_id,
            raw_payload=raw_payload,
            status=STATUS_RECEIVED,
        )
        .on_conflict_do_nothing(index_elements=["request_id"])
        .returning(BSEWebhookEvent.id)
    )
    result = await db.execute(stmt)
    inserted_id = result.scalar_one_or_none()
    await db.commit()
    return str(inserted_id) if inserted_id is not None else None


async def process_event(db: AsyncSession, event_id: str) -> None:
    """Process one stored webhook event (called from the Celery task).

    UAT posture: LOG + MARK PROCESSED only — no order execution / transactional
    side effects. Idempotent: an already-processed row is a no-op.
    """
    row = await db.scalar(
        select(BSEWebhookEvent).where(BSEWebhookEvent.id == event_id)
    )
    if row is None:
        logger.warning("bse.process_event: event %s not found", event_id)
        return
    if row.status == STATUS_PROCESSED:
        return  # idempotent — already done

    logger.info(
        "bse.webhook.process event_type=%s event=%s request_id=%s client_code=%s",
        row.event_type,
        row.event,
        row.request_id,
        row.client_code,
    )

    # --- transactional dispatch goes here in a later reviewed slice ---
    # (order/sxp/mandate/payment state machines). Intentionally inert at UAT.

    row.status = STATUS_PROCESSED
    row.processed_at = datetime.now(UTC)
    await db.commit()
