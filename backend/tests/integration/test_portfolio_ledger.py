"""Append-only ledger trigger (I12) — UI_DATA_ARCHITECTURE_PLAN.md §11.

The BEFORE UPDATE/DELETE trigger on mf.portfolio_transactions blocks every mutation, EXCEPT a
controlled purge (portfolio deletion / DPDP erasure) that opts in via `allow_ledger_purge`
(SET LOCAL mf.allow_ledger_purge='on'). The db_tables fixture's ORM `create_all` builds the
TABLE but not the TRIGGER, so each test first applies APPEND_ONLY_TRIGGER_STATEMENTS — the same
SQL migration 0050 installs in production (kept in sync in dhanradar.mf.ledger).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from dhanradar.mf.ledger import APPEND_ONLY_TRIGGER_STATEMENTS, allow_ledger_purge
from dhanradar.models.auth import User
from dhanradar.models.mf import MfPortfolio, MfPortfolioTransaction

pytestmark = pytest.mark.integration


async def _seed(db, *, email: str) -> MfPortfolioTransaction:
    """Install the trigger, then seed user → portfolio → one ledger row (FKs satisfied)."""
    for stmt in APPEND_ONLY_TRIGGER_STATEMENTS:
        await db.execute(text(stmt))
    user = User(email=email)
    db.add(user)
    await db.flush()
    pf = MfPortfolio(user_id=user.id, name="Ledger Test")
    db.add(pf)
    await db.flush()
    txn = MfPortfolioTransaction(
        portfolio_id=pf.id,
        user_id=user.id,
        asset_class="mf",
        instrument_id="INF0001",
        folio_number="F1",
        txn_type="purchase",
        txn_date=date(2025, 1, 1),
        units=Decimal("10"),
        nav_or_price=Decimal("100"),
        amount=Decimal("-1000"),  # outflow (B65 sign convention)
        source="cas",
        source_ref="stmt-1",
    )
    db.add(txn)
    await db.flush()
    return txn


async def test_update_is_forbidden(db_session):
    txn = await _seed(db_session, email="led-upd@test.dev")
    txn.amount = Decimal("-2000")
    with pytest.raises(DBAPIError) as exc:
        await db_session.flush()  # UPDATE → trigger raises
    assert "append-only" in str(exc.value)
    await db_session.rollback()


async def test_delete_is_forbidden(db_session):
    txn = await _seed(db_session, email="led-del@test.dev")
    await db_session.delete(txn)
    with pytest.raises(DBAPIError) as exc:
        await db_session.flush()  # DELETE without the GUC → trigger raises
    assert "append-only" in str(exc.value)
    await db_session.rollback()


async def test_controlled_purge_allows_delete(db_session):
    txn = await _seed(db_session, email="led-purge@test.dev")
    portfolio_id = txn.portfolio_id
    await allow_ledger_purge(db_session)  # SET LOCAL mf.allow_ledger_purge='on'
    await db_session.delete(txn)
    await db_session.flush()  # trigger now permits the DELETE
    remaining = await db_session.scalar(
        select(func.count())
        .select_from(MfPortfolioTransaction)
        .where(MfPortfolioTransaction.portfolio_id == portfolio_id)
    )
    assert remaining == 0


async def test_purge_guc_does_not_leak_past_commit(db_session):
    """SET LOCAL is transaction-scoped: after a committed purge, a later DELETE on a NEW
    transaction (same pooled connection) must be blocked again — proving no cross-request
    leak even if a future edit broke the SET LOCAL into a session-scoped SET."""
    txn = await _seed(db_session, email="led-leak@test.dev")
    portfolio_id, user_id = txn.portfolio_id, txn.user_id
    await db_session.commit()  # persist seed + trigger; the GUC was never set here

    # Transaction 2: arm the purge, delete, commit → SET LOCAL must revert at this commit.
    await allow_ledger_purge(db_session)
    await db_session.delete(txn)
    await db_session.commit()

    # Transaction 3 on the SAME session/connection: GUC must be back to unset → blocked.
    txn2 = MfPortfolioTransaction(
        portfolio_id=portfolio_id,
        user_id=user_id,
        asset_class="mf",
        instrument_id="INF0002",
        folio_number="F1",
        txn_type="purchase",
        txn_date=date(2025, 2, 1),
        units=Decimal("5"),
        nav_or_price=Decimal("200"),
        amount=Decimal("-1000"),
        source="cas",
        source_ref="stmt-2",
    )
    db_session.add(txn2)
    await db_session.flush()  # INSERT is allowed
    await db_session.delete(txn2)
    with pytest.raises(DBAPIError) as exc:
        await db_session.flush()  # DELETE blocked again — the purge GUC did not leak
    assert "append-only" in str(exc.value)
    await db_session.rollback()
