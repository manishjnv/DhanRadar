"""mf.manual_ingest_files — manual SEBI disclosure inbox (bot-blocked AMCs).

HDFC/SBI/ICICI-Pru/Kotak/Axis block the scraper (mf_constituents_fetch,
migration 0033/ADR-0033(a)); this is the human-supplied side-channel. Three
intake channels (admin upload, watched folder, email poller — dhanradar/mf/
manual_ingest.py + dhanradar/tasks/manual_ingest.py) share ONE table so the
admin UI has a single recent-files view regardless of how a file arrived.

sha256 is UNIQUE — the shared intake service dedups on it (a re-drop of the
same file across channels is a no-op, never re-parsed). uploaded_by is
nullable because 'folder' and 'email' channels have no authenticated actor.

Additive + reversible.

Revision ID: 0072
Revises: 0071
Create Date: 2026-07-06
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0072"
down_revision: str | None = "0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "manual_ingest_files",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column(
            "uploaded_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("auth.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("amc_detected", sa.Text(), nullable=True),
        sa.Column("period_detected", sa.Date(), nullable=True),
        sa.Column("rows_ingested", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "channel IN ('upload', 'folder', 'email')", name="ck_manual_ingest_files_channel"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'parsed', 'failed', 'duplicate', 'unsupported')",
            name="ck_manual_ingest_files_status",
        ),
        schema="mf",
    )
    op.create_index(
        "uq_mf_manual_ingest_files_sha256", "manual_ingest_files", ["sha256"], unique=True, schema="mf"
    )
    # Admin GET listing sorts by received_at desc (recent-files table).
    op.create_index(
        "ix_mf_manual_ingest_files_received_at",
        "manual_ingest_files",
        ["received_at"],
        schema="mf",
    )
    # Source-health "failed count" surfacing (Admin Ops alerts).
    op.create_index(
        "ix_mf_manual_ingest_files_status", "manual_ingest_files", ["status"], schema="mf"
    )


def downgrade() -> None:
    op.drop_index("ix_mf_manual_ingest_files_status", table_name="manual_ingest_files", schema="mf")
    op.drop_index(
        "ix_mf_manual_ingest_files_received_at", table_name="manual_ingest_files", schema="mf"
    )
    op.drop_index(
        "uq_mf_manual_ingest_files_sha256", table_name="manual_ingest_files", schema="mf"
    )
    op.drop_table("manual_ingest_files", schema="mf")
