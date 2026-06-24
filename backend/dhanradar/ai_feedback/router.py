"""User-facing AI output feedback submission — POST /api/v1/ai/feedback."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.compliance import service
from dhanradar.compliance.service import DuplicateFeedbackError
from dhanradar.db import get_db
from dhanradar.deps import RequireTier, UserContext

router = APIRouter(prefix="/ai", tags=["ai-feedback"])


class FeedbackRequest(BaseModel):
    audit_id: str = Field(..., description="ID of the ai_recommendation_audit row being rated.")
    helpful: bool = Field(..., description="True = helpful, False = not helpful.")
    feedback_text: str | None = Field(None, max_length=500)


class FeedbackCreated(BaseModel):
    id: str
    helpful: bool


@router.post("/feedback", response_model=FeedbackCreated, status_code=201)
async def submit_feedback(
    body: FeedbackRequest,
    user: Annotated[UserContext, Depends(RequireTier("free"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FeedbackCreated:
    """Submit thumbs-up/down feedback on an AI output.

    Append-only — no updates or deletes. Requires any authenticated (free+) user.
    One submission per user per audit output — duplicate returns 409.

    DPDP: stores ``user_id``. ``RequireConsent`` must be wired to this route
    before it goes live with real users (tracked in BLOCKERS.md B64).

    ``audit_id`` must be a valid UUID string; a malformed value returns 422.
    """
    try:
        row = await service.record_feedback(
            db,
            audit_id=body.audit_id,
            user_id=str(user.user_id),
            helpful=body.helpful,
            feedback_text=body.feedback_text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="invalid_audit_id") from exc
    except DuplicateFeedbackError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="feedback_already_submitted")
    return FeedbackCreated(id=row["id"], helpful=row["helpful"])
