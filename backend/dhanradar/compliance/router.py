"""
DhanRadar — Compliance Audit API router (architecture Global §4).

Public surface is intentionally tiny: the in-force disclaimer text by type. The
audit table is internal (no public read); admin disclaimer-management + label-churn
endpoints belong to the Admin module (deferred).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.compliance import service
from dhanradar.compliance.schemas import DisclaimerResponse
from dhanradar.db import get_db
from dhanradar.ratelimit import RateLimit

router = APIRouter(prefix="/disclaimers", tags=["compliance"])

# Known disclaimer types — validated BEFORE any DB/Redis access so an attacker
# cannot flood Redis with `disclaimer:active:{unique}` keys via unique path values.
_KNOWN_TYPES = frozenset({"ai_recommendation"})
_rl = RateLimit(max_requests=30, window_seconds=60)


@router.get("/{disclaimer_type}", response_model=DisclaimerResponse)
async def get_disclaimer(
    disclaimer_type: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _rl: Annotated[None, Depends(_rl)] = None,
) -> DisclaimerResponse:
    """Public: the active disclaimer for a type (e.g. `ai_recommendation`)."""
    if disclaimer_type not in _KNOWN_TYPES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="disclaimer_not_found")
    disc = await service.get_active_disclaimer(db, disclaimer_type)
    if disc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="disclaimer_not_found")
    return DisclaimerResponse(**disc)
