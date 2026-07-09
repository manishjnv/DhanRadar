"""
DhanRadar — Admin display helper: batch user-id → email resolution.

Admin list endpoints store actor/target ids as raw UUID strings (audit rows,
payment events, CAS jobs, scoring changelog). A non-technical operator cannot
read a UUID, so admin read endpoints attach the matching auth.users email as a
display-only field. This helper is the single place that resolution lives.

Read-only, admin-surface only — emails never leave the RequireAdmin() gate.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.models.auth import User


async def resolve_user_emails(
    db: AsyncSession, ids: set[str | None]
) -> dict[str, str]:
    """Map user-id strings → email for every id that exists in auth.users.

    Accepts raw strings (audit columns are TEXT); non-UUID or unknown ids are
    simply absent from the result — callers fall back to showing the raw id.
    """
    uuids: dict[UUID, str] = {}
    for raw in ids:
        if not raw:
            continue
        try:
            uuids[UUID(str(raw))] = str(raw)
        except ValueError:
            continue
    if not uuids:
        return {}
    rows = await db.execute(
        select(User.id, User.email).where(User.id.in_(uuids.keys()))
    )
    return {uuids[uid]: email for uid, email in rows.all() if email}
