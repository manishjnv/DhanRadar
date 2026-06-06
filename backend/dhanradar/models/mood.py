"""
DhanRadar — Mood Compass ORM models (architecture Mood Compass Module).

Tables live in the `mood` schema (schema-per-concern, non-neg #7). Alembic
migration 0007 creates the DDL; this file is the SQLAlchemy source of truth.

The market regime is EXPLICITLY DISTINCT from the per-security DhanRadar Score and
is never an input to security rankings (architecture §scoring-integration). The
numeric `mood_score`/`confidence_score` are SERVER-SIDE only (tier/no-numeric posture,
non-neg #2) — the public surface shows the `regime` bucket + `confidence_band` +
commentary, never a number.

`mood_history` (pgvector `vector(11)`, for the AI-Enrichment historical analogues)
is deferred with that module — not created here.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Integer, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dhanradar.models.base import Base

_SCHEMA = {"schema": "mood"}


class MarketMood(Base):
    __tablename__ = "market_mood"
    __table_args__ = _SCHEMA

    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    snapshot_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Server-side numerics (never serialized to a client surface, non-neg #2).
    mood_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)  # 0–100
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)  # 0–1
    # Public-safe projections.
    regime: Mapped[str] = mapped_column(Text, nullable=False)  # bucket label
    confidence_band: Mapped[str] = mapped_column(Text, nullable=False)  # high|medium|low|insufficient_data
    inputs_available: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    input_vector: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    contributing_factors: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'"))
    contradicting_factors: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'"))
    ai_commentary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_quality: Mapped[str] = mapped_column(Text, nullable=False, server_default="ok")  # ok|degraded
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
