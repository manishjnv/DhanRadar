"""
B44 — DPDP consent grant/revoke service.

Provides:
  apply_consent_change  — atomic jsonb_set writer, audit logger, single commit.
  read_state            — fresh {purpose: bool} read via the canonical reader.

Design notes:
  - jsonb_set per purpose (not read-modify-write in Python) avoids the
    lost-update race when two concurrent requests touch sibling purposes.
  - The revoke path writes {"granted": false, ...} — NEVER a "revoked" key
    (the reader in deps._consent_granted ignores a "revoked" key → fail-open
    trap; see REVOKE CONTRACT, deps.py:211-213).
  - All writes for a single call are committed in one transaction after the
    loop, so partial-purpose writes are impossible.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import String, cast, func, update
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.deps import CONSENT_PURPOSES, _consent_granted
from dhanradar.models.auth import User
from dhanradar.models.consent import ConsentAuditLog


async def apply_consent_change(
    db: AsyncSession,
    user_id: str,
    purposes: list[str],
    *,
    granted: bool,
    version: str,
    request_id: str | None,
) -> None:
    """Write a grant or revoke for each purpose atomically.

    Per purpose:
      1. `jsonb_set` on auth.users.dpdp_consents — atomic key-level update,
         no sibling clobber.
      2. Set auth.users.dpdp_consent_version = version.
      3. Append one ConsentAuditLog row (action='grant' or 'revoke').

    A single `await db.commit()` at the end makes this all-or-nothing.
    """
    uid = uuid.UUID(user_id)
    action = "grant" if granted else "revoke"
    ts_iso = datetime.now(UTC).isoformat()

    payload = {"granted": granted, "ts": ts_iso, "version": version}
    payload_json = json.dumps(payload)

    for purpose in purposes:
        # Build the Postgres text[] path for jsonb_set safely.
        # Purposes are taxonomy-validated (CONSENT_PURPOSES) before reaching here,
        # so there is no injection risk; we still pass the JSON value as a bound
        # cast (not string-interpolated).
        # jsonb_set(target, path text[], new_value jsonb, create_missing bool)
        path_arr = cast([purpose], ARRAY(String))

        result = await db.execute(
            update(User)
            .where(User.id == uid)
            .values(
                dpdp_consents=func.jsonb_set(
                    User.dpdp_consents,
                    path_arr,                    # text[] path
                    cast(payload_json, JSONB),   # new value (bound param)
                    True,                        # create_missing
                ),
                dpdp_consent_version=version,
            )
        )
        # The user row is gone (deleted mid-session / DPDP erasure race): the
        # UPDATE matched 0 rows. Do NOT commit an audit row for a write that
        # changed nothing — that would be a false forensic record. Roll back the
        # whole change and fail closed (the JWT is valid but the account no
        # longer exists; mirrors /auth/me's user_not_found handling).
        if result.rowcount == 0:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="user_not_found",
            )
        db.add(
            ConsentAuditLog(
                user_id=uid,
                purpose=purpose,
                action=action,
                consent_version=version,
                request_id=request_id,
            )
        )

    await db.commit()


async def read_state(db: AsyncSession, user_id: str) -> dict[str, bool]:
    """Return {purpose: bool} for every canonical purpose, read fresh from DB.

    Uses the same _consent_granted reader as RequireConsent / consent_granted
    so grant/revoke semantics are a single source of truth.
    """
    from sqlalchemy import select

    row = await db.execute(
        select(User.dpdp_consents).where(User.id == uuid.UUID(user_id))
    )
    consents = row.scalar_one_or_none() or {}
    return {p: _consent_granted(consents, p) for p in sorted(CONSENT_PURPOSES)}
