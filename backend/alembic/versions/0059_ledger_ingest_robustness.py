"""Ledger-ingest robustness (UI_DATA_ARCHITECTURE_PLAN.md §39.4) — two small schema deltas the
ingestion scenario matrix (S1-S20) needs:

1. `mf.portfolio_statement_checkpoints` (new) — per upload x (instrument, folio): the CAS-stated
   units/cost vs the ledger's replayed units, so a re-upload's evidence is never lost even when
   the ledger can't fully reconstruct a holding (S3 HOLDINGS_ONLY) or disagrees with it (S10
   mismatch). RLS owner-isolation mirrors migration 0056's pattern exactly.
2. Coverage-window columns on `mf.mf_cas_jobs` (the existing CAS upload/job table) — `stmt_from`/
   `stmt_to` from the CAS's own statement-period header (casparser `statement_period`); NULL when
   the source format doesn't expose one (CAMS Transaction-Details .txt/.xls have no such header).

Revision ID: 0059
Revises: 0058
Create Date: 2026-07-03
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from dhanradar.db_security import rls_downgrade_statements, rls_statements

revision: str = "0059"
down_revision: str | None = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mf.portfolio_statement_checkpoints (
            id                      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id                 uuid        NOT NULL
                REFERENCES auth.users(id) ON DELETE CASCADE,
            portfolio_id            uuid        NOT NULL
                REFERENCES mf.mf_portfolios(id) ON DELETE CASCADE,
            upload_ref              text        NOT NULL,
            instrument_id           text        NOT NULL,
            folio_number            text        NOT NULL,
            stated_units            numeric(20, 4) NOT NULL,
            stated_cost             numeric(18, 2) NULL,
            stmt_date               date        NULL,
            reconciliation_status   text        NOT NULL DEFAULT 'ok'
                CHECK (reconciliation_status IN ('ok', 'mismatch')),
            created_at              timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_portfolio_stmt_checkpoints_portfolio_instr_folio
            ON mf.portfolio_statement_checkpoints (portfolio_id, instrument_id, folio_number);
        """
    )
    # Grant the app role access. Least-priv (B80): checkpoints are append-only evidence —
    # the sole writer (_write_statement_checkpoints) INSERTs rows with their final status;
    # there is no UPDATE path, so no UPDATE grant.
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regrole('dhanradar_app') IS NOT NULL THEN
                GRANT SELECT, INSERT ON mf.portfolio_statement_checkpoints
                    TO dhanradar_app;
            END IF;
        END $$;
        """
    )
    # Owner-isolation RLS (mirrors 0056 exactly).
    _TABLE = "mf.portfolio_statement_checkpoints"
    for stmt in rls_statements(_TABLE):
        op.execute(stmt)

    # Coverage-window columns on the existing CAS upload/job table.
    op.add_column("mf_cas_jobs", sa.Column("stmt_from", sa.Date(), nullable=True), schema="mf")
    op.add_column("mf_cas_jobs", sa.Column("stmt_to", sa.Date(), nullable=True), schema="mf")


def downgrade() -> None:
    op.drop_column("mf_cas_jobs", "stmt_to", schema="mf")
    op.drop_column("mf_cas_jobs", "stmt_from", schema="mf")

    _TABLE = "mf.portfolio_statement_checkpoints"
    for stmt in rls_downgrade_statements(_TABLE):
        op.execute(stmt)
    op.execute("DROP TABLE IF EXISTS mf.portfolio_statement_checkpoints;")
