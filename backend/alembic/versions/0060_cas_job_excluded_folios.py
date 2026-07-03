"""Per-folio ownership guard (2026-07-04 family-merge incident) — `excluded_folios` on
`mf.mf_cas_jobs`.

A consolidated statement can carry a DIFFERENT investor's folios (e.g. a household member
sharing one RTA email); the CAS pipeline now excludes a folio whose OWN PAN disagrees with the
uploader's stored `investor_pan` entirely (no ledger rows, no holdings, no checkpoints) and
counts it here so `GET /mf/upload/cas/{job}/status` can surface it to the client.

Revision ID: 0060
Revises: 0059
Create Date: 2026-07-04
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0060"
down_revision: str | None = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mf_cas_jobs",
        sa.Column("excluded_folios", sa.Integer(), nullable=False, server_default="0"),
        schema="mf",
    )


def downgrade() -> None:
    op.drop_column("mf_cas_jobs", "excluded_folios", schema="mf")
