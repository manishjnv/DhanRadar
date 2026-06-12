"""
DhanRadar — News API schemas (B56 / B56-f4).

Public surface: title, source, url, published_at, category only.
Article body/excerpt is NEVER included (copyright + SEBI compliance).

B56-f4 additions: AdminNewsItem, CreateNewsItemRequest, UpdateNewsItemRequest
for the admin-managed CRUD workflow (RequireAdmin-gated).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NewsItem(BaseModel):
    title: str
    source: str
    url: str
    published_at: datetime
    category: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# B56-f4 — Admin CRUD schemas
# ---------------------------------------------------------------------------


class AdminNewsItem(BaseModel):
    id: str
    scope: str
    category: str
    title: str
    source: str
    canonical_url: str
    published_at: datetime
    provenance_source: str
    fetched_at: datetime
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateNewsItemRequest(BaseModel):
    title: str
    source: str
    canonical_url: str
    category: str
    scope: str = "market"
    published_at: datetime | None = None


class UpdateNewsItemRequest(BaseModel):
    title: str | None = None
    source: str | None = None
    canonical_url: str | None = None
    category: str | None = None
    scope: str | None = None
    published_at: datetime | None = None
    is_active: bool | None = None
