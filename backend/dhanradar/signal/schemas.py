"""Pydantic request/response schemas for the Signal API."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_validator


class SignalRulesOut(BaseModel):
    nifty_threshold: Decimal
    vix_threshold: Decimal
    breadth_threshold: Decimal
    deploy_ladder: list[int]
    alerts_on: bool

    model_config = {"from_attributes": True}


class SignalRulesUpdate(BaseModel):
    nifty_threshold: Decimal
    vix_threshold: Decimal
    breadth_threshold: Decimal
    deploy_ladder: list[int]
    alerts_on: bool

    @field_validator("deploy_ladder")
    @classmethod
    def ladder_must_have_five_entries(cls, v: list[int]) -> list[int]:
        if len(v) != 5:
            raise ValueError("deploy_ladder must have exactly 5 entries")
        if sum(v) > 100:
            raise ValueError("deploy_ladder total must not exceed 100%")
        return v


class SignalDipFundOut(BaseModel):
    balance: Decimal
    monthly_addition: Decimal
    last_updated: datetime

    model_config = {"from_attributes": True}


class AddDipFundBody(BaseModel):
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v


class SignalDeploymentOut(BaseModel):
    id: UUID
    date: date
    amount: Decimal | None
    signal_state: str | None
    market_snapshot: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VIXOut(BaseModel):
    value: float
    change_pct: float
    market_open: bool


class BreadthOut(BaseModel):
    advances: int
    declines: int
    ad_ratio: float
    market_open: bool
