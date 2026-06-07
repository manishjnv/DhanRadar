"""DhanRadar — Admin module Pydantic schemas (B26)."""

from __future__ import annotations

from pydantic import BaseModel


class CreateDisclaimerRequest(BaseModel):
    version: str
    content: str
    type: str = "ai_recommendation"


class CreateDisclaimerResponse(BaseModel):
    version: str
    type: str
    active: bool
    created_by: str


class ActivateDisclaimerResponse(BaseModel):
    version: str
    type: str
    active: bool
    effective_from: str
    snapshot_status: str
    snapshot_key: str | None


class LabelChurnResponse(BaseModel):
    recommendation_type: str
    previous_day: str | None
    current_day: str | None
    universe: int
    changed: int
    churn: float
    threshold: float
    decision: str
    requires_human_review: bool
    distribution_violations: list[str]
    reason: str
