"""user_fund_scores_flags — persist the engine's diagnostic flags for G10 show-your-working.

The rating engine already computes a `flags` list per score
(`partial_coverage / stale / low_liquidity / provisional_model / insufficient_data`)
but only the latest in-Redis result carried them; the persisted `user_fund_scores`
row dropped them. The transparency surface (PU2/G10) therefore had to *re-derive*
data-quality drivers from confidence_band + NAV age alone, which is lossy.

This adds a nullable `flags` JSONB column (default empty list) so the write path can
persist the engine's own flags verbatim, and the transparency surface can render
honest, axis-aware "why" + "what would change this" guidance from them.

COMPLIANCE: `flags` are qualitative string tags only — never a numeric score, weight,
or confidence float. They are safe to persist and (selectively) surface (non-neg #2
preserved). `unified_score` remains the only tier-gated numeric and is untouched here.

Reversible: downgrade drops the column. Existing rows backfill to NULL (read as []).

Revision ID: 0023
Revises: 0022
Create Date: 2026-06-13
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_fund_scores",
        sa.Column(
            "flags",
            JSONB,
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        schema="mf",
    )


def downgrade() -> None:
    op.drop_column("user_fund_scores", "flags", schema="mf")
