"""B3 — Holdings are a PROJECTION of the append-only ledger (UI_DATA_ARCHITECTURE_PLAN.md §11–§13).

Pure tests (no PG): replay-parity, dividend_reinvest gap-fix, redemption residual, idempotency,
ENGINE_VERSION constant. PG tests (live-PG CI): projected holdings written under RLS, cross-user
rejection, hard-fail propagation when the ledger append raises.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from dhanradar.db_security import set_rls_user
from dhanradar.mf.cas import ParsedCasIdentity, ParsedHolding, ParsedTxn, build_cas_ledger_rows
from dhanradar.mf.ledger import append_transactions
from dhanradar.mf.projection import ENGINE_VERSION, project_holdings_from_ledger
from dhanradar.models.auth import User

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Shared helpers
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
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'B3') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()
    await db_session.commit()
    return str(pid)


def _holding(
    txns: list[ParsedTxn],
    folio: str = "777/0",
    isin: str = "INF200K01VT2",
    units: float = 80.0,
    cost: float = 1600.0,
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
# PURE tests (no DB) — run with: pytest -k "parity or gap or residual or idempotent or engine_version"
# ---------------------------------------------------------------------------


def test_replay_parity_purchase_only():
    """I11 PARITY PROOF — projection reproduces the AMC-reported close/cost for a purchase-only holding.

    Two purchases: SIP 50u @-1000, purchase 30u @-600 → close=80, cost=1600. The projection's
    Σ units and Σ net-invested must equal the AMC-printed values on the CAS statement.
    """
    txns = [
        ParsedTxn(when=date(2026, 1, 5), amount=-1000.0, is_sip=True, txn_type="sip", units=50.0, nav=20.0),
        ParsedTxn(when=date(2026, 2, 5), amount=-600.0, is_sip=False, txn_type="purchase", units=30.0, nav=20.0),
    ]
    h = _holding(txns, units=80.0, cost=1600.0)
    rows = build_cas_ledger_rows([h], user_id=str(uuid.uuid4()), portfolio_id=str(uuid.uuid4()))
    proj = project_holdings_from_ledger(rows)

    # Key is (isin, normalized_folio) — normalize_folio("777/0") == "777"
    key = (h.isin, "777")
    assert key in proj, f"expected key {key!r} in projection; got keys: {list(proj)}"
    result = proj[key]

    assert result["units"] == Decimal("80"), f"units mismatch: {result['units']}"
    assert result["units"] == Decimal(str(h.units)), "projection units must equal AMC close balance"
    assert result["invested_amount"] == Decimal("1600"), f"invested_amount mismatch: {result['invested_amount']}"
    assert result["invested_amount"] == Decimal(str(h.cost)), "projection invested_amount must equal AMC-printed cost"


def test_gap_surfacing_reinvest_captured():
    """dividend_reinvest is captured in the ledger (units only, amount=0) so Σ units == AMC close balance.

    Without this capture the projection would sum to 100 (only the purchase), missing the 5 reinvested
    units — parity would FAIL and the gap would be surfaced. With the fix, Σ units == 105 == AMC close.
    """
    txns = [
        ParsedTxn(when=date(2026, 1, 5), amount=-2000.0, is_sip=False, txn_type="purchase", units=100.0, nav=20.0),
        ParsedTxn(when=date(2026, 2, 1), amount=0.0, is_sip=False, txn_type="dividend_reinvest", units=5.0, nav=21.0),
    ]
    h = _holding(txns, units=105.0, cost=2000.0)
    rows = build_cas_ledger_rows([h], user_id=str(uuid.uuid4()), portfolio_id=str(uuid.uuid4()))

    # (a) the dividend_reinvest row is captured in the ledger (the gap fix)
    reinvest_rows = [r for r in rows if r["txn_type"] == "dividend_reinvest"]
    assert len(reinvest_rows) >= 1, "dividend_reinvest txn must be captured in ledger rows (gap fix)"
    rr = reinvest_rows[0]
    assert rr["units"] == 5.0, f"reinvest units must be 5.0, got {rr['units']}"
    assert rr["amount"] == 0, f"reinvest amount must be 0 (XIRR-neutral), got {rr['amount']}"

    # (b) projection Σ units == 105 (purchase 100 + reinvest 5)
    # NOTE: without the dividend_reinvest capture this would be 100 and parity would FAIL
    proj = project_holdings_from_ledger(rows)
    key = (h.isin, "777")
    assert proj[key]["units"] == Decimal("105"), (
        f"projection units must be 105 (100 purchase + 5 reinvest); got {proj[key]['units']}"
    )


def test_invested_redemption_residual():
    """Redemption reduces net-invested; the result differs from the AMC FIFO cost basis.

    purchase 100u @-2000, redemption -20u @+500 → units=80, net_invested=2000-500=1500.
    NOTE: this net-invested DIFFERS from the AMC FIFO cost basis of the remaining 80 units
    — the documented residual (plan §13 redefines Invested as net-invested; AMC cost is not a
    deterministic ledger function).
    """
    txns = [
        ParsedTxn(when=date(2026, 1, 5), amount=-2000.0, is_sip=False, txn_type="purchase", units=100.0, nav=20.0),
        ParsedTxn(when=date(2026, 2, 5), amount=500.0, is_sip=False, txn_type="redemption", units=-20.0, nav=25.0),
    ]
    h = _holding(txns, units=80.0, cost=1500.0)
    rows = build_cas_ledger_rows([h], user_id=str(uuid.uuid4()), portfolio_id=str(uuid.uuid4()))
    proj = project_holdings_from_ledger(rows)
    key = (h.isin, "777")

    assert proj[key]["units"] == Decimal("80"), f"100 - 20 = 80 units; got {proj[key]['units']}"
    assert proj[key]["invested_amount"] == Decimal("1500"), (
        f"net invested = 2000 - 500 = 1500; got {proj[key]['invested_amount']}"
    )


def test_idempotent_projection():
    """Projecting the same rows twice yields identical result dicts (pure, deterministic)."""
    txns = [
        ParsedTxn(when=date(2026, 1, 5), amount=-1000.0, is_sip=True, txn_type="sip", units=50.0, nav=20.0),
        ParsedTxn(when=date(2026, 2, 5), amount=-600.0, is_sip=False, txn_type="purchase", units=30.0, nav=20.0),
    ]
    h = _holding(txns, units=80.0, cost=1600.0)
    rows = build_cas_ledger_rows([h], user_id=str(uuid.uuid4()), portfolio_id=str(uuid.uuid4()))
    proj1 = project_holdings_from_ledger(rows)
    proj2 = project_holdings_from_ledger(rows)
    assert proj1 == proj2, "projection must be deterministic — same rows → identical result"


def test_engine_version_constant():
    """ENGINE_VERSION is the stable versioned string recorded alongside projected holdings for I11 replay."""
    assert ENGINE_VERSION == "holdings-proj-1"


# ---------------------------------------------------------------------------
# PG tests (async — require app_session + db_session; run on live-PG CI only)
# ---------------------------------------------------------------------------


async def test_projected_holdings_written_under_rls(db_session, app_session):
    """Holdings written from the projection are owned by the uploader and visible under RLS."""
    uid = await _seed_user(db_session, "b3-proj-rls@test.dev")
    pid = await _seed_portfolio(db_session, uid)

    txns = [
        ParsedTxn(when=date(2026, 1, 5), amount=-1000.0, is_sip=True, txn_type="sip", units=50.0, nav=20.0),
        ParsedTxn(when=date(2026, 2, 5), amount=-600.0, is_sip=False, txn_type="purchase", units=30.0, nav=20.0),
    ]
    parsed = [_holding(txns, units=80.0, cost=1600.0)]

    # Append the ledger under the owner's GUC
    await set_rls_user(app_session, uid)
    rows = build_cas_ledger_rows(parsed, user_id=uid, portfolio_id=pid)
    await append_transactions(app_session, rows)
    await app_session.commit()

    # Project + write holdings
    await set_rls_user(app_session, uid)
    from dhanradar.tasks.mf import _project_and_write_holdings
    await _project_and_write_holdings(app_session, uid, parsed, pid)

    # Read back the holding under the owner's GUC
    await set_rls_user(app_session, uid)
    row = (
        await app_session.execute(
            text(
                "SELECT units, invested_amount, user_id::text AS uid"
                " FROM mf.mf_user_holdings WHERE portfolio_id = :p"
            ),
            {"p": pid},
        )
    ).one()

    assert row.units == Decimal("80"), f"projected units must be 80; got {row.units}"
    assert row.invested_amount == Decimal("1600"), f"projected invested_amount must be 1600; got {row.invested_amount}"
    assert row.uid == uid, f"holding must be owned by uploader {uid}; got {row.uid}"

    await app_session.rollback()


async def test_projection_write_rejects_cross_user(db_session, app_session):
    """Inserting a holding with user_id=B under GUC=A is rejected by RLS WITH CHECK."""
    a = await _seed_user(db_session, "b3-xuser-a@test.dev")
    b = await _seed_user(db_session, "b3-xuser-b@test.dev")
    pid = await _seed_portfolio(db_session, a)

    txns = [
        ParsedTxn(when=date(2026, 1, 5), amount=-1000.0, is_sip=True, txn_type="sip", units=50.0, nav=20.0),
        ParsedTxn(when=date(2026, 2, 5), amount=-600.0, is_sip=False, txn_type="purchase", units=30.0, nav=20.0),
    ]
    parsed = [_holding(txns, units=80.0, cost=1600.0)]

    # Append the ledger under A's GUC (the portfolio belongs to A)
    await set_rls_user(app_session, a)
    rows = build_cas_ledger_rows(parsed, user_id=a, portfolio_id=pid)
    await append_transactions(app_session, rows)
    await app_session.commit()

    # Under GUC=A, attempt to write holdings for user_id=B → RLS WITH CHECK rejects
    await set_rls_user(app_session, a)
    from dhanradar.tasks.mf import _project_and_write_holdings
    with pytest.raises(DBAPIError) as exc:
        await _project_and_write_holdings(app_session, b, parsed, pid)
    assert "row-level security" in str(exc.value).lower(), (
        f"expected RLS violation; got: {exc.value}"
    )

    await app_session.rollback()


async def test_hard_fail_ledger_error_fails_pipeline(db_session, app_session, monkeypatch, patch_redis):
    """When append_transactions raises, _run_pipeline propagates the error (HARD-FAIL, B3).

    Holdings must NOT be written (the pipeline failed before _project_and_write_holdings).
    """
    uid = await _seed_user(db_session, "b3-hardfail@test.dev")
    pid = await _seed_portfolio(db_session, uid)
    job_id = str(uuid.uuid4())

    # Seed an MfCasJob row so _run_pipeline can UPDATE it to "parsing"
    from dhanradar.models.mf import MfCasJob
    db_session.add(
        MfCasJob(
            job_id=uuid.UUID(job_id),
            user_id=uuid.UUID(uid),
            portfolio_id=uuid.UUID(pid),
            source_hash="x",
            status="queued",
            progress_pct=0,
        )
    )
    await db_session.commit()

    txns = [
        ParsedTxn(when=date(2026, 1, 5), amount=-1000.0, is_sip=True, txn_type="sip", units=50.0, nav=20.0),
        ParsedTxn(when=date(2026, 2, 5), amount=-600.0, is_sip=False, txn_type="purchase", units=30.0, nav=20.0),
    ]
    parsed_result = [_holding(txns, units=80.0, cost=1600.0)]

    # Monkeypatch detect_and_parse (module-level import in tasks/mf.py).
    # Contract returns (parsed, identity) since the investor-identity change; identity=None
    # here (this test exercises the ledger hard-fail path, not identity capture).
    monkeypatch.setattr(
        "dhanradar.tasks.mf.detect_and_parse",
        lambda path, pw: (parsed_result, ParsedCasIdentity(pan=None, investor_name=None)),
    )

    # Monkeypatch append_transactions to raise — the ledger write boom propagates
    async def _boom(db, rows):
        raise RuntimeError("ledger boom")

    # _run_pipeline does `from dhanradar.mf.ledger import append_transactions` at CALL time, so patching
    # the name on the LEDGER module (not dhanradar.tasks.mf) is the correct target — the local import
    # rebinds to the patched object. Do NOT "fix" this to dhanradar.tasks.mf.append_transactions.
    monkeypatch.setattr("dhanradar.mf.ledger.append_transactions", _boom)

    from dhanradar.tasks.mf import _run_pipeline
    with pytest.raises(RuntimeError, match="ledger boom"):
        await _run_pipeline(job_id, "/tmp/x.pdf", uid, pid)

    # Verify NO holdings were written (pipeline failed before _project_and_write_holdings)
    await set_rls_user(app_session, uid)
    count = await app_session.scalar(
        text("SELECT count(*) FROM mf.mf_user_holdings WHERE portfolio_id = :p"),
        {"p": pid},
    )
    assert count == 0, f"expected 0 holdings after hard-fail; got {count}"

    await app_session.rollback()


async def test_units_gap_falls_back_to_amc_close(db_session, app_session):
    """SAFETY: if a holding's ledger Σ units != the AMC close balance (an un-captured txn type or a
    deduped identical txn), the AMC close is authoritative — the holding falls back to the parsed
    close/cost rather than ship the wrong projected units (the gap is logged to drive a cas.py
    extension). The cutover can never regress units below today's behaviour."""
    uid = await _seed_user(db_session, "b3-gap@test.dev")
    pid = await _seed_portfolio(db_session, uid)

    # Ledger has only an 80-unit purchase, but the AMC close balance on the statement is 100 (a 20-unit
    # gap — e.g. an un-captured bonus). The holding must show the AMC close (100), not the projected 80.
    txns = [ParsedTxn(when=date(2026, 1, 5), amount=-1600.0, is_sip=False, txn_type="purchase", units=80.0, nav=20.0)]
    parsed = [_holding(txns, units=100.0, cost=2000.0)]

    await set_rls_user(app_session, uid)
    rows = build_cas_ledger_rows(parsed, user_id=uid, portfolio_id=pid)
    await append_transactions(app_session, rows)
    await app_session.commit()

    await set_rls_user(app_session, uid)
    from dhanradar.tasks.mf import _project_and_write_holdings
    await _project_and_write_holdings(app_session, uid, parsed, pid)

    await set_rls_user(app_session, uid)
    row = (
        await app_session.execute(
            text("SELECT units, invested_amount FROM mf.mf_user_holdings WHERE portfolio_id = :p"),
            {"p": pid},
        )
    ).one()
    assert row.units == Decimal("100"), f"gap → must fall back to AMC close 100, not projected 80; got {row.units}"
    assert row.invested_amount == Decimal("2000"), f"gap → AMC cost on fallback; got {row.invested_amount}"

    await app_session.rollback()


