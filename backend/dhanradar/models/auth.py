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
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
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

    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)

    tier: Mapped[UserTierEnum] = mapped_column(
        _user_tier_pg,
        nullable=False,
        server_default="free",
    )

    # TOTP — secret stored as plain text for now.
    # TODO Phase: encrypt totp_secret at rest (e.g. via Fernet with a KMS-backed key).
    totp_secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    totp_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # Risk profile — sole writer is the Onboarding module (later phase).
    risk_profile: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # DPDP / consent fields — managed by the Consent module (later phase).
    dpdp_consent_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dpdp_consents: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))

    deletion_requested_at: Mapped[Optional[datetime]] = mapped_column(
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

    razorpay_subscription_id: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, unique=True
    )

    # Raw Razorpay plan id (retained for backward-compat).
    plan: Mapped[str] = mapped_column(Text, nullable=False)
    # Transitional FK into the billing.plans catalog (D4). Nullable while the
    # catalog is populated; `plan` stays the source of truth until cutover.
    plan_id: Mapped[Optional[str]] = mapped_column(
        Text, ForeignKey("billing.plans.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)

    current_period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[Optional[datetime]] = mapped_column(
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
