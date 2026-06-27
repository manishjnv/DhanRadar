"""B82 — settle the ledger dedup/replay contract BEFORE B2 (CAS→ledger) writes through it.

The ledger (`mf.portfolio_transactions`, migration 0050) has NO prod rows yet, so the unique
constraint can be recreated safely. Two contract fixes:

1. IDEMPOTENCY KEY: the original `uq_portfolio_txn` omitted `source`, so two sources could collide on
   a shared `source_ref` and an amended re-issue could double-count. Add `source` to the key. CAS has
   no stable per-txn id, so the CAS writer derives a DETERMINISTIC `source_ref` fingerprint (so a
   re-upload of the same statement hits ON CONFLICT and is a no-op); the wide natural-key columns stay
   in the constraint as defence (the B82 "messy source → keep the wide key + ADD source" branch).
2. REPLAY VERSION (I11): add a nullable `parser_version` so a snapshot is reproducible from
   `ledger + NAV as-of + parser/engine version`.

Revision ID: 0055
Revises: 0054
Create Date: 2026-06-28
"""

from __future__ import annotations

from alembic import op

revision: str = "0055"
down_revision: str | None = "0054"
branch_labels = None
depends_on = None

_OLD_UQ_COLS = "portfolio_id, instrument_id, folio_number, txn_date, txn_type, amount, source_ref"
_NEW_UQ_COLS = "portfolio_id, source, instrument_id, folio_number, txn_date, txn_type, amount, source_ref"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF to_regclass('mf.portfolio_transactions') IS NULL THEN RETURN; END IF;
            ALTER TABLE mf.portfolio_transactions ADD COLUMN IF NOT EXISTS parser_version text;
            ALTER TABLE mf.portfolio_transactions DROP CONSTRAINT IF EXISTS uq_portfolio_txn;
            ALTER TABLE mf.portfolio_transactions
                ADD CONSTRAINT uq_portfolio_txn UNIQUE ({_NEW_UQ_COLS});
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF to_regclass('mf.portfolio_transactions') IS NULL THEN RETURN; END IF;
            ALTER TABLE mf.portfolio_transactions DROP CONSTRAINT IF EXISTS uq_portfolio_txn;
            ALTER TABLE mf.portfolio_transactions
                ADD CONSTRAINT uq_portfolio_txn UNIQUE ({_OLD_UQ_COLS});
            ALTER TABLE mf.portfolio_transactions DROP COLUMN IF EXISTS parser_version;
        END $$;
        """
    )
