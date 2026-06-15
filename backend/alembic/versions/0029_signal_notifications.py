"""signal_notifications: new table for in-app daily alerts.

Revision ID: 0029
Revises: 0028
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("signal_state", sa.String(20), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        schema="signal",
    )
    op.create_index(
        "ix_signal_notifications_user_unread",
        "signal_notifications",
        ["user_id", "read_at"],
        postgresql_where=sa.text("read_at IS NULL"),
        schema="signal",
    )


def downgrade() -> None:
    op.drop_index("ix_signal_notifications_user_unread", table_name="signal_notifications", schema="signal")
    op.drop_table("signal_notifications", schema="signal")
