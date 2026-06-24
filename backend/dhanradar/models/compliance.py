"""
DhanRadar — Compliance Audit domain ORM models (architecture Global §4, B26).

Tables live in the `compliance` schema (schema-per-concern, non-neg #7). Alembic
migration 0006 creates the DDL; this file is the SQLAlchemy source of truth.

Compliance-engineering invariants (deliberate, see docs/features/compliance-audit.md):
  * `ai_recommendation_audit` is the immutable 7-yr SEBI audit trail: every SERVED
    label/output persists `(label, model_used, disclaimer_version)` (non-neg #9 / B26).
  * `user_id` carries NO FK/CASCADE — the audit must OUTLIVE a DPDP erasure of the
    user (SEBI 7-yr retention > erasure for the audit trail). `disclaimer_version`
    is a denormalized NOT-NULL text (NOT a hard FK) so a fire-and-forget audit write
    can never be lost to a referential hiccup; `disclaimers` is the version registry,
    reconciled by value.
  * `recommendation_type` rejects `buy_sell` at the DB (CHECK) — no advisory output
    can ever be audited as served (non-neg #1).
  * In the real DB the table is RANGE-partitioned monthly on `served_at` (migration
    0006) with a DEFAULT partition so an insert always lands; the ORM model here is a
    plain table (the CI test DB builds from ORM metadata, like `mf_nav_history`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from dhanradar.models.base import Base

_SCHEMA = {"schema": "compliance"}


class Disclaimer(Base):
    """Disclaimer version registry. `version` is a globally-unique date-stamped id
    (e.g. `2026-06-06.v1`), used as the PK so the audit's denormalized
    `disclaimer_version` can be reconciled by value."""

    __tablename__ = "disclaimers"
    # Partial-unique index: at most one active disclaimer per type (single-active
    # invariant enforced atomically at the DB level; migration 0008). Mirrors the
    # raw-SQL `uq_disclaimer_active_per_type` so CI create_all == prod alembic.
    __table_args__ = (
        Index(
            "uq_disclaimer_active_per_type",
            "type",
            unique=True,
            postgresql_where=text("active"),
        ),
        _SCHEMA,
    )

    version: Mapped[str] = mapped_column(Text, primary_key=True)
    type: Mapped[str] = mapped_column(Text, nullable=False, server_default="ai_recommendation")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AiRecommendationAudit(Base):
    """Immutable 7-yr audit row for one served label/output. Append-only — no UPDATE/
    DELETE path. PK is composite `(id, served_at)` because the real table is
    partitioned on `served_at` (PG requires the partition key in the PK)."""

    __tablename__ = "ai_recommendation_audit"
    __table_args__ = (
        # POSITIVE allowlist (strictly safer than a denylist): only educational
        # recommendation types may ever be audited as served — no advisory verb
        # (buy/sell/hold/…) can enter the trail (non-neg #1). New types are added
        # deliberately via a migration (controlled vocabulary).
        CheckConstraint(
            "recommendation_type IN ('educational_label', 'mood_regime')",
            name="ck_audit_recommendation_type",
        ),
        Index("ix_audit_user", "user_id"),
        Index("ix_audit_served_at", "served_at"),
        _SCHEMA,
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    served_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False, server_default=func.now()
    )
    # NO FK/CASCADE — the audit outlives a DPDP erasure of the user.
    user_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    recommendation_type: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # B26: the served verb-label
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)  # SHA-256 of the served payload
    model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # model_used / engine version
    prompt_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    confidence_band: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Denormalized, NOT-NULL, no hard FK (never lose an audit row to a referential hiccup).
    disclaimer_version: Mapped[str] = mapped_column(Text, nullable=False)
    surface: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # mf_report | notification_*
    session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RatingEngineChangelog(Base):
    """Append-only methodology changelog for the scoring/rating engine.

    One row per methodology version change — stores factors before/after,
    the two-person approval outcome, and an optional methodology URL so every
    weight/band change is reproducible for SEBI regulatory purposes (spec §8).

    No writer wired yet — written by the B6/B28 two-person scoring-activation
    gate (slice 2) via ``compliance.service.record_engine_changelog``."""

    __tablename__ = "rating_engine_changelog"
    # Partial-unique: at most one ACTIVATED row per model_version (the single
    # activation-record-per-version invariant, enforced atomically; migration 0009).
    # Many activated=false rows per version are allowed (proposed methodology changes).
    __table_args__ = (
        Index(
            "uq_engine_changelog_activated_per_version",
            "model_version",
            unique=True,
            postgresql_where=text("activated"),
        ),
        _SCHEMA,
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    two_person_ok: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    factors_before: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'")
    )
    factors_after: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'")
    )
    methodology_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    backtest: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    drift: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    activated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    activated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AiLowConfidenceLog(Base):
    """Append-only log of AI/scoring surface emissions below the confidence floor.

    No writer wired yet — the AI/scoring confidence-floor consumer (B22) calls
    ``compliance.service.log_low_confidence``; built ahead like B20's call site so
    the schema is stable before the consumer lands."""

    __tablename__ = "ai_low_confidence_log"
    __table_args__ = (
        Index("ix_low_conf_logged_at", "logged_at"),
        _SCHEMA,
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    surface: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    identifier: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    confidence_band: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AiOutputFeedback(Base):
    """Append-only user feedback on a served AI output (thumbs up/down).

    Linked to ``compliance.ai_recommendation_audit`` by ``audit_id`` (no hard FK —
    the audit row is immutable and SEBI-retained, so referential integrity is
    guaranteed by design; a soft reference avoids lock coupling).

    DPDP note: ``user_id`` is stored. ``RequireConsent`` MUST be wired to the
    submission endpoint before this table is populated with real-user data
    (tracked in BLOCKERS.md B64). Append-only — no UPDATE or DELETE path.
    """

    __tablename__ = "ai_output_feedback"
    __table_args__ = (
        # One vote per user per audit output — prevents duplicate-vote spam.
        UniqueConstraint("audit_id", "user_id", name="uq_ai_output_feedback_per_user_audit"),
        Index("ix_ai_output_feedback_audit_id", "audit_id"),
        Index("ix_ai_output_feedback_user_id", "user_id"),
        _SCHEMA,
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Soft reference to compliance.ai_recommendation_audit.id (no hard FK — see docstring).
    audit_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
