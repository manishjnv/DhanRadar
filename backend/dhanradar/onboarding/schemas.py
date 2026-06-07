"""Pydantic v2 schemas for the onboarding risk-quiz endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RiskQuizRequest(BaseModel):
    answers: list[int] = Field(min_length=5, max_length=5)
    """5 option indices (0..3) — one per quiz question."""


class RiskQuizResponse(BaseModel):
    risk_profile: str
    """The computed risk profile: conservative | moderate | aggressive."""
