"""DhanRadar — Billing API schemas (Pydantic v2)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PlanOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    name: str
    price_inr: int
    interval: str
    features: list[Any] = Field(default_factory=list)


class CheckoutRequest(BaseModel):
    # Only the plan is client-supplied. The user is taken from the session,
    # never from the request body (prevents creating a sub for another user).
    plan_id: str = Field(min_length=1, max_length=128)


class CheckoutResponse(BaseModel):
    order_id: str
    amount_inr: int
    razorpay_key_id: str
