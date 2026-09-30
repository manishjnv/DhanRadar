"""Migration 0085 — DPDP/SEBI monthly retention purge.

Exercises the REAL DB objects the migration installs (mirrored into conftest's `db_tables`
fixture, since create_all() never runs Alembic — same pattern as 0052/0053's grant tests):

  * `compliance.retention_policy()` intervals == `dhanradar.compliance.data_policy.RETENTION_BY_TABLE`.
  * `compliance.retention_purge()` deletes only rows older than each table's period.
  * Neither runtime role (dhanradar_app, dhanradar_admin) has a general DELETE on any of the
    5 tables — including consent.consent_audit_log, which had NO per-table revoke before this
    migration (it only inherited the schema-wide `consent` grant).
  * dhanradar_admin (the role Celery's `admin_task_session` connects as) CAN call the function
    despite that, via EXECUTE + SECURITY DEFINER.
  * The Celery task (`dhanradar.tasks.compliance.retention_purge`) returns a per-table summary.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from dhanradar.compliance.data_policy import RETENTION_BY_TABLE

pytestmark = pytest.mark.integration

_NOW = datetime.now(UTC)


@pytest.fixture(autouse=True)
async def _truncate_audit_tables(db_session):
    """Same-connection truncate after each test (test_compliance.py pattern) — db_session's
    own teardown only handles consent.consent_audit_log/education/news/auth/billing; these 4
    tables have no FK to auth.users so nothing else clears them between tests in this file."""
    yield
    await db_session.rollback()
    await db_session.execute(
        text(
            "TRUNCATE TABLE compliance.ai_recommendation_audit, audit.payment_events, "
            "audit.security_events, audit.admin_actions RESTART IDENTITY CASCADE"
        )
    )
    await db_session.commit()


async def _seed(db_session) -> None:
    old = _NOW - timedelta(days=1)  # older than every period below
    recent = _NOW - timedelta(hours=1)
    uid = str(uuid4())

    for created_at, tag in ((old, "old"), (recent, "recent")):
        # consent.consent_audit_log — period 2922d, so shift far past it for "old".
        await db_session.execute(
            text(
                "INSERT INTO consent.consent_audit_log (user_id, purpose, action, created_at) "
                "VALUES (:u, 'test', 'grant', :ts)"
            ),
            {"u": uid, "ts": _cutoff("consent.consent_audit_log", tag)},
        )
        # compliance.ai_recommendation_audit — served_at is the retained column.
        await db_session.execute(
            text(
                "INSERT INTO compliance.ai_recommendation_audit "
                "(served_at, recommendation_type, content_hash, disclaimer_version) "
                "VALUES (:ts, 'educational_label', :h, 'v1')"
            ),
            {"ts": _cutoff("compliance.ai_recommendation_audit", tag), "h": f"{tag}-{uuid4().hex}"},
        )
        await db_session.execute(
            text(
                "INSERT INTO audit.payment_events (ts, user_id, status, row_hash) "
                "VALUES (:ts, :u, 'captured', :h)"
            ),
            {"ts": _cutoff("audit.payment_events", tag), "u": uid, "h": f"{tag}-{uuid4().hex}"},
        )
        await db_session.execute(
            text(
                "INSERT INTO audit.security_events (ts, event_type, row_hash) "
                "VALUES (:ts, 'login_success', :h)"
            ),
            {"ts": _cutoff("audit.security_events", tag), "h": f"{tag}-{uuid4().hex}"},
        )
        await db_session.execute(
            text(
                "INSERT INTO audit.admin_actions (ts, admin_id, action, result, row_hash) "
                "VALUES (:ts, 'admin1', 'activate_scoring_model', 'ok', :h)"
            ),
            {"ts": _cutoff("audit.admin_actions", tag), "h": f"{tag}-{uuid4().hex}"},
        )
    await db_session.commit()


def _cutoff(table: str, tag: str) -> datetime:
    period = RETENTION_BY_TABLE[table]
    if tag == "old":
        return _NOW - period - timedelta(days=1)
    return _NOW - timedelta(hours=1)


_COUNT_SQL = {
    "consent.consent_audit_log": "SELECT count(*) FROM consent.consent_audit_log",
    "compliance.ai_recommendation_audit": "SELECT count(*) FROM compliance.ai_recommendation_audit",
    "audit.payment_events": "SELECT count(*) FROM audit.payment_events",
    "audit.security_events": "SELECT count(*) FROM audit.security_events",
    "audit.admin_actions": "SELECT count(*) FROM audit.admin_actions",
}


async def test_retention_policy_matches_data_policy(db_session):
    rows = (
        await db_session.execute(text("SELECT table_name, retention_interval FROM compliance.retention_policy()"))
    ).all()
    db_policy = {r.table_name: r.retention_interval for r in rows}
    assert set(db_policy) == set(RETENTION_BY_TABLE)
    for table, py_period in RETENTION_BY_TABLE.items():
        assert db_policy[table] == py_period, (table, db_policy[table], py_period)


async def test_purge_deletes_old_keeps_recent(db_session):
    await _seed(db_session)
    for table, sql in _COUNT_SQL.items():
        n = await db_session.scalar(text(sql))
        assert n == 2, f"{table}: expected 2 seeded rows before purge, got {n}"

    result_raw = await db_session.scalar(text("SELECT compliance.retention_purge()::text"))
    import json

    result = json.loads(result_raw)
    for table in RETENTION_BY_TABLE:
        assert result[table] == 1, f"{table}: expected 1 row purged, got {result[table]}"

    await db_session.commit()
    for table, sql in _COUNT_SQL.items():
        n = await db_session.scalar(text(sql))
        assert n == 1, f"{table}: expected 1 row remaining after purge, got {n}"

    # A second run is a clean no-op (idempotent — nothing left old enough to purge).
    result_raw2 = await db_session.scalar(text("SELECT compliance.retention_purge()::text"))
    assert json.loads(result_raw2) == {t: 0 for t in RETENTION_BY_TABLE}


@pytest.mark.parametrize(
    "table",
    [
        "consent.consent_audit_log",
        "compliance.ai_recommendation_audit",
        "audit.payment_events",
        "audit.security_events",
        "audit.admin_actions",
    ],
)
async def test_runtime_roles_cannot_delete_directly(app_session, admin_session, table):
    """Neither dhanradar_app nor dhanradar_admin gets a general DELETE right — the whole
    point of routing the purge through a SECURITY DEFINER function."""
    for session in (app_session, admin_session):
        with pytest.raises(DBAPIError, match="permission denied"):
            await session.execute(text(f"DELETE FROM {table}"))
        await session.rollback()


async def test_admin_role_can_call_purge_function(db_session, admin_session):
    """dhanradar_admin (Celery's cross-user role) CAN call the function despite having no
    direct DELETE — EXECUTE + SECURITY DEFINER is the sanctioned path."""
    await _seed(db_session)
    result_raw = await admin_session.scalar(text("SELECT compliance.retention_purge()::text"))
    await admin_session.commit()
    import json

    result = json.loads(result_raw)
    assert all(result[t] == 1 for t in RETENTION_BY_TABLE), result


async def test_app_role_cannot_call_purge_function(db_session, app_session):
    """dhanradar_app has no EXECUTE grant — only dhanradar_admin (the Celery role for this
    cross-user job) does."""
    with pytest.raises(DBAPIError, match="permission denied"):
        await app_session.execute(text("SELECT compliance.retention_purge()"))
    await app_session.rollback()


async def test_retention_purge_task_summary(db_session, monkeypatch):
    """The Celery task wraps the DB function and returns a readable per-table summary."""
    await _seed(db_session)
    from dhanradar.tasks.compliance import _retention_purge

    summary = await _retention_purge()
    assert summary.startswith("retention_purge: ")
    for table in RETENTION_BY_TABLE:
        assert f"{table}=1" in summary, summary
