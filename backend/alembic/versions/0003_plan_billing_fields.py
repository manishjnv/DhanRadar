"""plan_billing_fields — add billing.plans.razorpay_plan_id + total_count.

Additive + reversible (B7/B8). Both nullable; no back-fill. Until a plan row has
BOTH set, /billing/checkout refuses (fail-safe: it is impossible to create a
charge with a wrong/missing Razorpay plan id or cycle count). The real values
are seeded once the Razorpay dashboard plans exist (data-only, no code change).

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-05
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column("razorpay_plan_id", sa.Text(), nullable=True),
        schema="billing",
    )
    op.create_unique_constraint(
        "uq_plans_razorpay_plan_id",
        "plans",
        ["razorpay_plan_id"],
        schema="billing",
    )
    op.add_column(
        "plans",
        sa.Column("total_count", sa.Integer(), nullable=True),
        schema="billing",
    )


def downgrade() -> None:
    op.drop_column("plans", "total_count", schema="billing")
    op.drop_constraint(
        "uq_plans_razorpay_plan_id", "plans", schema="billing", type_="unique"
    )
    op.drop_column("plans", "razorpay_plan_id", schema="billing")
