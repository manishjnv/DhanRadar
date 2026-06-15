"""signal_journal: update decision enum + add signal_state, fomo_avoided, premature columns.

Revision ID: 0028
Revises: 0027
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Replace Phase-1 placeholder decision enum with Phase-2 values
    op.execute(
        "ALTER TABLE signal.signal_journal "
        "DROP CONSTRAINT IF EXISTS ck_signal_journal_decision"
    )
    op.execute(
        "ALTER TABLE signal.signal_journal "
        "ADD CONSTRAINT ck_signal_journal_decision "
        "CHECK (decision IN ('deployed', 'watched', 'skipped'))"
    )

    # Add columns needed for behaviour analytics
    op.add_column(
        "signal_journal",
        sa.Column("signal_state", sa.String(20), nullable=True),
        schema="signal",
    )
    op.add_column(
        "signal_journal",
        sa.Column("fomo_avoided", sa.Boolean, nullable=True),
        schema="signal",
    )
    op.add_column(
        "signal_journal",
        sa.Column("premature", sa.Boolean, nullable=True),
        schema="signal",
    )


def downgrade() -> None:
    op.drop_column("signal_journal", "premature", schema="signal")
    op.drop_column("signal_journal", "fomo_avoided", schema="signal")
    op.drop_column("signal_journal", "signal_state", schema="signal")

    op.execute(
        "ALTER TABLE signal.signal_journal "
        "DROP CONSTRAINT IF EXISTS ck_signal_journal_decision"
    )
    op.execute(
        "ALTER TABLE signal.signal_journal "
        "ADD CONSTRAINT ck_signal_journal_decision "
        "CHECK (decision IN ('deployed', 'held', 'missed', 'partial'))"
    )
