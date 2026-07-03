"""Ledger-ingest robustness — UI_DATA_ARCHITECTURE_PLAN.md §39.2 scenario matrix.

PG tests (live-PG CI): a subset re-upload never loses ledger rows or holdings and writes
checkpoints ONLY for the folios the subset statement covers (S9); a statement whose stated
units disagree with the ledger's replayed units gets a 'mismatch' checkpoint WITHOUT the
ledger ever being mutated (S10); the checkpoint table is owner-scoped RLS like every other
mf personal table.

Mirrors test_b3_holdings_projection.py / test_b2_cas_ledger.py (the proven B2/B3 pattern).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from dhanradar.db_security import set_rls_user
from dhanradar.mf.cas import ParsedHolding, ParsedTxn, build_cas_ledger_rows
from dhanradar.mf.ledger import append_transactions
from dhanradar.models.auth import User

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Shared helpers (duplicated from test_b3_holdings_projection.py — each test
# file in this suite is self-contained, per the proven B2/B3 pattern).
# ---------------------------------------------------------------------------


async def _seed_user(db_session, email: str) -> str:
    u = User(email=email)
    db_session.add(u)
    await db_session.flush()
    uid = str(u.id)
    await db_session.commit()
    return uid


async def _seed_portfolio(db_session, uid: str) -> str:
    pid = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'Ledger') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()
    await db_session.commit()
    return str(pid)


def _holding(
    txns: list[ParsedTxn],
    folio: str,
    isin: str,
    units: float,
    cost: float,
) -> ParsedHolding:
    return ParsedHolding(
        isin=isin,
        amfi_code="1",
        scheme_name="X",
        folio_number=folio,
        units=units,
        nav=21.0,
        value=units * 21.0,
        cost=cost,
        as_of_date=date(2026, 3, 31),
        txns=txns,
    )


# ---------------------------------------------------------------------------
# S9 — subset / partial statement: nothing lost, checkpoints only for covered folios
# ---------------------------------------------------------------------------


async def test_subset_statement_no_rows_lost_checkpoints_only_covered(db_session, app_session):
    """Upload 1 covers funds A + B; upload 2 is a SUBSET statement covering only A. Fund B's
    ledger rows and holding must survive untouched (absence from a statement is never a
    redemption), and the second upload's checkpoints must exist ONLY for A (the covered fund)."""
    uid = await _seed_user(db_session, "s9@test.dev")
    pid = await _seed_portfolio(db_session, uid)

    txns_a = [
        ParsedTxn(
            when=date(2026, 1, 5), amount=-1000.0, is_sip=True, txn_type="sip", units=50.0, nav=20.0
        )
    ]
    txns_b = [
        ParsedTxn(
            when=date(2026, 1, 10),
            amount=-2000.0,
            is_sip=False,
            txn_type="purchase",
            units=100.0,
            nav=20.0,
        )
    ]
    hold_a = _holding(txns_a, folio="A1", isin="INF_S9_A", units=50.0, cost=1000.0)
    hold_b = _holding(txns_b, folio="B1", isin="INF_S9_B", units=100.0, cost=2000.0)
    parsed1 = [hold_a, hold_b]

    from dhanradar.tasks.mf import _project_and_write_holdings, _write_statement_checkpoints

    # Upload 1: both funds.
    await set_rls_user(app_session, uid)
    rows1 = build_cas_ledger_rows(parsed1, user_id=uid, portfolio_id=pid)
    ins1, _ = await append_transactions(app_session, rows1)
    await app_session.commit()
    assert ins1 == len(rows1)

    await set_rls_user(app_session, uid)
    invested1, projected1 = await _project_and_write_holdings(app_session, uid, parsed1, pid)
    job1 = str(uuid.uuid4())
    await _write_statement_checkpoints(app_session, uid, pid, job1, parsed1, projected1)
    await app_session.commit()

    # Upload 2 (subset statement): only fund A appears.
    parsed2 = [hold_a]
    await set_rls_user(app_session, uid)
    rows2 = build_cas_ledger_rows(parsed2, user_id=uid, portfolio_id=pid)
    ins2, skip2 = await append_transactions(app_session, rows2)
    await app_session.commit()
    assert (ins2, skip2) == (0, len(rows2)), "same txns re-ingested → idempotent no-op"

    await set_rls_user(app_session, uid)
    invested2, projected2 = await _project_and_write_holdings(app_session, uid, parsed2, pid)
    job2 = str(uuid.uuid4())
    await _write_statement_checkpoints(app_session, uid, pid, job2, parsed2, projected2)
    await app_session.commit()

    # Nothing lost: BOTH funds' ledger rows still present.
    await set_rls_user(app_session, uid)
    n_ledger = await app_session.scalar(
        text("SELECT count(*) FROM mf.portfolio_transactions WHERE portfolio_id = :p"), {"p": pid}
    )
    assert n_ledger == len(rows1), "subset re-upload must never drop existing ledger rows"

    # Fund B's holding is unchanged (absence from statement 2 != redemption).
    row_b = (
        await app_session.execute(
            text("SELECT units FROM mf.mf_user_holdings WHERE portfolio_id = :p AND isin = :i"),
            {"p": pid, "i": "INF_S9_B"},
        )
    ).one()
    assert row_b.units == Decimal("100")

    # Checkpoints for job2 exist ONLY for the covered folio (fund A), not fund B.
    cp_job2 = (
        (
            await app_session.execute(
                text(
                    "SELECT instrument_id FROM mf.portfolio_statement_checkpoints WHERE upload_ref = :j"
                ),
                {"j": job2},
            )
        )
        .scalars()
        .all()
    )
    assert cp_job2 == ["INF_S9_A"], f"expected checkpoint only for the covered fund; got {cp_job2}"

    # job1's checkpoints (both funds) are untouched — a prior upload's evidence is never overwritten.
    cp_job1 = (
        (
            await app_session.execute(
                text(
                    "SELECT instrument_id FROM mf.portfolio_statement_checkpoints WHERE upload_ref = :j"
                    " ORDER BY instrument_id"
                ),
                {"j": job1},
            )
        )
        .scalars()
        .all()
    )
    assert cp_job1 == ["INF_S9_A", "INF_S9_B"]

    await app_session.rollback()


