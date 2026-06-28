"""
DhanRadar — Portfolio Intelligence router (Plan Group 3).

Mounted at `/api/v1` (no extra prefix).
Paths:
  GET /api/v1/portfolio/{portfolio_id}/overlap
  GET /api/v1/portfolio/{portfolio_id}/concentration

Auth: cookie RS256 JWT only (`current_user_or_anonymous` → 401 if anonymous).
IDOR: user sees ONLY their own portfolios — service raises ValueError on mismatch → 404.
No advisory verbs in any response copy. Disclosure bundle on every response (non-neg #9).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.db import get_db
from dhanradar.deps import UserContext, current_user_or_anonymous
from dhanradar.insights import service
from dhanradar.insights.schemas import ConcentrationResponse, MoodContextResponse, OverlapResponse
from dhanradar.mf.projection import ENGINE_VERSION
from dhanradar.mf.serialization import RequestCtx, serialize_concept
from dhanradar.models.mf import MfPortfolio, MfUserHolding, UserFundScore

router = APIRouter(tags=["portfolio-intelligence"])


def _require_auth(user: UserContext) -> None:
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")


@router.get(
    "/portfolio/{portfolio_id}/overlap",
    response_model=OverlapResponse,
)
async def portfolio_overlap(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OverlapResponse:
    """
    Factual fund-overlap observations for the user's own portfolio.

    Cold-start / single-fund / no holdings → valid 200 with empty lists, never 404.
    Another user's portfolio_id → 404 (portfolio_not_found).
    Anonymous → 401.
    """
    _require_auth(user)
    try:
        return await service.get_overlap(db, user.user_id, portfolio_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found")


@router.get(
    "/portfolio/{portfolio_id}/concentration",
    response_model=ConcentrationResponse,
)
async def portfolio_concentration(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConcentrationResponse:
    """
    Factual concentration observations for the user's own portfolio.

    Cold-start / single-fund / no holdings → valid 200 with empty lists, never 404.
    Another user's portfolio_id → 404 (portfolio_not_found).
    Anonymous → 401.
    """
    _require_auth(user)
    try:
        return await service.get_concentration(db, user.user_id, portfolio_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found")


@router.get("/portfolio/{portfolio_id}/holdings")
async def portfolio_holdings(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """`holdings.list` (A3 pilot) — the user's own holdings served THROUGH the single serialization
    boundary (§10 layer 8). RLS scopes the rows to the owner; the boundary wraps them in the governance
    envelope and strips any raw DhanRadar score (#2). Each fund carries its educational label +
    confidence band (DOM-allowed) — NEVER the unified_score. Anonymous → 401; another user's portfolio → 404.
    """
    _require_auth(user)
    try:
        pid = uuid.UUID(portfolio_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found")
    owned = await db.scalar(
        select(MfPortfolio.id).where(
            MfPortfolio.id == pid, MfPortfolio.user_id == uuid.UUID(user.user_id)
        )
    )
    if owned is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found")

    # RLS-scoped read of the owner's holdings + the educational label/band. unified_score is NEVER
    # selected (correct by construction); the boundary's #2 scrub is the defence-in-depth backstop.
    rows = (
        await db.execute(
            select(
                MfUserHolding.isin,
                MfUserHolding.folio_number,
                MfUserHolding.units,
                MfUserHolding.invested_amount,
                MfUserHolding.avg_cost_nav,
                MfUserHolding.as_of_date,
                UserFundScore.verb_label,
                UserFundScore.confidence_band,
            )
            .select_from(MfUserHolding)
            .outerjoin(
                UserFundScore,
                (UserFundScore.portfolio_id == MfUserHolding.portfolio_id)
                & (UserFundScore.isin == MfUserHolding.isin),
            )
            .where(MfUserHolding.portfolio_id == pid)
            .order_by(MfUserHolding.isin)
        )
    ).mappings().all()

    holdings = [
        {
            "isin": r["isin"],
            "folio_number": r["folio_number"],
            "units": float(r["units"]) if r["units"] is not None else None,
            "invested_amount": float(r["invested_amount"]) if r["invested_amount"] is not None else None,
            "current_nav": float(r["avg_cost_nav"]) if r["avg_cost_nav"] is not None else None,
            "as_of": r["as_of_date"].isoformat() if r["as_of_date"] else None,
            "label": r["verb_label"],  # educational label (DOM-allowed, #1)
            "confidence_band": r["confidence_band"],  # band, not a number (#2)
        }
        for r in rows
    ]
    return serialize_concept(
        "holdings.list",
        {"portfolio_id": portfolio_id, "holdings": holdings},
        RequestCtx(tier=user.tier),
        source="cas",
        engine_version=ENGINE_VERSION,
    )


@router.get(
    "/portfolio/{portfolio_id}/mood-context",
    response_model=MoodContextResponse,
)
async def portfolio_mood_context(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MoodContextResponse:
    """
    Educational mood-context read: current market regime + portfolio structure summary.

    Surfaces THREE deterministic observation strings — no LLM, no advisory verbs,
    no numeric scores. Mood describes conditions; it does not predict direction.

    Cold-start / empty portfolio → valid 200 with honest empty read, never 404.
    Another user's portfolio_id → 404 (portfolio_not_found).
    Anonymous → 401.
    """
    _require_auth(user)
    try:
        return await service.get_mood_context(db, user.user_id, portfolio_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found")
