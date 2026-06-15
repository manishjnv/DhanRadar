"""signal_history: per-date trust engine backfill table.

Revision ID: 0030
Revises: 0029
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("signal_state", sa.String(20), nullable=False),
        sa.Column("nifty_close", sa.Numeric(10, 2), nullable=False),
        sa.Column("vix_close", sa.Numeric(6, 2), nullable=False),
        sa.Column("ad_ratio_proxy", sa.Numeric(5, 3), nullable=False),
        sa.Column("outcome_pct_90d", sa.Numeric(8, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("date", name="uq_signal_history_date"),
        schema="signal",
    )
    op.create_index(
        "ix_signal_history_date",
        "signal_history",
        ["date"],
        schema="signal",
    )


def downgrade() -> None:
    op.drop_index("ix_signal_history_date", table_name="signal_history", schema="signal")
    op.drop_table("signal_history", schema="signal")
