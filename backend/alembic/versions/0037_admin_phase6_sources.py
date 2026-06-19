"""admin_phase6_sources: expense_ratio_history, sebi_circulars, macro_indicators.

Backing tables for the three Phase-6 planned sources that have no existing canonical
home (Admin.md §18 step 6):
  - mf.expense_ratio_history  ← mf_expense_ratio_fetch  (source 'amc_expense_ratios')
  - mf.sebi_circulars         ← sebi_circulars_fetch     (source 'sebi_circulars')
  - mf.macro_indicators       ← macro_data_refresh       (source 'rbi_dbie')

The other two Phase-6 sources reuse existing tables created in 0035:
  - mf_scheme_master_refresh  → upserts mf.mf_funds
  - mf_fund_manager_fetch     → mf.fund_manager_history

All three new tables carry six-question provenance (source + run_id FK into
mf.ingestion_runs + ingested_at) and a write-time dedup unique key, per the
Data-Ingestion-Normalization invariants (§8.3, §8.6).

Revision ID: 0037
Revises: 0036
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # expense_ratio_history: TER per scheme over time; dedup on (isin, effective_date).
    op.create_table(
        "expense_ratio_history",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("isin", sa.Text(), nullable=False),
        sa.Column("ter_pct", sa.Numeric(6, 3), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("isin", "effective_date", name="uq_expense_ratio_isin_date"),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["mf.ingestion_runs.run_id"],
            name="fk_expense_ratio_history_run_id",
        ),
        sa.CheckConstraint(
            "ter_pct >= 0 AND ter_pct <= 10",
            name="ck_expense_ratio_ter_range",
        ),
        schema="mf",
    )
    op.create_index(
        "ix_mf_expense_ratio_isin_date",
        "expense_ratio_history",
        ["isin", "effective_date"],
        schema="mf",
    )

    # sebi_circulars: regulatory circular metadata; dedup on circular_number.
    op.create_table(
        "sebi_circulars",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("circular_number", sa.Text(), nullable=False),
        sa.Column("circular_date", sa.Date(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("circular_number", name="uq_sebi_circular_number"),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["mf.ingestion_runs.run_id"],
            name="fk_sebi_circulars_run_id",
        ),
        schema="mf",
    )
    op.create_index(
        "ix_mf_sebi_circulars_date",
        "sebi_circulars",
        ["circular_date"],
        schema="mf",
    )

    # macro_indicators: point-in-time RBI DBIE values; dedup on (indicator_key, as_of_date).
    op.create_table(
        "macro_indicators",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("indicator_key", sa.Text(), nullable=False),
        sa.Column("indicator_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "indicator_key", "as_of_date", name="uq_macro_indicator_key_date"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["mf.ingestion_runs.run_id"],
            name="fk_macro_indicators_run_id",
        ),
        schema="mf",
    )
    op.create_index(
        "ix_mf_macro_indicators_key_date",
        "macro_indicators",
        ["indicator_key", "as_of_date"],
        schema="mf",
    )


def downgrade() -> None:
    op.drop_table("macro_indicators", schema="mf")
    op.drop_table("sebi_circulars", schema="mf")
    op.drop_table("expense_ratio_history", schema="mf")
