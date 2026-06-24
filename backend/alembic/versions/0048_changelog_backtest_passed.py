"""rating_engine_changelog.backtest_passed (PR-5 — backtest pass-gate outcome).

Adds a nullable boolean column recording the §8 backtest pass-gate outcome
asserted at scoring-version activation. Surfaced read-only on /admin/ai/versions.
NULL = not asserted (older rows / proposed-but-not-activated versions).

Additive + reversible. No backfill — existing rows keep NULL (honest "not
asserted").

Revision ID: 0048
Revises: 0047
Create Date: 2026-06-24
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0048"
down_revision: str | None = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rating_engine_changelog",
        sa.Column("backtest_passed", sa.Boolean(), nullable=True),
        schema="compliance",
    )


def downgrade() -> None:
    op.drop_column(
        "rating_engine_changelog",
        "backtest_passed",
        schema="compliance",
    )
