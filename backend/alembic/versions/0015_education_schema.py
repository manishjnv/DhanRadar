"""education — education schema + tax_education_articles table (G8).

Static, FY-aware EDUCATIONAL content on Indian MF taxation. No FK / no personal
data (pure reference content — DPDP-irrelevant). The table ships EMPTY; the
authored content lives in `dhanradar/education/content.py` (ci_guards-scanned) and
is loaded by the idempotent `python -m dhanradar.education.seed` command. Mirrors
the mood (0007) / audit (0014) own-schema pattern; downgrade drops the schema
CASCADE so a future education.* object does not block a clean rollback.

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS education")

    op.create_table(
        "tax_education_articles",
        sa.Column("slug", sa.Text(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("fy_label", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.Column("fy_relevant_from", sa.Date(), nullable=True),
        sa.Column("fy_relevant_to", sa.Date(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema="education",
    )
    op.create_index(
        "ix_tax_edu_category", "tax_education_articles", ["category"], schema="education"
    )
    op.create_index(
        "ix_tax_edu_sort", "tax_education_articles", ["sort_order"], schema="education"
    )


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS education CASCADE")
