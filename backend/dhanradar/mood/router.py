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

from dhanradar.db import get_db
from dhanradar.mood import service
from dhanradar.mood.schemas import MoodHistoryItem, MoodPublic, WhyToday
from dhanradar.signal.schemas import BreadthOut, VIXOut

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
    return VIXOut(value=18.5, change_pct=-0.8, market_open=False)


@router.get("/breadth", response_model=BreadthOut)
async def market_breadth() -> BreadthOut:
    return BreadthOut(advances=1240, declines=260, ad_ratio=1.24, market_open=False)
