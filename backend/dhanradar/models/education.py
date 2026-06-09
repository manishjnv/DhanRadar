"""
DhanRadar — Tax-Education domain ORM models (G8).

Static, FY-aware EDUCATIONAL content on Indian MF taxation. Tables live in the
`education` schema (schema-per-concern, non-neg #7). Pure reference content — NO
user FK, NO personal data (DPDP-irrelevant); rows are authored, not user-generated.
Alembic migration 0015 creates the DDL; this file is the SQLAlchemy source of truth.

The authored content lives in `dhanradar/education/content.py` (ci_guards-scanned)
and is loaded into this table by the idempotent `python -m dhanradar.education.seed`
command — the table ships EMPTY from the migration.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from dhanradar.models.base import Base

_SCHEMA = {"schema": "education"}


class TaxEducationArticle(Base):
    """One educational tax article. `body_md` is Markdown; `fy_label` + `source_note`
    carry the dated FY citation so figures are never presented as timeless. No numeric
    score surface — this is pure educational reference content."""

    __tablename__ = "tax_education_articles"
    __table_args__ = (
        Index("ix_tax_edu_category", "category"),
        Index("ix_tax_edu_sort", "sort_order"),
        _SCHEMA,
    )

    slug: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    # Display label for the financial year the figures apply to, e.g.
    # "FY 2025-26 (AY 2026-27)". Figures are always shown with this label.
    fy_label: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    # Dated source citation, e.g. "As per Finance Act 2024; applicable FY 2025-26."
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optional FY-relevance window for filtering stale articles when slabs change.
    fy_relevant_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    fy_relevant_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
