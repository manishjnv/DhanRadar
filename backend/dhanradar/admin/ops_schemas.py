"""
DhanRadar — Admin Ops Pydantic schemas (Phase 1).

Separate from the compliance schemas in admin/schemas.py so the compliance load-bearing
contracts are never accidentally widened. These schemas serve the read-only and
operational-control endpoints: health, sources, tasks, runs, quality, and the is_admin
auth extension.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class RecentFailure(BaseModel):
    source: str
    reason: str
    failed_at: str
    # "failed" = the run produced nothing; "partial" = degraded but a fallback
    # or subset succeeded. Display-only distinction for the overview feed.
    status: str = "failed"


class RecentSignup(BaseModel):
    display_name: str
    plan: str
    joined_at: str


class RecentAlert(BaseModel):
    type: str
    message: str
    severity: str
    created_at: str


class AdminAlert(BaseModel):
    """One attention item for the admin alert bell. DERIVED from current state, not a
    failure-event log — so a job that NEVER RAN (dead scheduler) is still surfaced."""

    key: str
    severity: Literal["critical", "warning", "info"]
    title: str
    detail: str
    since: str | None = None  # ISO timestamp the condition has held from, if known
    href: str | None = None  # admin/app path to act on it


class AdminAlertsResponse(BaseModel):
    count: int
    alerts: list[AdminAlert]


class HealthResponse(BaseModel):
    sources_healthy: int
    sources_total: int
    last_nav_sync: str | None
    total_schemes: int
    active_users: int
    premium_users: int
    advice_boundary_breaches_today: int
    low_groundedness_flags_7d: int
    recent_failures: list[RecentFailure]
    recent_signups: list[RecentSignup]
    recent_alerts: list[RecentAlert]


# ---------------------------------------------------------------------------
# Sources endpoint
# ---------------------------------------------------------------------------


class SourceRow(BaseModel):
    source_key: str
    name: str
    tier: str
    description: str
    method: str
    schedule_display: str
    cost: str
    last_success_at: str | None
    last_records: int | None
    status: str  # 'Healthy' | 'Warning' | 'Failed' | 'Paused' | 'Planned'
    paused: bool


class SyncResponse(BaseModel):
    task_id: str


class OkResponse(BaseModel):
    ok: bool = True


# ---------------------------------------------------------------------------
# Tasks endpoint
# ---------------------------------------------------------------------------


class TaskRow(BaseModel):
    task_name: str
    schedule_display: str
    last_run_at: str | None
    next_run_at: str | None
    last_status: str | None
    last_duration_s: float | None
    last_rows: int | None
    paused: bool


# ---------------------------------------------------------------------------
# Runs endpoints
# ---------------------------------------------------------------------------


class RunListRow(BaseModel):
    run_id: int
    source: str
    task_name: str
    started_at: str
    finished_at: str | None
    duration_s: float | None
    records_written: int | None
    records_failed: int | None
    status: str
    error_class: str | None


class RunDetailResponse(RunListRow):
    error_detail: str | None
    raw_file_path: str | None
    run_metadata: dict[str, Any] | None


# ---------------------------------------------------------------------------
# Quality endpoint
# ---------------------------------------------------------------------------


class QualityRow(BaseModel):
    metric_key: str
    label: str
    current_value: float | None
    threshold: float | None
    unit: str
    status: str  # 'ok' | 'warning' | 'critical'
    acknowledged_until: str | None


class AcknowledgeRequest(BaseModel):
    duration_days: int


# ---------------------------------------------------------------------------
# Mood-status endpoint
# ---------------------------------------------------------------------------


class MoodStatus(BaseModel):
    snapshot_at: str | None          # ISO of latest snapshot_time
    regime: str | None
    inputs_available: int             # of 11
    total_signals: int = 11
    data_quality: str | None          # 'ok' | 'degraded'
    signals_present: list[str]        # keys present in the latest input_vector
    upstox_fii_flows: bool            # whether fii_flows fed the latest snapshot
    upstox_dii_flows: bool
    upstox_put_call_ratio: bool
