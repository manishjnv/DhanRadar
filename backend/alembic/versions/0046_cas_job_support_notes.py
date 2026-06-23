"""mf.mf_cas_jobs.support_notes: admin annotation field for failed CAS jobs.

Adds a NULLABLE ``support_notes TEXT`` column to ``mf.mf_cas_jobs`` so an
operator can annotate a failed CAS-upload job from the admin support view.
The column is admin-internal — it is never surfaced on a user-facing route.

Reversible: downgrade drops the column.

Revision ID: 0046
Revises: 0045
Create Date: 2026-06-23
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0046"
down_revision: str | None = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mf_cas_jobs",
        sa.Column("support_notes", sa.Text(), nullable=True),
        schema="mf",
    )


def downgrade() -> None:
    op.drop_column("mf_cas_jobs", "support_notes", schema="mf")
