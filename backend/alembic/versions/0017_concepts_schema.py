"""concepts — concepts schema + concept_explainers table (C1).

Static, evergreen EDUCATIONAL explainers for core investing concepts. No FK / no
personal data (pure reference content — DPDP-irrelevant). The table ships EMPTY;
the authored content lives in `dhanradar/concepts/content.py` (ci_guards-scanned)
and is loaded by the idempotent `python -m dhanradar.concepts.seed` command.
Mirrors the education (0015) own-schema pattern; downgrade drops the schema
CASCADE so a future concepts.* object does not block a clean rollback.

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS concepts")

    op.create_table(
        "concept_explainers",
        sa.Column("slug", sa.Text(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema="concepts",
    )
    op.create_index(
        "ix_concepts_category", "concept_explainers", ["category"], schema="concepts"
    )
    op.create_index(
        "ix_concepts_sort", "concept_explainers", ["sort_order"], schema="concepts"
    )


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS concepts CASCADE")
