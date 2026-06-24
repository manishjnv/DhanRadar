"""DhanRadar — Admin module Pydantic schemas (B26)."""

from __future__ import annotations

from pydantic import BaseModel, Field


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


# ---------------------------------------------------------------------------
# B6/B28 — two-person scoring-engine activation gate schemas
# ---------------------------------------------------------------------------


class ActivateModelRequest(BaseModel):
    backtest_passed: bool = False
    methodology_url: str | None = None
    backtest: dict | None = Field(None, description="Backtest results summary (free-form JSONB).")
    drift: dict | None = Field(None, description="Drift metrics vs prior version (free-form JSONB).")


class ActivateModelResponse(BaseModel):
    model_version: str
    created_by: str
    approved_by: str | None
    two_person_ok: bool
    activated: bool
    activated_at: str | None
    methodology_url: str | None
    backtest: dict | None = None
    drift: dict | None = None


class ModelActivationStatusResponse(BaseModel):
    model_version: str
    file_activated: bool
    registry_activated: bool
    effective_activated: bool
    provisional: bool
