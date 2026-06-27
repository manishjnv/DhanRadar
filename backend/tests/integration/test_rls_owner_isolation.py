"""B81 — Row-Level Security (I5) owner-isolation tests, designed to DEFEAT the 3 RLS false-green
traps (see docs/rca B80 + the B81 plan):

  (a) RLS is silently skipped for superuser / table owner / BYPASSRLS — so EVERY isolation test runs
      AS dhanradar_app (NOSUPERUSER, NOBYPASSRLS, not the table owner). The fixture-identity test
      asserts that, so a misconfigured fixture fails LOUDLY instead of vacuously passing.
  (b) An unset app.user_id denies ALL rows, so "B can't see A" can pass because RLS denied
      everything — every isolation test has a POSITIVE control (B sees B's OWN rows too).
  (c) create_all does NOT run migration 0053, so conftest applies the SAME rls_statements the
      migration installs; the migration-exercised test asserts pg_catalog reality, not a constant.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from dhanradar.db_schemas import APP_SCHEMAS
from dhanradar.db_security import (
    AUDIT_EXEMPT,
    PERSONAL_TABLES,
    RLS_ENFORCED,
    set_rls_user,
)
from dhanradar.models.auth import User
from dhanradar.models.mf import MfPortfolio

pytestmark = pytest.mark.integration


async def _seed_user_portfolio(db, email: str):
    user = User(email=email)
    db.add(user)
    await db.flush()
    pf = MfPortfolio(user_id=user.id, name="RLS")
    db.add(pf)
    await db.flush()
    return user, pf


async def _portfolio_ids(session) -> set:
    return set((await session.execute(text("SELECT id FROM mf.mf_portfolios"))).scalars().all())


# --- trap (a): the fixtures must NOT be able to bypass RLS, or every test below is vacuous --------


async def test_fixtures_have_the_right_roles(app_session, admin_session):
    arow = (
        await app_session.execute(
            text("SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        )
    ).one()
    assert arow[0] == "dhanradar_app", "RLS tests MUST run as dhanradar_app"
    assert arow[1] is False, "dhanradar_app must NOT be superuser (would bypass RLS)"
    assert arow[2] is False, "dhanradar_app must NOT be BYPASSRLS"
    await app_session.rollback()

    mrow = (
        await admin_session.execute(
            text("SELECT current_user, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        )
    ).one()
    assert mrow[0] == "dhanradar_admin"
    assert mrow[1] is True, "dhanradar_admin must be BYPASSRLS"
    await admin_session.rollback()


# --- trap (c): prove the MIGRATION's RLS is actually on the tables (pg_catalog reality) ----------


async def test_rls_enabled_forced_and_policied_on_every_enforced_table(db_session):
    for qualified in RLS_ENFORCED:
        schema, table = qualified.split(".")
        row = (
            await db_session.execute(
                text(
                    "SELECT c.relrowsecurity, c.relforcerowsecurity, "
                    "EXISTS (SELECT 1 FROM pg_policies p WHERE p.schemaname = :s AND p.tablename = :t) AS has_policy "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = :s AND c.relname = :t"
                ),
                {"s": schema, "t": table},
            )
        ).one()
        assert row.relrowsecurity is True, f"{qualified}: RLS not ENABLED"
        assert row.relforcerowsecurity is True, f"{qualified}: RLS not FORCED"
        assert row.has_policy is True, f"{qualified}: no policy"


# --- drift-vs-REALITY (B80 lesson) + B83 text-assert ---------------------------------------------


async def test_no_unclassified_user_id_table(db_session):
    """Every table with a user_id column in the app schemas MUST be consciously classified PERSONAL
    or AUDIT_EXEMPT — so a future personal table can't ship silently unprotected."""
    real = set(
        (
            await db_session.execute(
                text(
                    "SELECT n.nspname || '.' || c.relname "
                    "FROM pg_attribute a "
                    "JOIN pg_class c ON c.oid = a.attrelid AND c.relkind = 'r' "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE a.attname = 'user_id' AND a.attnum > 0 AND NOT a.attisdropped "
                    "AND n.nspname = ANY(:schemas)"
                ),
                {"schemas": list(APP_SCHEMAS)},
            )
        ).scalars().all()
    )
    classified = set(PERSONAL_TABLES) | set(AUDIT_EXEMPT)
    assert real <= classified, f"UNCLASSIFIED user_id tables (no RLS, no exemption): {real - classified}"


def test_rls_enforced_is_subset_of_personal():
    assert set(RLS_ENFORCED) <= set(PERSONAL_TABLES)


def test_full_i5_personal_tables_all_enforced():
    """PR-2 completes I5: every classified PERSONAL_TABLE is now FORCE-RLS enforced — no deferred
    personal table. A future personal table added to PERSONAL_TABLES but not RLS_ENFORCED fails here,
    forcing a conscious enforce-now-or-justify decision (the staged PR-1→PR-2 rollout is done)."""
    assert set(RLS_ENFORCED) == set(PERSONAL_TABLES), (
        f"PERSONAL tables not RLS-enforced: {set(PERSONAL_TABLES) - set(RLS_ENFORCED)}"
    )


