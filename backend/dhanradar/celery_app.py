"""
DhanRadar — Celery application instance.

Timezone: Asia/Kolkata (IST) — beat schedule times in the Implementation Plan
are expressed in IST; enable_utc=False ensures Celery honours them correctly.

Beat schedule is intentionally empty here — Phase 5 fills it in once the
scheduled tasks are validated and the cron windows are confirmed.
"""

from __future__ import annotations

from celery import Celery
from celery.signals import (
    setup_logging,
    task_failure,
    task_postrun,
    task_prerun,
    task_revoked,
)
from structlog.contextvars import bind_contextvars, clear_contextvars

from dhanradar.config import settings
from dhanradar.core.logging import configure_logging

celery_app = Celery(
    "dhanradar",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    # Explicit task-module imports so EVERY worker registers EVERY task on boot.
    # Do NOT rely on autodiscover_tasks(["dhanradar.tasks"]) — that resolves to
    # the non-existent module `dhanradar.tasks.tasks` (package + default
    # related_name="tasks") and `tasks/__init__.py` is empty, so the worker would
    # register ZERO tasks and silently discard every message as "unregistered"
    # (prod incident 2026-06-08: CAS jobs hung at status='queued'). Keep this list
    # in sync with the task modules under dhanradar/tasks/ (test_celery_task_registration).
    include=[
        "dhanradar.tasks.mf",
        "dhanradar.tasks.batch",
        "dhanradar.tasks.mood",
        "dhanradar.tasks.misc",
        "dhanradar.tasks.compliance",
        "dhanradar.tasks.news",
    ],
)

# ---------------------------------------------------------------------------
# Logging — disable Celery's logger hijack so our structlog JSON config is used.
# The setup_logging signal re-applies configure_logging() inside the worker process.
# ---------------------------------------------------------------------------
celery_app.conf.worker_hijack_root_logger = False


@setup_logging.connect
def _configure_worker_logging(**_: object) -> None:
    """Apply structlog JSON config when the Celery worker process starts."""
    configure_logging()


@task_prerun.connect
def _bind_log_context(
    task_id: str | None = None,
    task: object = None,
    args: object = None,
    kwargs: object = None,
    **_: object,
) -> None:
    """Bind per-task structlog context before each task runs.

    Clears any stale context from a previous task on this worker process first
    (contextvar-leak guard — the same OS thread/greenlet may be reused).
    """
    clear_contextvars()
    task_name = getattr(task, "name", None)
    request_id = (kwargs or {}).get("request_id") if isinstance(kwargs, dict) else None
    bind_contextvars(task=task_name, task_id=task_id, request_id=request_id)


@task_postrun.connect
def _clear_log_context_postrun(**_: object) -> None:
    """Clear structlog context after a task completes (prevents cross-task leakage)."""
    clear_contextvars()


@task_failure.connect
def _clear_log_context_failure(**_: object) -> None:
    """Clear structlog context after a task fails (prevents cross-task leakage)."""
    clear_contextvars()


@task_revoked.connect
def _clear_log_context_revoked(**_: object) -> None:
    """Clear context on revoke/SIGTERM/expiry — task_postrun/failure do NOT fire
    for a revoked task, so without this a revoked task's user_ref/request_id can
    survive on the worker and misattribute the next task's logs (DPDP leak)."""
    clear_contextvars()


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
    # Route news refresh to the existing batch worker (no dedicated news worker).
    "dhanradar.tasks.news.*": {"queue": "batch"},
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
    # Fund metrics precompute — 00:15 IST; must run after nav_daily_fetch so
    # metrics reflect the day's fresh NAV.
    "mf-metrics-refresh": {
        "task": "dhanradar.tasks.mf.mf_metrics_refresh",
        "schedule": crontab(hour=0, minute=15),
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
    # Compliance audit ↔ disclaimers reconcile (B34) — 02:30 IST daily. Flags any
    # served disclaimer_version missing from the registry (compliance gap alert).
    "compliance-reconcile-disclaimers": {
        "task": "dhanradar.tasks.compliance.reconcile_audit_disclaimers",
        "schedule": crontab(hour=2, minute=30),
    },
    # Mood Compass twice-daily snapshot — 09:00 & 16:00 IST (architecture cadence).
    "mood-compute-snapshot": {
        "task": "dhanradar.tasks.mood.compute_mood_snapshot",
        "schedule": crontab(hour="9,16", minute=0),
    },
    # Plus monthly re-score — 1st of each month, 03:00 IST. Re-scores every Plus
    # user's current holdings from the latest NAV (no re-upload required).
    "mf-monthly-rescore": {
        "task": "dhanradar.tasks.mf.monthly_rescore_plus_users",
        "schedule": crontab(day_of_month=1, hour=3, minute=0),
    },
    # News curated refresh — every 30 min best-effort (B56). Upserts admin-curated
    # headline rows; failures are caught so the endpoint always reads cached rows.
    "news-refresh-market": {
        "task": "dhanradar.tasks.news.refresh_market_news",
        "schedule": crontab(minute="*/30"),
    },
    # Stuck-job reaper — every 5 min. Marks CAS jobs orphaned at a non-terminal
    # status (queued/parsing/scoring) for more than 10 min as failed='stuck_timeout'
    # so the frontend stops spinning indefinitely.  Also clears Redis dedup keys so a
    # clean re-upload reprocesses.  Idempotent (completed_at IS NULL guard).
    "mf-reap-stuck-cas": {
        "task": "dhanradar.tasks.mf.reap_stuck_cas_jobs",
        "schedule": crontab(minute="*/5"),
    },
}

# ---------------------------------------------------------------------------
# Task registration is via the explicit `include=[...]` list on the Celery()
# constructor above (autodiscover_tasks was removed — it silently registered
# nothing; see the comment there). The worker imports those modules on boot.
# ---------------------------------------------------------------------------
