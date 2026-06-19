"""user_suspension: add suspended_at and suspended_reason to auth.users.

Adds two nullable columns that allow admins to suspend/unsuspend accounts
without triggering the DPDP erasure path. Login is blocked when suspended_at
IS NOT NULL (checked alongside deletion_requested_at in auth service).

Revision ID: 0038
Revises: 0037
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column("suspended_reason", sa.Text(), nullable=True),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_column("users", "suspended_reason", schema="auth")
    op.drop_column("users", "suspended_at", schema="auth")
