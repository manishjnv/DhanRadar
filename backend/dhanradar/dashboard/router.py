"""
DhanRadar — Dashboard router (B56).

Mounted at `/api/v1` (no extra prefix) so the path matches the frontend contract:
`/api/v1/indices`.

AUTHED: anonymous → 401 (RFC7807 via the global handler). Auth is the `__Host-`
RS256 cookie only (`current_user_or_anonymous`); there is no bearer path.

`/portfolio/summary` and `/instruments/top-scored` were decommissioned along with
the old /dashboard page (folded into /mf/portfolio).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from dhanradar.dashboard.indices import get_indices
from dhanradar.dashboard.schemas import MarketIndex
from dhanradar.deps import UserContext, current_user_or_anonymous

router = APIRouter(tags=["dashboard"])


def _require_auth(user: UserContext) -> None:
    """Authenticated-only gate. Anonymous → 401 (not 403); cookie auth, no bearer."""
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")


@router.get("/indices", response_model=list[MarketIndex])
async def indices(
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
) -> list[MarketIndex]:
    _require_auth(user)
    return await get_indices()
