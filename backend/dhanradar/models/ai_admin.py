"""
DhanRadar — AI Admin ORM models (Phase 5 prompt registry + budget caps).

Tables live in the `compliance` schema (AI governance concern; non-neg #7).
Alembic migration 0038 creates the DDL; this file is the SQLAlchemy source of truth.

NOTE: PromptTemplate rows are the admin CRUD registry only.  The AI gateway
does NOT yet consume active templates at request time — the gateway still accepts
prompts from callers.  Wiring the gateway to consume active templates is a future
Phase 6 step.  The comment is deliberate so the unconsumed registry is visible.

Invariants:
  - prompt_templates: partial unique index ``uq_prompt_active_per_key`` on
    (template_key) WHERE is_active ensures at most one active version per key.
    Enforced at the DB level.
  - ai_budget_caps: append-only history; effective caps = most-recent row
    (ordered by updated_at DESC).  No UPDATE/DELETE paths provided here.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from dhanradar.models.base import Base

_SCHEMA = {"schema": "compliance"}


class PromptTemplate(Base):
    """Versioned prompt template.  One active version per template_key at a time.

    Append-only on the version axis: new versions are always created as INACTIVE
    and activated explicitly by the admin activate endpoint (which first deactivates
    all sibling rows, then sets is_active=True for the target — single transaction).

    NOTE: registry is not yet consumed by the AI gateway.  See module docstring.
    """

    __tablename__ = "prompt_templates"
    __table_args__ = _SCHEMA

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    template_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AiBudgetCap(Base):
    """Append-only admin override record for AI budget caps.

    Effective caps = the most-recent row (by updated_at DESC).
    Each admin ``set_budget_caps`` call INSERTs a new row; prior rows are
    retained for audit history.  Redis override keys are the live-serving
    mechanism; this table is the durable audit trail.
    """

    __tablename__ = "ai_budget_caps"
    __table_args__ = _SCHEMA

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    free_cap: Mapped[int] = mapped_column(Integer, nullable=False)
    premium_soft_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    premium_hard_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
