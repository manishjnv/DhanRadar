"""Add investor_pan and full_name to auth.users for CAS ownership verification.

investor_pan — PAN extracted from the user's own CAS upload (plain text; encryption
               at rest is a future hardening step, same TODO as totp_secret).
full_name    — Investor name as printed in the CAS (replaces the email-prefix workaround
               used by admin/ops_router display_name).

Both are nullable; NULL means the user has not yet uploaded a CAS that contained them.
Populated by the CAS pipeline on first upload; never overwritten once set (so a later
upload with a different PAN is flagged as a mismatch rather than silently replaced).

Revision ID: 0057
Revises: 0056
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("investor_pan", sa.Text(), nullable=True),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column("full_name", sa.Text(), nullable=True),
        schema="auth",
    )
    # Partial index: fast lookup of "does any user own this PAN?" used by the mismatch check.
    op.create_index(
        "ix_auth_users_investor_pan",
        "users",
        ["investor_pan"],
        unique=False,
        schema="auth",
        postgresql_where=sa.text("investor_pan IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_auth_users_investor_pan", table_name="users", schema="auth")
    op.drop_column("users", "full_name", schema="auth")
    op.drop_column("users", "investor_pan", schema="auth")
