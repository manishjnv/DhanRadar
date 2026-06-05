"""
DhanRadar — Health check router.

GET /api/v1/health
  Checks DB and Redis connectivity; returns 200 when both are reachable.
  Used by the Docker healthcheck and by cloudflared upstream probes.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.db import get_db
from dhanradar.redis_client import get_redis

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", status_code=status.HTTP_200_OK)
async def health_check(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """
    Liveness + readiness probe.

    Returns::

        {"status": "ok", "db": "ok", "redis": "ok"}

    Raises 503 if either dependency is unreachable.
    """
    # Check DB
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:  # noqa: BLE001
        db_status = f"error: {exc}"

    # Check Redis
    try:
        redis = get_redis()
        await redis.ping()
        redis_status = "ok"
    except Exception as exc:  # noqa: BLE001
        redis_status = f"error: {exc}"

    if db_status != "ok" or redis_status != "ok":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "degraded", "db": db_status, "redis": redis_status},
        )

    return {"status": "ok", "db": db_status, "redis": redis_status}
