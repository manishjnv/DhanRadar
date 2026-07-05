"""Market-wide confidence band + signals on `mf.mf_fund_ranks`
(FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §10.1, §17 W2).

Every browsed fund gets what only held funds have today: a confidence band, the
engine's named confidence-quality factors, and the contributing/contradicting
signal words. The scoring bridge already computes all of this per fund inside
`compute_market_ranks` (`score_fund()`) — this migration only adds the columns
to PERSIST it; `verb_label` (already a column) is unchanged.

`confidence_factors` stores exactly the engine's `ScoringResult.confidence_factors`
shape (string keys → "high"/"medium"/"low" bands; today: consistency/recency/
volatility/data_coverage — the same confidence-quality dict already rendered for
held funds via `FactorStrengthBar`/`WhyThisLabelPanel`). It is NOT a per-axis
(quality/valuation/momentum/risk/trend) score band — the engine does not compute
or expose one; see the accompanying report for that finding. No numeric
(`unified_score`/`confidence` float) is ever added here (non-neg #2).

Additive + reversible.

Revision ID: 0064
Revises: 0063
Create Date: 2026-07-05
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0064"
down_revision: str | None = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mf_fund_ranks",
        sa.Column("confidence_band", sa.Text(), nullable=True),
        schema="mf",
    )
    op.add_column(
        "mf_fund_ranks",
        sa.Column("confidence_factors", postgresql.JSONB(), nullable=True),
        schema="mf",
    )
    op.add_column(
        "mf_fund_ranks",
        sa.Column("contributing_signals", postgresql.JSONB(), nullable=True),
        schema="mf",
    )
    op.add_column(
        "mf_fund_ranks",
        sa.Column("contradicting_signals", postgresql.JSONB(), nullable=True),
        schema="mf",
    )


def downgrade() -> None:
    op.drop_column("mf_fund_ranks", "contradicting_signals", schema="mf")
    op.drop_column("mf_fund_ranks", "contributing_signals", schema="mf")
    op.drop_column("mf_fund_ranks", "confidence_factors", schema="mf")
    op.drop_column("mf_fund_ranks", "confidence_band", schema="mf")
