"""
DhanRadar — Concept-Explainer domain ORM models (C1).

Static, evergreen EDUCATIONAL content on core investing concepts. Tables live in
the `concepts` schema (schema-per-concern, non-neg #7). Pure reference content —
NO user FK, NO personal data (DPDP-irrelevant); rows are authored, not
user-generated. Alembic migration 0017 creates the DDL; this file is the
SQLAlchemy source of truth.

The authored content lives in `dhanradar/concepts/content.py` (ci_guards-scanned)
and is loaded into this table by the idempotent `python -m dhanradar.concepts.seed`
command — the table ships EMPTY from the migration.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from dhanradar.models.base import Base

_SCHEMA = {"schema": "concepts"}


class ConceptExplainer(Base):
    """One evergreen concept explainer. `body_md` is Markdown; numeric examples in
    the body are clearly labelled hypothetical illustrations, never projections.
    No numeric score surface — this is pure educational reference content."""

    __tablename__ = "concept_explainers"
    __table_args__ = (
        Index("ix_concepts_category", "category"),
        Index("ix_concepts_sort", "sort_order"),
        _SCHEMA,
    )

    slug: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
