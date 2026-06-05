"""
DhanRadar — Celery application instance.

Timezone: Asia/Kolkata (IST) — beat schedule times in the Implementation Plan
are expressed in IST; enable_utc=False ensures Celery honours them correctly.

Beat schedule is intentionally empty here — Phase 5 fills it in once the
scheduled tasks are validated and the cron windows are confirmed.
"""

from __future__ import annotations

from celery import Celery

from dhanradar.config import settings

celery_app = Celery(
    "dhanradar",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# ---------------------------------------------------------------------------
# Timezone — MUST be IST; beat schedule times in the plan are IST
# ---------------------------------------------------------------------------
celery_app.conf.timezone = "Asia/Kolkata"
celery_app.conf.enable_utc = False

# ---------------------------------------------------------------------------
# Task routing
# ---------------------------------------------------------------------------
celery_app.conf.task_routes = {
    "dhanradar.tasks.batch.*": {"queue": "batch"},
    "dhanradar.tasks.mood.*":  {"queue": "mood"},
    "dhanradar.tasks.misc.*":  {"queue": "misc"},
}

# ---------------------------------------------------------------------------
# Beat schedule
# Phase 5 will populate this dict with the scheduled data-fetch and scoring
# tasks once cron windows are confirmed (ref: Implementation Plan Phase 5).
# ---------------------------------------------------------------------------
celery_app.conf.beat_schedule = {}  # populated in Phase 5

# ---------------------------------------------------------------------------
# Auto-discover tasks
# ---------------------------------------------------------------------------
celery_app.autodiscover_tasks(["dhanradar.tasks"])
