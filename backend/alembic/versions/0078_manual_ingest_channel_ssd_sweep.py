"""Widen ck_manual_ingest_files_channel to allow 'amfi_ssd_sweep' (PR #569 follow-up).

PR #569 shipped `amfi_ssd_sweep` writing ledger rows with channel='amfi_ssd_sweep'
but no migration widening this CHECK constraint — every real SSD hit raised a
CheckViolation that intake_file()'s duplicate-race handler swallowed, so the sweep
ran green while ingesting NOTHING (found by the first bounded prod sweep's
verification, 2026-07-12: 16 real SSDs, ingested=0, ledger empty; RCA G10).

Additive + reversible. Downgrade restores the old constraint — safe only if no
'amfi_ssd_sweep' rows exist (delete them first if downgrading past a sweep).

Revision ID: 0078
Revises: 0077
Create Date: 2026-07-12
"""

from __future__ import annotations

from alembic import op

revision: str = "0078"
down_revision: str | None = "0077"
branch_labels = None
depends_on = None

_NAME = "ck_manual_ingest_files_channel"
_TABLE = "manual_ingest_files"
_OLD = "channel IN ('upload', 'folder', 'email')"
_NEW = "channel IN ('upload', 'folder', 'email', 'amfi_ssd_sweep')"


def upgrade() -> None:
    op.drop_constraint(_NAME, _TABLE, schema="mf", type_="check")
    op.create_check_constraint(_NAME, _TABLE, _NEW, schema="mf")


def downgrade() -> None:
    op.drop_constraint(_NAME, _TABLE, schema="mf", type_="check")
    op.create_check_constraint(_NAME, _TABLE, _OLD, schema="mf")
