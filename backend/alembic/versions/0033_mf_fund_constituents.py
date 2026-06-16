"""mf_fund_constituents: per-scheme top-10 holding constituents table
(ADR-0033(a) SEBI Monthly Portfolio Disclosure Scraper).

Stores constituent rows sourced from SEBI-format XLSX/CSV published by
top-10 AMCs (~75-80% market AUM). Coverage gap for the remaining AMCs is
a logged gap, never imputed (§8.4).

Provenance: source_amc + as_of_month + ingested_at on every row
(six-question rule).

Revision ID: 0033
Revises: 0032
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mf_fund_constituents",
        sa.Column("isin", sa.Text(), nullable=False),
        sa.Column("constituent_name", sa.Text(), nullable=False),
        sa.Column("as_of_month", sa.Date(), nullable=False),
        sa.Column("constituent_isin", sa.Text(), nullable=True),
        sa.Column("sector", sa.Text(), nullable=True),
        sa.Column("rating", sa.Text(), nullable=True),
        sa.Column("weight_pct", sa.Numeric(6, 3), nullable=True),
        sa.Column("market_value_cr", sa.Numeric(14, 2), nullable=True),
        sa.Column("source_amc", sa.Text(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("isin", "constituent_name", "as_of_month"),
        schema="mf",
    )
    op.create_index(
        "ix_mf_fund_constituents_isin_month",
        "mf_fund_constituents",
        ["isin", "as_of_month"],
        schema="mf",
    )
    op.create_index(
        "ix_mf_fund_constituents_constituent_isin",
        "mf_fund_constituents",
        ["constituent_isin"],
        schema="mf",
    )


def downgrade() -> None:
    op.drop_table("mf_fund_constituents", schema="mf")
