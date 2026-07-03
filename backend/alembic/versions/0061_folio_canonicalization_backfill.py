"""Folio canonicalization backfill (2026-07-04 cross-format dedup incident, part 2).

`normalize_folio` (dhanradar/mf/cas.py) was hardened to strip ALL whitespace + uppercase, but
rows written BEFORE the hardening still hold old-form folio strings — the natural-key dedup and
the unique constraints compare against DB values, so without this backfill the very next upload
of an existing statement re-duplicates (the exact incident the hardening fixes). Three tables:

1. `mf.mf_user_holdings` — canonicalize `folio_number`; where two variant rows collapse to the
   same canonical `(portfolio_id, isin, folio_number)` (true duplicates), keep one (the
   already-canonical row if present, else the newest) and DELETE the rest — holdings are a
   projection and get rewritten on the next upload anyway.
2. `mf.portfolio_statement_checkpoints` — canonicalize `folio_number` (plain UPDATE; the table
   has no unique folio constraint — duplicate evidence rows are harmless history).
3. `mf.portfolio_transactions` — the append-only trigger (I12) forbids UPDATE unconditionally,
   so the backfill goes through the sanctioned purge path: SET LOCAL mf.allow_ledger_purge='on',
   INSERT canonicalized copies (source_ref recomputed via the SHARED `cas_txn_fingerprint`
   recipe) with ON CONFLICT DO NOTHING (a conflict = the duplicate variant merging away), then
   DELETE the old-form rows. One transaction; counts RAISE NOTICE'd.

The whole body lives in `_backfill(bind)` so tests/integration/test_migration_0061_folio_backfill.py
can run the REAL migration code against a seeded DB (the test suite's create_all DB never runs
alembic, so `upgrade()` itself can't be exercised there).

Revision ID: 0061
Revises: 0060
Create Date: 2026-07-04
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0061"
down_revision: str | None = "0060"
branch_labels = None
depends_on = None

# SQL twin of dhanradar.mf.cas.normalize_folio — strip ALL whitespace, uppercase, strip a
# trailing '/0+' plan suffix, IN THAT ORDER. If normalize_folio ever changes, change this
# expression in a NEW migration (this one is history). The ledger loop below uses the Python
# function directly, so only the two UPDATE statements rely on this mirror.
_CANON_SQL = "regexp_replace(upper(regexp_replace(folio_number, '\\s+', '', 'g')), '/0+$', '')"


def _backfill(bind: sa.engine.Connection) -> None:
    # --- 1. mf_user_holdings: dedupe canonical collisions, then canonicalize -------------------
    bind.execute(
        sa.text(f"""
        DO $$
        DECLARE n_dupes int; n_updated int;
        BEGIN
            WITH ranked AS (
                SELECT id, row_number() OVER (
                    PARTITION BY portfolio_id, isin, {_CANON_SQL}
                    -- the already-canonical row wins; else the most recently updated
                    ORDER BY (folio_number = {_CANON_SQL}) DESC, updated_at DESC, id
                ) AS rn
                FROM mf.mf_user_holdings
            )
            DELETE FROM mf.mf_user_holdings h USING ranked r WHERE h.id = r.id AND r.rn > 1;
            GET DIAGNOSTICS n_dupes = ROW_COUNT;

            UPDATE mf.mf_user_holdings
            SET folio_number = {_CANON_SQL}
            WHERE folio_number != {_CANON_SQL};
            GET DIAGNOSTICS n_updated = ROW_COUNT;

            RAISE NOTICE '0061 mf_user_holdings: % duplicate variant rows deleted, % canonicalized',
                n_dupes, n_updated;
        END $$;
        """)
    )

    # --- 2. portfolio_statement_checkpoints: plain canonicalize (no unique constraint) ---------
    bind.execute(
        sa.text(f"""
        DO $$
        DECLARE n int;
        BEGIN
            UPDATE mf.portfolio_statement_checkpoints
            SET folio_number = {_CANON_SQL}
            WHERE folio_number != {_CANON_SQL};
            GET DIAGNOSTICS n = ROW_COUNT;
            RAISE NOTICE '0061 portfolio_statement_checkpoints: % rows canonicalized', n;
        END $$;
        """)
    )

    # --- 3. portfolio_transactions: insert-canonical-copy + purge old (I12-sanctioned path) ----
    # Python loop so the canonical form and the recomputed source_ref come from the ONE shared
    # implementation (normalize_folio / cas_txn_fingerprint) — zero drift risk vs the parse path.
    from dhanradar.mf.cas import cas_txn_fingerprint, normalize_folio
    from dhanradar.mf.ledger import LEDGER_PURGE_GUC

    bind.execute(sa.text(f"SET LOCAL {LEDGER_PURGE_GUC} = 'on'"))

    rows = (
        bind.execute(
            sa.text(
                "SELECT id, portfolio_id, user_id, asset_class, instrument_id, folio_number,"
                " txn_type, txn_date, units, nav_or_price, amount, source, source_ref,"
                " parser_version, ingested_at"
                " FROM mf.portfolio_transactions"
            )
        )
        .mappings()
        .all()
    )
    migrated = merged = 0
    for r in rows:
        canon = normalize_folio(r["folio_number"])
        if canon == r["folio_number"]:
            continue
        ref = r["source_ref"]
        if r["source"] == "cas":
            # Recompute the deterministic fingerprint with the canonical folio, so a future
            # re-upload of the same statement (which now parses to the canonical folio) hits
            # ON CONFLICT instead of duplicating. Numeric(18,2)/Numeric(20,4) Decimals format
            # identically to the floats the parse path hashes ({:.2f}/{:.4f}).
            ref = cas_txn_fingerprint(
                r["instrument_id"], canon, r["txn_date"].isoformat(),
                r["txn_type"], r["amount"], r["units"],
            )
        result = bind.execute(
            sa.text(
                "INSERT INTO mf.portfolio_transactions"
                " (portfolio_id, user_id, asset_class, instrument_id, folio_number, txn_type,"
                "  txn_date, units, nav_or_price, amount, source, source_ref, parser_version,"
                "  ingested_at)"
                " VALUES (:pid, :uid, :ac, :iid, :folio, :tt, :td, :u, :nav, :amt, :src, :ref,"
                "  :pv, :ing)"
                " ON CONFLICT ON CONSTRAINT uq_portfolio_txn DO NOTHING"
            ),
            {
                "pid": r["portfolio_id"], "uid": r["user_id"], "ac": r["asset_class"],
                "iid": r["instrument_id"], "folio": canon, "tt": r["txn_type"],
                "td": r["txn_date"], "u": r["units"], "nav": r["nav_or_price"],
                "amt": r["amount"], "src": r["source"], "ref": ref,
                "pv": r["parser_version"], "ing": r["ingested_at"],
            },
        )
        if result.rowcount == 0:
            merged += 1  # a canonical twin already existed — the variant merges away
        bind.execute(
            sa.text("DELETE FROM mf.portfolio_transactions WHERE id = :id"), {"id": r["id"]}
        )
        migrated += 1

    bind.execute(
        sa.text(
            "DO $$ BEGIN RAISE NOTICE"
            f" '0061 portfolio_transactions: {migrated} old-form rows canonicalized,"
            f" {merged} merged into an existing canonical row'; END $$;"
        )
    )


def upgrade() -> None:
    _backfill(op.get_bind())


def downgrade() -> None:
    # Data canonicalization is not reversible (the old spacing variants are gone by design);
    # the canonical form is fully compatible with pre-0061 code. No-op.
    pass
