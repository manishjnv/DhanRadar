"""
DhanRadar — Admin MFU UAT console router (/admin/mfu-uat).

Phase 0: ping (config/health), session login/status, and api-log read. No
order calls yet. Mirrors admin/bse_uat_router.py's shape (RequireAdmin,
404-surface-hiding) but is a fully separate rail — this module must never pull
in the BSE package or its models (module isolation, non-neg #7).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.audit.service import record_admin_action
from dhanradar.config import settings
from dhanradar.db import get_admin_db
from dhanradar.deps import RequireAdmin, UserContext
from dhanradar.mfu.client import (
    _COOLDOWN_KEY,
    _TOKEN_KEY,
    MfuError,
    base_url,
    login,
)
from dhanradar.redis_client import get_redis

router = APIRouter(prefix="/admin/mfu-uat", tags=["admin-mfu-uat"])

_ERROR_STATUS = {
    "DISABLED": status.HTTP_503_SERVICE_UNAVAILABLE,
    "NOT_UAT_HOST": status.HTTP_503_SERVICE_UNAVAILABLE,
    "NOT_CONFIGURED": status.HTTP_503_SERVICE_UNAVAILABLE,
    "COOLDOWN": status.HTTP_429_TOO_MANY_REQUESTS,
}


def _http_status_for(err: MfuError) -> int:
    return _ERROR_STATUS.get(err.error_code, status.HTTP_502_BAD_GATEWAY)


@router.get("/ping")
async def ping(
    _admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> dict[str, Any]:
    base_url_ok = True
    try:
        base_url()
    except MfuError:
        base_url_ok = False

    redis = get_redis()
    ttl = await redis.ttl(_TOKEN_KEY)
    cooldown_ttl = await redis.ttl(_COOLDOWN_KEY)
    return {
        "enabled": settings.MFU_UAT_ENABLED,
        "base_url_ok": base_url_ok,
        "configured": {
            "entity_id": bool(settings.MFU_ENTITY_ID),
            "login_user": bool(settings.MFU_LOGIN_USER),
            "login_password": bool(settings.MFU_LOGIN_PASSWORD),
            "aes_key": bool(settings.MFU_AES_KEY),
            "aes_iv": bool(settings.MFU_AES_IV),
        },
        "token_cached": ttl > 0,
        "token_ttl_s": ttl if ttl > 0 else None,
        "cooldown_s": cooldown_ttl if cooldown_ttl > 0 else None,
    }


@router.post("/session")
async def create_session(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
) -> dict[str, Any]:
    try:
        _token, ttl_s = await login(db)
    except MfuError as exc:
        await record_admin_action(
            admin_id=str(admin.user_id),
            action="mfu_uat.session.login",
            target_type="mfu_uat",
            target_id=None,
            result=f"failed_{exc.error_code}",
        )
        raise HTTPException(
            _http_status_for(exc),
            detail={"error_code": exc.error_code, "error_msg": exc.error_msg},
        ) from exc
    await record_admin_action(
        admin_id=str(admin.user_id),
        action="mfu_uat.session.login",
        target_type="mfu_uat",
        target_id=None,
        result="success",
    )
    return {"ok": True, "ttl_s": ttl_s}


@router.get("/session")
async def session_status(
    _admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> dict[str, Any]:
    ttl = await get_redis().ttl(_TOKEN_KEY)
    return {"token_cached": ttl > 0, "ttl_s": ttl if ttl > 0 else None}


@router.get("/api-log")
async def api_log(
    _admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
    limit: int = 50,
) -> list[dict[str, Any]]:
    from dhanradar.models.mfu import MfuApiLog

    capped = min(max(limit, 1), 200)
    stmt = select(MfuApiLog).order_by(MfuApiLog.created_at.desc()).limit(capped)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "unique_id": r.unique_id,
            "api_type": r.api_type,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "http_status": r.http_status,
            "resp_flag": r.resp_flag,
            "error_code": r.error_code,
            "error_msg": r.error_msg,
            "latency_ms": r.latency_ms,
            "request_json": r.request_json,
            "response_json": r.response_json,
        }
        for r in rows
    ]
