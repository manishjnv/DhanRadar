"""
DhanRadar — News API schemas (B56).

Public surface: title, source, url, published_at, category only.
Article body/excerpt is NEVER included (copyright + SEBI compliance).
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
