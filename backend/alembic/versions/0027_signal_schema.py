"""signal schema: signal_rules, signal_dip_fund, signal_deployments, signal_journal.

Revision ID: 0027
Revises: 0026
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS signal")

    op.create_table(
        "signal_rules",
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("nifty_threshold", sa.Numeric(6, 2), nullable=False),
        sa.Column("vix_threshold", sa.Numeric(6, 2), nullable=False),
        sa.Column("breadth_threshold", sa.Numeric(4, 3), nullable=False),
        sa.Column("deploy_ladder", JSONB, nullable=False),
        sa.Column("alerts_on", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="signal",
    )

    op.create_table(
        "signal_dip_fund",
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("balance", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "monthly_addition", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="signal",
    )

    op.create_table(
        "signal_deployments",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(14, 2)),
        sa.Column("signal_state", sa.String(20)),
        sa.Column("market_snapshot", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "signal_state IN ('triggered', 'watch', 'no_signal')",
            name="ck_signal_deployments_state",
        ),
        schema="signal",
    )
    op.create_index(
        "ix_signal_deployments_user_date",
        "signal_deployments",
        ["user_id", "date"],
        schema="signal",
    )

    op.create_table(
        "signal_journal",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("decision", sa.String(20)),
        sa.Column("amount", sa.Numeric(14, 2)),
        sa.Column("emotion", JSONB),
        sa.Column("notes", sa.Text),
        sa.Column("market_snapshot", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "decision IN ('deployed', 'held', 'missed', 'partial')",
            name="ck_signal_journal_decision",
        ),
        schema="signal",
    )
    op.create_index(
        "ix_signal_journal_user_date",
        "signal_journal",
        ["user_id", "date"],
        schema="signal",
    )


def downgrade() -> None:
    op.drop_index("ix_signal_journal_user_date", table_name="signal_journal", schema="signal")
    op.drop_table("signal_journal", schema="signal")
    op.drop_index(
        "ix_signal_deployments_user_date", table_name="signal_deployments", schema="signal"
    )
    op.drop_table("signal_deployments", schema="signal")
    op.drop_table("signal_dip_fund", schema="signal")
    op.drop_table("signal_rules", schema="signal")
    op.execute("DROP SCHEMA IF EXISTS signal")
