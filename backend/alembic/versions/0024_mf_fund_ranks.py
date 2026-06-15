"""mf_fund_ranks: market-wide per-category rank table.

Pre-computed nightly after mf_metrics_refresh. Stores each fund's ordinal rank
within its sebi_category peer group so the report surface can show
"#1 of 30 in Large Cap" without any numeric score exposure (non-neg #2).

Revision ID: 0024
Revises: 0023
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mf_fund_ranks",
        sa.Column("isin", sa.Text(), nullable=False),
        sa.Column("sebi_category", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("total_in_cat", sa.Integer(), nullable=False),
        sa.Column("verb_label", sa.Text(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["isin"],
            ["mf.mf_funds.isin"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("isin", "as_of_date", name="pk_mf_fund_ranks"),
        schema="mf",
    )
    op.create_index(
        "ix_mf_fund_ranks_cat_date_rank",
        "mf_fund_ranks",
        ["sebi_category", "as_of_date", "rank"],
        schema="mf",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mf_fund_ranks_cat_date_rank",
        table_name="mf_fund_ranks",
        schema="mf",
    )
    op.drop_table("mf_fund_ranks", schema="mf")
