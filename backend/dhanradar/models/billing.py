"""
DhanRadar — Billing domain ORM models (schema `billing`).

`billing.plans` is the subscription-plan catalog (D4). Introduced additively:
`auth.subscriptions.plan` (TEXT, the raw Razorpay plan id) is retained; a new
nullable `auth.subscriptions.plan_id` FK → `billing.plans.id` is added for the
transition. Nothing is back-filled by the migration.

Schema-per-concern (architecture §B5): billing tables live in the `billing`
schema, never the flat public schema.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dhanradar.models.base import Base


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = {"schema": "billing"}

    # Stable string id (e.g. "pro_monthly"); also used as the public plan code.
    id: Mapped[str] = mapped_column(Text, primary_key=True)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    price_inr: Mapped[int] = mapped_column(Integer, nullable=False)
    # 'month' | 'year' | 'lifetime' (matches contracts/openapi.yaml Plan.interval)
    interval: Mapped[str] = mapped_column(Text, nullable=False)
    features: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
