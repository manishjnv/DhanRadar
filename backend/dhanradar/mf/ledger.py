"""mf.ledger — the transaction-ledger contract (UI_DATA_ARCHITECTURE_PLAN.md §11).

The ledger (`mf.portfolio_transactions`) is the SOURCE OF TRUTH; holdings, snapshots and
analytics are derived, replayable projections of it. It is append-only and immutable: a DB
trigger (migration 0050) forbids UPDATE and DELETE (I12) — corrections are reversal rows.

The ONE sanctioned exception is a *controlled purge* — portfolio deletion and DPDP user
erasure, which cascade-delete personal data. Those paths opt the current transaction into the
bypass via `allow_ledger_purge(db)` before the DELETE, so the append-only guarantee never
blocks legitimate data removal (and a path that forgets fails LOUDLY rather than silently
violating immutability).

This module is the single source for the GUC name + the trigger DDL so the integration test
applies exactly what the migration installs (ORM `create_all` does not create triggers).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

#: Session GUC the append-only trigger honours to permit a controlled DELETE.
LEDGER_PURGE_GUC = "mf.allow_ledger_purge"

#: Append-only enforcement (I12), as discrete statements (asyncpg rejects multi-statement
#: DDL in one execute). Migration 0050 inlines an identical copy — keep the two in sync.
APPEND_ONLY_TRIGGER_STATEMENTS: list[str] = [
    """
    CREATE OR REPLACE FUNCTION mf.forbid_portfolio_txn_mutation() RETURNS trigger AS $func$
    BEGIN
        -- UPDATE is never allowed; DELETE only under a controlled purge (see allow_ledger_purge).
        IF TG_OP = 'DELETE' AND current_setting('mf.allow_ledger_purge', true) = 'on' THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION
            'mf.portfolio_transactions is append-only (I12): % is forbidden. Corrections are reversal rows; a purge must SET LOCAL mf.allow_ledger_purge = ''on''.',
            TG_OP
            USING ERRCODE = 'restrict_violation';
    END;
    $func$ LANGUAGE plpgsql;
    """,
    "DROP TRIGGER IF EXISTS trg_portfolio_txn_append_only ON mf.portfolio_transactions;",
    """
    CREATE TRIGGER trg_portfolio_txn_append_only
        BEFORE UPDATE OR DELETE ON mf.portfolio_transactions
        FOR EACH ROW EXECUTE FUNCTION mf.forbid_portfolio_txn_mutation();
    """,
]


async def allow_ledger_purge(db: Any) -> None:
    """Opt the CURRENT transaction into a controlled ledger purge (portfolio deletion /
    DPDP erasure). Call on the same session+transaction as the cascading DELETE, before it.

    REQUIRED for ANY path that deletes a row the ledger cascades from: today that is
    `delete_portfolio`; in future, a hard DPDP user-erasure (`DELETE FROM auth.users`) MUST
    call this first. Without it the append-only trigger (I12) BLOCKS the cascade and the
    deletion fails — the user's data is NOT erased, breaking DPDP. (Tracked: BLOCKERS B79.)

    `SET LOCAL` is transaction-scoped, so the bypass auto-reverts at commit/rollback and
    never leaks to another statement, request, or pooled connection.
    """
    # GUC names are identifiers (not bindable params); LEDGER_PURGE_GUC is a trusted module
    # constant, never user input — do not interpolate a runtime value here.
    await db.execute(text(f"SET LOCAL {LEDGER_PURGE_GUC} = 'on'"))
