"""
DhanRadar — Portfolio Intelligence router (Plan Group 3).

Mounted at `/api/v1` (no extra prefix).
Paths:
  GET /api/v1/portfolio/{portfolio_id}/overlap          (raw Pydantic — data-starved, untouched)
  GET /api/v1/portfolio/{portfolio_id}/holdings         (C1, A3 envelope)
  GET /api/v1/portfolio/{portfolio_id}/summary          (C2, A3 envelope)
  GET /api/v1/portfolio/{portfolio_id}/risk             (C3, A3 envelope)
  GET /api/v1/portfolio/{portfolio_id}/allocation       (M2.1, A3 envelope)
  GET /api/v1/portfolio/{portfolio_id}/concentration    (M2.1, A3 envelope)
  GET /api/v1/portfolio/{portfolio_id}/diversification  (M2.1, A3 envelope)

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
from dhanradar.insights.schemas import MoodContextResponse, OverlapResponse
from dhanradar.mf.portfolio_read import (
    allocation_payload,
    concentration_payload,
    diversification_payload,
    holdings_payload,
    load_portfolio_read_model,
    load_portfolio_risk,
    risk_advanced_payload,
    risk_payload,
    summary_payload,
)
from dhanradar.mf.projection import ENGINE_VERSION
from dhanradar.mf.serialization import RequestCtx, is_tier_withheld, serialize_concept
from dhanradar.models.mf import MfPortfolio

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


async def _owned_portfolio_id(db: AsyncSession, portfolio_id: str, user_id: str) -> uuid.UUID:
    """The portfolio UUID iff it belongs to user_id; 404 otherwise (also 404 on a malformed UUID — never
    leaks existence). RLS is the second layer."""
    try:
        pid = uuid.UUID(portfolio_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found")
    owned = await db.scalar(
        select(MfPortfolio.id).where(MfPortfolio.id == pid, MfPortfolio.user_id == uuid.UUID(user_id))
    )
    if owned is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found")
    return pid


@router.get("/portfolio/{portfolio_id}/holdings")
async def portfolio_holdings(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """C1 `holdings.list` — the owner's holdings, enriched (fund name/category, latest-NAV current value)
    and served THROUGH the serialization boundary (§10 layer 8). Each fund carries its educational label +
    confidence band (DOM-allowed) — NEVER the unified_score (hand-built payload + the A3 #2 scrub backstop).
    `invested_amount` is ledger net-invested (B86). Anonymous → 401; another user's portfolio → 404.
    """
    _require_auth(user)
    await _owned_portfolio_id(db, portfolio_id, user.user_id)
    rm = await load_portfolio_read_model(db, portfolio_id)
    return serialize_concept(
        "holdings.list",
        holdings_payload(rm, portfolio_id),
        RequestCtx(tier=user.tier),
        source="cas",
        engine_version=ENGINE_VERSION,
    )


@router.get("/portfolio/{portfolio_id}/summary")
async def portfolio_summary(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """C2 `portfolio.summary` — the owner's value/invested/gain/XIRR (their own DOM-allowed numbers) + an
    overall data-confidence band, served THROUGH the boundary. HAND-BUILT: no portfolio composite score and
    no invented verdict label (#1/#2). `total_invested` is ledger net-invested (B86). 401/404 as above.
    """
    _require_auth(user)
    await _owned_portfolio_id(db, portfolio_id, user.user_id)
    rm = await load_portfolio_read_model(db, portfolio_id)
    return serialize_concept(
        "portfolio.summary",
        summary_payload(rm, portfolio_id),
        RequestCtx(tier=user.tier),
        source="computed",
        engine_version=ENGINE_VERSION,
    )


@router.get("/portfolio/{portfolio_id}/risk")
async def portfolio_risk(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
    advanced: bool = False,
) -> dict:
    """C3 `portfolio.risk` (free) — the portfolio's risk band + value-weighted volatility / max-drawdown
    (standard ratios, DOM-allowed) served THROUGH the boundary. `?advanced=true` serves
    `portfolio.risk_advanced` (plus: Sharpe/Sortino/rolling); A3 withholds it for a free caller → HTTP 402
    (the client renders the upgrade state). The DhanRadar risk COMPOSITE is NEVER selected (hand-built;
    standard ratios only). Anonymous → 401; another user's portfolio → 404.
    """
    _require_auth(user)
    await _owned_portfolio_id(db, portfolio_id, user.user_id)
    r = await load_portfolio_risk(db, portfolio_id)
    if advanced:
        env = serialize_concept(
            "portfolio.risk_advanced",
            risk_advanced_payload(r, portfolio_id),
            RequestCtx(tier=user.tier),
            source="computed",
            engine_version=ENGINE_VERSION,
        )
        if is_tier_withheld(env):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="tier_upgrade_required"
            )
        return env
    return serialize_concept(
        "portfolio.risk",
        risk_payload(r, portfolio_id),
        RequestCtx(tier=user.tier),
        source="computed",
        engine_version=ENGINE_VERSION,
    )


@router.get("/portfolio/{portfolio_id}/allocation")
async def portfolio_allocation(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
    by: str = "category",
) -> dict:
    """M2.1 `portfolio.allocation` — the owner's value-weighted split by `category` (default) or `amc`,
    served THROUGH the A3 boundary. bucket/value/weight_pct are the user's own calculated facts (§13,
    DOM-allowed); no DhanRadar composite is selected (hand-built). `by=sector|cap` → empty buckets
    ('coming soon', data-starved). Anonymous → 401; another user's portfolio → 404.
    """
    _require_auth(user)
    await _owned_portfolio_id(db, portfolio_id, user.user_id)
    rm = await load_portfolio_read_model(db, portfolio_id)
    return serialize_concept(
        "portfolio.allocation",
        allocation_payload(rm, portfolio_id, by),
        RequestCtx(tier=user.tier),
        source="computed",
        engine_version=ENGINE_VERSION,
    )


@router.get("/portfolio/{portfolio_id}/concentration")
async def portfolio_concentration(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """M2.1 `portfolio.concentration` — top-fund / top-AMC weights + an indicative concentration band,
    served THROUGH the A3 boundary (was previously a raw Pydantic response bypassing it). Weights are the
    user's own % (§13, DOM-allowed); the band is a factual descriptor — no DhanRadar composite (hand-built).
    Cold-start / single-fund / no holdings → 200 with null top/empty list. 401/404 as above.
    """
    _require_auth(user)
    await _owned_portfolio_id(db, portfolio_id, user.user_id)
    rm = await load_portfolio_read_model(db, portfolio_id)
    return serialize_concept(
        "portfolio.concentration",
        concentration_payload(rm, portfolio_id),
        RequestCtx(tier=user.tier),
        source="computed",
        engine_version=ENGINE_VERSION,
    )


@router.get("/portfolio/{portfolio_id}/diversification")
async def portfolio_diversification(
    portfolio_id: str,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """M2.1 `portfolio.diversification` — a band/word read of how widely the holdings spread across
    categories, served THROUGH the A3 boundary. #2: band word only — the raw spread measure never
    serializes (same shape as C3 `risk_band`); the category count/top-category % are the user's own
    facts (DOM-allowed). No DhanRadar composite. Anonymous → 401; another user's portfolio → 404.
    """
    _require_auth(user)
    await _owned_portfolio_id(db, portfolio_id, user.user_id)
    rm = await load_portfolio_read_model(db, portfolio_id)
    return serialize_concept(
        "portfolio.diversification",
        diversification_payload(rm, portfolio_id),
        RequestCtx(tier=user.tier),
        source="computed",
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
