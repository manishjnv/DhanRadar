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

from dhanradar.core.logging import get_logger

_slog = get_logger(__name__)

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


#: Natural-key tuple for cross-format/cross-source dedup (§39.3, adapted): a real-world transaction
#: is the SAME transaction regardless of which format/source printed it, so it must collide on this
#: key even when its content-hash `source_ref` differs (the 2026-07-04 incident — CAMS-vs-KFin folio
#: spacing variance produced two different `source_ref`s for one real SIP). Deliberately excludes
#: `source`/`source_ref` — those are exactly the columns that can legitimately differ for one real
#: transaction re-ingested from a second format/rail.
_NaturalKey = tuple[str, str, Any, str, float, float]


def _natural_key(
    instrument_id: str, folio_number: str, txn_date: Any, txn_type: str, units: Any, amount: Any
) -> _NaturalKey:
    """Rounding-bucket natural key: units to 3 decimals (~±0.001 tolerance), amount to the nearest
    rupee (~±1 tolerance) — exact match after rounding, per spec (no epsilon-neighbourhood search).
    `folio_number` is expected ALREADY CANONICAL (normalize_folio) — every ledger-row producer must
    normalize before this point, so this function does not re-normalize."""
    return (
        instrument_id,
        folio_number,
        txn_date,
        txn_type,
        round(float(units), 3),
        round(float(amount)),
    )


async def append_transactions(db: Any, rows: list[dict[str, Any]]) -> tuple[int, int]:
    """SOLE writer of the append-only ledger (B2). Bulk `INSERT ... ON CONFLICT ON CONSTRAINT
    uq_portfolio_txn DO NOTHING` — so re-ingesting the same txns is a no-op (diff-and-append, §22);
    only genuinely-new rows land. Returns (inserted, skipped).

    Second-stage natural-key dedup (§39.3, adapted — the 2026-07-04 cross-format incident): BEFORE
    the INSERT, any candidate row that matches an EXISTING row of this portfolio on
    `(instrument_id, folio_number, txn_date, txn_type, round(units,3), round(amount))` is dropped —
    regardless of `source_ref` — so the same real-world transaction re-ingested under a different
    content-hash fingerprint (a different format's folio spacing, or a future second source rail)
    still collides to ONE row. Logged as `ledger.cross_format_skipped`. The ON CONFLICT path below
    stays as the final (cheaper, exact-hash) safety net for genuine re-ingests of the same source.

    Runs on the CALLER's session — the CAS pipeline's `rls_user_session`, so RLS WITH CHECK enforces
    each row's `user_id` == the GUC owner: a row for any other user is REJECTED by the policy (the row
    can only belong to the authenticated uploader). DO NOTHING (never DO UPDATE) keeps it an INSERT, so
    the append-only trigger (which blocks UPDATE/DELETE, I12) never fires. NEVER write the ledger with a
    bare ORM `add` — idempotency, RLS, and immutability all depend on this single path (test-enforced).
    """
    if not rows:
        return (0, 0)

    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from dhanradar.models.mf import MfPortfolioTransaction

    # All rows in one call belong to the same portfolio (one CAS upload / one sync batch).
    portfolio_id = rows[0]["portfolio_id"]
    existing = (
        await db.execute(
            select(
                MfPortfolioTransaction.instrument_id,
                MfPortfolioTransaction.folio_number,
                MfPortfolioTransaction.txn_date,
                MfPortfolioTransaction.txn_type,
                MfPortfolioTransaction.units,
                MfPortfolioTransaction.amount,
            ).where(MfPortfolioTransaction.portfolio_id == portfolio_id)
        )
    ).all()
    existing_keys = {
        _natural_key(r.instrument_id, r.folio_number, r.txn_date, r.txn_type, r.units, r.amount)
        for r in existing
    }

    candidate_rows: list[dict[str, Any]] = []
    seen_in_batch: set[_NaturalKey] = set()
    cross_format_skipped = 0
    for row in rows:
        key = _natural_key(
            row["instrument_id"],
            row["folio_number"],
            row["txn_date"],
            row["txn_type"],
            row["units"],
            row["amount"],
        )
        if key in existing_keys or key in seen_in_batch:
            cross_format_skipped += 1
            continue
        seen_in_batch.add(key)
        candidate_rows.append(row)

    if cross_format_skipped:
        _slog.info("ledger.cross_format_skipped", count=cross_format_skipped, total=len(rows))

    if not candidate_rows:
        return (0, len(rows))

    stmt = (
        pg_insert(MfPortfolioTransaction)
        .values(candidate_rows)
        .on_conflict_do_nothing(constraint="uq_portfolio_txn")
        .returning(MfPortfolioTransaction.id)
    )
    result = await db.execute(stmt)
    inserted = len(result.fetchall())  # RETURNING yields only inserted rows; conflicts are skipped
    return inserted, len(rows) - inserted
