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
) -> dict[str, object]:
    """
    Liveness + readiness probe.

    Returns::

        {"status": "ok", "db": "ok", "redis": "ok", "db_role_hardened": true}

    Raises 503 if either dependency is unreachable. `db_role_hardened` is INFORMATIONAL only
    (never gates the probe): True means the app's actual DB connection is the least-privilege
    non-superuser role (B80) so the append-only trigger (I12) + RLS (I5) bind it; False means it
    fell back to the owner role (DHANRADAR_APP_DB_PASSWORD unset). Watch this to alert on the gap.
    """
    # Check DB + observe the runtime role's privilege (B80).
    db_role_hardened = False
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
        is_super = await db.scalar(text("SELECT current_setting('is_superuser')"))
        db_role_hardened = str(is_super).lower() == "off"
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

    return {
        "status": "ok",
        "db": db_status,
        "redis": redis_status,
        "db_role_hardened": db_role_hardened,
    }
