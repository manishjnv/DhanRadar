"""
DhanRadar — News items ORM model (news schema, B56).

Stores ONLY headline metadata: title, source, canonical_url, published_at,
category.  Article body/excerpt is NEVER stored (copyright compliance).
Tables live in the `news` schema (schema-per-concern, non-neg #7).
Alembic migration 0016 creates the DDL; this file is the SQLAlchemy source
of truth.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from dhanradar.models.base import Base

_SCHEMA = "news"


class NewsItem(Base):
    __tablename__ = "news_items"
    __table_args__ = (
        Index("ix_news_scope_pub", "scope", "published_at"),
        Index("ix_news_active", "is_active"),
        {"schema": _SCHEMA},
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    scope: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="market"
    )
    category: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    # Unique per item — canonical source URL (link-out only, never body).
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    provenance_source: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="admin_curated"
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(
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
