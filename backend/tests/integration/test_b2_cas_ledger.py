"""B2 — CAS pipeline writes the append-only transaction ledger (idempotent diff-and-append) + B82
contract.

Pure tests (no PG): B65 sign convention, folio normalization, deterministic source_ref, the sole-writer
guard. PG tests (run on the live-PG backend job — RLS exists only on a migration/conftest-built DB):
idempotent re-append, diff-and-append, RLS WITH-CHECK scoping, parser_version recorded. All PG writes
go through `append_transactions` AS dhanradar_app with the per-request GUC set (the CAS pipeline's
`rls_user_session` discipline), so a row can only be written for the GUC owner.
"""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from dhanradar.db_security import set_rls_user
from dhanradar.mf.cas import (
    PARSER_VERSION,
    ParsedHolding,
    ParsedTxn,
    _cas_source_ref,
    build_cas_ledger_rows,
    normalize_folio,
)
from dhanradar.mf.ledger import append_transactions
from dhanradar.models.auth import User

pytestmark = pytest.mark.integration


def _txns_base() -> list[ParsedTxn]:
    return [
        ParsedTxn(when=date(2026, 1, 5), amount=-1000.0, is_sip=True, txn_type="sip", units=50.0, nav=20.0),
        ParsedTxn(when=date(2026, 2, 5), amount=500.0, is_sip=False, txn_type="redemption", units=-10.0, nav=50.0),
    ]


def _holding(txns: list[ParsedTxn]) -> ParsedHolding:
    return ParsedHolding(
        isin="INF200K01VT2", amfi_code="118989", scheme_name="Test Fund", folio_number="777/0",
        units=40.0, nav=21.0, value=840.0, cost=1000.0, as_of_date=None, txns=txns,
    )


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
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'B2') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()
    await db_session.commit()
    return str(pid)


# --- pure (no PG) ---------------------------------------------------------------------------------


def test_sign_convention_b65():
    """Purchase = outflow NEGATIVE; redemption = inflow POSITIVE (B65 investor convention), reused
    from parse_cas — never raw casparser amounts."""
    rows = build_cas_ledger_rows([_holding(_txns_base())], user_id=str(uuid.uuid4()), portfolio_id=str(uuid.uuid4()))
    by_type = {r["txn_type"]: r for r in rows}
    assert by_type["sip"]["amount"] < 0 and by_type["sip"]["units"] == 50.0
    assert by_type["redemption"]["amount"] > 0 and by_type["redemption"]["units"] == -10.0


def test_folio_normalization():
    assert normalize_folio("12345/0") == "12345"
    assert normalize_folio("  9999 / 0 ") == "9999"
    assert normalize_folio("12340") == "12340"  # never strips folio-body digits
    assert normalize_folio("") == ""


def test_source_ref_deterministic_and_distinct():
    t1, t2 = _txns_base()
    a = _cas_source_ref("INF1", "777", t1)
    assert a == _cas_source_ref("INF1", "777", t1)  # stable across re-parse → idempotent
    assert a != _cas_source_ref("INF1", "777", t2)  # different txn → different ref
    assert a.startswith("cas:")


def test_ledger_sole_writer_no_bare_constructor():
    """append_transactions is the SOLE writer (B2): no bare `MfPortfolioTransaction(...)` construction
    anywhere in dhanradar/ (the helper uses pg_insert). A bare ORM add would bypass idempotency + RLS."""
    backend = Path(__file__).resolve().parents[2]
    offenders = []
    for f in (backend / "dhanradar").rglob("*.py"):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "MfPortfolioTransaction(" in line and not line.lstrip().startswith("class MfPortfolioTransaction("):
                offenders.append(f"{f.relative_to(backend)}:{i}")
    assert not offenders, f"bare MfPortfolioTransaction(...) — append_transactions is the SOLE writer (B2): {offenders}"


# --- PG (live-PG backend job) ----------------------------------------------------------------------


