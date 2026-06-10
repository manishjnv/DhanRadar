"""
DhanRadar — News API router (B56 news deferral closure).

Anonymous-allowed endpoint: returns headline + link-out metadata only.
No article body/excerpt (copyright compliance, SEBI-safe).

Endpoint contract: GET /api/v1/news?scope=market&limit=N
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.db import get_db
from dhanradar.news import service
from dhanradar.news.schemas import NewsItem

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=list[NewsItem])
async def list_news(
    db: Annotated[AsyncSession, Depends(get_db)],
    scope: Annotated[str, Query()] = "market",
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[NewsItem]:
    """Return curated headline metadata for the given scope.

    Always 200; returns [] when no curated items exist.
    Only title, source, url, published_at, category are returned.
    Never serves article body/excerpt.
    """
    return await service.list_news(db, scope=scope, limit=limit)
