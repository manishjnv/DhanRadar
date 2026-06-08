"""
DhanRadar — Consent Audit domain ORM model (B44).

Table lives in the `consent` schema (schema-per-concern, non-neg #7).
Alembic migration 0010 creates the DDL; this file is the SQLAlchemy
source of truth.

Consent-engineering invariants (deliberate):
  * `consent_audit_log` is an append-only audit trail for every DPDP
    consent grant/revoke action.
  * `user_id` carries NO FK/CASCADE — the audit trail must survive a
    DPDP erasure of the user row (right-to-erasure does not erase the
    audit record of the consent action itself; only PII content is
    erased, not the fact of consent).
  * `action` is constrained to ('grant', 'revoke') at the DB level.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from dhanradar.models.base import Base

_SCHEMA = "consent"


class ConsentAuditLog(Base):
    """Append-only audit row for one DPDP consent grant or revoke action."""

    __tablename__ = "consent_audit_log"
    __table_args__ = (
        Index("ix_consent_audit_user", "user_id", "created_at"),
        # Mirror the migration DDL CHECK so create_all() test schemas (which do
        # not run Alembic) also enforce the action domain.
        CheckConstraint("action IN ('grant', 'revoke')", name="ck_consent_audit_action"),
        {"schema": _SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # NO FK/CASCADE — append-only audit must survive user deletion (DPDP erasure).
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)  # 'grant' | 'revoke'
    consent_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
