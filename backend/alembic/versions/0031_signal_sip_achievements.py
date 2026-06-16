"""signal: sip_day + earned_achievements on signal_rules; mf_sip_transactions table.

Revision ID: 0031
Revises: 0030
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # mf schema SIP transaction log (populated by CAS pipeline)
    op.create_table(
        "mf_sip_transactions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "portfolio_id",
            UUID(as_uuid=True),
            sa.ForeignKey("mf.mf_portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("txn_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        schema="mf",
    )
    op.create_index(
        "ix_mf_sip_transactions_portfolio",
        "mf_sip_transactions",
        ["portfolio_id"],
        schema="mf",
    )
    op.create_index(
        "ix_mf_sip_transactions_user",
        "mf_sip_transactions",
        ["user_id"],
        schema="mf",
    )

    # signal_rules: SIP day + earned achievements
    op.add_column(
        "signal_rules",
        sa.Column(
            "sip_day",
            sa.SmallInteger,
            nullable=True,
        ),
        schema="signal",
    )
    op.create_check_constraint(
        "ck_signal_rules_sip_day",
        "signal_rules",
        "sip_day IS NULL OR (sip_day BETWEEN 1 AND 31)",
        schema="signal",
    )
    op.add_column(
        "signal_rules",
        sa.Column(
            "earned_achievements",
            ARRAY(sa.Text),
            nullable=False,
            server_default="{}",
        ),
        schema="signal",
    )


def downgrade() -> None:
    op.drop_column("signal_rules", "earned_achievements", schema="signal")
    op.drop_constraint("ck_signal_rules_sip_day", "signal_rules", schema="signal")
    op.drop_column("signal_rules", "sip_day", schema="signal")
    op.drop_index("ix_mf_sip_transactions_user", table_name="mf_sip_transactions", schema="mf")
    op.drop_index("ix_mf_sip_transactions_portfolio", table_name="mf_sip_transactions", schema="mf")
    op.drop_table("mf_sip_transactions", schema="mf")
