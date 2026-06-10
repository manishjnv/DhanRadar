"""news — news schema + news_items table (B56).

Stores admin-curated headline metadata only (title, source, canonical_url,
published_at, category).  Article body/excerpt is never stored (copyright +
SEBI compliance).  Mirrors the mood (0007) / education (0015) own-schema
pattern; downgrade drops the schema CASCADE.

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS news")

    op.create_table(
        "news_items",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("scope", sa.Text(), nullable=False, server_default="market"),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "provenance_source",
            sa.Text(),
            nullable=False,
            server_default="admin_curated",
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("canonical_url", name="uq_news_items_canonical_url"),
        schema="news",
    )

    op.create_index(
        "ix_news_scope_pub",
        "news_items",
        ["scope", "published_at"],
        schema="news",
    )
    op.create_index(
        "ix_news_active",
        "news_items",
        ["is_active"],
        schema="news",
    )


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS news CASCADE")
