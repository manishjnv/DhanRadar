"""
DhanRadar — Mood Compass API router (architecture Mood Compass public interface).

All endpoints are ANON (acquisition magnet, ships before auth). The public surface
is the regime bucket + confidence band + commentary + evidence — never the numeric
mood_score (non-neg #2). Disclosure bundle + NOT_ADVICE injected in the schema.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.dashboard.indices import get_indices
from dhanradar.dashboard.schemas import MarketIndex
from dhanradar.db import get_db
from dhanradar.market_data.providers.yahoo import fetch_macro_quotes
from dhanradar.mood import service
from dhanradar.mood.schemas import MoodHistoryItem, MoodPublic, WhyToday
from dhanradar.signal.schemas import BreadthOut, MacroQuote, VIXOut

router = APIRouter(prefix="/market", tags=["mood-compass"])


@router.get("/mood", response_model=MoodPublic)
async def market_mood(db: Annotated[AsyncSession, Depends(get_db)]) -> MoodPublic:
    """Return the latest market mood snapshot.

    Always returns 200; when no snapshot exists, returns regime='data_unavailable'
    instead of 404 so the public widget never shows an error state (GAP c).
    """
    latest = await service.get_latest(db)
    return latest or service.unavailable_public()


@router.get("/mood/embed")
async def market_mood_embed(db: Annotated[AsyncSession, Depends(get_db)]) -> Response:
    """Return a self-contained embeddable HTML widget for the Mood Compass (GAP b).

    The widget is inline-styled (no external JS/CSS), suitable for iframes or
    direct embedding.  It contains no numeric mood_score or confidence_score.
    """
    html = await service.get_embed_html(db)
    return Response(content=html, media_type="text/html")


@router.get("/mood/history", response_model=list[MoodHistoryItem])
async def market_mood_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> list[MoodHistoryItem]:
    return await service.get_history(db, days)


@router.get("/why-today", response_model=WhyToday)
async def market_why_today(db: Annotated[AsyncSession, Depends(get_db)]) -> WhyToday:
    """Always 200: when no snapshot exists, return a structured data_unavailable
    body (not 404) so the anon acquisition surface never shows an error state —
    consistent with GET /mood (B35 gap c)."""
    why = await service.get_why_today(db)
    return why or service.why_today_unavailable()


@router.get("/vix", response_model=VIXOut)
async def market_vix() -> VIXOut:
    return await service.get_vix()


@router.get("/breadth", response_model=BreadthOut)
async def market_breadth() -> BreadthOut:
    return await service.get_breadth()


@router.get("/indices", response_model=list[MarketIndex])
async def market_indices() -> list[MarketIndex]:
    """Public index levels (Nifty 50, Sensex, …). `value`/`change_pct` are PUBLIC
    market data — explicitly DOM-allowed (see MarketIndex), NOT a DhanRadar score —
    so this mirrors the public /market/vix and /market/breadth: no auth, the mood
    page is public. Interface-only reuse of the shared index fetcher."""
    return await get_indices()


@router.get("/quotes", response_model=list[MacroQuote])
async def market_quotes() -> list[MacroQuote]:
    """Raw public quotes (level + % change) for the macro mood signals — S&P 500,
    US 10Y, Brent, USD/INR, India VIX, Nifty 50. Public Yahoo market data, DOM-allowed
    (NOT the proprietary mood score). Cached 5 min; public like /vix and /breadth."""
    return [MacroQuote(**q) for q in await fetch_macro_quotes()]
