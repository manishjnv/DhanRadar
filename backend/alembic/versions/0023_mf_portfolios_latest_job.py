"""mf_portfolios: add latest_job_id for portfolio lifecycle (no re-upload required).

Stores the job_id of the last successfully processed CAS upload per portfolio.
Used by GET /mf/portfolio/latest so the frontend can navigate to the report
without the user supplying or re-uploading.  Also enables the daily portfolio
refresh task to rebuild reports from stored holdings + today's NAV.

Revision ID: 0023
Revises: 0022
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mf_portfolios",
        sa.Column("latest_job_id", sa.UUID(), nullable=True),
        schema="mf",
    )


def downgrade() -> None:
    op.drop_column("mf_portfolios", "latest_job_id", schema="mf")