# ---------------------------------------------------------------------------
# S10 — conflicting rows: checkpoint flags mismatch, ledger NEVER mutated (I12)
# ---------------------------------------------------------------------------


async def test_mismatch_checkpoint_never_mutates_ledger(db_session, app_session):
    """Statement says close units = 100 but the ledger only reconstructs 80 (a 20-unit gap —
    e.g. an un-captured corporate action). The checkpoint must flag 'mismatch'; the ledger row
    count must be untouched (no reversal, no silent overwrite — I12)."""
    uid = await _seed_user(db_session, "s10@test.dev")
    pid = await _seed_portfolio(db_session, uid)

    txns = [
        ParsedTxn(
            when=date(2026, 1, 5),
            amount=-1600.0,
            is_sip=False,
            txn_type="purchase",
            units=80.0,
            nav=20.0,
        )
    ]
    parsed = [_holding(txns, folio="C1", isin="INF_S10", units=100.0, cost=2000.0)]

    await set_rls_user(app_session, uid)
    rows = build_cas_ledger_rows(parsed, user_id=uid, portfolio_id=pid)
    await append_transactions(app_session, rows)
    await app_session.commit()

    from dhanradar.tasks.mf import _project_and_write_holdings, _write_statement_checkpoints

    await set_rls_user(app_session, uid)
    invested, projected = await _project_and_write_holdings(app_session, uid, parsed, pid)
    job = str(uuid.uuid4())
    await _write_statement_checkpoints(app_session, uid, pid, job, parsed, projected)
    await app_session.commit()

    await set_rls_user(app_session, uid)
    cp = (
        await app_session.execute(
            text(
                "SELECT reconciliation_status, stated_units FROM mf.portfolio_statement_checkpoints"
                " WHERE upload_ref = :j"
            ),
            {"j": job},
        )
    ).one()
    assert cp.reconciliation_status == "mismatch"
    assert cp.stated_units == Decimal("100.0000")

    n_ledger = await app_session.scalar(
        text("SELECT count(*) FROM mf.portfolio_transactions WHERE portfolio_id = :p"), {"p": pid}
    )
    assert n_ledger == len(rows), "I12: a reconciliation mismatch must never mutate the ledger"

    await app_session.rollback()