async def test_ledgerless_holding_gets_stated_invested_not_null(db_session, app_session):
    """Fix 2a (2026-07-04 XIRR-basis-break retest): a holding with NO ledger txns at ALL (a
    holdings-only source, e.g. a KFin consolidated PDF with no transaction section) must write
    invested_amount from the statement's stated cost (ParsedHolding.cost) — never NULL — so
    portfolio.summary's invested/cost_value totals cover this holding too, not just the
    ledger-backed ones."""
    uid = await _seed_user(db_session, "b3-ledgerless@test.dev")
    pid = await _seed_portfolio(db_session, uid)

    parsed = [_holding([], isin="INF_LEDGERLESS", units=50.0, cost=50_000.0)]

    await set_rls_user(app_session, uid)
    rows = build_cas_ledger_rows(parsed, user_id=uid, portfolio_id=pid)
    assert rows == [], "txn-less holding must produce zero ledger rows"

    from dhanradar.tasks.mf import _project_and_write_holdings
    await _project_and_write_holdings(app_session, uid, parsed, pid)

    await set_rls_user(app_session, uid)
    row = (
        await app_session.execute(
            text("SELECT units, invested_amount FROM mf.mf_user_holdings WHERE portfolio_id = :p"),
            {"p": pid},
        )
    ).one()
    assert row.units == Decimal("50")
    assert row.invested_amount == Decimal("50000.00"), (
        f"ledger-less holding must write the stated cost as invested, never NULL; got {row.invested_amount}"
    )

    await app_session.rollback()
