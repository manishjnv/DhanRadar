"""
DhanRadar — Admin "Account deletions" console (DPDP B79 follow-up).

Read-only: shows every pending deletion request with its erase-window status
(waiting / ready / overdue), the last 90 days of hard erasures (identity-free —
once erased there is nothing left to show), the retention policy in plain
words, and the monthly retention job's last run.

RequireAdmin() (404 to non-admins — surface-hiding). All periods come from
compliance.data_policy — the single source of truth (never hardcoded here).

Module isolation (#7): reads auth.users (deletion_requested_at) and
audit.admin_actions (via audit.service.list_admin_actions) — the same tables
admin/users_router.py already reads for the same purpose. No cross-module
JOIN/INSERT; retention-job info reads mf.ingestion_runs by task_name, the same
pattern admin/ops_router.py's GET /admin/tasks uses.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.audit.service import list_admin_actions
from dhanradar.compliance.data_policy import ERASURE_DUE, ERASURE_WAIT, RETENTION_BY_TABLE
from dhanradar.db import get_admin_db
from dhanradar.deps import RequireAdmin, UserContext
from dhanradar.models.auth import User
from dhanradar.models.mf import MfIngestionRun

from ._people import resolve_user_emails
from .deletions_schemas import (
    AdminDeletionsResponse,
    DeletionsPolicy,
    PendingDeletion,
    RecentErasure,
    RetentionJobStatus,
    RetentionRow,
)

router = APIRouter(prefix="/admin", tags=["admin-deletions"])

# Plain-word labels for the retention table (admin UI convention: no raw
# schema-qualified table names on the surface).
_RETENTION_LABELS: dict[str, str] = {
    "consent.consent_audit_log": "Consent records",
    "compliance.ai_recommendation_audit": "AI output records",
    "audit.payment_events": "Payment records",
    "audit.security_events": "Security logs",
    "audit.admin_actions": "Admin action logs",
}

# Matches the result string written by admin/users_router.py's erase_user:
# f"erased:{sum(counts.values())}_rows"
_ERASED_ROWS_RE = re.compile(r"^erased:(\d+)_rows$")

# The monthly retention-purge Celery task (registered in celery_app.py's beat
# schedule by another builder; this reads its ingestion_runs rows by name only —
# no coupling to the beat registry itself, so it degrades to `null` cleanly if
# the task has never run).
_RETENTION_TASK_NAME = "dhanradar.tasks.compliance.retention_purge"

_RECENT_ERASURES_WINDOW_DAYS = 90


def _parse_rows_removed(result: str | None) -> int | None:
    if not result:
        return None
    m = _ERASED_ROWS_RE.match(result)
    return int(m.group(1)) if m else None


@router.get("/deletions", response_model=AdminDeletionsResponse)
async def get_deletions(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
) -> AdminDeletionsResponse:
    now = datetime.now(UTC)

    # ── Pending deletions — oldest first ────────────────────────────────────
    pending_result = await db.execute(
        select(User.id, User.email, User.deletion_requested_at)
        .where(User.deletion_requested_at.isnot(None))
        .order_by(User.deletion_requested_at.asc())
    )
    pending: list[PendingDeletion] = []
    for uid, email, requested_at in pending_result.all():
        earliest_erase_at = requested_at + ERASURE_WAIT
        erase_by = requested_at + ERASURE_DUE
        age = now - requested_at
        item_status: Literal["waiting", "ready", "overdue"]
        if age > ERASURE_DUE:
            item_status = "overdue"
        elif age >= ERASURE_WAIT:
            item_status = "ready"
        else:
            item_status = "waiting"
        pending.append(
            PendingDeletion(
                user_id=str(uid),
                email=email,
                requested_at=requested_at,
                earliest_erase_at=earliest_erase_at,
                erase_by=erase_by,
                status=item_status,
            )
        )

    # ── Recent erasures — last 90 days, newest first ────────────────────────
    since = now - timedelta(days=_RECENT_ERASURES_WINDOW_DAYS)
    erasure_rows = await list_admin_actions(
        db, action="erase_user", since=since, limit=500, offset=0
    )
    admin_ids = {row.get("admin_id") for row in erasure_rows}
    emails = await resolve_user_emails(db, admin_ids)
    recent_erasures = [
        RecentErasure(
            erased_at=row["ts"],
            rows_removed=_parse_rows_removed(row.get("result")),
            erased_by=emails.get(str(row.get("admin_id")), "Admin"),
        )
        for row in erasure_rows
    ]

    # ── Policy (plain words) ────────────────────────────────────────────────
    retention = [
        RetentionRow(label=_RETENTION_LABELS.get(table, table), keep_days=td.days)
        for table, td in RETENTION_BY_TABLE.items()
    ]
    policy = DeletionsPolicy(
        erase_wait_days=ERASURE_WAIT.days,
        erase_due_days=ERASURE_DUE.days,
        retention=retention,
    )

    # ── Retention job — last run of the monthly purge, if it has ever run ──
    job_row = (
        await db.execute(
            select(MfIngestionRun)
            .where(MfIngestionRun.task_name == _RETENTION_TASK_NAME)
            .order_by(MfIngestionRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    retention_job = (
        RetentionJobStatus(
            last_run_at=(job_row.finished_at or job_row.started_at).isoformat(),
            result=job_row.status,
        )
        if job_row is not None
        else None
    )

    return AdminDeletionsResponse(
        pending=pending,
        recent_erasures=recent_erasures,
        policy=policy,
        retention_job=retention_job,
    )
