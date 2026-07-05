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
        "dhanradar.tasks.signal_alerts",
        # Phase 6 — planned data sources (one module per source; task names are
        # explicitly "dhanradar.tasks.mf.*" so they match the mf batch route and the
        # admin source catalog, regardless of the module they live in).
        "dhanradar.tasks.mf_scheme_master",
        "dhanradar.tasks.mf_expense_ratio",
        "dhanradar.tasks.mf_fund_manager",
        "dhanradar.tasks.sebi_circulars",
        "dhanradar.tasks.macro_data",
        # W3 — AMFI free-source enrichment (Phase A verified 2026-07-05):
        # cap classification (half-yearly) + category-wise flows (monthly).
        # Riskometer (the 3rd candidate) was BLOCKED at Phase A — see
        # docs/project-state/DATA_SOURCES.md.
        "dhanradar.tasks.mf_cap_classification",
        "dhanradar.tasks.mf_category_flows",
        # BSE Star MF 2.0 webhook async processing (misc queue).
        "dhanradar.tasks.bse",
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
    # Signal daily alerts run in the batch queue (low-volume, once-daily).
    "dhanradar.tasks.signal_alerts.*": {"queue": "batch"},
    # BSE webhook processing — misc queue (NOT mood; mood worker is mem-capped).
    "dhanradar.tasks.bse.*": {"queue": "misc"},
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
    # Market-wide category rank — 01:00 IST; after metrics (00:15), before portfolio
    # refresh (01:30). Computes ordinal ranks within each sebi_category peer group
    # and upserts into mf_fund_ranks so the report surface can show "#1 of 30".
    "mf-compute-market-ranks": {
        "task": "dhanradar.tasks.mf.compute_market_ranks",
        "schedule": crontab(hour=1, minute=0),
    },
    # Portfolio daily refresh — 01:30 IST; after NAV (23:30) + metrics (00:15).
    # Rebuilds cached reports from stored holdings + today's NAV so users see a
    # fresh portfolio when they log in without re-uploading their CAS statement.
    "mf-daily-portfolio-refresh": {
        "task": "dhanradar.tasks.mf.daily_portfolio_refresh",
        "schedule": crontab(hour=1, minute=30),
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
    # Enrichment item 4 — daily regime-history snapshot, 16:05 IST (5 min after the
    # 16:00 compute_mood_snapshot run so mood:latest is fresh). PURE Redis cache
    # consumer: reads mood:latest, writes one mood.mood_regime_history row. Cold
    # cache -> no-op (fail-closed). Prerequisite for per-fund "performance by market
    # phase" (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §10.8).
    "mood-history-snapshot": {
        "task": "dhanradar.tasks.mood.mood_history_snapshot",
        "schedule": crontab(hour=16, minute=5),
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
    # Signal daily alert — 09:15 IST on weekdays. Creates in-app notification for
    # users whose signal is triggered. Idempotency guard: one unread per 20 hours.
    # Phase 4: reads live VIX + breadth from Redis cache pre-warmed by market-data-refresh.
    "signal-daily-alert": {
        "task": "dhanradar.tasks.signal_alerts.daily_signal_alert",
        "schedule": crontab(hour=9, minute=15, day_of_week="1-5"),
    },
    # Phase 4 — Market data refresh: pre-warm VIX + breadth cache every 15 min
    # during trading hours (09:00–16:00 IST, Mon–Fri). Makes /market/vix and
    # /market/breadth endpoints near-instant (serve from cache, not live fetch).
    "market-data-refresh": {
        "task": "dhanradar.tasks.signal_alerts.market_data_refresh",
        "schedule": crontab(minute="*/15", hour="9-16", day_of_week="1-5"),
    },
    # Phase 4 — Auto-log: insert a 'skipped' journal entry at 21:00 IST for users
    # who had a triggered/watch signal today but made no journal entry.
    "auto-log-no-action": {
        "task": "dhanradar.tasks.signal_alerts.auto_log_no_action",
        "schedule": crontab(hour=21, minute=0, day_of_week="1-5"),
    },
    # Phase 4 — SIP reminder: insert an in-app notification at 09:00 IST every day.
    # Phase 5: uses user's real sip_day from CAS; falls back to 1st of month.
    "sip-reminder": {
        "task": "dhanradar.tasks.signal_alerts.sip_reminder",
        "schedule": crontab(hour=9, minute=0),
    },
    # Phase 5 — Check achievements: evaluate unlock conditions for all users at 22:00 IST.
    # Idempotent — only adds achievements not already in earned_achievements[].
    "check-achievements": {
        "task": "dhanradar.tasks.signal_alerts.check_achievements",
        "schedule": crontab(hour=22, minute=0),
    },
    # ADR-0033(a) — SEBI monthly portfolio disclosure scraper — 10th of each month, 04:00 IST.
    # AMCs must publish by the 10th; running on the 10th catches all but the latest laggards.
    # Playwright URL-discovery results are Redis-cached 25 days so re-runs are cheap.
    "mf-constituents-fetch": {
        "task": "dhanradar.tasks.mf.mf_constituents_fetch",
        "schedule": crontab(day_of_month=10, hour=4, minute=0),
    },
    # Kite MF instrument enrichment — weekly, Saturday 03:00 IST (low-load window).
    # Fills plan_type / option_type on mf_funds rows where AMFI name-parsing left NULL.
    # No-op when KITE_* env vars are absent; access_token is TOTP-refreshed automatically.
    "mf-kite-enrich": {
        "task": "dhanradar.tasks.mf.mf_kite_enrich",
        "schedule": crontab(day_of_week=6, hour=3, minute=0),
    },
    # M2.2 — daily portfolio valuation series — 04:00 IST (after NAV fetch 23:30 +
    # daily_portfolio_refresh 01:30).  One upsert per portfolio: total market value
    # = Σ (units × latest NAV).  Foundation for TRUE Sharpe/σ/drawdown (M2.3, B88).
    "mf-portfolio-daily-valuations": {
        "task": "dhanradar.tasks.mf.compute_portfolio_daily_valuations",
        "schedule": crontab(hour=4, minute=0),
    },
    # ADR-0037 — Nifty 50 price-index daily close — 23:45 IST (after NSE EOD at ~15:30;
    # gives Yahoo Finance time to publish the close before midnight).  One upsert into
    # mf.mf_benchmark_daily for the Portfolio vs Market chart.  Runs on the 640 MB batch
    # queue — do NOT move to celery-mood (192 MB, OOM risk from live yfinance downloads).
    "nifty-close-daily": {
        "task": "dhanradar.tasks.mf.nifty_close_daily",
        "schedule": crontab(hour=23, minute=45),
    },
    # ----- Phase 6 — planned data sources (Admin.md §18 step 6). Each task writes an
    # mf.ingestion_runs row + an mf.source_health row via tasks/ingestion_run.py, so
    # the Ops console flips the source Planned → Healthy on the first successful run.
    # AMFI scheme master — weekly Sunday 03:00 IST. New/closed/merged schemes.
    "mf-scheme-master-refresh": {
        "task": "dhanradar.tasks.mf.mf_scheme_master_refresh",
        "schedule": crontab(day_of_week=0, hour=3, minute=0),
    },
    # AMC expense ratios (TER) — monthly 15th 04:00 IST. Most AMC factsheet pages are
    # bot-blocked (HDFC/SBI/ICICI_PRU/KOTAK/AXIS) — task degrades gracefully, never crashes.
    "mf-expense-ratio-fetch": {
        "task": "dhanradar.tasks.mf.mf_expense_ratio_fetch",
        "schedule": crontab(day_of_month=15, hour=4, minute=0),
    },
    # AMC fund managers — monthly 15th 04:30 IST (after expense-ratio). Same bot-block reality.
    "mf-fund-manager-fetch": {
        "task": "dhanradar.tasks.mf.mf_fund_manager_fetch",
        "schedule": crontab(day_of_month=15, hour=4, minute=30),
    },
    # SEBI circulars — weekly Wednesday 05:00 IST. Regulatory/merger/category metadata only.
    "sebi-circulars-fetch": {
        "task": "dhanradar.tasks.mf.sebi_circulars_fetch",
        "schedule": crontab(day_of_week=3, hour=5, minute=0),
    },
    # RBI DBIE macro — weekly Sunday 06:00 IST. Repo rate, CPI, WPI, GDP, money supply.
    "macro-data-refresh": {
        "task": "dhanradar.tasks.mf.macro_data_refresh",
        "schedule": crontab(day_of_week=0, hour=6, minute=0),
    },
    # W3 — AMFI half-yearly Large/Mid/Small Cap classification. DAILY 04:15 IST
    # (not monthly cron) — freshness addendum: the task itself checks whether the
    # current half's data is already stored and exits immediately without a network
    # call when it is, so a real fetch only happens on the few days AMFI first
    # publishes each half (avoids guessing the exact publish date with a fixed cron).
    "mf-cap-classification-fetch": {
        "task": "dhanradar.tasks.mf.mf_cap_classification_fetch",
        "schedule": crontab(hour=4, minute=15),
    },
    # W3 — AMFI monthly category-wise fund flows. DAILY 04:45 IST, same freshness-
    # addendum pattern as above (monthly data, daily check-then-skip).
    "mf-category-flows-fetch": {
        "task": "dhanradar.tasks.mf.mf_category_flows_fetch",
        "schedule": crontab(hour=4, minute=45),
    },
}

# ---------------------------------------------------------------------------
# Task registration is via the explicit `include=[...]` list on the Celery()
# constructor above (autodiscover_tasks was removed — it silently registered
# nothing; see the comment there). The worker imports those modules on boot.
# ---------------------------------------------------------------------------
