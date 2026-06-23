"""
DhanRadar — Admin Phase 3+5: Platform response schemas.

Covers: feature flags, CAS failure support, analytics overview,
notification health (read-only), and broadcast composer (mutation, Phase 5).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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
    support_notes: str | None = None


class CasNotesRequest(BaseModel):
    """Body for POST /admin/support/cas-failures/{job_id}/notes.

    ``notes`` annotates a failed CAS job for support triage. An empty string is
    allowed and clears the note (sets the column to ''); the max length caps
    operator free-text to keep the column bounded.
    """

    notes: str = Field(..., max_length=2000)


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


# ---------------------------------------------------------------------------
# Phase 5: Admin broadcast composer (mutation schemas)
# ---------------------------------------------------------------------------


class BroadcastRequest(BaseModel):
    """Body for POST /admin/notifications/broadcast.

    ``confirm`` must be explicitly True — prevents accidental broadcasts from
    misconfigured clients or copy-paste errors (one extra field = the intent is
    unambiguous).  ``channel`` is fixed to ``telegram_public`` for the MVP;
    extend to a Union[Literal] when email/WhatsApp channels are wired.
    """

    title: str = Field(..., min_length=1, max_length=120)
    body: str = Field(..., min_length=1, max_length=1000)
    channel: Literal["telegram_public"] = "telegram_public"
    confirm: bool = False


class BroadcastResponse(BaseModel):
    """Successful broadcast confirmation returned to the admin caller."""

    ok: bool
    delivered: bool
    channel: str
    broadcast_id: str  # the echoed Idempotency-Key, usable for audit lookups
