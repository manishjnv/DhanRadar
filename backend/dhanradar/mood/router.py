"""
DhanRadar — Mood Compass API router (architecture Mood Compass public interface).

All endpoints are ANON (acquisition magnet, ships before auth). The public surface
is the regime bucket + confidence band + commentary + evidence — never the numeric
mood_score (non-neg #2). Disclosure bundle + NOT_ADVICE injected in the schema.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.db import get_db
from dhanradar.mood import service
from dhanradar.mood.schemas import MoodHistoryItem, MoodPublic, WhyToday

router = APIRouter(prefix="/market", tags=["mood-compass"])


@router.get("/mood", response_model=MoodPublic)
async def market_mood(db: Annotated[AsyncSession, Depends(get_db)]) -> MoodPublic:
    latest = await service.get_latest(db)
    if latest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mood_unavailable")
    return latest


@router.get("/mood/history", response_model=list[MoodHistoryItem])
async def market_mood_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> list[MoodHistoryItem]:
    return await service.get_history(db, days)


@router.get("/why-today", response_model=WhyToday)
async def market_why_today(db: Annotated[AsyncSession, Depends(get_db)]) -> WhyToday:
    why = await service.get_why_today(db)
    if why is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mood_unavailable")
    return why
