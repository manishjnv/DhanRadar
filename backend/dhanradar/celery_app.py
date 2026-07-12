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
        # Block 0.8 — real T-bill risk-free rate source (RBI press releases).
        "dhanradar.tasks.rbi_tbill",
        # BSE Star MF 2.0 webhook async processing (misc queue).
        "dhanradar.tasks.bse",
        # BSE StAR scheme-master enrichment (exit load / min amounts) —
        # dormant-safe (flag+creds+prod gates inside the task itself).
        "dhanradar.tasks.bse_enrich",
        # Manual disclosure ingestion inbox (ADR-0033(a) human side-channel for
        # HDFC/SBI/ICICI-Pru/Kotak/Axis, which block the scraper).
        "dhanradar.tasks.manual_ingest",
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
    "dhanradar.tasks.mood.*": {"queue": "mood"},
    "dhanradar.tasks.misc.*": {"queue": "misc"},
    "dhanradar.tasks.mf.*": {"queue": "batch"},
    "dhanradar.tasks.compliance.*": {"queue": "batch"},
    # Route news refresh to the existing batch worker (no dedicated news worker).
    "dhanradar.tasks.news.*": {"queue": "batch"},
    # Signal daily alerts run in the batch queue (low-volume, once-daily).
    "dhanradar.tasks.signal_alerts.*": {"queue": "batch"},
    # BSE webhook processing — misc queue (NOT mood; mood worker is mem-capped).
    "dhanradar.tasks.bse.*": {"queue": "misc"},
    # Manual disclosure inbox — batch queue (same volume + memory headroom as
    # mf_constituents_fetch/CAS parse, which this reuses openpyxl parsing from).
    "dhanradar.tasks.manual_ingest.*": {"queue": "batch"},
}

