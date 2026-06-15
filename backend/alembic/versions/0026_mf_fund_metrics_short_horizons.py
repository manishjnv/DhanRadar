"""mf_fund_metrics: add return_3m_pct, return_6m_pct, return_5y_pct (Fund Explorer sort).

Revision ID: 0026
Revises: 0025
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mf_fund_metrics", sa.Column("return_3m_pct", sa.Numeric(8, 2), nullable=True), schema="mf")
    op.add_column("mf_fund_metrics", sa.Column("return_6m_pct", sa.Numeric(8, 2), nullable=True), schema="mf")
    op.add_column("mf_fund_metrics", sa.Column("return_5y_pct", sa.Numeric(8, 2), nullable=True), schema="mf")


def downgrade() -> None:
    op.drop_column("mf_fund_metrics", "return_5y_pct", schema="mf")
    op.drop_column("mf_fund_metrics", "return_6m_pct", schema="mf")
    op.drop_column("mf_fund_metrics", "return_3m_pct", schema="mf")
