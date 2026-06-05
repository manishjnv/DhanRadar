"""
DhanRadar — Shared declarative base for all SQLAlchemy ORM models.

All domain models import `Base` from here so Alembic can discover every
table through a single `target_metadata = Base.metadata`.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Project-wide declarative base.  All models must inherit from this."""
    pass