# ---------------------------------------------------------------------------
# Task time limits — the resilience fix for "a hung task blocks the whole
# single-concurrency queue forever" (found 2026-07-08: a scraper task hung
# mid-run with zero progress for 20+ minutes; nothing detected it, nothing
# recovered it — no task_time_limit existed anywhere, so the worker just sat
# wedged; every other task queued behind it, INCLUDING the beat-scheduled
# reap_stuck_cas_jobs reaper, which never got a turn to run).
#
# `soft_time_limit` raises SoftTimeLimitExceeded INSIDE the task (a normal,
# catchable Python exception — cooperative, lets a task log/clean-up before
# exiting); `time_limit` (hard) SIGKILLs the worker's child process a little
# later if the task hasn't exited by then. This worker runs the default
# PREFORK pool (no `--pool=solo`/`--pool=threads` anywhere in docker-compose),
# so the hard kill is real process-level enforcement, not best-effort — the
# worker's main process detects the dead child and immediately respawns a
# fresh one, so the QUEUE self-heals with NO container restart required.
# This is the primary auto-recovery mechanism (the docker-compose healthcheck
# added alongside this is for visibility/alerting only, not recovery).
#
# Two tiers, both bounding EVERY task uniformly (no scraper/extractor is ever
# exempt from a bound) — see docs/rca/README.md (2026-07-08) for the full
# incident + docs/project-state/ARCHITECTURE_DECISIONS.md for the policy ADR:
#
#   1. Global default ('*') — 25 min soft / 30 min hard. Covers every
#      multi-source scraper/extractor task (mf_constituents_fetch and the
#      Phase-6 AMC scrapers: expense-ratio/fund-manager/scheme-master/
#      sebi-circulars/macro-data/tbill/cap-classification/category-flows/
#      kite-enrich/nav-daily-fetch) — these legitimately loop over many
#      AMCs/sources with per-source timeouts and backoff, so they need real
#      headroom, but NONE of them has ever taken anywhere near 30 min when
#      working correctly; 30 min is a genuine "this is now abnormal" bound,
#      not a tight one.
#   2. Named fast-bucket overrides — 4 min soft / 5 min hard. Every task here
#      is DB-only, a single lightweight HTTP call, or a per-request parse
#      that observably completes in well under a minute on real prod data;
#      5 min hard-bounds a hang far sooner than the 30-min default would,
#      so the queue recovers faster for the tasks that run most frequently
#      (some are scheduled every 1/15/30 min — a 30-min bound on those would
#      let a hang starve 2+ scheduled runs before self-healing).
#
# Update this list when adding a new task: default to the global 30-min bound
# (safe for anything) and only add a fast-bucket entry once its real-world
# duration is observed to be short — never guess a task into the fast bucket.
# ---------------------------------------------------------------------------
_FAST_BUCKET_TASKS = {
    # DB-only nightly/monthly compute — no network calls.
    "dhanradar.tasks.mf.mf_metrics_refresh",
    "dhanradar.tasks.mf.compute_market_ranks",
    "dhanradar.tasks.mf.fund_events_refresh",
    "dhanradar.tasks.mf.monthly_rescore_plus_users",
    "dhanradar.tasks.mf.daily_portfolio_refresh",
    "dhanradar.tasks.mf.purge_cas_files",
    "dhanradar.tasks.mf.mf_fund_metadata_backfill",
    "dhanradar.tasks.mf.compute_portfolio_daily_valuations",
    # Reapers/housekeeping — must self-bound tightly; they exist specifically
    # to unblock OTHER stuck work, so they can never be allowed to become the
    # next thing blocking the queue.
    "dhanradar.tasks.mf.reap_stuck_cas_jobs",
    "dhanradar.tasks.manual_ingest.reap_stuck_manual_ingest_files",
    "dhanradar.tasks.manual_ingest.scan_incoming_folder",
    "dhanradar.tasks.manual_ingest.poll_email_inbox",
    # Per-request parses — real prod timing is sub-second-to-low-seconds per file.
    "dhanradar.tasks.mf.parse_cas_job",
    "dhanradar.tasks.manual_ingest.parse_manual_disclosure_file",
    # Single-index/single-file fetches — one HTTP call, not a multi-source loop.
    "dhanradar.tasks.mf.nifty_close_daily",
    # Mood/misc/signal-alerts/compliance/news/bse/legacy-batch — DB-only or a
    # single lightweight external call each; several run every few minutes, so
    # they need the tight bound (see policy note above).
    "dhanradar.tasks.mood.compute_mood_snapshot",
    "dhanradar.tasks.mood.mood_history_snapshot",
    "dhanradar.tasks.mood.run_sentiment_analysis",
    "dhanradar.tasks.misc.send_notification",
    "dhanradar.tasks.misc.drain_notifications",
    "dhanradar.tasks.signal_alerts.daily_signal_alert",
    "dhanradar.tasks.signal_alerts.market_data_refresh",
    "dhanradar.tasks.signal_alerts.auto_log_no_action",
    "dhanradar.tasks.signal_alerts.sip_reminder",
    "dhanradar.tasks.signal_alerts.check_achievements",
    "dhanradar.tasks.compliance.archive_audit_daily",
    "dhanradar.tasks.compliance.reconcile_audit_disclaimers",
    "dhanradar.tasks.news.refresh_market_news",
    "dhanradar.tasks.bse.process_webhook_event",
    "dhanradar.tasks.batch.run_nav_ingestion",
}

# Long, rare, manual multi-year historical backfill (ops runbook: normally
# invoked as a one-off `docker run`, but also directly callable via celery —
# the global 30-min default would kill a legitimate run partway through).
_LONG_RUNNING_TASKS = {
    "dhanradar.tasks.mf.nav_backfill": (6300, 6600),  # 105 min / 110 min
}


class _TaskTimeLimits:
    """Custom `task_annotations` object — NOT a plain dict.

    Celery's plain-dict annotation form has a confirmed footgun (celery 5.6.3,
    reproduced empirically 2026-07-08): a combined `{'*': {...}, 'task_name':
    {...}}` dict resolves BOTH the exact-name match AND the '*' wildcard match
    for every task, then applies them via `setattr` in the fixed order
    (specific FIRST, wildcard SECOND — see `celery.app.annotations.resolve_all`
    and `Task.annotate()`), so the wildcard UNCONDITIONALLY overwrites any
    task-specific entry that sets the same keys. A task-specific
    `soft_time_limit`/`time_limit` override therefore silently never took
    effect when tried as a plain dict — every task showed the global default.
    A custom object implementing only `annotate(task)` (no `annotate_any`)
    sidesteps this entirely: Celery calls `.annotate(task)` once per task and
    uses that single return value, no merge/overwrite step at all. This is the
    documented escape hatch for exactly this case (Celery docs: `task_annotations`
    may be a class instance/string import path implementing `annotate`).
    """

    def annotate(self, task):
        if task.name in _LONG_RUNNING_TASKS:
            soft, hard = _LONG_RUNNING_TASKS[task.name]
            return {"soft_time_limit": soft, "time_limit": hard}
        if task.name in _FAST_BUCKET_TASKS:
            return {"soft_time_limit": 240, "time_limit": 300}  # 4 min / 5 min
        return {"soft_time_limit": 1500, "time_limit": 1800}  # 25 min / 30 min


