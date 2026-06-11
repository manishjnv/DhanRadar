"""
DhanRadar — Concept-Explainer response schemas (C1).

Every public response carries the not-advice disclosure bundle (non-neg #9):
`disclosure` (concepts-specific text), `not_advice`, and the in-force
`disclaimer_version`. No numeric-score surface here — this is evergreen
educational reference content.
"""

from __future__ import annotations

from pydantic import BaseModel


class _Disclosed(BaseModel):
    """Mixin fields every concepts response carries (non-neg #9)."""

    disclosure: str
    not_advice: str
    disclaimer_version: str


class ConceptSummary(BaseModel):
    slug: str
    title: str
    summary: str
    category: str


class ConceptListResponse(_Disclosed):
    concepts: list[ConceptSummary]


class ConceptDetail(_Disclosed):
    slug: str
    title: str
    summary: str
    body_md: str
    category: str
    updated_at: str