def test_rls_migrations_table_list_matches_rls_enforced():
    """B83 drift text-assert: the inlined table literals across the RLS migrations (0053 mf.* + 0054
    signal/notify/auth/compliance) == db_security.RLS_ENFORCED, so a table dropped from the constant
    but left in a migration (or vice versa) — in EITHER file — fails CI."""
    versions = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    schema_alt = "|".join(re.escape(s) for s in APP_SCHEMAS)
    pat = re.compile(rf'"((?:{schema_alt})\.[a-z_]+)"')
    found: set[str] = set()
    for fname in (
        "0053_rls_personal_tables_and_admin_role.py",
        "0054_rls_signal_notify_auth_compliance.py",
    ):
        found |= set(pat.findall((versions / fname).read_text(encoding="utf-8")))
    assert found == set(RLS_ENFORCED), f"migration vs RLS_ENFORCED drift: {found ^ set(RLS_ENFORCED)}"


def test_schema_grant_lists_match_app_schemas():
    """B83 drift text-assert: the two FROZEN copies of the app-schema GRANT list — migration 0052's
    `_SCHEMAS` (the prod migration path) and infra/postgres/init/01_init.sql's grant FOREACH ARRAY
    (fresh-volume path) — must equal db_schemas.APP_SCHEMAS. A 14th schema added to APP_SCHEMAS but
    forgotten in either copy is the exact B80 grant-gap recurrence (CI's `migrations` job runs them
    but never connects AS dhanradar_app to notice the missing grant). Pure text assert (no DB)."""
    backend = Path(__file__).resolve().parents[2]
    repo = backend.parent
    expected = set(APP_SCHEMAS)

    mig = (
        backend / "alembic" / "versions" / "0052_app_db_role_grants_real_schemas.py"
    ).read_text(encoding="utf-8")
    mig_block = re.search(r"_SCHEMAS\s*=\s*\[(.*?)\]", mig, re.DOTALL).group(1)
    mig_schemas = set(re.findall(r'"(\w+)"', mig_block))
    assert mig_schemas == expected, f"0052._SCHEMAS drift vs APP_SCHEMAS: {mig_schemas ^ expected}"

    init = (repo / "infra" / "postgres" / "init" / "01_init.sql").read_text(encoding="utf-8")
    init_arr = re.search(r"FOREACH\s+s\s+IN\s+ARRAY\s+ARRAY\[(.*?)\]", init, re.DOTALL).group(1)
    init_schemas = set(re.findall(r"'(\w+)'", init_arr))
    assert init_schemas == expected, f"01_init.sql grant list drift vs APP_SCHEMAS: {init_schemas ^ expected}"


# --- trap (b): isolation WITH positive control (AS dhanradar_app) ---------------------------------


async def test_owner_isolation_with_positive_control(db_session, app_session):
    a, pa = await _seed_user_portfolio(db_session, "rls-a@test.dev")
    b, pb = await _seed_user_portfolio(db_session, "rls-b@test.dev")
    await db_session.commit()

    await set_rls_user(app_session, str(a.id))
    seen_a = await _portfolio_ids(app_session)
    assert pa.id in seen_a, "POSITIVE control failed: A cannot see A's own row (RLS denied everything?)"
    assert pb.id not in seen_a, "ISOLATION failed: A can see B's row"
    await app_session.rollback()

    await set_rls_user(app_session, str(b.id))
    seen_b = await _portfolio_ids(app_session)
    assert pb.id in seen_b, "POSITIVE control failed: B cannot see B's own row"
    assert pa.id not in seen_b, "ISOLATION failed: B can see A's row"
    await app_session.rollback()


async def test_unset_guc_denies_all_without_error(db_session, app_session):
    await _seed_user_portfolio(db_session, "rls-unset@test.dev")
    await db_session.commit()
    # No set_rls_user → app.user_id unset → NULLIF(NULL,'')::uuid = NULL → user_id = NULL is FALSE
    # → deny-all (fail-SAFE), and NO 500 (the NULLIF guards against ''::uuid).
    seen = await _portfolio_ids(app_session)
    assert seen == set()
    await app_session.rollback()


async def test_with_check_rejects_foreign_owner(db_session, app_session):
    a, _ = await _seed_user_portfolio(db_session, "rls-wc-a@test.dev")
    b, _ = await _seed_user_portfolio(db_session, "rls-wc-b@test.dev")
    await db_session.commit()
    await set_rls_user(app_session, str(b.id))
    with pytest.raises(DBAPIError) as exc:
        await app_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'evil')"),
            {"u": str(a.id)},
        )
    assert "row-level security" in str(exc.value).lower()
    await app_session.rollback()


# --- bypass scoping: admin sees all, app does NOT (reader-works-under-RLS proof) ------------------


async def test_admin_bypass_sees_all_app_does_not(db_session, app_session, admin_session):
    a, pa = await _seed_user_portfolio(db_session, "rls-byp-a@test.dev")
    b, pb = await _seed_user_portfolio(db_session, "rls-byp-b@test.dev")
    await db_session.commit()

    # The admin/Celery-aggregate engine (BYPASSRLS) sees EVERY owner's rows — non-empty cross-user
    # read (proves the rescore/refresh/admin readers won't silently empty on the admin engine).
    admin_seen = await _portfolio_ids(admin_session)
    assert pa.id in admin_seen and pb.id in admin_seen
    await admin_session.rollback()

    # Contrast: the normal app role scoped to A sees ONLY A's.
    await set_rls_user(app_session, str(a.id))
    app_seen = await _portfolio_ids(app_session)
    assert pa.id in app_seen and pb.id not in app_seen
    await app_session.rollback()