async def test_append_idempotent(db_session, app_session):
    uid = await _seed_user(db_session, "b2-idem@test.dev")
    pid = await _seed_portfolio(db_session, uid)
    rows = build_cas_ledger_rows([_holding(_txns_base())], user_id=uid, portfolio_id=pid)

    await set_rls_user(app_session, uid)
    ins1, skip1 = await append_transactions(app_session, rows)
    await app_session.commit()
    assert (ins1, skip1) == (len(rows), 0)

    await set_rls_user(app_session, uid)  # GUC reset by the commit above — re-set (SET LOCAL)
    ins2, skip2 = await append_transactions(app_session, rows)
    await app_session.commit()
    assert (ins2, skip2) == (0, len(rows)), "re-uploading the same CAS must be a no-op (all-skipped)"

    await set_rls_user(app_session, uid)
    n = await app_session.scalar(
        text("SELECT count(*) FROM mf.portfolio_transactions WHERE portfolio_id = :p"), {"p": pid}
    )
    assert n == len(rows)
    await app_session.rollback()


async def test_diff_and_append(db_session, app_session):
    uid = await _seed_user(db_session, "b2-diff@test.dev")
    pid = await _seed_portfolio(db_session, uid)
    base = build_cas_ledger_rows([_holding(_txns_base())], user_id=uid, portfolio_id=pid)

    await set_rls_user(app_session, uid)
    ins1, _ = await append_transactions(app_session, base)
    await app_session.commit()
    assert ins1 == len(base)

    # A second statement with one NEW txn appended — only the new row lands; history preserved.
    extra = ParsedTxn(when=date(2026, 3, 5), amount=-2000.0, is_sip=False, txn_type="purchase", units=80.0, nav=25.0)
    fuller = build_cas_ledger_rows([_holding([*_txns_base(), extra])], user_id=uid, portfolio_id=pid)

    await set_rls_user(app_session, uid)
    ins2, skip2 = await append_transactions(app_session, fuller)
    await app_session.commit()
    assert (ins2, skip2) == (1, len(base)), "diff-and-append: only the new txn appends, the rest skip"

    await set_rls_user(app_session, uid)
    n = await app_session.scalar(
        text("SELECT count(*) FROM mf.portfolio_transactions WHERE portfolio_id = :p"), {"p": pid}
    )
    assert n == len(base) + 1
    await app_session.rollback()


async def test_rls_scoped_write_rejects_cross_user(db_session, app_session):
    a = await _seed_user(db_session, "b2-rls-a@test.dev")
    b = await _seed_user(db_session, "b2-rls-b@test.dev")
    pid = await _seed_portfolio(db_session, a)

    # A row owned by B, appended under the GUC of A → RLS WITH CHECK rejects (the row can only belong
    # to the GUC owner). A unique date/amount guarantees these rows can NEVER conflict with anything,
    # so the insert is genuinely ATTEMPTED and WITH CHECK is what rejects it — not a silent skip.
    bad_txns = [ParsedTxn(when=date(2099, 1, 1), amount=-1.0, is_sip=False, txn_type="purchase", units=1.0, nav=1.0)]
    bad = build_cas_ledger_rows([_holding(bad_txns)], user_id=b, portfolio_id=pid)
    await set_rls_user(app_session, a)
    with pytest.raises(DBAPIError) as exc:
        await append_transactions(app_session, bad)
    assert "row-level security" in str(exc.value).lower()
    await app_session.rollback()

    # Positive control: A's own rows DO land under A's GUC.
    good = build_cas_ledger_rows([_holding(_txns_base())], user_id=a, portfolio_id=pid)
    await set_rls_user(app_session, a)
    ins, _ = await append_transactions(app_session, good)
    await app_session.commit()
    assert ins == len(good)
    await app_session.rollback()


async def test_parser_version_recorded(db_session, app_session):
    uid = await _seed_user(db_session, "b2-pv@test.dev")
    pid = await _seed_portfolio(db_session, uid)
    rows = build_cas_ledger_rows([_holding(_txns_base())], user_id=uid, portfolio_id=pid)

    await set_rls_user(app_session, uid)
    await append_transactions(app_session, rows)
    await app_session.commit()

    await set_rls_user(app_session, uid)
    pv = await app_session.scalar(
        text("SELECT DISTINCT parser_version FROM mf.portfolio_transactions WHERE portfolio_id = :p"),
        {"p": pid},
    )
    assert pv == PARSER_VERSION
    await app_session.rollback()
