"""billing_plans — create billing schema + billing.plans catalog; add
auth.subscriptions.plan_id (nullable FK).  Backward-compatible (D4): the
existing auth.subscriptions.plan TEXT column is retained and not back-filled.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-05

Run via (inside container):
    docker compose exec dhanradar-fastapi alembic upgrade head
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. billing schema (schema-per-concern; never flat public)
    # ------------------------------------------------------------------
    op.execute("CREATE SCHEMA IF NOT EXISTS billing")

    # ------------------------------------------------------------------
    # 2. billing.plans catalog
    # ------------------------------------------------------------------
    op.create_table(
        "plans",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("price_inr", sa.Integer(), nullable=False),
        sa.Column("interval", sa.Text(), nullable=False),
        sa.Column(
            "features",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "active", sa.Boolean(), server_default=sa.text("true"), nullable=False
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
        schema="billing",
    )

    # ------------------------------------------------------------------
    # 3. auth.subscriptions.plan_id — nullable FK → billing.plans(id)
    #    `plan` (TEXT) is retained; nothing is back-filled (transition).
    # ------------------------------------------------------------------
    op.add_column(
        "subscriptions",
        sa.Column("plan_id", sa.Text(), nullable=True),
        schema="auth",
    )
    op.create_foreign_key(
        "fk_subscriptions_plan_id",
        source_table="subscriptions",
        referent_table="plans",
        local_cols=["plan_id"],
        remote_cols=["id"],
        source_schema="auth",
        referent_schema="billing",
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_subscriptions_plan_id",
        "subscriptions",
        schema="auth",
        type_="foreignkey",
    )
    op.drop_column("subscriptions", "plan_id", schema="auth")
    op.drop_table("plans", schema="billing")
    op.execute("DROP SCHEMA IF EXISTS billing")
