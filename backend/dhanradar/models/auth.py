"""
DhanRadar — Auth domain ORM models.

Tables live in the `auth` schema (already created by infra/postgres/init/01_init.sql).
Alembic migration 0001_auth_init creates the actual DDL; this file is the
SQLAlchemy source of truth.

Typing: SQLAlchemy 2.x mapped_column / Mapped style throughout.
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dhanradar.models.base import Base

# ---------------------------------------------------------------------------
# Postgres ENUM — auth.user_tier
# ---------------------------------------------------------------------------

class UserTierEnum(str, enum.Enum):
    anonymous = "anonymous"
    free = "free"
    pro = "pro"
    pro_plus = "pro_plus"
    founder_lifetime = "founder_lifetime"


# SQLAlchemy Enum type bound to the Postgres schema-qualified enum.
# `create_type=False` because the migration creates it explicitly via
# `sa.Enum(..., schema="auth", name="user_tier", create_type=True)`.
_user_tier_pg = Enum(
    UserTierEnum,
    schema="auth",
    name="user_tier",
    create_type=False,
)


# ---------------------------------------------------------------------------
# auth.users
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    # Primary key — server-generated UUID via pgcrypto's gen_random_uuid()
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Email stored lower-cased (enforced at application layer on write).
    # UNIQUE constraint is created in the migration.
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    # Nullable for SSO-only accounts (Google SSO users have no password).
    hashed_password: Mapped[str | None] = mapped_column(Text, nullable=True)

    tier: Mapped[UserTierEnum] = mapped_column(
        _user_tier_pg,
        nullable=False,
        server_default="free",
    )

    # Google SSO — the opaque subject identifier from Google's id_token.
    # Null for password-only accounts; unique across all rows.
    google_sub: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)

    # TOTP — secret stored as plain text for now.
    # TODO Phase: encrypt totp_secret at rest (e.g. via Fernet with a KMS-backed key).
    totp_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # Risk profile — sole writer is the Onboarding module (later phase).
    risk_profile: Mapped[str | None] = mapped_column(Text, nullable=True)

    # DPDP / consent fields — managed by the Consent module (later phase).
    dpdp_consent_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    dpdp_consents: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))

    deletion_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Admin suspend/unsuspend — set by admin endpoints; blocks login while set.
    suspended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    suspended_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )

    # PHASE 5M tiering — Plus time-window grant + one-time AI-commentary taster.
    pro_access_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pro_access_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_taster_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Investor identity — populated from the user's first CAS upload (migration 0057).
    # investor_pan: PAN extracted from the CAS (plain text; encryption at rest is a
    #   future hardening step, same TODO as totp_secret). Never overwritten once set —
    #   a subsequent upload with a different PAN triggers a mismatch warning.
    # full_name: investor name as printed in the CAS (replaces the email-prefix
    #   workaround used by admin/ops_router for display_name).
    investor_pan: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Set to the current server time on every genuine login success (password,
    # TOTP, email-OTP, Google SSO).  NOT updated on token refresh.
    # NULL for users who have never logged in since migration 0044.
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationship
    subscriptions: Mapped[list[Subscription]] = relationship(
        "Subscription", back_populates="user", lazy="raise"
    )


# ---------------------------------------------------------------------------
# auth.subscriptions
# ---------------------------------------------------------------------------

class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscriptions_user_id", "user_id"),
        {"schema": "auth"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
    )

    razorpay_subscription_id: Mapped[str | None] = mapped_column(
        Text, nullable=True, unique=True
    )

    # Raw Razorpay plan id (retained for backward-compat).
    plan: Mapped[str] = mapped_column(Text, nullable=False)
    # Transitional FK into the billing.plans catalog (D4). Nullable while the
    # catalog is populated; `plan` stays the source of truth until cutover.
    plan_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("billing.plans.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)

    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationship
    user: Mapped[User] = relationship("User", back_populates="subscriptions", lazy="raise")


# ---------------------------------------------------------------------------
# auth.user_activity_log
# ---------------------------------------------------------------------------

class UserActivityLog(Base):
    """One row per auth event (login, future: logout, totp_setup, …).

    Inserted best-effort by ``record_login`` in auth.service — never raises.
    The composite index ix_user_activity_user_time (user_id, occurred_at DESC)
    is created by migration 0045 via a raw DDL statement.
    """

    __tablename__ = "user_activity_log"
    # Composite index matches migration 0045 exactly (name + columns + DESC) so the
    # model and the DB agree — no autogenerate drift. user_id is the leading column,
    # so this also serves single-user lookups (no separate single-col index needed).
    __table_args__ = (
        Index("ix_user_activity_user_time", "user_id", text("occurred_at DESC")),
        {"schema": "auth"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 'login' (only value at launch; extensible to 'logout', 'totp_setup', …)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)

    # 'password' | 'totp' | 'email_otp' | 'sso' — NULL only for non-login events
    method: Mapped[str | None] = mapped_column(Text, nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Populated in future when the service layer has request context wired in
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Reserved for future structured metadata (e.g. IP geolocation, device)
    # Attribute name avoids conflict with SQLAlchemy's reserved `.metadata`
    event_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'"),
    )