async def test_ok_checkpoint_when_units_agree(db_session, app_session):
    """Sanity control: when the ledger fully reconstructs the AMC close balance, the checkpoint
    is 'ok' (not 'mismatch') — the S10 test above isn't just always flagging mismatch."""
    uid = await _seed_user(db_session, "s10-ok@test.dev")
    pid = await _seed_portfolio(db_session, uid)

    txns = [
        ParsedTxn(
            when=date(2026, 1, 5),
            amount=-1600.0,
            is_sip=False,
            txn_type="purchase",
            units=80.0,
            nav=20.0,
        )
    ]
    parsed = [_holding(txns, folio="D1", isin="INF_S10_OK", units=80.0, cost=1600.0)]

    await set_rls_user(app_session, uid)
    rows = build_cas_ledger_rows(parsed, user_id=uid, portfolio_id=pid)
    await append_transactions(app_session, rows)
    await app_session.commit()

    from dhanradar.tasks.mf import _project_and_write_holdings, _write_statement_checkpoints

    await set_rls_user(app_session, uid)
    invested, projected = await _project_and_write_holdings(app_session, uid, parsed, pid)
    job = str(uuid.uuid4())
    await _write_statement_checkpoints(app_session, uid, pid, job, parsed, projected)
    await app_session.commit()

    await set_rls_user(app_session, uid)
    status = await app_session.scalar(
        text(
            "SELECT reconciliation_status FROM mf.portfolio_statement_checkpoints WHERE upload_ref = :j"
        ),
        {"j": job},
    )
    assert status == "ok"

    await app_session.rollback()


# ---------------------------------------------------------------------------
# Checkpoint RLS — owner-scoped like every other mf personal table
# ---------------------------------------------------------------------------


async def test_checkpoint_rls_rejects_cross_user(db_session, app_session):
    """Writing a checkpoint owned by user B under GUC=A is rejected by RLS WITH CHECK — mirrors
    test_projection_write_rejects_cross_user in test_b3_holdings_projection.py."""
    a = await _seed_user(db_session, "cp-a@test.dev")
    b = await _seed_user(db_session, "cp-b@test.dev")
    pid = await _seed_portfolio(db_session, a)

    txns = [
        ParsedTxn(
            when=date(2026, 1, 5), amount=-1000.0, is_sip=True, txn_type="sip", units=50.0, nav=20.0
        )
    ]
    parsed = [_holding(txns, folio="E1", isin="INF_CP_RLS", units=50.0, cost=1000.0)]

    await set_rls_user(app_session, a)
    rows = build_cas_ledger_rows(parsed, user_id=a, portfolio_id=pid)
    await append_transactions(app_session, rows)
    await app_session.commit()

    from dhanradar.tasks.mf import _project_and_write_holdings, _write_statement_checkpoints

    await set_rls_user(app_session, a)
    invested, projected = await _project_and_write_holdings(app_session, a, parsed, pid)

    with pytest.raises(DBAPIError) as exc:
        await _write_statement_checkpoints(
            app_session, b, pid, str(uuid.uuid4()), parsed, projected
        )
    assert "row-level security" in str(exc.value).lower()

    await app_session.rollback()
