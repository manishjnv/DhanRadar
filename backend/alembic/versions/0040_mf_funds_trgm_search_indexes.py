"""mf_funds trigram search indexes — pg_trgm GIN on scheme_name + amc_name.

Enables typo-tolerant, fast fund search via the public GET /api/v1/mf/search
endpoint.  Two GIN trigram indexes on ``mf.mf_funds``:

  * ``ix_mf_funds_scheme_name_trgm`` — accelerates ILIKE and word_similarity
    queries on the primary search field (scheme_name).
  * ``ix_mf_funds_amc_name_trgm``    — accelerates the secondary AMC-name
    search path.

Both use ``gin_trgm_ops`` from the ``pg_trgm`` extension (already bundled with
PostgreSQL; CREATE EXTENSION IF NOT EXISTS is idempotent).

Index only; no schema or data change.  Reversible downgrade drops both indexes
in reverse order.

Revision ID: 0040
Revises: 0039
Create Date: 2026-06-21
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Ensure the pg_trgm extension is available.  Idempotent — safe to run
    # even if the extension was already enabled by a previous migration or the
    # database init script.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # GIN trigram index on scheme_name — primary search field.
    op.create_index(
        "ix_mf_funds_scheme_name_trgm",
        "mf_funds",
        ["scheme_name"],
        unique=False,
        schema="mf",
        postgresql_using="gin",
        postgresql_ops={"scheme_name": "gin_trgm_ops"},
    )

    # GIN trigram index on amc_name — secondary (AMC) search field.
    op.create_index(
        "ix_mf_funds_amc_name_trgm",
        "mf_funds",
        ["amc_name"],
        unique=False,
        schema="mf",
        postgresql_using="gin",
        postgresql_ops={"amc_name": "gin_trgm_ops"},
    )


def downgrade() -> None:
    # Drop in reverse creation order.
    op.drop_index("ix_mf_funds_amc_name_trgm", table_name="mf_funds", schema="mf")
    op.drop_index("ix_mf_funds_scheme_name_trgm", table_name="mf_funds", schema="mf")
    # NOTE: pg_trgm extension is intentionally NOT dropped here.  Dropping it
    # would CASCADE and remove any other GIN/GIST trgm indexes created outside
    # this migration, which is destructive and unexpected for a downgrade.
