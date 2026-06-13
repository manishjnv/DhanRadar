"""mf_funds cohort-key indexes — category + sebi_category (B66-f1 pt2 / B58-f3).

The peer-cohort builder (``tasks/mf._build_cohort_context``) groups peers with a
``WHERE <grouping_col> IN (:categories)`` lookup on ``mf.mf_funds``. That column
is unindexed, so the lookup is a sequential scan (B58-f3) — trivial at ~14k funds
today, but it grows with the universe (ETF / debt / index expansion).

This adds a btree index on BOTH candidate grouping columns:
  * ``category``      — the v1.1 ACTIVE grouping key (closes B58-f3).
  * ``sebi_category`` — the B66-f1 pt2 rewire grouping key (validated canonical
    leaf). NULL legacy-umbrella rows are simply absent from the btree; a partial
    index is unnecessary at this size.

Index only; no data or column change (``sebi_category`` already exists since
0004). Reversible downgrade drops both indexes.

Revision ID: 0022
Revises: 0021
Create Date: 2026-06-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_mf_funds_category", "mf_funds", ["category"], unique=False, schema="mf"
    )
    op.create_index(
        "ix_mf_funds_sebi_category",
        "mf_funds",
        ["sebi_category"],
        unique=False,
        schema="mf",
    )


def downgrade() -> None:
    op.drop_index("ix_mf_funds_sebi_category", table_name="mf_funds", schema="mf")
    op.drop_index("ix_mf_funds_category", table_name="mf_funds", schema="mf")
