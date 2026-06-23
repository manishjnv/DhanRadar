"""auth.user_activity_log: per-user login event table for admin activity feed.

Creates ``auth.user_activity_log`` — a BigInteger-keyed event log that records
every genuine login (event_type='login') with the auth method used.  Rows are
inserted by ``record_login`` in the auth service layer (best-effort, never
breaks login on failure).

Adds a composite index ``ix_user_activity_user_time`` on (user_id, occurred_at
DESC) to support per-user history and global recent-logins queries efficiently.

Reversible: downgrade drops the table (CASCADE covers the FK index).

Revision ID: 0045
Revises: 0044
Create Date: 2026-06-23
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0045"
down_revision: str | None = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_activity_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("method", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column(
            "event_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth.users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="auth",
    )
    # Composite index: (user_id ASC, occurred_at DESC) — per-user history +
    # global recent-logins ordered newest-first.
    op.execute(
        sa.text(
            "CREATE INDEX ix_user_activity_user_time"
            " ON auth.user_activity_log (user_id, occurred_at DESC)"
        )
    )


def downgrade() -> None:
    op.drop_table("user_activity_log", schema="auth")
