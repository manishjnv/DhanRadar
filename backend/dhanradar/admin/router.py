"""
DhanRadar — Admin compliance router (B26).

Every route is gated by ``RequireAdmin()`` (404 to ALL non-admins, including
authenticated non-admins — surface-hiding). These are mutating compliance actions:
disclaimer version management + label-churn operator review.

Idempotency-Key (non-neg #6) is deferred for this slice:
  - ``POST /disclaimers`` is conflict-guarded (second POST with same version → 409)
    so duplicate-submit safety holds without a key.
  - ``POST /disclaimers/{version}/activate`` is naturally idempotent (re-activating
    an already-active version is a no-op in practice; the DB update is safe to
    repeat).
  - Tracked as a B30-class residual for a future hardening pass.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.audit.service import record_admin_action
from dhanradar.compliance import service
from dhanradar.compliance.service import (
    ActivationConflictError,
    DisclaimerConflictError,
)
from dhanradar.db import get_db
from dhanradar.deps import RequireAdmin, UserContext
from dhanradar.scoring.engine import activation
from dhanradar.scoring.engine.config import get_config
from dhanradar.scoring.engine.governance import TwoPersonGateError

from .schemas import (
    ActivateDisclaimerResponse,
    ActivateModelRequest,
    ActivateModelResponse,
    CreateDisclaimerRequest,
    CreateDisclaimerResponse,
    LabelChurnResponse,
    ModelActivationStatusResponse,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post(
    "/disclaimers",
    response_model=CreateDisclaimerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_disclaimer(
    body: CreateDisclaimerRequest,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CreateDisclaimerResponse:
    """Create a new disclaimer version (INACTIVE). Activation is a separate step."""
    try:
        result = await service.create_disclaimer(
            db,
            version=body.version,
            content=body.content,
            type=body.type,
            created_by=admin.user_id,
        )
    except DisclaimerConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="disclaimer_version_exists",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid_disclaimer: {exc}",
        ) from exc
    return CreateDisclaimerResponse(**result)


@router.post(
    "/disclaimers/{version}/activate",
    response_model=ActivateDisclaimerResponse,
)
async def activate_disclaimer(
    version: str,
    request: Request,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ActivateDisclaimerResponse:
    """Promote a disclaimer version to active (single-active-per-type invariant)."""
    try:
        result = await service.activate_disclaimer(
            db, version=version, activated_by=admin.user_id
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="disclaimer_not_found",
        ) from exc
    except ActivationConflictError as exc:
        # A concurrent activation of a different version won the race; the loser's
        # commit was rejected by the partial-unique index. Surface a clean 409.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="activation_conflict",
        ) from exc
    # Fire-and-forget audit — failure MUST NOT break the handler.
    await record_admin_action(
        admin_id=admin.user_id,
        action="activate_disclaimer",
        target_type="disclaimer",
        target_id=version,
        result="success",
        request_id=getattr(request.state, "request_id", None),
    )
    return ActivateDisclaimerResponse(**result)


# ---------------------------------------------------------------------------
# B6/B28 — two-person scoring-engine activation gate
# The registry (rating_engine_changelog) is authoritative; the engine's sync
# score() uses the file flag as the no-DB-context fallback.
# ---------------------------------------------------------------------------


@router.post(
    "/scoring/{model_version}/activate",
    response_model=ActivateModelResponse,
)
async def activate_scoring_model(
    model_version: str,
    body: ActivateModelRequest,
    request: Request,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ActivateModelResponse:
    """Activate a scoring model_version (B6/B28 two-person + backtest gate).

    The calling admin becomes ``approved_by``.  Only the currently loaded config
    version is activatable; any other model_version returns 404.
    """
    cfg = get_config()
    if model_version != cfg.model_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="model_version_not_found",
        )

    factors_after = {a.value: w for a, w in cfg.axis_weights.items()}

    try:
        entry = await activation.activate_model_version(
            db,
            model_version=model_version,
            created_by=cfg.created_by,
            approved_by=admin.user_id,
            factors_before={},
            factors_after=factors_after,
            methodology_url=(body.methodology_url or cfg.methodology_url),
            backtest_passed=body.backtest_passed,
        )
    except TwoPersonGateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="two_person_gate_failed",
        ) from exc
    except activation.BacktestNotPassedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="backtest_not_passed",
        ) from exc
    except activation.AlreadyActivatedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="model_already_activated",
        ) from exc

    # Fire-and-forget audit — failure MUST NOT break the handler.
    await record_admin_action(
        admin_id=admin.user_id,
        action="activate_scoring_model",
        target_type="scoring_model",
        target_id=model_version,
        result="success",
        request_id=getattr(request.state, "request_id", None),
    )
    return ActivateModelResponse(
        model_version=entry["model_version"],
        created_by=entry["created_by"],
        approved_by=entry["approved_by"],
        two_person_ok=entry["two_person_ok"],
        activated=entry["activated"],
        activated_at=entry["activated_at"],
        methodology_url=entry["methodology_url"],
    )


@router.get(
    "/scoring/{model_version}/status",
    response_model=ModelActivationStatusResponse,
)
async def get_scoring_model_status(
    model_version: str,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ModelActivationStatusResponse:
    """Return the activation status of a scoring model_version (B6/B28).

    ``file_activated`` is the static flag from the loaded JSON config.
    ``registry_activated`` is the authoritative DB-registry state.
    ``effective_activated`` is True when either source is True.
    """
    cfg = get_config()
    file_activated = cfg.activated if model_version == cfg.model_version else False
    registry_activated = await service.is_engine_version_activated(db, model_version)
    # `effective` = what a serving surface would actually observe (the sync score()
    # path still reads the file flag). But `provisional` tracks the GATE: a model is
    # non-provisional ONLY once it has a registry activation (two-person + backtest).
    # A manual file-flip without a registry row stays provisional — the discrepancy is
    # visible via file_activated vs registry_activated.
    effective = file_activated or registry_activated
    return ModelActivationStatusResponse(
        model_version=model_version,
        file_activated=file_activated,
        registry_activated=registry_activated,
        effective_activated=effective,
        provisional=not registry_activated,
    )


@router.get(
    "/audit/label-churn",
    response_model=LabelChurnResponse,
)
async def get_label_churn(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    recommendation_type: str = "educational_label",
) -> LabelChurnResponse:
    """Churn review over the two most-recent audit batch days for a recommendation type."""
    try:
        result = await service.label_churn_review(db, recommendation_type=recommendation_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid_recommendation_type: {exc}",
        ) from exc
    return LabelChurnResponse(**result)
