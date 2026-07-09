"""
DhanRadar — Admin Users Pydantic schemas (Phase 2).

Separate from ops_schemas.py (which owns the MF/health operational surface)
and billing_schemas.py (which owns billing reads). These schemas serve the
user-management read endpoints: summary, list, detail, audit log, and the
per-user / global activity feed.

Load-bearing classification: this file is a LOAD-BEARING path (extends the
admin surface). Every change requires Opus line-by-line diff review before merge.

Fields wired by migration 0044:
  - last_login_at: auth.users.last_login_at (NULLABLE; set on genuine logins)
  - cas_uploads: live query on mf.mf_cas_jobs for the user

Fields wired by migration 0045:
  - login_history: live query on auth.user_activity_log (UserDetailResponse)
  - ActivityEventRow: global recent-logins feed (GET /admin/users/activity)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# User Summary
# ---------------------------------------------------------------------------


class UserSummaryResponse(BaseModel):
    """Aggregate counts for the users summary card."""

    total: int
    active: int
    premium: int
    trials: int
    blocked: int  # users with deletion_requested_at IS NOT NULL


# ---------------------------------------------------------------------------
# User List
# ---------------------------------------------------------------------------


class UserListItem(BaseModel):
    """One row in the paginated user list."""

    id: str
    email: str
    # ABSENT from auth.users — derived as email.split('@')[0]
    display_name: str
    tier: str
    # 'active' | 'deletion_requested' — derived from deletion_requested_at
    status: str
    # Populated from auth.users.last_login_at (migration 0044). NULL for users
    # who have not logged in since the column was added.
    last_login_at: datetime | None = None
    created_at: datetime


class UserListResponse(BaseModel):
    total: int
    users: list[UserListItem]


# ---------------------------------------------------------------------------
# User Detail
# ---------------------------------------------------------------------------


class UserDetailResponse(BaseModel):
    """Full detail view for one user."""

    id: str
    email: str
    # ABSENT from auth.users — derived as email.split('@')[0]
    display_name: str
    tier: str
    # 'active' | 'deletion_requested' | 'suspended'
    status: str
    created_at: datetime
    # auth.users.last_login_at (migration 0044). NULL until the user's first
    # genuine login since the column was added (no backfill).
    last_login_at: datetime | None = None
    pro_access_until: datetime | None = None
    pro_access_reason: str | None = None
    risk_profile: str | None = None
    dpdp_consent_version: str | None = None
    # Set when account is administratively suspended; None when active.
    suspended_at: str | None = None
    # Most recent subscription dict or None (from billing.service.get_user_subscription)
    subscription: dict[str, Any] | None = None
    # Payment events from audit.payment_events (from audit.service.list_payment_events)
    payments: list[dict[str, Any]]
    # Live query on auth.user_activity_log (migration 0045). Each entry is a
    # dict with: event_type, method, occurred_at (ISO string), request_id.
    login_history: list[Any]
    # Live query on mf.mf_cas_jobs (migration 0044 wiring). Each entry is a
    # dict with: job_id, status, created_at, completed_at, error_message, portfolio_id.
    cas_uploads: list[Any]


# ---------------------------------------------------------------------------
# Activity Feed (migration 0045 — auth.user_activity_log)
# ---------------------------------------------------------------------------


class ActivityEventRow(BaseModel):
    """One row in the global recent-logins feed (GET /admin/users/activity)."""

    user_id: str
    email: str
    event_type: str
    method: str | None
    occurred_at: str  # ISO 8601 string — set by the router via .isoformat()


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------


class AuditLogItem(BaseModel):
    """One row from audit.admin_actions.

    admin_email / target_label are display-only enrichments resolved by the
    router (audit.admin_actions itself stores raw ids and stays isolated).
    Either may be None when the id no longer resolves (e.g. deleted user).
    """

    id: str
    ts: datetime
    admin_id: str
    action: str
    target_type: str | None = None
    target_id: str | None = None
    result: str | None = None
    request_id: str | None = None
    admin_email: str | None = None
    target_label: str | None = None


# ---------------------------------------------------------------------------
# Suspend / Unsuspend
# ---------------------------------------------------------------------------


class SuspendRequest(BaseModel):
    """Body for POST /admin/users/{user_id}/suspend."""

    reason: str | None = None


class UserActionResponse(BaseModel):
    """Response for suspend / unsuspend endpoints."""

    ok: bool
    status: str
