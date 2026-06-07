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

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.compliance import service
from dhanradar.compliance.service import (
    ActivationConflictError,
    DisclaimerConflictError,
)
from dhanradar.db import get_db
from dhanradar.deps import RequireAdmin, UserContext

from .schemas import (
    ActivateDisclaimerResponse,
    CreateDisclaimerRequest,
    CreateDisclaimerResponse,
    LabelChurnResponse,
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
    return ActivateDisclaimerResponse(**result)


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
