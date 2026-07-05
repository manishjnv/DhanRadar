"""mf.stock_cap_classification + mf.mf_category_flows — W3 AMFI free-source
enrichment (2 of 3 candidate sources; source A, riskometer, was BLOCKED at
Phase A verification — see docs/project-state/DATA_SOURCES.md).

  - mf.stock_cap_classification ← mf_cap_classification_fetch
    (source_key 'amfi_cap_classification'). Half-yearly AMFI Large/Mid/Small
    Cap stock list. Stock-level (equity ISINs, INE... prefix) — no FK to
    mf_funds. Dedup key: (stock_isin, effective_period).
  - mf.mf_category_flows ← mf_category_flows_fetch
    (source_key 'amfi_category_flows'). Monthly category-wise mobilisation /
    redemption / net-flow, AMFI's raw SEBI category label stored verbatim.
    Dedup key: (period_month, scheme_category).

Both tables carry six-question provenance (source_url + run_id FK into
mf.ingestion_runs + fetched_at), per Data-Ingestion-Normalization §8.3/§8.6.
New tables in an existing schema auto-inherit `dhanradar_app` privileges via
the ALTER DEFAULT PRIVILEGES set in migration 0052 — no per-table grants
needed here.

Additive + reversible.

Revision ID: 0064
Revises: 0063
Create Date: 2026-07-05
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0064"
down_revision: str | None = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # stock_cap_classification: half-yearly Large/Mid/Small Cap stock list.
    op.create_table(
        "stock_cap_classification",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("stock_isin", sa.Text(), nullable=False),
        sa.Column("stock_name", sa.Text(), nullable=False),
        sa.Column("cap_class", sa.Text(), nullable=False),
        sa.Column("avg_market_cap_cr", sa.Numeric(16, 2), nullable=True),
        sa.Column("effective_period", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "stock_isin", "effective_period", name="uq_stock_cap_classification_isin_period"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["mf.ingestion_runs.run_id"],
            name="fk_stock_cap_classification_run_id",
        ),
        sa.CheckConstraint(
            "cap_class IN ('Large Cap', 'Mid Cap', 'Small Cap')",
            name="ck_stock_cap_classification_cap_class",
        ),
        schema="mf",
    )
    op.create_index(
        "ix_stock_cap_classification_period",
        "stock_cap_classification",
        ["effective_period"],
        schema="mf",
    )

    # mf_category_flows: monthly category-wise mobilisation/redemption/net-flow.
    op.create_table(
        "mf_category_flows",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("period_month", sa.Date(), nullable=False),
        sa.Column("scheme_category", sa.Text(), nullable=False),
        sa.Column("num_schemes", sa.Integer(), nullable=True),
        sa.Column("num_folios", sa.BigInteger(), nullable=True),
        sa.Column("funds_mobilized_cr", sa.Numeric(16, 2), nullable=True),
        sa.Column("redemption_cr", sa.Numeric(16, 2), nullable=True),
        sa.Column("net_flow_cr", sa.Numeric(16, 2), nullable=True),
        sa.Column("net_aum_cr", sa.Numeric(16, 2), nullable=True),
        sa.Column("avg_aum_cr", sa.Numeric(16, 2), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "period_month", "scheme_category", name="uq_mf_category_flows_month_category"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["mf.ingestion_runs.run_id"],
            name="fk_mf_category_flows_run_id",
        ),
        schema="mf",
    )
    op.create_index(
        "ix_mf_category_flows_period_month",
        "mf_category_flows",
        ["period_month"],
        schema="mf",
    )


def downgrade() -> None:
    op.drop_table("mf_category_flows", schema="mf")
    op.drop_table("stock_cap_classification", schema="mf")
