"""
DhanRadar — Admin Phase 3: Scoring model read-only router.

# TIER-C LOAD-BEARING: Scoring engine read — requires Opus diff review before merge

Exposes GET /admin/scoring/model — read-only summary of the active scoring engine
config, registry versions, and MF fund coverage count.

No mutation endpoints. The activation path lives in admin/router.py.
RequireAdmin() gates every route (404 surface-hiding to non-admins).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.compliance.service import is_engine_version_activated, list_engine_versions
from dhanradar.db import get_db
from dhanradar.deps import RequireAdmin, UserContext
from dhanradar.models.mf import MfFund
from dhanradar.scoring.engine.config import get_config

from .scoring_read_schemas import CoverageInfo, EngineVersionRecord, ScoringModelResponse

router = APIRouter(prefix="/admin", tags=["admin-scoring-read"])


@router.get("/scoring/model", response_model=ScoringModelResponse)
async def get_scoring_model(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScoringModelResponse:
    """Return the current scoring engine config, registry history, and coverage.

    ``provisional`` is True when the current model_version has no registry-activated
    row (i.e. the two-person + backtest gate was never run for this version).
    ``axis_weights`` keys are the Axis enum string values (e.g. "momentum").
    ``registry_versions`` lists the last 50 changelog rows, newest first.
    ``coverage.total_funds`` is the current mf.mf_funds row count.
    """
    cfg = get_config()

    # 1. Registry activation state (authoritative — DB registry wins over file flag)
    registry_activated = await is_engine_version_activated(db, cfg.model_version)
    provisional = not registry_activated

    # 2. Changelog history (newest first, limit 50)
    version_rows = await list_engine_versions(db, limit=50)

    # 3. MF fund coverage count
    total_funds = (await db.scalar(select(func.count()).select_from(MfFund))) or 0

    # 4. axis_weights: convert Axis enum keys to their string values
    axis_weights = {axis.value: weight for axis, weight in cfg.axis_weights.items()}

    return ScoringModelResponse(
        model_version=cfg.model_version,
        activated=registry_activated,
        provisional=provisional,
        methodology_url=cfg.methodology_url or None,
        created_by=cfg.created_by or None,
        axis_weights=axis_weights,
        coverage=CoverageInfo(total_funds=total_funds),
        registry_versions=[EngineVersionRecord(**row) for row in version_rows],
    )
