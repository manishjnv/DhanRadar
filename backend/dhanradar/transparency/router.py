"""
DhanRadar — Transparency API router (Plan Group 9 / PU2).

Mounted at /api/v1 (no extra prefix); endpoint:
  GET /api/v1/portfolio/{portfolio_id}/transparency

Authed (cookie RS256 only; anonymous → 401). IDOR: user sees only their own
portfolios (ownership check in service; other user's portfolio → 404).

No numeric score, no unified_score, no raw confidence float in any response.
Confidence BAND (high/medium/low/insufficient_data) only (non-neg #2/#4).
Disclosure bundle on every response (non-neg #9).
insufficient_data rendered as explicit refusal (PU2), not error/blank.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.db import get_db
from dhanradar.deps import UserContext, current_user_or_anonymous
from dhanradar.transparency import service
from dhanradar.transparency.schemas import PortfolioTransparencyResponse

router = APIRouter(tags=["transparency"])


def _require_auth(user: UserContext) -> None:
    """Cookie auth only; anonymous → 401."""
    if user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated"
        )


@router.get(
    "/portfolio/{portfolio_id}/transparency",
    response_model=PortfolioTransparencyResponse,
    summary="Data transparency for a portfolio (Plan Group 9 / PU2)",
    description=(
        "Returns confidence band, data-quality drivers, provenance sources, "
        "and NAV freshness for every fund in the portfolio. "
        "insufficient_data funds surface an explicit educational refusal. "
        "Read-only. No numeric score in any response field."
    ),
)
async def portfolio_transparency(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PortfolioTransparencyResponse:
    _require_auth(user)

    try:
        pid = uuid.UUID(portfolio_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found"
        )

    try:
        uid = uuid.UUID(user.user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated"
        )

    result = await service.get_portfolio_transparency(db, pid, uid)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found"
        )
    return result
