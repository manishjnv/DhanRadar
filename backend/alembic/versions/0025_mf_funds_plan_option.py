"""mf_funds: add plan_type and option_type columns (B67 Task 3).

Parsed from the AMFI scheme name at nightly upsert time (nav_daily_fetch).
Both columns are nullable — legacy schemes whose names predate the
Direct/Regular bifurcation (SEBI 2013 circular) will have NULL.

Revision ID: 0025
Revises: 0024
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mf_funds",
        sa.Column("plan_type", sa.String(10), nullable=True),
        schema="mf",
    )
    op.add_column(
        "mf_funds",
        sa.Column("option_type", sa.String(20), nullable=True),
        schema="mf",
    )


def downgrade() -> None:
    op.drop_column("mf_funds", "option_type", schema="mf")
    op.drop_column("mf_funds", "plan_type", schema="mf")
