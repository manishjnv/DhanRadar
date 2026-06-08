"""
DhanRadar — Notification API router (Phase 6, architecture Global §5).

Endpoints (all under /api/v1):
  GET  /notifications/preferences   (authed)      — read channel/quiet-hours prefs
  POST /notifications/preferences   (authed)      — partial update (only sent keys)
  POST /notifications/test          (authed, Pro) — enqueue a test_ping to a channel

Auth is checked first (401 for anonymous) before any work. `/test` additionally
requires the `pro` tier (402 below). Delivery itself is async via the celery-misc
drain — the endpoint only enqueues and returns.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.db import get_db
from dhanradar.deps import RequireTier, UserContext, current_user_or_anonymous
from dhanradar.notifications import service
from dhanradar.notifications.schemas import (
    PreferencesResponse,
    PreferencesUpdate,
    TestNotificationRequest,
    TestNotificationResponse,
)
from dhanradar.ratelimit import RateLimit
from dhanradar.redis_client import get_redis

router = APIRouter(prefix="/notifications", tags=["notifications"])

_rl_test = RateLimit(max_requests=5, window_seconds=60)
# Tier gate invoked explicitly AFTER the auth check so an anonymous caller gets
# 401 (not 402) — RequireTier alone treats anonymous as `free` and would 402 first.
_pro_gate = RequireTier("pro")


def _require_auth(user: UserContext) -> None:
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")


@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
) -> PreferencesResponse:
    _require_auth(user)
    prefs = await service.get_preferences(db, user.user_id)
    return PreferencesResponse(**prefs)


@router.post("/preferences", response_model=PreferencesResponse)
async def update_preferences(
    body: PreferencesUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
) -> PreferencesResponse:
    _require_auth(user)
    # exclude_unset → only the keys the client actually sent are written (partial).
    fields = body.model_dump(exclude_unset=True)
    prefs = await service.upsert_preferences(db, user.user_id, fields)
    return PreferencesResponse(**prefs)


@router.post("/test", response_model=TestNotificationResponse)
async def test_notification(
    body: TestNotificationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    _rl: Annotated[None, Depends(_rl_test)] = None,
) -> TestNotificationResponse:
    _require_auth(user)        # 401 first (anonymous) ...
    await _pro_gate(user, db)  # ... then 402 (tier below pro); RequireTier needs db (PHASE 5M is_plus)
    # Refuse if the user has not configured/opted into the chosen channel — a test
    # send to an unconfigured channel would just fail at the drain.
    prefs = await service.get_preferences(db, user.user_id)
    if body.channel == "telegram" and not prefs["telegram_chat_id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="telegram_not_set")

    redis = get_redis()
    await service.publish_notification(
        redis, user.user_id, body.channel, "test_ping", data={}, priority="high"
    )
    return TestNotificationResponse(
        enqueued=True, channel=body.channel, detail="queued for delivery"
    )
