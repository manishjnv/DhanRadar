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
    "dhanradar.tasks.mf.*":    {"queue": "batch"},
    "dhanradar.tasks.compliance.*": {"queue": "batch"},
}

# ---------------------------------------------------------------------------
# Beat schedule (timezone = Asia/Kolkata, enable_utc=False above)
# ---------------------------------------------------------------------------
from celery.schedules import crontab  # noqa: E402

celery_app.conf.beat_schedule = {
    # AMFI NAV daily refresh — 23:30 IST (data-fetch pipeline; currently a stub
    # pending the AMFI NAVAll.txt fetch — Implementation Plan Phase 5 §2).
    "mf-nav-daily-fetch": {
        "task": "dhanradar.tasks.mf.nav_daily_fetch",
        "schedule": crontab(hour=23, minute=30),
    },
    # Raw CAS file purge — 24h backstop (anti-pattern guard). 02:00 IST.
    "mf-purge-cas-files": {
        "task": "dhanradar.tasks.mf.purge_cas_files",
        "schedule": crontab(hour=2, minute=0),
    },
    # Notification queue drain — every minute (Phase 6). Pops the Redis channel
    # queues, applies quiet-hours + rate caps, delivers, logs, retries transient.
    "notify-drain": {
        "task": "dhanradar.tasks.misc.drain_notifications",
        "schedule": crontab(minute="*"),
    },
    # Compliance audit → R2 daily archival (§4). 02:00 IST, 7-yr lifecycle.
    "compliance-archive-audit": {
        "task": "dhanradar.tasks.compliance.archive_audit_daily",
        "schedule": crontab(hour=2, minute=0),
    },
}

# ---------------------------------------------------------------------------
# Auto-discover tasks
# ---------------------------------------------------------------------------
celery_app.autodiscover_tasks(["dhanradar.tasks"])
