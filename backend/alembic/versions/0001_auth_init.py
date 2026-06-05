"""auth_init — create auth.user_tier enum, auth.users and auth.subscriptions tables.

Revision ID: 0001
Revises: (none — initial migration)
Create Date: 2026-05-19

Notes:
  - pgcrypto is created first so gen_random_uuid() is available for UUID
    server defaults.  The extension is idempotent (CREATE IF NOT EXISTS).
  - The `auth` schema is already created by infra/postgres/init/01_init.sql
    so we do NOT create it here.
  - auth.user_tier Postgres ENUM is created before the users table.
  - Indexes: users.email (unique), subscriptions.user_id, subscriptions.razorpay_subscription_id (unique).
  - downgrade() drops in reverse dependency order.

Run via (inside container):
    docker compose exec dhanradar-fastapi alembic upgrade head
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. pgcrypto — needed for gen_random_uuid() server default
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ------------------------------------------------------------------
    # 2. auth.user_tier ENUM
    # ------------------------------------------------------------------
    user_tier_enum = postgresql.ENUM(
        "anonymous",
        "free",
        "pro",
        "pro_plus",
        "founder_lifetime",
        name="user_tier",
        schema="auth",
    )
    user_tier_enum.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # 3. auth.users table
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("hashed_password", sa.Text(), nullable=False),
        sa.Column(
            "tier",
            postgresql.ENUM(
                "anonymous",
                "free",
                "pro",
                "pro_plus",
                "founder_lifetime",
                name="user_tier",
                schema="auth",
                create_type=False,  # already created above
            ),
            server_default="free",
            nullable=False,
        ),
        sa.Column("totp_secret", sa.Text(), nullable=True),
        sa.Column(
            "totp_verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("risk_profile", sa.Text(), nullable=True),
        sa.Column("dpdp_consent_version", sa.Text(), nullable=True),
        sa.Column(
            "dpdp_consents",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "deletion_requested_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        # UNIQUE(email) — Postgres backs this with an implicit unique index,
        # so no separate CREATE INDEX is needed (a second one would be dead
        # weight on every write).
        sa.UniqueConstraint("email", name="uq_users_email"),
        schema="auth",
    )

    # ------------------------------------------------------------------
    # 4. auth.subscriptions table
    # ------------------------------------------------------------------
    op.create_table(
        "subscriptions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "razorpay_subscription_id", sa.Text(), nullable=True
        ),
        sa.Column("plan", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "current_period_start",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "current_period_end",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth.users.id"],
            ondelete="CASCADE",
            name="fk_subscriptions_user_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "razorpay_subscription_id",
            name="uq_subscriptions_razorpay_id",
        ),
        schema="auth",
    )
    op.create_index(
        "ix_subscriptions_user_id",
        "subscriptions",
        ["user_id"],
        unique=False,
        schema="auth",
    )


def downgrade() -> None:
    # Drop in reverse dependency order.

    # 4. subscriptions indexes + table
    op.drop_index(
        "ix_subscriptions_user_id",
        table_name="subscriptions",
        schema="auth",
    )
    op.drop_table("subscriptions", schema="auth")

    # 3. users table (UNIQUE(email) is dropped with the table)
    op.drop_table("users", schema="auth")

    # 2. auth.user_tier ENUM
    user_tier_enum = postgresql.ENUM(
        "anonymous",
        "free",
        "pro",
        "pro_plus",
        "founder_lifetime",
        name="user_tier",
        schema="auth",
    )
    user_tier_enum.drop(op.get_bind(), checkfirst=True)

    # Note: we intentionally do NOT drop pgcrypto as other schemas may use it.
