"""
DhanRadar — Notification domain ORM models (Phase 6, architecture Global §5).

Tables live in the `notify` schema (schema-per-concern, non-neg #7). Alembic
migration 0005 creates the DDL; this file is the SQLAlchemy source of truth.

Module isolation: `user_id` references `auth.users.id` (referential integrity,
like `auth.subscriptions` / the MF tables) — the Notification module never JOINs
into or writes other modules' tables. It owns delivery state only; it generates no
content (templates render label + disclosure, never a numeric score, non-neg #2/#9).
"""

from __future__ import annotations

from datetime import datetime, time
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Text,
    Time,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from dhanradar.models.base import Base

_SCHEMA = {"schema": "notify"}


class NotificationPreference(Base):
    """One row per user — channel addresses, quiet-hours window, enabled channels.

    `quiet_hours_*` are wall-clock times interpreted in IST (the project tz). A
    null window means "no quiet hours". `channels_enabled` is the opt-in map
    (e.g. {"telegram": true, "email": true}); a channel absent/false means the
    user has not opted that channel in — delivery is suppressed (fail-closed).
    """

    __tablename__ = "notification_preferences"
    __table_args__ = _SCHEMA

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    telegram_chat_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    whatsapp_number: Mapped[str | None] = mapped_column(Text, nullable=True)  # Y2, not delivered P1
    quiet_hours_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    quiet_hours_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    channels_enabled: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class NotificationLog(Base):
    """Append-only delivery log. `status` ∈ sent | failed | rate_capped | deferred;
    `error_text` carries an OPAQUE failure code (never a raw provider body/PII)."""

    __tablename__ = "notification_log"
    __table_args__ = (
        Index("ix_notification_log_user", "user_id"),
        Index("ix_notification_log_created", "created_at"),
        _SCHEMA,
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False)  # telegram | email
    template_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
