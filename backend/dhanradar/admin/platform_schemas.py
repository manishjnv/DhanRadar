"""
DhanRadar — Admin Phase 3: Platform read-only response schemas.

Covers: feature flags, CAS failure support, analytics overview,
and notification health. All read-only — no mutation schemas.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FeatureFlagResponse(BaseModel):
    key: str
    value: bool
    description: str
    source: str   # always "env"
    mutable: bool  # always False (flags are env-only, no runtime toggle)


class CasFailureRecord(BaseModel):
    job_id: str
    user_id: str
    status: str
    error_message: str | None
    created_at: datetime | None
    completed_at: datetime | None


class FunnelStats(BaseModel):
    cas_uploaded: int
    portfolio_created: int
    report_generated: int


class AnalyticsOverviewResponse(BaseModel):
    signups_total: int
    signups_30d: int
    cas_uploads_total: int
    cas_uploads_30d: int
    portfolios_created: int
    reports_generated: int
    premium_conversions: int
    funnel: FunnelStats
    conversion_rate_pct: float


class QueueDepth(BaseModel):
    telegram: int
    email: int


class TemplateInfo(BaseModel):
    id: str


class NotificationHealthResponse(BaseModel):
    queue_depth: QueueDepth
    sent: int
    failed: int
    rate_capped: int
    deferred: int
    last_sent_at: datetime | None
    templates: list[TemplateInfo]
    broadcast_available: bool
