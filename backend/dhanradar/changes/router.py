"""
DhanRadar — What Changed API router (Plan Group 2).

Mounted at /api/v1 (no extra prefix on this router); endpoint:
  GET /api/v1/portfolio/{portfolio_id}/changes

Authed (cookie RS256 only; anonymous → 401). IDOR: user sees only their own
portfolios (ownership check inline; other user's portfolio → 404, never 403).

No numeric score, no unified_score, no raw confidence float in any response.
Confidence BAND (high/medium/low/insufficient_data) is the only confidence
surface (non-neg #2/#4).
Disclosure bundle on every response (non-neg #9).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.changes import service
from dhanradar.changes.schemas import PortfolioChangesResponse
from dhanradar.db import get_db
from dhanradar.deps import UserContext, current_user_or_anonymous
from dhanradar.models.mf import MfPortfolio

router = APIRouter(tags=["changes"])


def _require_auth(user: UserContext) -> None:
    """Cookie auth only; anonymous → 401."""
    if user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated"
        )


@router.get(
    "/portfolio/{portfolio_id}/changes",
    response_model=PortfolioChangesResponse,
    summary="What Changed explainability for a portfolio (Plan Group 2)",
    description=(
        "Returns a per-fund label/band diff between the two most recent scored snapshots. "
        "Educational framing only — describes category-relative form movement, never advice. "
        "Read-only. No numeric score in any response field."
    ),
)
async def portfolio_changes(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PortfolioChangesResponse:
    _require_auth(user)

    # Parse portfolio_id — ValueError → 404 (never leaks whether the row exists)
    try:
        pid = uuid.UUID(portfolio_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found"
        )

    # Parse user_id defensively
    try:
        uid = uuid.UUID(user.user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated"
        )

    # IDOR ownership check: other user's portfolio → 404 (not 403)
    portfolio_row = (
        await db.execute(
            select(MfPortfolio.id, MfPortfolio.user_id).where(
                MfPortfolio.id == pid,
                MfPortfolio.user_id == uid,
            )
        )
    ).first()
    if portfolio_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found"
        )

    changes = await service.build_portfolio_changes(
        db,
        user_id=str(uid),
        portfolio_id=str(pid),
    )

    # Late import to avoid circular: changes → scoring/engine (same pattern as
    # transparency/service.py and mf/router.py). Read-only constants only.
    from dhanradar.scoring.engine.schemas import (  # noqa: PLC0415
        DISCLAIMER_VERSION,
        DISCLOSURE_BUNDLE,
        NOT_ADVICE,
    )

    return PortfolioChangesResponse(
        portfolio_id=str(pid),
        changes=changes,
        disclosure=DISCLOSURE_BUNDLE,
        not_advice=NOT_ADVICE,
        disclaimer_version=DISCLAIMER_VERSION,
    )
