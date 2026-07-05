"""mf_fund_metrics — rolling-3Y columns (W2-B1, plan §10.5) — HOTFIX re-issue.

The original 0065_mf_rolling_3y_metrics was LOST during PR #470's rebase: a concurrent
session's #469 claimed revision id 0065 first (0065_amfi_cap_classification_category_flows),
and the resolving builder mistook that pre-existing head for its own migration — #470 merged
model columns with no migration. Prod fund endpoints 500'd (UndefinedColumnError) for a few
minutes on 2026-07-05 until the columns were added by emergency DDL (see docs/rca/README.md).

IDEMPOTENT on purpose: prod already has these columns from the emergency DDL, so this
migration must no-op there while still creating them everywhere else (CI, fresh installs).

Revision ID: 0066
Revises: 0065
Create Date: 2026-07-05
"""

from __future__ import annotations

from alembic import op

revision: str = "0066"
down_revision: str | None = "0065"
branch_labels = None
depends_on = None

_COLUMNS = (
    "rolling_3y_avg_pct",
    "rolling_3y_min_pct",
    "rolling_3y_max_pct",
    "rolling_3y_pct_positive",
)


def upgrade() -> None:
    for col in _COLUMNS:
        op.execute(
            f"ALTER TABLE mf.mf_fund_metrics ADD COLUMN IF NOT EXISTS {col} double precision"
        )


def downgrade() -> None:
    for col in _COLUMNS:
        op.execute(f"ALTER TABLE mf.mf_fund_metrics DROP COLUMN IF EXISTS {col}")
