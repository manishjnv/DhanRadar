"""score_history — per-fund label history + portfolio snapshot writer.

Creates ``mf.mf_user_fund_score_history`` to retain label + band over time
(one row per user/isin/date).  NO numeric column — zero numeric-leak surface.
The MfPortfolioSnapshot table already exists (0004); this migration only adds
the history table.

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mf_user_fund_score_history",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("auth.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("isin", sa.Text(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("verb_label", sa.Text(), nullable=False),
        sa.Column("confidence_band", sa.Text(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "scored_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "user_id",
            "isin",
            "snapshot_date",
            name="uq_mf_score_history",
        ),
        schema="mf",
    )
    op.create_index(
        "ix_mf_score_history_user_date",
        "mf_user_fund_score_history",
        ["user_id", "snapshot_date"],
        schema="mf",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mf_score_history_user_date",
        table_name="mf_user_fund_score_history",
        schema="mf",
    )
    op.drop_table("mf_user_fund_score_history", schema="mf")
