"""
DhanRadar — Dashboard router (B56).

Mounted at `/api/v1` (no extra prefix) so the paths match the frontend contract:
`/api/v1/portfolio/summary`, `/api/v1/indices`, `/api/v1/instruments/top-scored`.

All three are AUTHED: anonymous → 401 (RFC7807 via the global handler). Auth is the
`__Host-` RS256 cookie only (`current_user_or_anonymous`); there is no bearer path.
`portfolio/summary` returns RFC7807 404 on cold-start (no portfolio) — the frontend
hook treats 404 as the empty state and does not retry.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.dashboard import service
from dhanradar.dashboard.indices import get_indices
from dhanradar.dashboard.schemas import MarketIndex, PortfolioSummary, TopScoredResponse
from dhanradar.db import get_db
from dhanradar.deps import UserContext, current_user_or_anonymous

router = APIRouter(tags=["dashboard"])


def _require_auth(user: UserContext) -> None:
    """Authenticated-only gate. Anonymous → 401 (not 403); cookie auth, no bearer."""
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")


@router.get("/portfolio/summary", response_model=PortfolioSummary)
async def portfolio_summary(
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PortfolioSummary:
    _require_auth(user)
    summary = await service.get_portfolio_summary(db, user.user_id)
    if summary is None:
        # Cold start — no portfolio yet. RFC7807 404 (the FE empty-state contract).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no_portfolio")
    return summary


@router.get("/indices", response_model=list[MarketIndex])
async def indices(
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
) -> list[MarketIndex]:
    _require_auth(user)
    return await get_indices()


@router.get("/instruments/top-scored", response_model=TopScoredResponse)
async def top_scored(
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
    instrument_type: Annotated[str, Query(alias="type")] = "fund",
) -> TopScoredResponse:
    _require_auth(user)
    if instrument_type != "fund":
        # Only mutual funds are scored today; other instrument types → empty funds
        # list (the widget renders its empty state) rather than a 4xx. The disclosure
        # bundle still rides along for a consistent label-surface contract.
        return service.top_scored_envelope([])
    return await service.get_top_scored(db, user.user_id)
