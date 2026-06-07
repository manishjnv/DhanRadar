"""engine_activation_unique — at most one ACTIVATED changelog row per model_version.

The B6/B28 scoring-activation gate writes an activated `rating_engine_changelog`
row when a model_version is activated. The application-level SELECT dup-guard has a
multi-worker TOCTOU race that could write two `activated=true` rows for one version
— an ambiguous, non-reproducible regulatory activation record. This partial-unique
index enforces the single-activation-record-per-version invariant atomically at the
DB level (a concurrent loser's INSERT is rejected → surfaced as 409). Many
`activated=false` rows per version are still allowed (proposed methodology changes).

Additive + reversible. Mirrors `uq_disclaimer_active_per_type` (migration 0008).

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-07
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX uq_engine_changelog_activated_per_version "
        "ON compliance.rating_engine_changelog (model_version) WHERE activated"
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS compliance.uq_engine_changelog_activated_per_version"
    )
