"""
B44 — DPDP consent grant/revoke router.

Endpoints:
  GET  /consent          — return current consent state for the authenticated user.
  POST /consent/grant    — grant one or more canonical DPDP purposes.
  POST /consent/revoke   — revoke one or more canonical DPDP purposes.

Security invariants:
  - Anonymous → 401 not_authenticated (checked IN-BODY FIRST, before any DB access).
    Do NOT use Depends(RequireTier) — it 402s anonymous before 401 (known RCA bug).
  - Idempotency-Key header: if present and already seen (Redis NX set returns falsy),
    skip writes and return current state — no new DB write, no new audit row.
  - Mutating endpoints honour the Idempotency-Key contract (architecture §API).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.config import settings
from dhanradar.consent.schemas import ConsentChangeRequest, ConsentStateResponse
from dhanradar.consent.service import apply_consent_change, read_state
from dhanradar.db import get_db
from dhanradar.deps import UserContext, current_user_or_anonymous
from dhanradar.ratelimit import RateLimit

router = APIRouter(prefix="/consent", tags=["consent"])

logger = logging.getLogger(__name__)

_rl = RateLimit(max_requests=20, window_seconds=60)


# ---------------------------------------------------------------------------
# GET /consent
# ---------------------------------------------------------------------------

@router.get("", response_model=ConsentStateResponse)
async def get_consent_state(
    request: Request,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _rate: Annotated[None, Depends(_rl)] = None,
) -> ConsentStateResponse:
    """Return the current DPDP consent state for the authenticated user."""
    if user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not_authenticated",
        )

    consents = await read_state(db, user.user_id)
    return ConsentStateResponse(
        consents=consents,
        consent_version=settings.DPDP_CONSENT_VERSION,
    )


# ---------------------------------------------------------------------------
# POST /consent/grant
# ---------------------------------------------------------------------------

@router.post("/grant", response_model=ConsentStateResponse)
async def grant_consent(
    request: Request,
    body: ConsentChangeRequest,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    _rate: Annotated[None, Depends(_rl)] = None,
) -> ConsentStateResponse:
    """Grant the listed DPDP purposes for the authenticated user."""
    if user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not_authenticated",
        )

    # Idempotency check (Redis NX, TTL=24h). The key is scoped by ACTION
    # ("grant") so a key reused across a grant then a revoke cannot make the
    # revoke look like a replay and be silently skipped (a fail-open trap —
    # consent would stay granted while the caller receives 200).
    if idempotency_key:
        from redis.exceptions import RedisError

        from dhanradar.redis_client import get_redis
        redis = get_redis()
        redis_key = f"consent:idem:grant:{user.user_id}:{idempotency_key}"
        try:
            stored = await redis.set(redis_key, "1", nx=True, ex=86400)
        except RedisError:
            # Redis unavailable — degrade gracefully: proceed with the write
            # (consent capture must not be blocked by a cache outage; the write
            # is idempotent on the column, only replay-dedup is lost).
            logger.warning("Redis unavailable on consent grant idempotency check; proceeding without dedup")
            stored = True
        if not stored:
            # Replay — return current state without writing
            consents = await read_state(db, user.user_id)
            return ConsentStateResponse(
                consents=consents,
                consent_version=settings.DPDP_CONSENT_VERSION,
            )

    request_id: str | None = getattr(request.state, "request_id", None)
    await apply_consent_change(
        db,
        user.user_id,
        body.purposes,
        granted=True,
        version=settings.DPDP_CONSENT_VERSION,
        request_id=request_id,
    )

    consents = await read_state(db, user.user_id)
    return ConsentStateResponse(
        consents=consents,
        consent_version=settings.DPDP_CONSENT_VERSION,
    )


# ---------------------------------------------------------------------------
# POST /consent/revoke
# ---------------------------------------------------------------------------

@router.post("/revoke", response_model=ConsentStateResponse)
async def revoke_consent(
    request: Request,
    body: ConsentChangeRequest,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    _rate: Annotated[None, Depends(_rl)] = None,
) -> ConsentStateResponse:
    """Revoke the listed DPDP purposes for the authenticated user.

    Writes {"granted": false, ...} per purpose — NEVER a "revoked" key.
    See REVOKE CONTRACT in deps.py:211-213.
    """
    if user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not_authenticated",
        )

    # Idempotency check — scoped by ACTION ("revoke") so a key reused across a
    # grant then a revoke cannot make the revoke look like a replay (fail-open).
    if idempotency_key:
        from redis.exceptions import RedisError

        from dhanradar.redis_client import get_redis
        redis = get_redis()
        redis_key = f"consent:idem:revoke:{user.user_id}:{idempotency_key}"
        try:
            stored = await redis.set(redis_key, "1", nx=True, ex=86400)
        except RedisError:
            # Redis unavailable — degrade gracefully and proceed (see grant path).
            logger.warning("Redis unavailable on consent revoke idempotency check; proceeding without dedup")
            stored = True
        if not stored:
            consents = await read_state(db, user.user_id)
            return ConsentStateResponse(
                consents=consents,
                consent_version=settings.DPDP_CONSENT_VERSION,
            )

    request_id: str | None = getattr(request.state, "request_id", None)
    await apply_consent_change(
        db,
        user.user_id,
        body.purposes,
        granted=False,
        version=settings.DPDP_CONSENT_VERSION,
        request_id=request_id,
    )

    consents = await read_state(db, user.user_id)
    return ConsentStateResponse(
        consents=consents,
        consent_version=settings.DPDP_CONSENT_VERSION,
    )
