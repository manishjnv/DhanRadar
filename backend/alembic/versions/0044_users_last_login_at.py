"""auth.users: add last_login_at (tracks last successful login timestamp).

Adds a NULLABLE ``last_login_at TIMESTAMP WITH TIME ZONE`` column to
``auth.users``. The column is populated by the service layer on every
genuine login success (password, TOTP, email-OTP, Google SSO) but NOT on
token refresh.  Existing rows stay NULL — no backfill, no default.

Reversible: downgrade drops the column.

Revision ID: 0044
Revises: 0043
Create Date: 2026-06-23
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0044"
down_revision: str | None = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_column("users", "last_login_at", schema="auth")
