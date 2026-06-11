"""
DhanRadar — Concept-Explainer router (C1).

Mounted at `/api/v1`. Both routes are PUBLIC-READ (anonymous-allowed +
crawlable — no auth dependency, no bearer). RFC7807 errors via the global
handler; a bad slug → 404 `concept_not_found`.

No static sibling path exists under `/learn/concepts`, so route order is not
load-bearing here — but if one is ever added (e.g. `/learn/concepts/glossary`),
declare it BEFORE the `{slug}` route (see education/router.py for the trap).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.concepts import service
from dhanradar.concepts.schemas import ConceptDetail, ConceptListResponse
from dhanradar.db import get_db

router = APIRouter(tags=["learn"])


@router.get("/learn/concepts", response_model=ConceptListResponse)
async def list_concepts(
    db: Annotated[AsyncSession, Depends(get_db)],
    category: Annotated[str | None, Query()] = None,
) -> ConceptListResponse:
    """Public list of concept explainers, with an optional category filter."""
    return await service.list_concepts(db, category=category)


@router.get("/learn/concepts/{slug}", response_model=ConceptDetail)
async def get_concept(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConceptDetail:
    """Public read of one concept by slug; unknown slug → RFC7807 404."""
    concept = await service.get_concept(db, slug)
    if concept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="concept_not_found")
    return concept
