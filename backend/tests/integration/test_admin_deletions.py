"""Integration tests — Admin "Account deletions" console (DPDP B79 follow-up).

Covers:
  - GET /admin/deletions: 404 for anonymous/non-admin (surface-hiding)
  - status derivation (waiting / ready / overdue) via backdated
    deletion_requested_at, against compliance.data_policy's real periods
  - recent_erasures parsing of audit.admin_actions.result, incl. a malformed
    result string (rows_removed -> null, not a crash)
  - policy numbers equal compliance.data_policy exactly (never hardcoded)
  - alert derivation (_derive_admin_alerts): amber "ready" + red "overdue"

Infrastructure: db_session, async_client, make_auth_headers — mirrors
test_b79_hard_erasure.py's admin-auth pattern.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from dhanradar.admin.ops_router import _derive_admin_alerts
from dhanradar.audit.service import record_admin_action
from dhanradar.compliance.data_policy import ERASURE_DUE, ERASURE_WAIT, RETENTION_BY_TABLE
from dhanradar.models.auth import User

pytestmark = pytest.mark.integration


async def _signup(client, email: str, password: str = "DeletionsTest42!") -> tuple[str, str]:
    from tests.conftest import extract_cookie

    r = await client.post("/api/v1/auth/signup", json={"email": email, "password": password})
    assert r.status_code in (200, 201), r.text
    return str(r.json()["user"]["id"]), extract_cookie(r, "__Host-access")


async def _make_admin_headers(async_client, monkeypatch, email: str) -> dict:
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, admin_access = await _signup(async_client, email)
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    return make_auth_headers(access_token=admin_access)


# ---------------------------------------------------------------------------
# Surface-hiding
# ---------------------------------------------------------------------------


async def test_deletions_404_for_anonymous(async_client):
    r = await async_client.get("/api/v1/admin/deletions")
    assert r.status_code == 404


async def test_deletions_404_for_non_admin(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")
    _uid, access = await _signup(async_client, "nonadmin_deletions@example.com")
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/deletions", headers=headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Status derivation — waiting / ready / overdue
# ---------------------------------------------------------------------------


async def test_pending_status_waiting_ready_overdue(async_client, monkeypatch, db_session):
    headers = await _make_admin_headers(async_client, monkeypatch, "admin_del_status@example.com")

    now = datetime.now(UTC)
    waiting = User(email="waiting@example.com", deletion_requested_at=now - timedelta(days=1))
    ready = User(email="ready@example.com", deletion_requested_at=now - ERASURE_WAIT - timedelta(hours=1))
    overdue = User(email="overdue@example.com", deletion_requested_at=now - ERASURE_DUE - timedelta(days=1))
    db_session.add_all([waiting, ready, overdue])
    await db_session.commit()

    r = await async_client.get("/api/v1/admin/deletions", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    by_email = {row["email"]: row for row in body["pending"]}
    assert by_email["waiting@example.com"]["status"] == "waiting"
    assert by_email["ready@example.com"]["status"] == "ready"
    assert by_email["overdue@example.com"]["status"] == "overdue"

    # Oldest first.
    emails_in_order = [row["email"] for row in body["pending"]]
    assert emails_in_order.index("overdue@example.com") < emails_in_order.index("ready@example.com")
    assert emails_in_order.index("ready@example.com") < emails_in_order.index("waiting@example.com")

    # earliest_erase_at / erase_by derive from the requested_at + policy periods.
    row = by_email["waiting@example.com"]
    requested_at = datetime.fromisoformat(row["requested_at"].replace("Z", "+00:00"))
    earliest = datetime.fromisoformat(row["earliest_erase_at"].replace("Z", "+00:00"))
    erase_by = datetime.fromisoformat(row["erase_by"].replace("Z", "+00:00"))
    assert earliest == requested_at + ERASURE_WAIT
    assert erase_by == requested_at + ERASURE_DUE


# ---------------------------------------------------------------------------
# Recent erasures — result-string parsing, incl. malformed
# ---------------------------------------------------------------------------


async def test_recent_erasures_parses_rows_removed_and_handles_malformed(
    async_client, monkeypatch, db_session
):
    headers = await _make_admin_headers(async_client, monkeypatch, "admin_del_erasures@example.com")

    await record_admin_action(
        admin_id="11111111-1111-1111-1111-111111111111",
        action="erase_user",
        target_type="user",
        target_id="22222222-2222-2222-2222-222222222222",
        result="erased:7_rows",
    )
    await record_admin_action(
        admin_id="11111111-1111-1111-1111-111111111111",
        action="erase_user",
        target_type="user",
        target_id="33333333-3333-3333-3333-333333333333",
        result="not_a_recognised_format",
    )
    # A non-erase action must never show up in recent_erasures.
    await record_admin_action(
        admin_id="11111111-1111-1111-1111-111111111111",
        action="suspend_user",
        target_type="user",
        target_id="44444444-4444-4444-4444-444444444444",
        result="suspended",
    )

    r = await async_client.get("/api/v1/admin/deletions", headers=headers)
    assert r.status_code == 200, r.text
    erasures = r.json()["recent_erasures"]
    assert len(erasures) == 2

    rows_removed = {e["rows_removed"] for e in erasures}
    assert 7 in rows_removed
    assert None in rows_removed  # malformed result -> null, not a crash

    # No user identity is ever returned (nothing to leak — the row is gone).
    for e in erasures:
        assert "user_id" not in e
        assert "email" not in e


# ---------------------------------------------------------------------------
# Policy numbers — always sourced from compliance.data_policy
# ---------------------------------------------------------------------------


async def test_policy_matches_data_policy_constants(async_client, monkeypatch):
    headers = await _make_admin_headers(async_client, monkeypatch, "admin_del_policy@example.com")

    r = await async_client.get("/api/v1/admin/deletions", headers=headers)
    assert r.status_code == 200, r.text
    policy = r.json()["policy"]

    assert policy["erase_wait_days"] == ERASURE_WAIT.days
    assert policy["erase_due_days"] == ERASURE_DUE.days
    assert len(policy["retention"]) == len(RETENTION_BY_TABLE)
    keep_days = {row["keep_days"] for row in policy["retention"]}
    assert keep_days == {td.days for td in RETENTION_BY_TABLE.values()}
    # Plain-word labels, not raw schema-qualified table names.
    for row in policy["retention"]:
        assert "." not in row["label"]


async def test_retention_job_null_when_never_run(async_client, monkeypatch):
    headers = await _make_admin_headers(async_client, monkeypatch, "admin_del_job@example.com")

    r = await async_client.get("/api/v1/admin/deletions", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["retention_job"] is None


# ---------------------------------------------------------------------------
# Alert derivation — amber "ready" + red "overdue"
# ---------------------------------------------------------------------------


async def test_alerts_flag_ready_and_overdue_deletions(db_session):
    now = datetime.now(UTC)
    ready = User(email="alert-ready@example.com", deletion_requested_at=now - ERASURE_WAIT - timedelta(hours=1))
    overdue = User(email="alert-overdue@example.com", deletion_requested_at=now - ERASURE_DUE - timedelta(days=1))
    db_session.add_all([ready, overdue])
    await db_session.commit()

    alerts = await _derive_admin_alerts(db_session)
    keys = {a.key for a in alerts}
    assert "deletions_ready" in keys
    assert "deletions_overdue" in keys

    ready_alert = next(a for a in alerts if a.key == "deletions_ready")
    overdue_alert = next(a for a in alerts if a.key == "deletions_overdue")
    assert ready_alert.severity == "warning"
    assert overdue_alert.severity == "critical"
    assert ready_alert.href == "/admin/deletions"
    assert overdue_alert.href == "/admin/deletions"
    # An overdue request is counted once (overdue), never also as ready.
    assert ready_alert.title.startswith("1 ")
    assert overdue_alert.title.startswith("1 ")


async def test_alerts_silent_when_no_pending_deletions(db_session):
    alerts = await _derive_admin_alerts(db_session)
    keys = {a.key for a in alerts}
    assert "deletions_ready" not in keys
    assert "deletions_overdue" not in keys
