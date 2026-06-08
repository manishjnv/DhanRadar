"""
B43 — Onboarding risk-quiz router.

Endpoints:
  POST /onboarding/risk-quiz — submit 5-question quiz, persist risk profile.

Security invariants:
  - Anonymous → 401 not_authenticated (checked IN-BODY FIRST, before any DB access).
    Do NOT use Depends(RequireTier) — it 402s anonymous before 401.
  - Idempotency-Key header: if present and already seen (Redis NX set returns falsy),
    skip the write and return the user's current risk_profile from DB.
  - Mutating endpoint honours the Idempotency-Key contract (architecture §API).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.db import get_db
from dhanradar.deps import UserContext, current_user_or_anonymous
from dhanradar.models.auth import User
from dhanradar.onboarding.schemas import RiskQuizRequest, RiskQuizResponse
from dhanradar.onboarding.service import set_risk_profile
from dhanradar.ratelimit import RateLimit

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

logger = logging.getLogger(__name__)

_rl = RateLimit(max_requests=20, window_seconds=60)


# ---------------------------------------------------------------------------
# POST /onboarding/risk-quiz
# ---------------------------------------------------------------------------


@router.post("/risk-quiz", response_model=RiskQuizResponse)
async def submit_risk_quiz(
    request: Request,
    body: RiskQuizRequest,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    _rate: Annotated[None, Depends(_rl)] = None,
) -> RiskQuizResponse:
    """Submit a 5-question risk quiz and persist the computed profile."""
    # Anonymous check IN-BODY FIRST — before any DB access.
    if user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not_authenticated",
        )

    # Idempotency check (Redis NX, TTL=24h). Scoped by action + user_id + key
    # so a key reused by the same user for a future re-quiz does not silence a
    # legitimate write (fail-open trap similar to consent scoping).
    if idempotency_key:
        from redis.exceptions import RedisError

        from dhanradar.redis_client import get_redis
        redis = get_redis()
        redis_key = f"onboarding:risk-quiz:{user.user_id}:{idempotency_key}"
        try:
            stored = await redis.set(redis_key, "1", nx=True, ex=86400)
        except RedisError:
            # Redis unavailable — degrade gracefully: proceed with the write
            # (quiz submission must not be blocked by a cache outage; the write
            # is idempotent on the column, only replay-dedup is lost).
            logger.warning(
                "Redis unavailable on onboarding risk-quiz idempotency check; "
                "proceeding without dedup"
            )
            stored = True
        if not stored:
            # Replay — return current persisted profile without a new write.
            from uuid import UUID
            try:
                uid = UUID(user.user_id)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="not_authenticated",
                )
            current_profile = await db.scalar(
                select(User.risk_profile).where(User.id == uid)
            )
            return RiskQuizResponse(risk_profile=current_profile or "conservative")

    # Normal (non-replay) path.
    try:
        profile = await set_risk_profile(db, user.user_id, body.answers)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid_answers",
        )

    return RiskQuizResponse(risk_profile=profile)
