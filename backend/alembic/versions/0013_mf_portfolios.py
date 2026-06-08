"""mf_portfolios — named portfolio entity + thread portfolio_id through MF tables.

Introduces ``mf.mf_portfolios`` so Plus users can hold multiple named portfolios
and Free users are capped at one.  All existing implicit (user-scoped) data is
backfilled into a per-user 'Default' portfolio before any NOT NULL constraint is
applied.

Steps (data-preserving — read the inline comments):
  (a) create mf_portfolios
  (b) add nullable portfolio_id FK to the 5 mf tables
  (c) backfill one 'Default' portfolio per distinct user; UPDATE all 5 tables
  (d) ALTER portfolio_id NOT NULL on 4 tables (mf_cas_jobs stays nullable)
  (e) drop old user_id-based UQs (same names); recreate with portfolio_id instead

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID  # noqa: N814

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID = PG_UUID(as_uuid=True)
_GEN = sa.text("gen_random_uuid()")


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # (a) Create mf_portfolios
    # -------------------------------------------------------------------------
    op.create_table(
        "mf_portfolios",
        sa.Column("id", _UUID, primary_key=True, server_default=_GEN, nullable=False),
        sa.Column(
            "user_id",
            _UUID,
            sa.ForeignKey("auth.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="mf",
    )
    op.create_index("ix_mf_portfolios_user", "mf_portfolios", ["user_id"], schema="mf")

    # -------------------------------------------------------------------------
    # (b) Add nullable portfolio_id to the 5 tables
    # -------------------------------------------------------------------------
    for table in (
        "mf_user_holdings",
        "mf_portfolio_snapshots",
        "mf_user_fund_score_history",
        "user_fund_scores",
        "mf_cas_jobs",
    ):
        op.add_column(
            table,
            sa.Column(
                "portfolio_id",
                _UUID,
                sa.ForeignKey("mf.mf_portfolios.id", ondelete="CASCADE"),
                nullable=True,
            ),
            schema="mf",
        )

    # -------------------------------------------------------------------------
    # (c) Backfill: one 'Default' portfolio per distinct user across ALL 5 tables,
    #     then UPDATE each table so portfolio_id points to it.
    # -------------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO mf.mf_portfolios (user_id, name)
        SELECT DISTINCT user_id, 'Default' FROM (
          SELECT user_id FROM mf.mf_user_holdings
          UNION SELECT user_id FROM mf.mf_portfolio_snapshots
          UNION SELECT user_id FROM mf.mf_user_fund_score_history
          UNION SELECT user_id FROM mf.user_fund_scores
          UNION SELECT user_id FROM mf.mf_cas_jobs
        ) u
        """
    )

    for table in (
        "mf_user_holdings",
        "mf_portfolio_snapshots",
        "mf_user_fund_score_history",
        "user_fund_scores",
        "mf_cas_jobs",
    ):
        op.execute(
            f"""
            UPDATE mf.{table} t
            SET portfolio_id = p.id
            FROM mf.mf_portfolios p
            WHERE p.user_id = t.user_id
            """
        )

    # -------------------------------------------------------------------------
    # (d) Set NOT NULL on 4 tables; mf_cas_jobs stays nullable.
    # -------------------------------------------------------------------------
    for table in (
        "mf_user_holdings",
        "mf_portfolio_snapshots",
        "mf_user_fund_score_history",
        "user_fund_scores",
    ):
        op.alter_column(table, "portfolio_id", nullable=False, schema="mf")

    # -------------------------------------------------------------------------
    # (e) Replace old UQs (same names) — drop old, create new with portfolio_id.
    # -------------------------------------------------------------------------
    op.drop_constraint("uq_mf_holding", "mf_user_holdings", schema="mf", type_="unique")
    op.create_unique_constraint(
        "uq_mf_holding",
        "mf_user_holdings",
        ["portfolio_id", "isin", "folio_number"],
        schema="mf",
    )

    op.drop_constraint("uq_mf_snapshot", "mf_portfolio_snapshots", schema="mf", type_="unique")
    op.create_unique_constraint(
        "uq_mf_snapshot",
        "mf_portfolio_snapshots",
        ["portfolio_id", "snapshot_date"],
        schema="mf",
    )

    op.drop_constraint(
        "uq_mf_score_history", "mf_user_fund_score_history", schema="mf", type_="unique"
    )
    op.create_unique_constraint(
        "uq_mf_score_history",
        "mf_user_fund_score_history",
        ["portfolio_id", "isin", "snapshot_date"],
        schema="mf",
    )

    op.drop_constraint("uq_user_fund_score", "user_fund_scores", schema="mf", type_="unique")
    op.create_unique_constraint(
        "uq_user_fund_score",
        "user_fund_scores",
        ["portfolio_id", "isin"],
        schema="mf",
    )


def downgrade() -> None:
    # Reverse (e): drop new UQs, recreate old user_id-based ones (same names).
    op.drop_constraint("uq_mf_holding", "mf_user_holdings", schema="mf", type_="unique")
    op.create_unique_constraint(
        "uq_mf_holding", "mf_user_holdings", ["user_id", "isin", "folio_number"], schema="mf"
    )

    op.drop_constraint("uq_mf_snapshot", "mf_portfolio_snapshots", schema="mf", type_="unique")
    op.create_unique_constraint(
        "uq_mf_snapshot", "mf_portfolio_snapshots", ["user_id", "snapshot_date"], schema="mf"
    )

    op.drop_constraint(
        "uq_mf_score_history", "mf_user_fund_score_history", schema="mf", type_="unique"
    )
    op.create_unique_constraint(
        "uq_mf_score_history",
        "mf_user_fund_score_history",
        ["user_id", "isin", "snapshot_date"],
        schema="mf",
    )

    op.drop_constraint("uq_user_fund_score", "user_fund_scores", schema="mf", type_="unique")
    op.create_unique_constraint(
        "uq_user_fund_score", "user_fund_scores", ["user_id", "isin"], schema="mf"
    )

    # Reverse (b): drop portfolio_id from all 5 tables.
    for table in (
        "mf_user_holdings",
        "mf_portfolio_snapshots",
        "mf_user_fund_score_history",
        "user_fund_scores",
        "mf_cas_jobs",
    ):
        op.drop_column(table, "portfolio_id", schema="mf")

    # Reverse (a): drop mf_portfolios.
    op.drop_index("ix_mf_portfolios_user", table_name="mf_portfolios", schema="mf")
    op.drop_table("mf_portfolios", schema="mf")
