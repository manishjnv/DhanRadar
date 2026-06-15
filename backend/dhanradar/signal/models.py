"""SQLAlchemy ORM models for the Signal feature (signal Postgres schema)."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from dhanradar.models.base import Base


class SignalRules(Base):
    """Per-user signal threshold configuration."""

    __tablename__ = "signal_rules"
    __table_args__ = {"schema": "signal"}

    user_id = sa.Column(UUID(as_uuid=True), primary_key=True)
    nifty_threshold = sa.Column(sa.Numeric(6, 2), nullable=False)
    vix_threshold = sa.Column(sa.Numeric(6, 2), nullable=False)
    breadth_threshold = sa.Column(sa.Numeric(4, 3), nullable=False)
    deploy_ladder = sa.Column(JSONB, nullable=False)
    alerts_on = sa.Column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))
    updated_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        onupdate=sa.func.now(),
    )


class SignalDipFund(Base):
    """Per-user dip fund balance and monthly addition."""

    __tablename__ = "signal_dip_fund"
    __table_args__ = {"schema": "signal"}

    user_id = sa.Column(UUID(as_uuid=True), primary_key=True)
    balance = sa.Column(sa.Numeric(14, 2), nullable=False, server_default=sa.text("0"))
    monthly_addition = sa.Column(sa.Numeric(14, 2), nullable=False, server_default=sa.text("0"))
    last_updated = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))


class SignalDeployment(Base):
    """Record of each dip-fund deployment by the user."""

    __tablename__ = "signal_deployments"
    __table_args__ = (
        sa.Index("ix_signal_deployments_user_date", "user_id", "date"),
        sa.CheckConstraint(
            "signal_state IN ('triggered', 'watch', 'no_signal')",
            name="ck_signal_deployments_state",
        ),
        {"schema": "signal"},
    )

    id = sa.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id = sa.Column(UUID(as_uuid=True), nullable=False)
    date = sa.Column(sa.Date, nullable=False)
    amount = sa.Column(sa.Numeric(14, 2))
    signal_state = sa.Column(sa.String(20))
    market_snapshot = sa.Column(JSONB)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))


class SignalJournal(Base):
    """Investment journal entry (Phase 2 Reflect tab)."""

    __tablename__ = "signal_journal"
    __table_args__ = (
        sa.Index("ix_signal_journal_user_date", "user_id", "date"),
        sa.CheckConstraint(
            "decision IN ('deployed', 'watched', 'skipped')",
            name="ck_signal_journal_decision",
        ),
        {"schema": "signal"},
    )

    id = sa.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id = sa.Column(UUID(as_uuid=True), nullable=False)
    date = sa.Column(sa.Date, nullable=False)
    decision = sa.Column(sa.String(20))
    amount = sa.Column(sa.Numeric(14, 2))
    emotion = sa.Column(JSONB)   # list[str]
    notes = sa.Column(sa.Text)
    market_snapshot = sa.Column(JSONB)   # {nifty_pct, vix_level, breadth_ratio}
    signal_state = sa.Column(sa.String(20))   # signal state at time of entry (looked up)
    fomo_avoided = sa.Column(sa.Boolean)   # derived: skipped + fomo emotion
    premature = sa.Column(sa.Boolean)   # derived: deployed when signal was no_signal
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))


class SignalNotification(Base):
    """In-app daily alert notification for a user."""

    __tablename__ = "signal_notifications"
    __table_args__ = (
        sa.Index(
            "ix_signal_notifications_user_unread",
            "user_id",
            "read_at",
            postgresql_where=sa.text("read_at IS NULL"),
        ),
        {"schema": "signal"},
    )

    id = sa.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id = sa.Column(UUID(as_uuid=True), nullable=False)
    message = sa.Column(sa.Text, nullable=False)
    signal_state = sa.Column(sa.String(20), nullable=False)
    read_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))
