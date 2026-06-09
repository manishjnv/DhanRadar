"""
DhanRadar — Tax-Education response schemas (G8).

Every public response carries the not-advice disclosure bundle (non-neg #9):
`disclosure` (education-specific text), `not_advice`, and the in-force
`disclaimer_version`. No numeric-score surface here — this is reference content.
"""

from __future__ import annotations

from pydantic import BaseModel


class _Disclosed(BaseModel):
    """Mixin fields every education response carries (non-neg #9)."""

    disclosure: str
    not_advice: str
    disclaimer_version: str


class ArticleSummary(BaseModel):
    slug: str
    title: str
    summary: str
    category: str
    fy_label: str


class ArticleListResponse(_Disclosed):
    articles: list[ArticleSummary]


class ArticleDetail(_Disclosed):
    slug: str
    title: str
    summary: str
    body_md: str
    category: str
    fy_label: str
    source_note: str | None
    updated_at: str


class KeyDateItem(BaseModel):
    label: str
    date: str
    note: str


class CalendarResponse(_Disclosed):
    fy_label: str
    fy_start: str
    fy_end: str
    key_dates: list[KeyDateItem]
    elss_note: str
