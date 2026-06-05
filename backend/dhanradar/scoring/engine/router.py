"""
DhanRadar — internal scoring read endpoint (architecture §S interface).

`GET /internal/v1/score/{instrument_type}/{identifier}` returns the FULL internal
result (numeric score + confidence INCLUDED — server-side, tier-gated use only).

INTERNAL-ONLY: the cloudflared ingress routes only `^/api/.*` to FastAPI (default
→ Next.js), so `/internal/...` is NOT reachable through the public tunnel — it is
a server-to-server read for sibling modules. It is mounted WITHOUT the `/api/v1`
prefix for that reason. The public, no-numeric projection is delivered via the
`scoring.result.published` event (PublicScore), never this path.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, status

from dhanradar.redis_client import get_redis

router = APIRouter(prefix="/internal/v1", tags=["internal-scoring"])


@router.get("/score/{instrument_type}/{identifier}")
async def get_internal_score(instrument_type: str, identifier: str) -> dict[str, Any]:
    redis = get_redis()
    raw = await redis.get(f"scoring:result:{instrument_type}:{identifier}")
    if not raw:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="score_not_found")
    return json.loads(raw)
