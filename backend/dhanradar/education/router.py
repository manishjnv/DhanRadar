"""
DhanRadar — Tax-Education router (G8).

Mounted at `/api/v1`. All three routes are PUBLIC-READ (anonymous-allowed +
crawlable — no auth dependency, no bearer). RFC7807 errors via the global handler;
a bad slug → 404 `article_not_found`.

Route order matters: `/learn/tax/calendar` is declared BEFORE `/learn/tax/{slug}`
so the static calendar path is not captured as a slug.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.db import get_db
from dhanradar.education import service
from dhanradar.education.calendar import today_ist
from dhanradar.education.schemas import ArticleDetail, ArticleListResponse, CalendarResponse

router = APIRouter(tags=["learn"])


@router.get("/learn/tax", response_model=ArticleListResponse)
async def list_tax_articles(
    db: Annotated[AsyncSession, Depends(get_db)],
    category: Annotated[str | None, Query()] = None,
    fy: Annotated[str | None, Query()] = None,
) -> ArticleListResponse:
    """Public list of tax-education articles, with optional category + FY filters."""
    return await service.list_articles(db, category=category, fy=fy)


@router.get("/learn/tax/calendar", response_model=CalendarResponse)
async def tax_calendar() -> CalendarResponse:
    """FY-aware statutory key dates computed from today's date in IST (public, no DB)."""
    return service.get_calendar(today_ist())


@router.get("/learn/tax/{slug}", response_model=ArticleDetail)
async def get_tax_article(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ArticleDetail:
    """Public read of one article by slug; unknown slug → RFC7807 404."""
    article = await service.get_article(db, slug)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="article_not_found")
    return article
