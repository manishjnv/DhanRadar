"""user_fund_scores composite (user_id, isin, scored_at DESC) index (B56-f3).

Adds `ix_user_fund_scores_user_isin_scored_at` on `mf.user_fund_scores
(user_id, isin, scored_at DESC)` so the dashboard's per-user latest-score read
path (lookup by user+isin, ordered by recency) doesn't degrade under real
load. Table is small today, so a plain (non-concurrent) `create_index` is
used — no other migration in this repo uses `postgresql_concurrently`, so
that pattern is not introduced here either. Mirrored in the SQLAlchemy model's
`__table_args__` (dhanradar/models/mf.py) so autogenerate stays in sync.

Additive + reversible.

Revision ID: 0084
Revises: 0083
Create Date: 2026-09-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0084"
down_revision: str | None = "0083"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_user_fund_scores_user_isin_scored_at",
        "user_fund_scores",
        ["user_id", "isin", sa.text("scored_at DESC")],
        schema="mf",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_fund_scores_user_isin_scored_at",
        table_name="user_fund_scores",
        schema="mf",
    )
