"""pro_access — PHASE 5M tiering columns on auth.users.

Adds three columns to support the freemium tier-gate:
  - pro_access_until  : time-window grant (founding / triggered_trial)
  - pro_access_reason : origin of the grant (founding / triggered_trial / subscription)
  - ai_taster_used_at : one-time free commentary taster consumption timestamp

Backfills existing users with the founding-access window.

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("pro_access_until", sa.DateTime(timezone=True), nullable=True),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column(
            "pro_access_reason",
            sa.Text(),
            nullable=True,
            comment="Values: founding / triggered_trial / subscription",
        ),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column("ai_taster_used_at", sa.DateTime(timezone=True), nullable=True),
        schema="auth",
    )

    # Backfill existing users with founding access.
    op.execute(
        "UPDATE auth.users "
        "SET pro_access_until = TIMESTAMPTZ '2026-12-31 23:59:59+00', "
        "    pro_access_reason = 'founding' "
        "WHERE pro_access_until IS NULL"
    )


def downgrade() -> None:
    op.drop_column("users", "ai_taster_used_at", schema="auth")
    op.drop_column("users", "pro_access_reason", schema="auth")
    op.drop_column("users", "pro_access_until", schema="auth")
