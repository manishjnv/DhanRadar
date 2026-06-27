"""B80 — the runtime DB role (dhanradar_app) is de-superusered, making I12 append-only a HARD
invariant rather than a guardrail a superuser could skip.

These tests connect as the least-privilege dhanradar_app role (`app_session`) and prove the
privilege boundary; owner-side setup uses the superuser `db_session`. The two are separate
connections to the same test DB, so owner seed is COMMITTED before the app role reads it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from dhanradar.db_schemas import APP_SCHEMAS
from dhanradar.mf.ledger import APPEND_ONLY_TRIGGER_STATEMENTS
from dhanradar.models.auth import User
from dhanradar.models.mf import MfPortfolio, MfPortfolioTransaction

pytestmark = pytest.mark.integration


async def _seed_owner(db, *, email: str, with_trigger: bool = False):
    """Owner-side seed (committed so the dhanradar_app connection can see it): user + portfolio,
    and optionally the append-only trigger + one ledger row."""
    if with_trigger:
        for stmt in APPEND_ONLY_TRIGGER_STATEMENTS:
            await db.execute(text(stmt))
    user = User(email=email)
    db.add(user)
    await db.flush()
    pf = MfPortfolio(user_id=user.id, name="B80")
    db.add(pf)
    await db.flush()
    txn = None
    if with_trigger:
        txn = MfPortfolioTransaction(
            portfolio_id=pf.id, user_id=user.id, asset_class="mf", instrument_id="INF1",
            folio_number="F1", txn_type="purchase", txn_date=date(2025, 1, 1),
            units=Decimal("1"), nav_or_price=Decimal("10"), amount=Decimal("-10"),
            source="cas", source_ref="r1",
        )
        db.add(txn)
        await db.flush()
    await db.commit()
    return user, pf, txn


async def test_app_role_cannot_set_session_replication_role(app_session):
    """A superuser could `SET session_replication_role='replica'` to skip ALL triggers.
    dhanradar_app is NOSUPERUSER → denied, so it cannot disarm the append-only trigger."""
    with pytest.raises(DBAPIError):
        await app_session.execute(text("SET session_replication_role = 'replica'"))
    await app_session.rollback()


async def test_app_role_cannot_disable_trigger(app_session):
    """dhanradar_app does not OWN the table → ALTER TABLE … DISABLE TRIGGER is denied."""
    with pytest.raises(DBAPIError):
        await app_session.execute(text("ALTER TABLE mf.portfolio_transactions DISABLE TRIGGER ALL"))
    await app_session.rollback()


async def test_app_role_is_bound_by_append_only_trigger(db_session, app_session):
    """As a normal role, dhanradar_app cannot skip the trigger — UPDATE and DELETE both raise.
    (If grants were missing this would be a privilege error; asserting 'append-only' proves it is
    the trigger, i.e. the role HAS DML but is bound by I12.)"""
    _, _, txn = await _seed_owner(db_session, email="b80-trig@test.dev", with_trigger=True)
    with pytest.raises(DBAPIError) as exc:
        await app_session.execute(
            text("UPDATE mf.portfolio_transactions SET amount = -99 WHERE id = :i"),
            {"i": str(txn.id)},
        )
    assert "append-only" in str(exc.value)
    await app_session.rollback()
    with pytest.raises(DBAPIError) as exc2:
        await app_session.execute(
            text("DELETE FROM mf.portfolio_transactions WHERE id = :i"), {"i": str(txn.id)}
        )
    assert "append-only" in str(exc2.value)
    await app_session.rollback()


async def test_app_role_can_arm_purge_and_delete(db_session, app_session):
    """delete_portfolio's controlled purge must keep working under least-priv: dhanradar_app CAN
    set the custom namespaced GUC (settable by any role) and then the trigger permits the DELETE."""
    _, _, txn = await _seed_owner(db_session, email="b80-purge@test.dev", with_trigger=True)
    await app_session.execute(text("SET LOCAL mf.allow_ledger_purge = 'on'"))
    await app_session.execute(
        text("DELETE FROM mf.portfolio_transactions WHERE id = :i"), {"i": str(txn.id)}
    )
    remaining = await app_session.scalar(
        text("SELECT count(*) FROM mf.portfolio_transactions WHERE id = :i"), {"i": str(txn.id)}
    )
    assert remaining == 0
    await app_session.rollback()


async def test_app_role_is_not_superuser(app_session):
    """The runtime role reports as a NON-superuser — exactly what /health's `db_role_hardened`
    field surfaces (so an operator can alert if a deploy fell back to the owner role)."""
    is_super = await app_session.scalar(text("SELECT current_setting('is_superuser')"))
    assert str(is_super).lower() == "off"


async def test_app_role_has_no_bypassrls(app_session):
    """B81 (RLS) depends on dhanradar_app being NOBYPASSRLS — otherwise FORCE RLS would not bind it
    and owner-scoping would silently leak across users."""
    bypass = await app_session.scalar(
        text("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
    )
    assert bypass is False


async def test_app_role_can_read_every_app_schema(db_session, app_session):
    """REGRESSION for the B80 grant-gap (the test that would have caught it): dhanradar_app must be
    able to read a table in EVERY schema that has tables — this failed for 7 schemas (audit,
    billing, bse, concepts, education, notify, signal) before the 0052 fix. Also asserts the
    centralized APP_SCHEMAS equals the schemas that actually have tables, so adding a schema (or a
    typo like notif→notify) without granting it fails here instead of in prod."""
    rows = (
        await db_session.execute(
            text(
                "SELECT table_schema, min(table_name) AS t FROM information_schema.tables "
                "WHERE table_type = 'BASE TABLE' "
                "AND table_schema NOT IN ('pg_catalog', 'information_schema', 'public') "
                "AND table_schema NOT LIKE '\\_timescaledb%' "
                "GROUP BY table_schema"
            )
        )
    ).all()
    table_by_schema = {s: t for s, t in rows}
    real_schemas = set(table_by_schema)

    # No drift: the single-source constant == the schemas that actually have tables. (The test DB
    # is built by ORM create_all, so every app schema needs a registered model in conftest's
    # db_tables — which is already required for the suite to run; a future raw-SQL-only schema must
    # add its model there too, the same place the grant set is derived from.)
    assert real_schemas == set(APP_SCHEMAS), (
        f"APP_SCHEMAS drift — ungranted-schema-with-tables={real_schemas - set(APP_SCHEMAS)}, "
        f"phantom-in-APP_SCHEMAS={set(APP_SCHEMAS) - real_schemas}"
    )

    # dhanradar_app can SELECT a table in each (would 'permission denied' for an ungranted schema).
    for schema, table in table_by_schema.items():
        await app_session.execute(text(f'SELECT 1 FROM "{schema}"."{table}" LIMIT 1'))
    await app_session.rollback()


async def test_app_role_cannot_mutate_audit_ledger(db_session, app_session):
    """Audit tables are append-only (SEBI 7-yr / DPDP): dhanradar_app may INSERT + SELECT but must
    NOT UPDATE or DELETE (the 0052 REVOKE — DB-level enforcement until the immutability trigger
    ships). Checked via has_table_privilege so no real audit row is touched."""
    audit_table = await db_session.scalar(
        text(
            "SELECT format('%I.%I', table_schema, table_name) FROM information_schema.tables "
            "WHERE table_schema = 'audit' AND table_type = 'BASE TABLE' ORDER BY table_name LIMIT 1"
        )
    )
    assert audit_table is not None, "expected at least one audit table"
    privs = {}
    for p in ("INSERT", "SELECT", "UPDATE", "DELETE"):
        privs[p] = await app_session.scalar(
            text("SELECT has_table_privilege(:t, :p)").bindparams(t=audit_table, p=p)
        )
    assert privs == {"INSERT": True, "SELECT": True, "UPDATE": False, "DELETE": False}, privs


async def test_app_role_normal_crud_works(db_session, app_session):
    """Sanity: the de-superusered role still has full DML on personal tables (no outage)."""
    user, pf, _ = await _seed_owner(db_session, email="b80-crud@test.dev")
    await app_session.execute(
        text(
            "INSERT INTO mf.mf_user_holdings (user_id, portfolio_id, isin, folio_number, units, source) "
            "VALUES (:u, :p, 'INFCRUD', 'F1', 5, 'cas')"
        ),
        {"u": str(user.id), "p": str(pf.id)},
    )
    cnt = await app_session.scalar(
        text("SELECT count(*) FROM mf.mf_user_holdings WHERE portfolio_id = :p"), {"p": str(pf.id)}
    )
    assert cnt == 1
    await app_session.execute(
        text("UPDATE mf.mf_user_holdings SET units = 6 WHERE portfolio_id = :p"), {"p": str(pf.id)}
    )
    await app_session.execute(
        text("DELETE FROM mf.mf_user_holdings WHERE portfolio_id = :p"), {"p": str(pf.id)}
    )
    await app_session.rollback()
