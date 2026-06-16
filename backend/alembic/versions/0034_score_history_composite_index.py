"""score_history — composite index (user_id, isin, scored_at DESC).

Speeds up per-user label-history queries that filter by user_id + isin
and order by scored_at descending (B56-f3).

Revision ID: 0034
Revises: 0033
Create Date: 2026-06-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_mf_score_history_user_isin_scored_at "
        "ON mf.mf_user_fund_score_history (user_id, isin, scored_at DESC)"
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS mf.ix_mf_score_history_user_isin_scored_at"
    )
