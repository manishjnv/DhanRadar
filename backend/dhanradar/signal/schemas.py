"""Pydantic request/response schemas for the Signal API."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_validator


class SignalRulesOut(BaseModel):
    nifty_threshold: float
    vix_threshold: float
    breadth_threshold: float
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


# ---------------------------------------------------------------------------
# Journal (Phase 2 — Reflect tab)
# ---------------------------------------------------------------------------

VALID_DECISIONS = {"deployed", "watched", "skipped"}
VALID_EMOTIONS = {"fearful", "calm", "excited", "fomo", "disciplined"}


class JournalEntryCreate(BaseModel):
    date: date
    decision: str
    amount_deployed: Decimal | None = None
    emotions: list[str] = []
    notes: str | None = None
    nifty_pct: float | None = None
    vix_level: float | None = None
    breadth_ratio: float | None = None

    @field_validator("decision")
    @classmethod
    def decision_must_be_valid(cls, v: str) -> str:
        if v not in VALID_DECISIONS:
            raise ValueError(f"decision must be one of: {', '.join(sorted(VALID_DECISIONS))}")
        return v

    @field_validator("emotions")
    @classmethod
    def emotions_must_be_valid(cls, v: list[str]) -> list[str]:
        invalid = set(v) - VALID_EMOTIONS
        if invalid:
            raise ValueError(f"unknown emotions: {invalid}")
        return v


class JournalEntryOut(BaseModel):
    id: UUID
    date: date
    decision: str
    amount_deployed: Decimal | None = None
    emotions: list[str] = []
    notes: str | None = None
    nifty_pct: float | None = None
    vix_level: float | None = None
    breadth_ratio: float | None = None
    signal_state: str | None = None
    fomo_avoided: bool | None = None
    premature: bool | None = None
    created_at: datetime

    @classmethod
    def from_orm_row(cls, row: Any) -> JournalEntryOut:
        snapshot: dict[str, Any] = row.market_snapshot or {}
        return cls(
            id=row.id,
            date=row.date,
            decision=row.decision or "",
            amount_deployed=row.amount,
            emotions=row.emotion or [],
            notes=row.notes,
            nifty_pct=snapshot.get("nifty_pct"),
            vix_level=snapshot.get("vix_level"),
            breadth_ratio=snapshot.get("breadth_ratio"),
            signal_state=row.signal_state,
            fomo_avoided=row.fomo_avoided,
            premature=row.premature,
            created_at=row.created_at,
        )


class BehaviourScoresOut(BaseModel):
    discipline_score: int
    patience_score: int
    investor_score: int
    trust_wins: int
    trust_total: int
    has_trust_data: bool


class JournalOut(BaseModel):
    entries: list[JournalEntryOut]
    behaviour: BehaviourScoresOut


class JournalEntryCreatedOut(BaseModel):
    id: UUID
    created_at: datetime


class LearningArticleOut(BaseModel):
    slug: str
    title: str
    read_min: int
    link: str


class LearningContentOut(BaseModel):
    articles: list[LearningArticleOut]


class SignalNotificationOut(BaseModel):
    id: UUID
    message: str
    signal_state: str
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationsResponse(BaseModel):
    unread: list[SignalNotificationOut]
