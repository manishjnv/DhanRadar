"""B81 PR-2 — RLS owner-isolation for the signal / notify / auth / compliance personal tables, plus
the CAS multi-commit per-user-GUC hardening. All run AS dhanradar_app (app_session — NOSUPERUSER,
NOBYPASSRLS, not the table owner), each defeats the same 3 false-green traps PR-1 documented:

  (a) RLS is skipped for superuser/owner/BYPASSRLS → tests run AS dhanradar_app (the fixture-identity
      guard in test_rls_owner_isolation.py asserts that), never the owner/admin.
  (b) An unset app.user_id denies ALL rows → every isolation test has a POSITIVE control (the owner
      sees their OWN row too), so a deny-all can't masquerade as isolation.
  (c) create_all does NOT run the migration → conftest applies the SAME rls_statements over
      RLS_ENFORCED (now all 18 tables), and the existing pg_catalog-reality test asserts it.

The "reader-works-under-RLS" tests prove the BYPASSRLS admin engine (which the signal Celery jobs, the
notification drain, the Razorpay webhook and the admin routes were wired onto) returns the non-empty
cross-user result the app engine would silently empty. The CAS tests prove rls_user_session keeps one
owner GUC across the pipeline's multi-commit flow.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from dhanradar.db_security import rls_user_session, set_rls_user
from dhanradar.models.auth import User

pytestmark = pytest.mark.integration


# --- one representative owner-scoped table per subsystem -------------------------------------------


@dataclass(frozen=True)
class _Case:
    table: str          # schema.table under FORCE RLS
    insert_owned: str    # INSERT one row owned by :u (a row whose user_id = :u)


_CASES: list[_Case] = [
    _Case(
        "signal.signal_rules",
        "INSERT INTO signal.signal_rules (user_id, nifty_threshold, vix_threshold, breadth_threshold, "
        "deploy_ladder) VALUES (:u, -5, 20, 0.8, '[]'::jsonb)",
    ),
    _Case(
        "signal.signal_dip_fund",
        "INSERT INTO signal.signal_dip_fund (user_id) VALUES (:u)",
    ),
    _Case(
        "signal.signal_deployments",
        "INSERT INTO signal.signal_deployments (user_id, date) VALUES (:u, DATE '2026-01-01')",
    ),
    _Case(
        "signal.signal_journal",
        "INSERT INTO signal.signal_journal (user_id, date) VALUES (:u, DATE '2026-01-01')",
    ),
    _Case(
        "notify.notification_preferences",
        "INSERT INTO notify.notification_preferences (user_id) VALUES (:u)",
    ),
    _Case(
        "auth.subscriptions",
        "INSERT INTO auth.subscriptions (user_id, plan, status) VALUES (:u, 'plus', 'active')",
    ),
    _Case(
        "compliance.ai_output_feedback",
        "INSERT INTO compliance.ai_output_feedback (audit_id, user_id, helpful) "
        "VALUES (gen_random_uuid(), :u, true)",
    ),
]
_IDS = [c.table for c in _CASES]


# --- cleanup: the non-FK tables (signal.*, ai_output_feedback) are NOT reached by db_session's -----
#     auth.users CASCADE truncate, so wipe all PR-2 tables after each test to avoid cross-test bleed.


@pytest_asyncio.fixture(autouse=True)
async def _truncate_pr2_tables(db_session):
    yield
    await db_session.execute(
        text(
            "TRUNCATE TABLE signal.signal_rules, signal.signal_dip_fund, signal.signal_deployments, "
            "signal.signal_journal, signal.signal_notifications, notify.notification_preferences, "
            "notify.notification_log, auth.subscriptions, auth.user_activity_log, "
            "compliance.ai_output_feedback RESTART IDENTITY CASCADE"
        )
    )
    await db_session.commit()


async def _seed_two_users(db_session) -> tuple[str, str]:
    """Two real auth.users (committed so the app/admin connections — separate sessions — see them and
    the FK-bearing tables satisfy their FK before RLS is even evaluated)."""
    a = User(email="rls2-a@test.dev")
    b = User(email="rls2-b@test.dev")
    db_session.add_all([a, b])
    await db_session.flush()
    ids = (str(a.id), str(b.id))
    await db_session.commit()
    return ids


async def _seed_user(db_session, email: str) -> str:
    u = User(email=email)
    db_session.add(u)
    await db_session.flush()
    uid = str(u.id)
    await db_session.commit()
    return uid


async def _visible_user_ids(session, table: str) -> set[str]:
    rows = (
        await session.execute(text(f"SELECT DISTINCT user_id::text AS uid FROM {table}"))
    ).scalars().all()
    return set(rows)


# --- trap (b): isolation WITH positive control, per subsystem --------------------------------------


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
async def test_owner_isolation_with_positive_control(case, db_session, app_session):
    a, b = await _seed_two_users(db_session)
    # Seed one row for each owner via the superuser session (bypasses RLS — it can write any user_id).
    await db_session.execute(text(case.insert_owned), {"u": a})
    await db_session.execute(text(case.insert_owned), {"u": b})
    await db_session.commit()

    await set_rls_user(app_session, a)
    seen_a = await _visible_user_ids(app_session, case.table)
    assert a in seen_a, f"{case.table}: POSITIVE control failed (A can't see A's own row — deny-all?)"
    assert b not in seen_a, f"{case.table}: ISOLATION failed (A sees B's row)"
    await app_session.rollback()

    await set_rls_user(app_session, b)
    seen_b = await _visible_user_ids(app_session, case.table)
    assert b in seen_b, f"{case.table}: POSITIVE control failed for B"
    assert a not in seen_b, f"{case.table}: ISOLATION failed (B sees A's row)"
    await app_session.rollback()


# --- trap: unset GUC denies all (no 500) ----------------------------------------------------------


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
async def test_unset_guc_denies_all_without_error(case, db_session, app_session):
    a, _ = await _seed_two_users(db_session)
    await db_session.execute(text(case.insert_owned), {"u": a})
    await db_session.commit()
    # No set_rls_user → app.user_id unset → NULLIF(NULL,'')::uuid = NULL → user_id = NULL is FALSE →
    # deny-all (fail-SAFE), no 500 (the NULLIF guards against ''::uuid).
    seen = await _visible_user_ids(app_session, case.table)
    assert seen == set()
    await app_session.rollback()


# --- WITH CHECK: cross-owner insert rejected ------------------------------------------------------


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
async def test_with_check_rejects_foreign_owner(case, db_session, app_session):
    # Seed only the users (so the FK is satisfiable → the rejection is RLS, not FK), NOT the row.
    a, b = await _seed_two_users(db_session)
    await set_rls_user(app_session, b)
    with pytest.raises(DBAPIError) as exc:
        await app_session.execute(text(case.insert_owned), {"u": a})
    assert "row-level security" in str(exc.value).lower(), f"{case.table}: not an RLS rejection"
    await app_session.rollback()


# --- reader-works-under-RLS: the BYPASSRLS engine sees cross-user; the app engine is scoped --------
#     (proves the signal Celery jobs / notification drain / webhook / admin routes — all on the admin
#      engine — get a NON-EMPTY cross-user result, while the app engine would silently empty.)


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
async def test_admin_bypass_sees_all_app_is_scoped(case, db_session, app_session, admin_session):
    a, b = await _seed_two_users(db_session)
    await db_session.execute(text(case.insert_owned), {"u": a})
    await db_session.execute(text(case.insert_owned), {"u": b})
    await db_session.commit()

    admin_seen = await _visible_user_ids(admin_session, case.table)
    assert {a, b} <= admin_seen, f"{case.table}: BYPASSRLS reader did NOT see all owners"
    await admin_session.rollback()

    await set_rls_user(app_session, a)
    app_seen = await _visible_user_ids(app_session, case.table)
    assert app_seen == {a}, f"{case.table}: app engine not scoped to A"
    await app_session.rollback()


# --- CAS hardening: rls_user_session keeps ONE owner GUC across the pipeline's multi-commit flow ---

_INS_PF = "INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, :n)"


async def test_rls_user_session_survives_multi_commit(db_session):
    """The CAS pipeline commits 3+ times (and per fund inside append_score_history). rls_user_session
    re-applies the owner GUC on every transaction begin, so a write AFTER a commit still passes WITH
    CHECK — this is what makes the multi-commit CAS pipeline RLS-enforced instead of bypassed."""
    a = await _seed_user(db_session, "rls2-cas-a@test.dev")
    async with rls_user_session(a) as db:
        await db.execute(text(_INS_PF), {"u": a, "n": "cas-1"})
        await db.commit()
        # Second write is in a NEW transaction (and, under NullPool, a fresh connection) — it only
        # succeeds because after_begin re-applied the GUC.
        await db.execute(text(_INS_PF), {"u": a, "n": "cas-2"})
        await db.commit()
        seen = await _visible_user_ids(db, "mf.mf_portfolios")
        assert seen == {a}


async def test_rls_user_session_rejects_foreign_owner(db_session):
    """A CAS write for a DIFFERENT user_id than the authenticated uploader is rejected by WITH CHECK
    even though the pipeline holds the (legitimately wide-grant) app role."""
    a = await _seed_user(db_session, "rls2-cas-own@test.dev")
    b = await _seed_user(db_session, "rls2-cas-other@test.dev")
    async with rls_user_session(a) as db:
        with pytest.raises(DBAPIError) as exc:
            await db.execute(text(_INS_PF), {"u": b, "n": "evil"})
        assert "row-level security" in str(exc.value).lower()


async def test_rls_user_session_rejects_non_uuid_owner(db_session):
    """rls_user_session validates the owner as a UUID up front — a malformed owner raises (never a
    silently-unscoped bypass write)."""
    with pytest.raises(ValueError):
        async with rls_user_session("not-a-uuid"):
            pass
