"""notify_schema — Notification module schema (Phase 6).

Creates the `notify` schema + 2 tables (architecture Global §5 Notification
Module): `notification_preferences` (one row/user — channel addresses, quiet-hours,
opt-in map) and `notification_log` (append-only delivery audit). Delivery queues
live in Redis (`notifications:queue:{telegram,email}`), not Postgres.

Additive + reversible. user_id columns FK auth.users(id) ON DELETE CASCADE
(referential integrity only; the Notification module never writes other modules'
tables, non-neg #7).

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-06
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)
_GEN = sa.text("gen_random_uuid()")


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS notify")

    op.create_table(
        "notification_preferences",
        sa.Column("user_id", _UUID, sa.ForeignKey("auth.users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("telegram_chat_id", sa.Text(), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("whatsapp_number", sa.Text(), nullable=True),
        sa.Column("quiet_hours_start", sa.Time(), nullable=True),
        sa.Column("quiet_hours_end", sa.Time(), nullable=True),
        sa.Column("channels_enabled", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="notify",
    )

    op.create_table(
        "notification_log",
        sa.Column("id", _UUID, primary_key=True, server_default=_GEN),
        sa.Column("user_id", _UUID, sa.ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("template_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="notify",
    )
    op.create_index("ix_notification_log_user", "notification_log", ["user_id"], schema="notify")
    op.create_index("ix_notification_log_created", "notification_log", ["created_at"], schema="notify")


def downgrade() -> None:
    op.drop_table("notification_log", schema="notify")
    op.drop_table("notification_preferences", schema="notify")
    op.execute("DROP SCHEMA IF EXISTS notify")
