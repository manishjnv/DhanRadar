"""
DhanRadar — Admin Users Pydantic schemas (Phase 2).

Separate from ops_schemas.py (which owns the MF/health operational surface)
and billing_schemas.py (which owns billing reads). These schemas serve the
user-management read endpoints: summary, list, detail, and audit log.

Load-bearing classification: this file is a LOAD-BEARING path (extends the
admin surface). Every change requires Opus line-by-line diff review before merge.

ABSENT fields (model gaps — do NOT add columns without a migration):
  - display_name: ABSENT from auth.users → derived as email.split('@')[0]
  - login_history: no user_activity_log table → always [] (deferred)

Fields wired by migration 0044:
  - last_login_at: auth.users.last_login_at (NULLABLE; set on genuine logins)
  - cas_uploads: live query on mf.mf_cas_jobs for the user
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
    # Deferred — requires a dedicated auth events table (no user_activity_log yet)
    login_history: list[Any]
    # Live query on mf.mf_cas_jobs (migration 0044 wiring). Each entry is a
    # dict with: job_id, status, created_at, completed_at, error_message, portfolio_id.
    cas_uploads: list[Any]


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------


class AuditLogItem(BaseModel):
    """One row from audit.admin_actions."""

    id: str
    ts: datetime
    admin_id: str
    action: str
    target_type: str | None = None
    target_id: str | None = None
    result: str | None = None
    request_id: str | None = None


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
