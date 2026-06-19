"""
DhanRadar — Admin Users router (Phase 2).

Read-only endpoints for user management and audit log reads.
ALL routes are gated by RequireAdmin() (404 to non-admins — surface-hiding).
NO mutations: no suspend/unsuspend/reset/refund.

Load-bearing classification: LOAD-BEARING path (extends the admin surface,
touches auth.users PII). Every change requires Opus line-by-line diff review
before merge.

Module isolation (#7): user counts / detail via ORM on auth.users (this module
owns admin reads on that table). Subscription data delegated to
billing.service. Payment events delegated to audit.service. No cross-module
JOIN/INSERT.

ABSENT signals (stubbed — no migration required):
  - display_name: ABSENT from auth.users → email.split('@')[0]
  - last_login_at: ABSENT → always None (TODO: no user_activity_log table)
  - login_history: always [] (no user_activity_log table)
  - cas_uploads: always [] (no CAS upload query wired yet)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.audit.service import list_admin_actions, list_payment_events
from dhanradar.billing.service import get_user_subscription
from dhanradar.db import get_db
from dhanradar.deps import RequireAdmin, UserContext
from dhanradar.models.auth import User, UserTierEnum

from .users_schemas import (
    AuditLogItem,
    UserDetailResponse,
    UserListItem,
    UserListResponse,
    UserSummaryResponse,
)

router = APIRouter(prefix="/admin", tags=["admin-users"])

# Tiers that count as "premium" (paid access)
_PREMIUM_TIERS = {
    UserTierEnum.pro,
    UserTierEnum.pro_plus,
    UserTierEnum.founder_lifetime,
}
_PREMIUM_TIER_VALUES = {t.value for t in _PREMIUM_TIERS}


def _derive_display_name(email: str) -> str:
    """Derive a display name from email (auth.users has no display_name column)."""
    return email.split("@")[0]


def _derive_status(user: User) -> str:
    """Derive user status from deletion_requested_at."""
    return "deletion_requested" if user.deletion_requested_at is not None else "active"


# ---------------------------------------------------------------------------
# GET /admin/users/summary
# ---------------------------------------------------------------------------


@router.get("/users/summary", response_model=UserSummaryResponse)
async def get_users_summary(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserSummaryResponse:
    """Aggregate user counts for the admin dashboard summary card."""
    now = datetime.now(UTC)

    total = await db.scalar(select(func.count()).select_from(User)) or 0

    active = await db.scalar(
        select(func.count()).select_from(User).where(User.deletion_requested_at.is_(None))
    ) or 0

    premium = await db.scalar(
        select(func.count()).select_from(User).where(
            User.tier.in_(_PREMIUM_TIERS)
        )
    ) or 0

    trials = await db.scalar(
        select(func.count()).select_from(User).where(User.pro_access_until > now)
    ) or 0

    blocked = await db.scalar(
        select(func.count()).select_from(User).where(User.deletion_requested_at.isnot(None))
    ) or 0

    return UserSummaryResponse(
        total=int(total),
        active=int(active),
        premium=int(premium),
        trials=int(trials),
        blocked=int(blocked),
    )


# ---------------------------------------------------------------------------
# GET /admin/users
# ---------------------------------------------------------------------------


@router.get("/users", response_model=UserListResponse)
async def list_users(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    plan: Annotated[str | None, Query(description="Filter by tier value")] = None,
    status: Annotated[
        str | None,
        Query(description="'active' or 'deletion_requested'"),
    ] = None,
    search: Annotated[
        str | None,
        Query(description="Email ILIKE search"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UserListResponse:
    """Paginated user list with optional filters.

    - plan: maps to the tier column value (e.g. 'pro', 'pro_plus')
    - status: 'active' or 'deletion_requested'
    - search: email ILIKE %search% — uses ORM bound parameter (not f-string SQL)
    """
    stmt = select(User)

    if plan is not None:
        # plan query param maps to the User.tier enum value
        try:
            tier_enum = UserTierEnum(plan)
        except ValueError:
            raise HTTPException(
                status_code=status_code_400(),
                detail="invalid_tier_value",
            )
        stmt = stmt.where(User.tier == tier_enum)

    if status is not None:
        if status == "deletion_requested":
            stmt = stmt.where(User.deletion_requested_at.isnot(None))
        elif status == "active":
            stmt = stmt.where(User.deletion_requested_at.is_(None))
        else:
            raise HTTPException(
                status_code=status_code_400(),
                detail="invalid_status_value",
            )

    if search is not None and search.strip():
        # CRITICAL: use ORM ilike — SQLAlchemy binds the param; no f-string SQL
        stmt = stmt.where(User.email.ilike(f"%{search}%"))

    # count total before pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt) or 0

    stmt = stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    users = result.scalars().all()

    items = [
        UserListItem(
            id=str(u.id),
            email=u.email,
            display_name=_derive_display_name(u.email),
            tier=u.tier.value,
            status=_derive_status(u),
            # TODO: last_login_at ABSENT — no user_activity_log table
            last_login_at=None,
            created_at=u.created_at,
        )
        for u in users
    ]
    return UserListResponse(total=int(total), users=items)


def status_code_400() -> int:
    return status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# GET /admin/users/{user_id}
# ---------------------------------------------------------------------------


@router.get("/users/{user_id}", response_model=UserDetailResponse)
async def get_user_detail(
    user_id: str,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserDetailResponse:
    """Full detail for one user including latest subscription and payment events."""
    try:
        uid = UUID(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="not_found",
        )

    user = await db.scalar(select(User).where(User.id == uid))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="not_found",
        )

    # Delegate to billing service (module isolation)
    subscription = await get_user_subscription(db, user_id)

    # Delegate to audit service (module isolation)
    payments = await list_payment_events(db, user_id=user_id, limit=50)

    return UserDetailResponse(
        id=str(user.id),
        email=user.email,
        display_name=_derive_display_name(user.email),
        tier=user.tier.value,
        status=_derive_status(user),
        created_at=user.created_at,
        pro_access_until=user.pro_access_until,
        pro_access_reason=user.pro_access_reason,
        risk_profile=user.risk_profile,
        dpdp_consent_version=user.dpdp_consent_version,
        subscription=subscription,
        payments=payments,
        # TODO: no user_activity_log table — login_history always []
        login_history=[],
        # TODO: no CAS upload query wired yet — cas_uploads always []
        cas_uploads=[],
    )


# ---------------------------------------------------------------------------
# GET /admin/audit
# ---------------------------------------------------------------------------


@router.get("/audit", response_model=list[AuditLogItem])
async def get_audit_log(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    since: Annotated[datetime | None, Query(description="Filter ts >= since")] = None,
    until: Annotated[datetime | None, Query(description="Filter ts <= until")] = None,
    action: Annotated[str | None, Query(description="Filter by action")] = None,
    admin_id: Annotated[str | None, Query(description="Filter by admin_id")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditLogItem]:
    """Read audit.admin_actions with optional filters."""
    rows = await list_admin_actions(
        db,
        since=since,
        until=until,
        action=action,
        admin_id=admin_id,
        limit=limit,
        offset=offset,
    )
    return [AuditLogItem(**row) for row in rows]
