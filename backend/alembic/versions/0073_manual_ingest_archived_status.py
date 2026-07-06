"""mf.manual_ingest_files — add 'archived' status (PDF accept-and-archive).

PDFs are now accepted by the manual disclosure inbox but never parsed (the
SEBI parser is xlsx-only, contract §2) — the parse task marks them
'archived' immediately: file kept on disk, row kept, no fake parsing, no
OCR. The existing status CHECK constraint only allows
('pending','parsed','failed','duplicate','unsupported'), so 'archived' needs
a widened constraint. Additive + reversible (downgrade only works if no row
already carries 'archived' — same convention as any CHECK-narrowing rollback).

Revision ID: 0073
Revises: 0072
Create Date: 2026-07-06
"""

from __future__ import annotations

from alembic import op

revision: str = "0073"
down_revision: str | None = "0072"
branch_labels = None
depends_on = None

_OLD_STATUSES = "'pending', 'parsed', 'failed', 'duplicate', 'unsupported'"
_NEW_STATUSES = "'pending', 'parsed', 'failed', 'duplicate', 'unsupported', 'archived'"


def upgrade() -> None:
    op.drop_constraint(
        "ck_manual_ingest_files_status", "manual_ingest_files", schema="mf", type_="check"
    )
    op.create_check_constraint(
        "ck_manual_ingest_files_status",
        "manual_ingest_files",
        f"status IN ({_NEW_STATUSES})",
        schema="mf",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_manual_ingest_files_status", "manual_ingest_files", schema="mf", type_="check"
    )
    op.create_check_constraint(
        "ck_manual_ingest_files_status",
        "manual_ingest_files",
        f"status IN ({_OLD_STATUSES})",
        schema="mf",
    )
