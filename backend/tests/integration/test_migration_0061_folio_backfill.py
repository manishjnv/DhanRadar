"""Migration 0061 — folio canonicalization backfill (2026-07-04 incident, part 2).

The test suite's DB is create_all-built (alembic never runs here), so this exercises the REAL
migration code by importing 0061 by file path and calling its `_backfill(bind)` body against a
seeded pre-fix state: old-form folio strings (internal whitespace) in the ledger, holdings and
checkpoints, plus a canonical/variant duplicate pair that must merge. The append-only trigger is
installed first, so the ledger part genuinely exercises the sanctioned purge-GUC path.
"""

from __future__ import annotations

import importlib.util
import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import text

from dhanradar.mf.cas import cas_txn_fingerprint
from dhanradar.mf.ledger import APPEND_ONLY_TRIGGER_STATEMENTS
from dhanradar.models.auth import User

pytestmark = pytest.mark.integration

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "0061_folio_canonicalization_backfill.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_0061", _MIGRATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def test_backfill_canonicalizes_and_merges(db_session):
    m0061 = _load_migration()

    # Trigger first — the ledger backfill must go through the purge-GUC path, not a bare DELETE.
    for stmt in APPEND_ONLY_TRIGGER_STATEMENTS:
        await db_session.execute(text(stmt))

    u = User(email="m0061@test.dev")
    db_session.add(u)
    await db_session.flush()
    uid = str(u.id)
    pid = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'M61') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()

    d = date(2026, 1, 5)
    canon_ref_b = cas_txn_fingerprint("INF_M61_B", "5555/73", d.isoformat(), "sip", -1000.0, 50.0)

    async def _ledger_row(isin: str, folio: str, ref: str) -> None:
        await db_session.execute(
            text(
                "INSERT INTO mf.portfolio_transactions"
                " (portfolio_id, user_id, asset_class, instrument_id, folio_number, txn_type,"
                "  txn_date, units, nav_or_price, amount, source, source_ref, parser_version)"
                " VALUES (:p, :u, 'mf', :i, :f, 'sip', :d, 50.0, 20.0, -1000.00, 'cas', :r,"
                "  'cas-1')"
            ),
            {"p": pid, "u": uid, "i": isin, "f": folio, "d": d, "r": ref},
        )

    # 1. Old-form ledger row (internal spaces) with a pre-fix ref — must be canonicalized and its
    #    ref recomputed with the canonical folio.
    await _ledger_row("INF_M61_A", "123 45/ 73", "cas:oldform-a")
    # 2. Canonical/variant duplicate pair (the incident shape): the variant's recomputed ref
    #    collides with the already-canonical row — it must merge away, leaving ONE row.
    await _ledger_row("INF_M61_B", "5555/73", canon_ref_b)
    await _ledger_row("INF_M61_B", "5555/ 73", "cas:oldform-b-variant")

    # 3. Holdings: canonical + variant (must merge to the canonical row), and a variant-only pair
    #    with NO canonical row present (one survives, updated to canonical form).
    async def _holding_row(isin: str, folio: str) -> None:
        await db_session.execute(
            text(
                "INSERT INTO mf.mf_user_holdings"
                " (user_id, portfolio_id, isin, folio_number, units, invested_amount, source)"
                " VALUES (:u, :p, :i, :f, 50.0, 1000.00, 'cas')"
            ),
            {"u": uid, "p": pid, "i": isin, "f": folio},
        )

    await _holding_row("INF_M61_H", "6666/73")
    await _holding_row("INF_M61_H", "6666/ 73")
    await _holding_row("INF_M61_H2", "7777/ 73")
    await _holding_row("INF_M61_H2", "7777 /73")

    # 4. Checkpoint with an old-form folio.
    await db_session.execute(
        text(
            "INSERT INTO mf.portfolio_statement_checkpoints"
            " (user_id, portfolio_id, upload_ref, instrument_id, folio_number, stated_units)"
            " VALUES (:u, :p, :j, 'INF_M61_A', '123 45/ 73', 50.0)"
        ),
        {"u": uid, "p": pid, "j": str(uuid.uuid4())},
    )
    await db_session.commit()

    # Run the REAL migration body (SET LOCAL purge GUC + backfill, one transaction).
    conn = await db_session.connection()
    await conn.run_sync(m0061._backfill)
    await db_session.commit()

    # Ledger: row A canonicalized, ref recomputed with the canonical folio.
    row_a = (
        await db_session.execute(
            text(
                "SELECT folio_number, source_ref FROM mf.portfolio_transactions"
                " WHERE portfolio_id = :p AND instrument_id = 'INF_M61_A'"
            ),
            {"p": pid},
        )
    ).one()
    assert row_a.folio_number == "12345/73"
    assert row_a.source_ref == cas_txn_fingerprint(
        "INF_M61_A", "12345/73", d.isoformat(), "sip", -1000.0, 50.0
    )

    # Ledger: the variant merged into the canonical row — exactly ONE row left for ISIN B.
    rows_b = (
        await db_session.execute(
            text(
                "SELECT folio_number, source_ref FROM mf.portfolio_transactions"
                " WHERE portfolio_id = :p AND instrument_id = 'INF_M61_B'"
            ),
            {"p": pid},
        )
    ).all()
    assert len(rows_b) == 1
    assert rows_b[0].folio_number == "5555/73"
    assert rows_b[0].source_ref == canon_ref_b

    # Holdings: one canonical row per isin, no variants left anywhere.
    holdings = (
        await db_session.execute(
            text(
                "SELECT isin, folio_number FROM mf.mf_user_holdings WHERE portfolio_id = :p"
                " ORDER BY isin"
            ),
            {"p": pid},
        )
    ).all()
    assert [(h.isin, h.folio_number) for h in holdings] == [
        ("INF_M61_H", "6666/73"),
        ("INF_M61_H2", "7777/73"),
    ]

    # Checkpoint canonicalized.
    cp_folio = await db_session.scalar(
        text("SELECT folio_number FROM mf.portfolio_statement_checkpoints WHERE portfolio_id = :p"),
        {"p": pid},
    )
    assert cp_folio == "12345/73"

    # Idempotency: a second run is a clean no-op (already-canonical data).
    conn = await db_session.connection()
    await conn.run_sync(m0061._backfill)
    await db_session.commit()
    n = await db_session.scalar(
        text("SELECT count(*) FROM mf.portfolio_transactions WHERE portfolio_id = :p"), {"p": pid}
    )
    assert n == 2
