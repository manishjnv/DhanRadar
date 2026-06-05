"""
DhanRadar — internal scoring read endpoint (architecture §S interface).

`GET /internal/v1/score/{instrument_type}/{identifier}` returns the FULL internal
result (numeric score + confidence INCLUDED — server-side, tier-gated use only).

Two defenses (defense-in-depth) on the numeric:
  1. NETWORK: the cloudflared ingress routes only `^/api/.*` to FastAPI (default
     → Next.js), so `/internal/...` is NOT reachable through the public tunnel.
     It is mounted WITHOUT the `/api/v1` prefix for that reason.
  2. SECRET: a shared `X-Internal-Token` (settings.INTERNAL_API_TOKEN) is required.
     FAIL-CLOSED — if the token is unset the endpoint is DISABLED (503), so the
     numeric is never served in a dev/preview box that merely binds port 8000.

The public, no-numeric projection is delivered via the `scoring.result.published`
event (PublicScore), never this path.
"""

from __future__ import annotations

import hmac
import json
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, HTTPException, status

from dhanradar.config import settings
from dhanradar.redis_client import get_redis

router = APIRouter(prefix="/internal/v1", tags=["internal-scoring"])


def _require_internal_token(x_internal_token: Optional[str]) -> None:
    token = settings.INTERNAL_API_TOKEN
    if not token:
        # Fail-closed: the internal numeric endpoint is OFF unless a token is set.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="internal_api_disabled"
        )
    if not x_internal_token or not hmac.compare_digest(x_internal_token, token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")


@router.get("/score/{instrument_type}/{identifier}")
async def get_internal_score(
    instrument_type: str,
    identifier: str,
    x_internal_token: Annotated[Optional[str], Header(alias="X-Internal-Token")] = None,
) -> dict[str, Any]:
    _require_internal_token(x_internal_token)
    redis = get_redis()
    raw = await redis.get(f"scoring:result:{instrument_type}:{identifier}")
    if not raw:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="score_not_found")
    return json.loads(raw)
