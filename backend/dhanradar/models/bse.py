"""
DhanRadar — BSE Star MF 2.0 webhook inbox ORM model.

One append-mostly table in the `bse` schema: `webhook_events`. It is the durable
store-and-forward inbox for every BSE Star MF 2.0 webhook (UCC / ORDER / SXP /
MANDATES / PAYMENT GATEWAY). The HTTP receiver writes the verified+decrypted
event here and commits BEFORE acknowledging BSE, so a webhook is never lost; all
business processing happens asynchronously off this row (Celery).

Idempotency: `request_id` (BSE supplies one per event) is UNIQUE — a retry/replay
hits the conflict and is acknowledged without reprocessing.

NO FK on any column — BSE identifiers (`client_code`, `order_id`, …) are BSE's, not
our user/portfolio ids; module isolation (non-neg #7) means the bse module never
joins or writes another module's tables.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from dhanradar.models.base import Base

_SCHEMA = {"schema": "bse"}

# Lifecycle of one inbox row.
STATUS_RECEIVED = "received"   # persisted, not yet processed
STATUS_PROCESSED = "processed"  # processor ran to completion
STATUS_FAILED = "failed"       # processor raised; ret riable
STATUS_DEAD = "dead"           # processing retries exhausted (dead-letter)


class BSEWebhookEvent(Base):
    """One BSE Star MF 2.0 webhook event (verified + decrypted)."""

    __tablename__ = "webhook_events"
    __table_args__ = (
        Index("ix_bse_webhook_events_status", "status"),
        Index("ix_bse_webhook_events_received_at", "received_at"),
        Index("ix_bse_webhook_events_client_code", "client_code"),
        _SCHEMA,
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # BSE's per-event id — UNIQUE is the DB-level idempotency guard (defence in
    # depth alongside the Redis SETNX in the router).
    request_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    event_type: Mapped[str] = mapped_column(Text, nullable=False)   # UCC / ORDER / SXP / MANDATES / PAYMENT GATEWAY
    event: Mapped[str] = mapped_column(Text, nullable=False)        # e.g. match_pending, ACTIVE, reg
    # Extracted identifiers (nullable — present only on the relevant event types).
    client_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    sxp_reg_num: Mapped[str | None] = mapped_column(Text, nullable=True)
    mandate_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The webhook_ack id we returned to BSE (YYYYMMDD-[A-Za-z0-9]{8}).
    ack_id: Mapped[str] = mapped_column(Text, nullable=False)

    # Full decrypted clear-text event JSON (the `action` envelope + member/investor).
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text(f"'{STATUS_RECEIVED}'"))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
