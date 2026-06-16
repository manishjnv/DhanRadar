"""mf_funds: add launch_date, is_segregated columns + plan_type/is_segregated indexes
(MF Master DB Phase 1).

launch_date: proxy for fund inception — backfilled from min(nav_date) per ISIN.
is_segregated: derived from scheme_name at ingest; server_default FALSE so NOT NULL
  is safe on existing rows.

Revision ID: 0032
Revises: 0031
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mf_funds",
        sa.Column("launch_date", sa.Date(), nullable=True),
        schema="mf",
    )
    op.add_column(
        "mf_funds",
        sa.Column("is_segregated", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="mf",
    )
    op.create_index("ix_mf_funds_plan_type", "mf_funds", ["plan_type"], schema="mf")
    op.create_index("ix_mf_funds_is_segregated", "mf_funds", ["is_segregated"], schema="mf")


def downgrade() -> None:
    op.drop_index("ix_mf_funds_is_segregated", table_name="mf_funds", schema="mf")
    op.drop_index("ix_mf_funds_plan_type", table_name="mf_funds", schema="mf")
    op.drop_column("mf_funds", "is_segregated", schema="mf")
    op.drop_column("mf_funds", "launch_date", schema="mf")
