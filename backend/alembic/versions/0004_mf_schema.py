"""mf_schema — Mutual Fund module schema (Phase 5).

Creates the `mf` schema + 6 tables (architecture Tier-C MF Module). `mf_nav_history`
is a TimescaleDB hypertable (1-month chunks); the `mf_nav_monthly_agg` continuous
aggregate lands with the AMFI NAV pipeline (it needs populated NAV data) — deferred,
not created here. The hypertable step is guarded on the timescaledb extension so the
migration also applies on a plain-Postgres box (it no-ops there); the CI test DB
builds tables from ORM metadata, not this migration.

Additive + reversible. user_id columns FK auth.users(id) ON DELETE CASCADE
(referential integrity only; the MF module never writes other modules' tables).

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-06
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)
_GEN = sa.text("gen_random_uuid()")


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS mf")

    op.create_table(
        "mf_funds",
        sa.Column("isin", sa.Text(), primary_key=True),
        sa.Column("amfi_code", sa.Text(), nullable=True),
        sa.Column("scheme_name", sa.Text(), nullable=False),
        sa.Column("amc_name", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("sub_category", sa.Text(), nullable=True),
        sa.Column("aum_crore", sa.Numeric(14, 2), nullable=True),
        sa.Column("expense_ratio_pct", sa.Numeric(6, 3), nullable=True),
        sa.Column("exit_load_pct", sa.Numeric(6, 3), nullable=True),
        sa.Column("exit_load_days", sa.Integer(), nullable=True),
        sa.Column("benchmark_index", sa.Text(), nullable=True),
        sa.Column("sebi_category", sa.Text(), nullable=True),
        sa.Column("risk_o_meter", sa.Text(), nullable=True),
        schema="mf",
    )
    op.create_index("ix_mf_funds_amfi", "mf_funds", ["amfi_code"], schema="mf")

    op.create_table(
        "mf_nav_history",
        sa.Column("isin", sa.Text(), primary_key=True),
        sa.Column("nav_date", sa.Date(), primary_key=True),
        sa.Column("nav", sa.Numeric(14, 4), nullable=False),
        sa.Column("source", sa.Text(), nullable=False, server_default="amfi"),
        sa.UniqueConstraint("isin", "nav_date", name="uq_mf_nav_isin_date"),
        schema="mf",
    )

    op.create_table(
        "mf_user_holdings",
        sa.Column("id", _UUID, primary_key=True, server_default=_GEN),
        sa.Column("user_id", _UUID, sa.ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("isin", sa.Text(), nullable=False),
        sa.Column("folio_number", sa.Text(), nullable=False),
        sa.Column("units", sa.Numeric(20, 4), nullable=False),
        sa.Column("avg_cost_nav", sa.Numeric(14, 4), nullable=True),
        sa.Column("invested_amount", sa.Numeric(16, 2), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="cas"),
        sa.Column("as_of_date", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "isin", "folio_number", name="uq_mf_holding"),
        schema="mf",
    )
    op.create_index("ix_mf_holdings_user", "mf_user_holdings", ["user_id"], schema="mf")
    op.create_index("ix_mf_holdings_isin", "mf_user_holdings", ["isin"], schema="mf")

    op.create_table(
        "mf_portfolio_snapshots",
        sa.Column("id", _UUID, primary_key=True, server_default=_GEN),
        sa.Column("user_id", _UUID, sa.ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("total_invested", sa.Numeric(16, 2), nullable=True),
        sa.Column("current_value", sa.Numeric(16, 2), nullable=True),
        sa.Column("xirr_pct", sa.Numeric(8, 2), nullable=True),
        sa.Column("category_allocation", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("overlap_matrix", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "snapshot_date", name="uq_mf_snapshot"),
        schema="mf",
    )

    op.create_table(
        "mf_cas_jobs",
        sa.Column("job_id", _UUID, primary_key=True, server_default=_GEN),
        sa.Column("user_id", _UUID, sa.ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_hash", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        schema="mf",
    )
    op.create_index("ix_mf_cas_jobs_user", "mf_cas_jobs", ["user_id"], schema="mf")

    op.create_table(
        "user_fund_scores",
        sa.Column("id", _UUID, primary_key=True, server_default=_GEN),
        sa.Column("user_id", _UUID, sa.ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("isin", sa.Text(), nullable=False),
        sa.Column("unified_score", sa.Integer(), nullable=True),
        sa.Column("confidence_band", sa.Text(), nullable=False),
        sa.Column("verb_label", sa.Text(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False, server_default="v1"),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "isin", name="uq_user_fund_score"),
        schema="mf",
    )
    op.create_index("ix_user_fund_scores_user", "user_fund_scores", ["user_id"], schema="mf")

    # TimescaleDB hypertable + continuous aggregate — guarded so a plain-Postgres
    # box (and the CI test DB) simply skips them.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
            PERFORM create_hypertable('mf.mf_nav_history', 'nav_date',
                                      chunk_time_interval => INTERVAL '1 month',
                                      if_not_exists => TRUE, migrate_data => TRUE);
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    for tbl in (
        "user_fund_scores", "mf_cas_jobs", "mf_portfolio_snapshots",
        "mf_user_holdings", "mf_nav_history", "mf_funds",
    ):
        op.drop_table(tbl, schema="mf")
    op.execute("DROP SCHEMA IF EXISTS mf")
