"""mf_funds_category_index — index mf.mf_funds.category for cohort peer lookup (B58-f3).

The cohort builder (`tasks/mf.py::_build_cohort_context`) filters peers with
`MfFund.category.IN (...)` on every monthly rescore and every CAS upload. `category`
was unindexed, so that filter was a sequential scan over the full fund universe
(~10k+ rows) on a hot path. This adds a plain btree index on `mf.mf_funds.category`.

Set-membership (`IN`) on a low-cardinality text column benefits from a btree index
once the planner estimates the matched fraction is small — which holds here (a user's
holdings span a handful of categories out of ~40). The index is small and write-cheap
(category is written only by the monthly AMFI fund-master refresh, not the daily NAV
fetch), so there is no meaningful ingestion-side cost.

Reversible: downgrade drops the index. No data change.

Revision ID: 0022
Revises: 0021
Create Date: 2026-06-13
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "ix_mf_funds_category"


def upgrade() -> None:
    # IF NOT EXISTS keeps the migration idempotent/re-runnable on a box where a prior
    # manual index may already exist (the live KVM4 DB has occasionally drifted ahead
    # of the chain). Plain (non-CONCURRENT) create: it runs inside Alembic's
    # transaction and briefly takes a SHARE lock on mf_funds. mf_funds is small and
    # written only by the monthly refresh, so the lock window is negligible — no need
    # for the CONCURRENTLY/autocommit dance that a large hot table would require.
    op.create_index(
        _INDEX,
        "mf_funds",
        ["category"],
        unique=False,
        schema="mf",
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="mf_funds", schema="mf", if_exists=True)
