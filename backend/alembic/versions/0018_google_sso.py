"""google_sso — add google_sub column + make hashed_password nullable.

Adds Google SSO support to auth.users:
  - google_sub TEXT nullable, unique (uq_users_google_sub): the opaque subject
    identifier from Google's id_token.  NULL for password-only accounts.
  - hashed_password TEXT nullable (was NOT NULL): SSO-only accounts have no
    password and store NULL here.

Downgrade note: the downgrade will FAIL if any row has hashed_password IS NULL
(i.e. SSO-only users exist), because restoring NOT NULL on a column with NULL
values is a Postgres error.  This is an acceptable deployment risk — always take
a backup before downgrading after SSO is live.

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add google_sub column (nullable, unique).
    op.add_column(
        "users",
        sa.Column("google_sub", sa.Text(), nullable=True),
        schema="auth",
    )
    op.create_unique_constraint(
        "uq_users_google_sub",
        "users",
        ["google_sub"],
        schema="auth",
    )

    # Make hashed_password nullable (SSO-only users have no password).
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.Text(),
        nullable=True,
        schema="auth",
    )


def downgrade() -> None:
    # NOTE: This downgrade will fail if any row has hashed_password IS NULL.
    # Ensure no SSO-only users exist before running downgrade.
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.Text(),
        nullable=False,
        schema="auth",
    )

    op.drop_constraint(
        "uq_users_google_sub",
        "users",
        type_="unique",
        schema="auth",
    )
    op.drop_column("users", "google_sub", schema="auth")
