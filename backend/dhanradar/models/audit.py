"""
DhanRadar — Audit ledger ORM models (B57 P2).

Three append-only tables in the `audit` schema:
  * AdminAction      — admin compliance actions (activate_disclaimer, activate_scoring_model, …)
  * PaymentEvent     — Razorpay subscription lifecycle (SEBI 7-yr financial record)
  * SecurityEvent    — security incidents (token reuse, TOTP lockout, …)

All three are RANGE-partitioned monthly on `ts` in the real DB (migration 0014);
the ORM model is a plain table so CI create_all works without PARTITION BY.

Append-only by convention — no UPDATE/DELETE code path is provided here.
NOTE: a DB-level UPDATE/DELETE-blocking trigger is deferred hardening (future slice).

NO FK on any column — audit records must outlive user/subscription deletion
(SEBI 7-yr retention coexists with DPDP erasure).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from dhanradar.models.base import Base

_SCHEMA = {"schema": "audit"}


class AdminAction(Base):
    """Immutable audit row for one admin compliance action.

    `admin_id` is stored RAW (staff id, not end-user PII).
    PK is composite `(id, ts)` because the real table is partitioned on `ts`.
    """

    __tablename__ = "admin_actions"
    __table_args__ = (
        Index("ix_audit_admin_actions_ts", "ts"),
        Index("ix_audit_admin_actions_admin_id", "admin_id"),
        _SCHEMA,
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False, server_default=func.now()
    )
    # NO FK — audit outlives user deletion.
    admin_id: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_hash: Mapped[str] = mapped_column(Text, nullable=False)


class PaymentEvent(Base):
    """Immutable audit row for one Razorpay payment/subscription lifecycle event.

    `user_id` is stored RAW (identifiable by design — SEBI 7-yr financial record,
    per ADR-0022; NOT hashed here unlike SecurityEvent).
    PK is composite `(id, ts)` because the real table is partitioned on `ts`.
    """

    __tablename__ = "payment_events"
    __table_args__ = (
        Index("ix_audit_payment_events_ts", "ts"),
        Index("ix_audit_payment_events_user_id", "user_id"),
        _SCHEMA,
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False, server_default=func.now()
    )
    # NO FK — audit outlives user deletion.
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    order_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_hash: Mapped[str] = mapped_column(Text, nullable=False)


class SecurityEvent(Base):
    """Immutable audit row for one security incident.

    `user_ref` stores `hash_user_ref(user_id)` — a 16-hex-char SHA-256 prefix,
    never the raw user_id (DPDP privacy; column name is user_ref, not user_id).
    PK is composite `(id, ts)` because the real table is partitioned on `ts`.
    """

    __tablename__ = "security_events"
    __table_args__ = (
        Index("ix_audit_security_events_ts", "ts"),
        Index("ix_audit_security_events_event_type", "event_type"),
        _SCHEMA,
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False, server_default=func.now()
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    # Hashed user ref — never the raw user_id.
    user_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_hash: Mapped[str] = mapped_column(Text, nullable=False)