celery_app.conf.task_annotations = _TaskTimeLimits()

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
    # Per-category chained median-return index (Phase 4c pt2) — 00:00 IST; after
    # nav_daily_fetch (23:30), before mf-metrics-refresh (00:15). Materializes
    # mf.mf_category_series from the day's fresh NAV (fund-detail "category
    # average" chart line — data layer only this session, no API/DOM exposure).
    "mf-category-series-refresh": {
        "task": "dhanradar.tasks.mf.category_series_refresh",
        "schedule": crontab(hour=0, minute=0),
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
    # What-Changed diff engine — 01:15 IST; after compute_market_ranks (01:00), before
    # daily_portfolio_refresh (01:30). Diffs rank/TER/holding-weight month-over-month
    # into mf_fund_events (FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §10.6, §17 W2).
    "mf-fund-events-refresh": {
        "task": "dhanradar.tasks.mf.fund_events_refresh",
        "schedule": crontab(hour=1, minute=15),
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
    # Stuck-file reaper (2026-07-08, celery-resilience hardening) — every 5 min.
    # Marks manual_ingest_files rows orphaned at status='pending' for more than
    # 30 min as failed='stuck_timeout' — the manual-ingest-inbox counterpart to
    # mf-reap-stuck-cas above (parse_manual_disclosure_file has no other
    # self-heal path if hard-killed mid-flight by the new task_time_limit).
    # BSE StAR scheme-master enrichment — weekly Sun 05:30 IST (guide: pull
    # gently, weekly is plenty; runs AFTER the 03:00 AMFI scheme-master refresh
    # so freshly listed ISINs exist before BSE fields land on them). Dormant
    # no-op until BSE_ENRICH_ENABLED + credentials (+ BSE_ENV=prod for writes).
    "bse-scheme-master-enrich": {
        "task": "dhanradar.tasks.bse_enrich.bse_scheme_master_enrich",
        "schedule": crontab(hour=5, minute=30, day_of_week="0"),
    },
    "manual-ingest-reap-stuck": {
        "task": "dhanradar.tasks.manual_ingest.reap_stuck_manual_ingest_files",
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
    # Phase 4c pt3 — Benchmark TRI (Total Return Index) daily fetch, 23:45 IST (same
    # slot as nifty-close-daily — both are single-purpose low-load fetches on the batch
    # queue; no conflict). Writes mf.mf_benchmark_tri for the 4 canonical equity
    # indices (niftyindices.com). COMPLIANCE (ADR-0033): internal-compute only, never
    # DOM/API-exposed — see tests/unit/test_mf_benchmark_tri_compliance.py.
    "mf-benchmark-tri-fetch": {
        "task": "dhanradar.tasks.mf.benchmark_tri_fetch",
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
    # RBI 91-day T-bill yield — weekly Wednesday 17:00 IST. Sovereign risk-free rate
    # from weekly T-bill auctions (typically held Wednesday; results published same day).
    # Feeds resolve_risk_free_rate() for Sharpe/Sortino denominators (mf/risk.py).
    "rbi-tbill-refresh": {
        "task": "dhanradar.tasks.mf.rbi_tbill_refresh",
        "schedule": crontab(day_of_week=3, hour=17, minute=0),
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
    # Manual disclosure inbox — Channel B (watched folder). Every 15 min: scans
    # MANUAL_INGEST_DIR/incoming/, intakes new files, moves them to processed/failed.
    "manual-ingest-scan-folder": {
        "task": "dhanradar.tasks.manual_ingest.scan_incoming_folder",
        "schedule": crontab(minute="*/15"),
    },
    # Manual disclosure inbox — Channel C (email poller). Every 30 min. DORMANT
    # (no-op) until MANUAL_INGEST_IMAP_HOST/USER/PASSWORD are all set.
    "manual-ingest-poll-email": {
        "task": "dhanradar.tasks.manual_ingest.poll_email_inbox",
        "schedule": crontab(minute="*/30"),
    },
}

# ---------------------------------------------------------------------------
# Task registration is via the explicit `include=[...]` list on the Celery()
# constructor above (autodiscover_tasks was removed — it silently registered
# nothing; see the comment there). The worker imports those modules on boot.
# ---------------------------------------------------------------------------
