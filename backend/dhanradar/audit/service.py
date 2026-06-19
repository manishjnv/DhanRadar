"""
DhanRadar — Audit ledger emit helpers (B57 P2).

Three fire-and-forget helpers that write append-only rows to the
`audit` schema:

  * record_admin_action   → audit.admin_actions
  * record_payment_event  → audit.payment_events
  * record_security_event → audit.security_events

Each helper:
  - Opens its OWN AsyncSession (never reuses the caller's session).
  - Computes a SHA-256 row hash over immutable business fields for
    tamper-evidence (hash is reproducible from the stored row).
  - NEVER raises — swallows all exceptions, logs, and returns False so
    audit failures cannot break or slow down the serving path.
  - Sets `ts` explicitly in Python (not relying solely on DB DEFAULT) so
    the row hash is reproducible: the same `ts` is passed to both the
    ORM row and the hash computation.

Module isolation invariant (non-neg #7): this module imports ONLY from
``dhanradar.core.logging``, ``dhanradar.db``, ``dhanradar.models.audit``,
and stdlib.  It MUST NOT import from auth / billing / admin / compliance /
subscriptions.

Append-only: no UPDATE / DELETE code path is provided.
NOTE: a DB-level UPDATE/DELETE-blocking trigger is deferred hardening.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from dhanradar.core.logging import get_logger, hash_user_ref

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Row-hash helper (local — no cross-module import)
# ---------------------------------------------------------------------------


def _row_hash(fields: dict) -> str:
    """SHA-256 over the canonical JSON of the immutable business fields.

    Hash is over the stored (post-hash/redaction) values ONLY — excludes
    `id` and `row_hash` itself.  `ts` is included because it is set
    explicitly in Python before the row is written, making the hash
    reproducible from a stored row.

    `datetime` values are normalised with `.isoformat()` so the hash is
    STABLE across a Postgres `timestamptz` round-trip (asyncpg's returned
    datetime must rehash identically to the in-Python value).

    NOTE (tamper-evidence scope): this detects application-layer row
    tampering (e.g. a compromised app pod editing rows via the ORM). It is
    NOT a defence against a DB-level attacker, who can recompute a matching
    hash. A hash-chain is the deferred upgrade (LOGGING_PLAN §9).
    """
    norm = {
        k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in fields.items()
    }
    blob = json.dumps(norm, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Best-effort failure metric (local — mirrors compliance.service pattern)
# ---------------------------------------------------------------------------


async def _bump_failure_metric(table: str) -> None:
    """Increment a daily Redis failure counter for audit observability.

    Best-effort: NEVER raises.  Ops/alerting reads
    ``metrics:audit:{table}_write_failures:{YYYYMMDD}``.
    """
    try:
        from dhanradar.redis_client import get_redis

        redis = get_redis()
        day = datetime.now(UTC).strftime("%Y%m%d")
        key = f"metrics:audit:{table}_write_failures:{day}"
        await redis.incrby(key, 1)
        await redis.expire(key, 35 * 86400)
    except Exception:  # noqa: BLE001 — observability is best-effort
        logger.warning("audit: failure metric bump failed for table=%s", table)


# ---------------------------------------------------------------------------
# Public emit helpers
# ---------------------------------------------------------------------------


async def record_admin_action(
    *,
    admin_id: str,
    action: str,
    target_type: str | None,
    target_id: str | None,
    result: str,
    request_id: str | None = None,
) -> bool:
    """Persist one admin compliance action row.

    `admin_id` is stored RAW (staff id, not end-user PII).

    Returns True iff written.  NEVER raises.
    """
    try:
        from dhanradar.db import TaskSessionLocal
        from dhanradar.models.audit import AdminAction

        ts = datetime.now(UTC)
        fields = {
            "ts": ts,
            "admin_id": admin_id,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "result": result,
            "request_id": request_id,
        }
        async with TaskSessionLocal() as db:
            db.add(
                AdminAction(
                    ts=ts,
                    admin_id=admin_id,
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    result=result,
                    request_id=request_id,
                    row_hash=_row_hash(fields),
                )
            )
            await db.commit()
        return True
    except Exception:  # noqa: BLE001 — fire-and-forget: audit must not break the caller
        logger.exception(
            "audit: admin_action write failed admin_id=%s action=%s", admin_id, action
        )
        await _bump_failure_metric("admin_actions")
        return False


async def record_payment_event(
    *,
    user_id: str,
    order_id: str | None,
    razorpay_payment_id: str | None,
    status: str,
    request_id: str | None = None,
) -> bool:
    """Persist one payment/subscription lifecycle audit row.

    `user_id` is stored RAW — identifiable by design per ADR-0022
    (SEBI 7-yr financial record requirement).

    Returns True iff written.  NEVER raises.
    """
    try:
        from dhanradar.db import TaskSessionLocal
        from dhanradar.models.audit import PaymentEvent

        ts = datetime.now(UTC)
        fields = {
            "ts": ts,
            "user_id": user_id,
            "order_id": order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "status": status,
            "request_id": request_id,
        }
        async with TaskSessionLocal() as db:
            db.add(
                PaymentEvent(
                    ts=ts,
                    user_id=user_id,
                    order_id=order_id,
                    razorpay_payment_id=razorpay_payment_id,
                    status=status,
                    request_id=request_id,
                    row_hash=_row_hash(fields),
                )
            )
            await db.commit()
        return True
    except Exception:  # noqa: BLE001 — fire-and-forget: audit must not break the caller
        # Log the HASHED user ref, never the raw user_id — a raw UUID in the
        # message string would bypass value-regex redaction (DPDP).
        logger.exception(
            "audit: payment_event write failed",
            user_ref=hash_user_ref(user_id),
            status=status,
        )
        await _bump_failure_metric("payment_events")
        return False


async def record_security_event(
    *,
    event_type: str,
    user_id: str | None,
    request_id: str | None = None,
) -> bool:
    """Persist one security incident audit row.

    `user_id` is HASHED via hash_user_ref before storage — column name in
    the DB is `user_ref`, never the raw user_id (DPDP privacy).

    Returns True iff written.  NEVER raises.
    """
    try:
        from dhanradar.db import TaskSessionLocal
        from dhanradar.models.audit import SecurityEvent

        ts = datetime.now(UTC)
        user_ref: str | None = hash_user_ref(user_id) if user_id else None
        fields = {
            "ts": ts,
            "event_type": event_type,
            "user_ref": user_ref,
            "request_id": request_id,
        }
        async with TaskSessionLocal() as db:
            db.add(
                SecurityEvent(
                    ts=ts,
                    event_type=event_type,
                    user_ref=user_ref,
                    request_id=request_id,
                    row_hash=_row_hash(fields),
                )
            )
            await db.commit()
        return True
    except Exception:  # noqa: BLE001 — fire-and-forget: audit must not break the caller
        logger.exception(
            "audit: security_event write failed event_type=%s", event_type
        )
        await _bump_failure_metric("security_events")
        return False


# ---------------------------------------------------------------------------
# Admin read helpers (Phase 2 — audit log reads)
# Module isolation: these are the only read fns in this module; all write fns
# above remain fire-and-forget (never import from auth/billing/admin/compliance).
# These reads accept an AsyncSession from the caller (passed in from the route).
# ---------------------------------------------------------------------------


async def list_admin_actions(
    db: Any,  # AsyncSession — imported lazily to avoid circular imports
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    action: str | None = None,
    admin_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Read audit.admin_actions with optional filters.

    Accepts an AsyncSession from the caller. Uses ORM select — no raw SQL,
    no f-string interpolation.

    Returns list of dicts: id, ts, admin_id, action, target_type, target_id,
    result, request_id.
    """
    from sqlalchemy import select as sa_select

    from dhanradar.models.audit import AdminAction

    stmt = sa_select(AdminAction)
    if since is not None:
        stmt = stmt.where(AdminAction.ts >= since)
    if until is not None:
        stmt = stmt.where(AdminAction.ts <= until)
    if action is not None:
        stmt = stmt.where(AdminAction.action == action)
    if admin_id is not None:
        stmt = stmt.where(AdminAction.admin_id == admin_id)
    stmt = stmt.order_by(AdminAction.ts.desc()).limit(limit).offset(offset)

    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": row.id,
            "ts": row.ts,
            "admin_id": row.admin_id,
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "result": row.result,
            "request_id": row.request_id,
        }
        for row in rows
    ]


async def list_payment_events(
    db: Any,  # AsyncSession
    *,
    user_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Read audit.payment_events, optionally filtered by user_id.

    Returns list of dicts: user_id, order_id, razorpay_payment_id, status,
    request_id, ts.
    """
    from sqlalchemy import select as sa_select

    from dhanradar.models.audit import PaymentEvent

    stmt = sa_select(PaymentEvent)
    if user_id is not None:
        # user_id in payment_events is stored as TEXT (raw UUID string)
        stmt = stmt.where(PaymentEvent.user_id == str(user_id))
    stmt = stmt.order_by(PaymentEvent.ts.desc()).limit(limit).offset(offset)

    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "user_id": row.user_id,
            "order_id": row.order_id,
            "razorpay_payment_id": row.razorpay_payment_id,
            "status": row.status,
            "request_id": row.request_id,
            "ts": row.ts,
        }
        for row in rows
    ]
