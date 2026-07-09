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
from dhanradar.db import get_admin_db
from dhanradar.deps import RequireAdmin, UserContext
from dhanradar.models.mf import MfFund, MfFundRanks
from dhanradar.scoring.engine.config import get_config

from ._people import resolve_user_emails
from .amc_coverage_router import _SCHEME_KEY
from .scoring_read_schemas import CoverageInfo, EngineVersionRecord, ScoringModelResponse

router = APIRouter(prefix="/admin", tags=["admin-scoring-read"])


@router.get("/scoring/model", response_model=ScoringModelResponse)
async def get_scoring_model(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
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

    # 2. Changelog history (newest first, limit 50) — enrich the created_by /
    # approved_by UUIDs with emails so the operator sees people, not ids.
    version_rows = await list_engine_versions(db, limit=50)
    emails = await resolve_user_emails(
        db,
        {cfg.created_by}
        | {row.get("created_by") for row in version_rows}
        | {row.get("approved_by") for row in version_rows},
    )
    for row in version_rows:
        row["created_by_email"] = emails.get(str(row.get("created_by")))
        row["approved_by_email"] = emails.get(str(row.get("approved_by")))

    # 3. MF fund coverage counts.
    #    total_funds  — every mf_funds row (one per plan-variant ISIN)
    #    total_schemes — distinct schemes (same dedup key as the AMC Coverage page)
    #    labelled_funds — distinct ISINs labelled in the latest ranking run
    total_funds = (await db.scalar(select(func.count()).select_from(MfFund))) or 0
    total_schemes = (
        await db.scalar(select(func.count(func.distinct(_SCHEME_KEY))))
    ) or 0
    latest_rank_date = select(func.max(MfFundRanks.as_of_date)).scalar_subquery()
    labelled_funds = (
        await db.scalar(
            select(func.count(func.distinct(MfFundRanks.isin))).where(
                MfFundRanks.as_of_date == latest_rank_date
            )
        )
    ) or 0

    # 4. axis_weights: convert Axis enum keys to their string values
    axis_weights = {axis.value: weight for axis, weight in cfg.axis_weights.items()}

    return ScoringModelResponse(
        model_version=cfg.model_version,
        activated=registry_activated,
        provisional=provisional,
        methodology_url=cfg.methodology_url or None,
        created_by=cfg.created_by or None,
        created_by_email=emails.get(str(cfg.created_by)) if cfg.created_by else None,
        axis_weights=axis_weights,
        coverage=CoverageInfo(
            total_funds=total_funds,
            total_schemes=total_schemes,
            labelled_funds=labelled_funds,
        ),
        registry_versions=[EngineVersionRecord(**row) for row in version_rows],
    )
