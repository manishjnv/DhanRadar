"""
DhanRadar — Admin Ops router (Phase 1).

Implements the operational-visibility and control endpoints for the Admin Console.
ALL routes are gated by RequireAdmin() (404 to non-admins — surface-hiding).

New endpoints go here, NOT in admin/router.py (which owns compliance: disclaimers,
scoring activation, label-churn). Keep the two routers separate so a future reviewer
can audit the compliance surface without wading through ops code.

Mutating endpoints audit-log via record_admin_action() — fire-and-forget pattern
mirrors activate_disclaimer in admin/router.py: failure MUST NOT break the handler.

Load-bearing classification: this file is a LOAD-BEARING path (extends the admin
surface, reads mf schema, touches Redis). Every change requires Opus line-by-line
diff review before merge.

Module isolation (non-neg #7): reads mf.ingestion_runs / mf.source_health via
SQLAlchemy directly (same schema, same module — mf ops data is owned by the admin
ops layer; these tables have no owning service module yet). Reads ai_recommendation_audit
via the compliance.service interface (never a raw cross-schema join into compliance).
Reads auth.users counts via raw SQL (aggregate only — no user PII surfaces here).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.ai_gateway.metrics import read_advisory_breaches, read_groundedness_window
from dhanradar.audit.service import record_admin_action
from dhanradar.db import get_admin_db
from dhanradar.deps import RequireAdmin, UserContext
from dhanradar.models.mf import (
    MfFund,
    MfIngestionRun,
    MfSourceHealth,
)
from dhanradar.redis_client import get_redis

from .ops_schemas import (
    AcknowledgeRequest,
    AdminAlert,
    AdminAlertsResponse,
    HealthResponse,
    MoodStatus,
    OkResponse,
    QualityRow,
    RecentAlert,
    RecentFailure,
    RecentSignup,
    RunDetailResponse,
    RunListRow,
    SourceRow,
    SyncResponse,
    TaskRow,
)

router = APIRouter(prefix="/admin", tags=["admin-ops"])

# ---------------------------------------------------------------------------
# Source catalog (static registry — Admin.md §4)
# Keyed by source value stored in mf.ingestion_runs.source
# ---------------------------------------------------------------------------

_SOURCE_CATALOG: list[dict[str, str]] = [
    {
        "source_key": "amfi_nav",
        "name": "AMFI NAVAll.txt",
        "tier": "1",
        "description": "Daily NAV for all ~10,000+ MF schemes",
        "method": "HTTP file download",
        "schedule_display": "Daily 23:30 IST",
        "cost": "Free",
        "celery_task": "dhanradar.tasks.mf.nav_daily_fetch",
        "beat_key": "mf-nav-daily-fetch",
    },
    {
        "source_key": "amfi_scheme_master",
        "name": "AMFI Scheme Master",
        "tier": "1",
        "description": "Scheme metadata, ISINs, fund house codes",
        "method": "HTTP scrape",
        "schedule_display": "Weekly Sun 03:00 IST",
        "cost": "Free",
        "celery_task": "dhanradar.tasks.mf.mf_scheme_master_refresh",
        "beat_key": "mf-scheme-master-refresh",
    },
    {
        "source_key": "amc_constituents",
        "name": "AMC Portfolio Disclosures",
        "tier": "2",
        "description": "Monthly constituent holdings (top-10 AMCs)",
        "method": "Playwright scrape",
        "schedule_display": "Monthly 10th 04:00 IST",
        "cost": "Free",
        "celery_task": "dhanradar.tasks.mf.mf_constituents_fetch",
        "beat_key": "mf-constituents-fetch",
    },
    {
        "source_key": "amc_expense_ratios",
        "name": "AMC Expense Ratios",
        "tier": "2",
        "description": "TER per scheme; effective date",
        "method": "Scrape",
        "schedule_display": "Monthly 15th 04:00 IST",
        "cost": "Free",
        "celery_task": "dhanradar.tasks.mf.mf_expense_ratio_fetch",
        "beat_key": "mf-expense-ratio-fetch",
    },
    {
        "source_key": "amc_fund_managers",
        "name": "AMC Fund Managers",
        "tier": "2",
        "description": "Manager name, start/end date per scheme",
        "method": "Scrape",
        "schedule_display": "Monthly 15th 04:30 IST",
        "cost": "Free",
        "celery_task": "dhanradar.tasks.mf.mf_fund_manager_fetch",
        "beat_key": "mf-fund-manager-fetch",
    },
    {
        "source_key": "sebi_circulars",
        "name": "SEBI Circulars",
        "tier": "3",
        "description": "Regulatory updates, scheme mergers, category changes",
        "method": "Scrape",
        "schedule_display": "Weekly Wed 05:00 IST",
        "cost": "Free",
        "celery_task": "dhanradar.tasks.mf.sebi_circulars_fetch",
        "beat_key": "sebi-circulars-fetch",
    },
    {
        "source_key": "mfapi",
        "name": "mfapi.in",
        "tier": "4",
        "description": "Historical NAV fallback; no auth; no rate limits",
        "method": "REST API",
        "schedule_display": "On-demand",
        "cost": "Free",
        "celery_task": "",
        "beat_key": "",
    },
    {
        "source_key": "yahoo_finance",
        "name": "Yahoo Finance (yfinance)",
        "tier": "Market",
        "description": "NIFTY 50 returns, India VIX, market breadth",
        "method": "Python library",
        "schedule_display": "Every 15 min (market hours)",
        "cost": "Free",
        "celery_task": "dhanradar.tasks.signal_alerts.market_data_refresh",
        "beat_key": "market-data-refresh",
    },
    {
        "source_key": "nse_india",
        "name": "NSE India",
        "tier": "Market",
        "description": "Live indices, VIX (fallback — bot-protected)",
        "method": "HTTP scrape",
        "schedule_display": "Fallback only",
        "cost": "Free",
        "celery_task": "",
        "beat_key": "",
    },
    {
        "source_key": "rbi_dbie",
        "name": "RBI DBIE",
        "tier": "Macro",
        "description": "Repo rate, CPI, WPI, GDP, money supply",
        "method": "HTTP download",
        "schedule_display": "Weekly Sun 06:00 IST",
        "cost": "Free",
        "celery_task": "dhanradar.tasks.mf.macro_data_refresh",
        "beat_key": "macro-data-refresh",
    },
    {
        "source_key": "rbi_rss",
        "name": "RBI RSS Feeds",
        "tier": "News",
        "description": "Press releases, policy notifications",
        "method": "RSS",
        "schedule_display": "Every 30 min",
        "cost": "Free",
        "celery_task": "dhanradar.tasks.news.refresh_market_news",
        "beat_key": "news-refresh-market",
    },
    {
        "source_key": "upstox_analytics",
        "name": "Upstox Analytics",
        "tier": "Market",
        "description": "FII/DII net flows + Nifty put-call ratio (Mood Compass signals)",
        "method": "REST API (Bearer token)",
        "schedule_display": "Twice daily (09:00 & 16:00 IST mood snapshot)",
        "cost": "Free (Analytics token)",
        "celery_task": "dhanradar.tasks.mood.compute_mood_snapshot",
        "beat_key": "mood-compute-snapshot",
    },
]

# Map source_key → celery task name for sync/trigger endpoints
_SOURCE_TO_TASK: dict[str, str] = {
    s["source_key"]: s["celery_task"]
    for s in _SOURCE_CATALOG
    if s["celery_task"]
}

# ---------------------------------------------------------------------------
# Celery beat task registry (mirrors celery_app.py beat_schedule).
# Used by GET /admin/tasks to produce the task list without importing celery_app
# at request time (avoids broker connection at import).
# schedule_display is human-readable; next_run_at is approximate (computed from cron
# expression at query time — we don't want to spin up a beat scheduler just for a
# display value, so we return null and mark it as TODO for a future beat-introspection
# integration).
# ---------------------------------------------------------------------------

_BEAT_TASKS: list[dict] = [
    {
        "beat_key": "mf-nav-daily-fetch",
        "task_name": "dhanradar.tasks.mf.nav_daily_fetch",
        "schedule_display": "Daily 23:30 IST",
        "cron": {"hour": 23, "minute": 30},
    },
    {
        "beat_key": "mf-metrics-refresh",
        "task_name": "dhanradar.tasks.mf.mf_metrics_refresh",
        "schedule_display": "Daily 00:15 IST",
        "cron": {"hour": 0, "minute": 15},
    },
    {
        "beat_key": "mf-compute-market-ranks",
        "task_name": "dhanradar.tasks.mf.compute_market_ranks",
        "schedule_display": "Daily 01:00 IST",
        "cron": {"hour": 1, "minute": 0},
    },
    {
        "beat_key": "mf-daily-portfolio-refresh",
        "task_name": "dhanradar.tasks.mf.daily_portfolio_refresh",
        "schedule_display": "Daily 01:30 IST",
        "cron": {"hour": 1, "minute": 30},
    },
    {
        "beat_key": "mf-purge-cas-files",
        "task_name": "dhanradar.tasks.mf.purge_cas_files",
        "schedule_display": "Daily 02:00 IST",
        "cron": {"hour": 2, "minute": 0},
    },
    {
        "beat_key": "notify-drain",
        "task_name": "dhanradar.tasks.misc.drain_notifications",
        "schedule_display": "Every 1 min",
        "cron": {"minute": "*"},
    },
    {
        "beat_key": "compliance-archive-audit",
        "task_name": "dhanradar.tasks.compliance.archive_audit_daily",
        "schedule_display": "Daily 02:00 IST",
        "cron": {"hour": 2, "minute": 0},
    },
    {
        "beat_key": "compliance-reconcile-disclaimers",
        "task_name": "dhanradar.tasks.compliance.reconcile_audit_disclaimers",
        "schedule_display": "Daily 02:30 IST",
        "cron": {"hour": 2, "minute": 30},
    },
    {
        "beat_key": "mood-compute-snapshot",
        "task_name": "dhanradar.tasks.mood.compute_mood_snapshot",
        "schedule_display": "Daily 09:00 & 16:00 IST",
        "cron": {"hour": "9,16", "minute": 0},
    },
    {
        "beat_key": "mf-monthly-rescore",
        "task_name": "dhanradar.tasks.mf.monthly_rescore_plus_users",
        "schedule_display": "1st of month 03:00 IST",
        "cron": {"day_of_month": 1, "hour": 3, "minute": 0},
    },
    {
        "beat_key": "news-refresh-market",
        "task_name": "dhanradar.tasks.news.refresh_market_news",
        "schedule_display": "Every 30 min",
        "cron": {"minute": "*/30"},
    },
    {
        "beat_key": "mf-reap-stuck-cas",
        "task_name": "dhanradar.tasks.mf.reap_stuck_cas_jobs",
        "schedule_display": "Every 5 min",
        "cron": {"minute": "*/5"},
    },
    {
        "beat_key": "signal-daily-alert",
        "task_name": "dhanradar.tasks.signal_alerts.daily_signal_alert",
        "schedule_display": "09:15 IST Mon–Fri",
        "cron": {"hour": 9, "minute": 15, "day_of_week": "1-5"},
    },
    {
        "beat_key": "market-data-refresh",
        "task_name": "dhanradar.tasks.signal_alerts.market_data_refresh",
        "schedule_display": "Every 15 min 09:00–16:00 IST Mon–Fri",
        "cron": {"minute": "*/15", "hour": "9-16", "day_of_week": "1-5"},
    },
    {
        "beat_key": "auto-log-no-action",
        "task_name": "dhanradar.tasks.signal_alerts.auto_log_no_action",
        "schedule_display": "21:00 IST Mon–Fri",
        "cron": {"hour": 21, "minute": 0, "day_of_week": "1-5"},
    },
    {
        "beat_key": "sip-reminder",
        "task_name": "dhanradar.tasks.signal_alerts.sip_reminder",
        "schedule_display": "Daily 09:00 IST",
        "cron": {"hour": 9, "minute": 0},
    },
    {
        "beat_key": "check-achievements",
        "task_name": "dhanradar.tasks.signal_alerts.check_achievements",
        "schedule_display": "Daily 22:00 IST",
        "cron": {"hour": 22, "minute": 0},
    },
    {
        "beat_key": "mf-constituents-fetch",
        "task_name": "dhanradar.tasks.mf.mf_constituents_fetch",
        "schedule_display": "Monthly 10th 04:00 IST",
        "cron": {"day_of_month": 10, "hour": 4, "minute": 0},
    },
    {
        "beat_key": "mf-kite-enrich",
        "task_name": "dhanradar.tasks.mf.mf_kite_enrich",
        "schedule_display": "Weekly Sat 03:00 IST",
        "cron": {"day_of_week": 6, "hour": 3, "minute": 0},
    },
    # Phase 6 — now registered in celery_app.beat_schedule (no longer planned).
    {
        "beat_key": "mf-scheme-master-refresh",
        "task_name": "dhanradar.tasks.mf.mf_scheme_master_refresh",
        "schedule_display": "Weekly Sun 03:00 IST",
        "cron": {"day_of_week": 0, "hour": 3, "minute": 0},
    },
    {
        "beat_key": "mf-expense-ratio-fetch",
        "task_name": "dhanradar.tasks.mf.mf_expense_ratio_fetch",
        "schedule_display": "Monthly 15th 04:00 IST",
        "cron": {"day_of_month": 15, "hour": 4, "minute": 0},
    },
    {
        "beat_key": "mf-fund-manager-fetch",
        "task_name": "dhanradar.tasks.mf.mf_fund_manager_fetch",
        "schedule_display": "Monthly 15th 04:30 IST",
        "cron": {"day_of_month": 15, "hour": 4, "minute": 30},
    },
    {
        "beat_key": "sebi-circulars-fetch",
        "task_name": "dhanradar.tasks.mf.sebi_circulars_fetch",
        "schedule_display": "Weekly Wed 05:00 IST",
        "cron": {"day_of_week": 3, "hour": 5, "minute": 0},
    },
    {
        "beat_key": "macro-data-refresh",
        "task_name": "dhanradar.tasks.mf.macro_data_refresh",
        "schedule_display": "Weekly Sun 06:00 IST",
        "cron": {"day_of_week": 0, "hour": 6, "minute": 0},
    },
    {
        "beat_key": "nifty-close-daily",
        "task_name": "dhanradar.tasks.mf.nifty_close_daily",
        "schedule_display": "Daily 23:45 IST",
        "cron": {"hour": 23, "minute": 45},
    },
]

# Map beat_key → celery task name for pause/resume/trigger
_BEAT_KEY_TO_TASK: dict[str, str] = {t["beat_key"]: t["task_name"] for t in _BEAT_TASKS}

# Redis set key for paused sources / tasks
_PAUSED_SOURCES_KEY = "paused_sources"
_PAUSED_TASKS_KEY = "paused_tasks"

# Sort order for the /admin/sources response: Healthy first, then Planned, Paused, Failed.
# Unknown statuses sort last (99). Python list.sort is stable so catalog order is
# preserved within each status group.
_STATUS_ORDER: dict[str, int] = {"Healthy": 0, "Planned": 1, "Paused": 2, "Failed": 3}


# ---------------------------------------------------------------------------
# Helper: ISO 8601 string from datetime or None
# ---------------------------------------------------------------------------


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


def _duration_s(started_at: datetime | None, finished_at: datetime | None) -> float | None:
    if started_at is None or finished_at is None:
        return None
    started = started_at.replace(tzinfo=UTC) if started_at.tzinfo is None else started_at
    finished = finished_at.replace(tzinfo=UTC) if finished_at.tzinfo is None else finished_at
    return round((finished - started).total_seconds(), 2)


# ---------------------------------------------------------------------------
# _next_run_at — cron-based next-fire-time (no broker connection required)
# ---------------------------------------------------------------------------

# Celery app timezone — read from celery_app.conf.timezone at module load via the
# constant below; importing celery_app at request time is fine (conf is read-only
# here) but we MUST NOT import beat_schedule (triggers broker connection).
_CELERY_TZ = "Asia/Kolkata"


def _next_run_at(cron: dict | None, tz_name: str) -> str | None:
    """Return the next fire time for a crontab spec as an ISO-8601 string.

    Builds a ``celery.schedules.crontab`` from *cron* kwargs, then uses
    ``remaining_estimate`` to find the delta to the next fire.  All arithmetic
    is done in *tz_name* so the result honours IST schedules correctly.

    Returns *None* on any error (missing cron, bad tz, unexpected crontab
    exception) so the endpoint never breaks due to a scheduling edge-case.
    """
    if not cron:
        return None
    try:
        from celery.schedules import crontab as _crontab  # type: ignore[import-untyped]

        tab = _crontab(**cron)
        now_aware = datetime.now(ZoneInfo(tz_name))
        remaining = tab.remaining_estimate(now_aware)
        next_fire = now_aware + remaining
        return next_fire.isoformat()
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# _derive_admin_alerts — shared helper used by both /alerts and /health
# ---------------------------------------------------------------------------


async def _derive_admin_alerts(db: AsyncSession) -> list[AdminAlert]:
    """Derive current attention items from DB state (no event log required).

    Encapsulates the same logic previously inlined in ``get_alerts`` so that
    ``get_health`` can populate its ``recent_alerts`` field without duplicating
    the derivation.  Behaviour is identical to the original ``get_alerts`` body.
    """
    from dhanradar.models.mood import MarketMood

    alerts: list[AdminAlert] = []
    now = datetime.now(UTC)

    # 1) Market-Mood freshness — the silent-failure case (scheduler never ran).
    latest = (
        await db.execute(
            select(
                MarketMood.snapshot_time,
                MarketMood.data_quality,
                MarketMood.inputs_available,
            )
            .order_by(MarketMood.snapshot_date.desc())
            .limit(1)
        )
    ).first()
    if latest is None:
        alerts.append(
            AdminAlert(
                key="mood_missing",
                severity="critical",
                title="Market Mood has never been computed",
                detail="No DMMI snapshot exists yet — the scheduled mood job may not be running.",
                href="/admin",
            )
        )
    else:
        snap_time, dq, inputs = latest
        age_h = (now - snap_time).total_seconds() / 3600 if snap_time else 999.0
        # 9 AM / 4 PM IST runs leave a ~17h overnight gap, so >20h means a run was missed.
        if age_h > 20:
            alerts.append(
                AdminAlert(
                    key="mood_stale",
                    severity="critical",
                    title="Market Mood snapshot is stale",
                    detail=(
                        f"The last DMMI read is ~{int(age_h)}h old; a scheduled run "
                        "(≈9 AM / 4 PM IST) was likely missed."
                    ),
                    since=_iso(snap_time),
                    href="/admin",
                )
            )
        elif dq == "degraded" or inputs < 7:
            alerts.append(
                AdminAlert(
                    key="mood_degraded",
                    severity="warning",
                    title="Market Mood is running degraded",
                    detail=f"Only {inputs} of 11 signals are feeding the read; confidence is capped.",
                    since=_iso(snap_time),
                    href="/mood",
                )
            )

    # 2) Recent data-ingestion failures (last 24h).
    fail_count = (
        await db.scalar(
            select(func.count())
            .select_from(MfIngestionRun)
            .where(MfIngestionRun.status.in_(["failed", "partial"]))
            .where(MfIngestionRun.started_at >= now - timedelta(hours=24))
        )
    ) or 0
    if fail_count:
        alerts.append(
            AdminAlert(
                key="ingestion_failures",
                severity="warning",
                title=f"{fail_count} data-ingestion failure(s) in 24h",
                detail="One or more source ingestion runs failed or completed partially.",
                href="/admin",
            )
        )

    # 3) Unreachable data sources (latest health row per source).
    subq = (
        select(
            MfSourceHealth.source,
            func.max(MfSourceHealth.check_time).label("max_ct"),
        )
        .group_by(MfSourceHealth.source)
        .subquery()
    )
    health_rows = (
        await db.scalars(
            select(MfSourceHealth).join(
                subq,
                (MfSourceHealth.source == subq.c.source)
                & (MfSourceHealth.check_time == subq.c.max_ct),
            )
        )
    ).all()
    unhealthy = [r.source for r in health_rows if not r.reachable]
    if unhealthy:
        alerts.append(
            AdminAlert(
                key="sources_unhealthy",
                severity="warning",
                title=f"{len(unhealthy)} data source(s) unreachable",
                detail="Latest health check failed for: " + ", ".join(sorted(unhealthy)[:6]),
                href="/admin",
            )
        )

    return alerts


# ---------------------------------------------------------------------------
# GET /admin/health
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse)
async def get_health(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
) -> HealthResponse:
    """Operational health summary for the Overview page.

    Sources healthy/total derive from mf.source_health (most recent row per source).
    last_nav_sync from the most recent successful ingestion_run for amfi_nav.
    total_schemes from mf.mf_funds count.
    active_users / premium_users from auth.users aggregate (cross-schema raw SQL is
    acceptable here — admin-only, aggregate only, no PII returned).
    advice_boundary_breaches_today / low_groundedness_flags_7d deferred:
      ai_recommendation_audit does not yet have a queryable breach/flag column
      (Safety Monitor is Phase 4 — AI Ops console). Returns 0 with TODO.
    recent_failures from last 5 failed ingestion_runs.
    recent_signups from last 5 auth.users ordered by created_at desc.
    recent_alerts: derived via _derive_admin_alerts (same logic as /admin/alerts bell).
    """
    # Source health: latest row per source
    # Using a subquery to get max check_time per source
    subq = (
        select(
            MfSourceHealth.source,
            func.max(MfSourceHealth.check_time).label("max_ct"),
        )
        .group_by(MfSourceHealth.source)
        .subquery()
    )
    health_rows = (
        await db.scalars(
            select(MfSourceHealth).join(
                subq,
                (MfSourceHealth.source == subq.c.source)
                & (MfSourceHealth.check_time == subq.c.max_ct),
            )
        )
    ).all()

    sources_total = len(health_rows)
    sources_healthy = sum(1 for r in health_rows if r.reachable)

    # last_nav_sync: latest finished_at for a successful amfi_nav run
    nav_run = await db.scalar(
        select(MfIngestionRun.finished_at)
        .where(MfIngestionRun.source == "amfi_nav")
        .where(MfIngestionRun.status == "success")
        .order_by(MfIngestionRun.finished_at.desc())
        .limit(1)
    )

    # total_schemes
    total_schemes = (await db.scalar(select(func.count()).select_from(MfFund))) or 0

    # active_users / premium_users — aggregate SQL against auth.users (admin-only)
    user_counts = await db.execute(
        text(
            "SELECT COUNT(*) AS total, "
            "COUNT(*) FILTER (WHERE tier IN ('pro','pro_plus','founder_lifetime')) AS premium "
            "FROM auth.users "
            "WHERE deletion_requested_at IS NULL"
        )
    )
    row = user_counts.one()
    active_users: int = int(row.total)
    premium_users: int = int(row.premium)

    # advice_boundary_breaches_today: today's count of advisory-screen rejections.
    # low_groundedness_flags_7d: sampled outputs scoring below the groundedness
    # threshold over 7 days. Both from the gateway's Redis counters (non-fatal
    # reads; 0 on a Redis failure).
    advice_boundary_breaches_today = (await read_advisory_breaches(1))["value"]
    low_groundedness_flags_7d = (await read_groundedness_window(7))["low_flags"]

    # recent_failures: last 5 failed ingestion_runs
    failure_rows = (
        await db.scalars(
            select(MfIngestionRun)
            .where(MfIngestionRun.status.in_(["failed", "partial"]))
            .order_by(MfIngestionRun.started_at.desc())
            .limit(5)
        )
    ).all()

    recent_failures = [
        RecentFailure(
            source=r.source,
            reason=r.error_class or r.error_detail or "unknown",
            failed_at=_iso(r.started_at) or "",
        )
        for r in failure_rows
    ]

    # recent_signups: last 5 users by created_at
    # NOTE: no display_name column on auth.users yet — use email prefix as display name.
    # TODO: add display_name to users table in a future migration.
    signup_rows = await db.execute(
        text(
            "SELECT email, tier, created_at FROM auth.users "
            "WHERE deletion_requested_at IS NULL "
            "ORDER BY created_at DESC LIMIT 5"
        )
    )
    recent_signups = [
        RecentSignup(
            display_name=row.email.split("@")[0],
            plan=row.tier,
            joined_at=_iso(row.created_at) or "",
        )
        for row in signup_rows
    ]

    # recent_alerts: derived from current DB state (same logic as /admin/alerts bell).
    raw_alerts = await _derive_admin_alerts(db)
    now_iso = datetime.now(UTC).isoformat()
    recent_alerts: list[RecentAlert] = [
        RecentAlert(
            type=a.key,
            message=a.title + (" — " + a.detail if a.detail else ""),
            severity=a.severity,
            created_at=a.since or now_iso,
        )
        for a in raw_alerts[:10]
    ]

    return HealthResponse(
        sources_healthy=sources_healthy,
        sources_total=sources_total,
        last_nav_sync=_iso(nav_run),
        total_schemes=total_schemes,
        active_users=active_users,
        premium_users=premium_users,
        advice_boundary_breaches_today=advice_boundary_breaches_today,
        low_groundedness_flags_7d=low_groundedness_flags_7d,
        recent_failures=recent_failures,
        recent_signups=recent_signups,
        recent_alerts=recent_alerts,
    )


# ---------------------------------------------------------------------------
# GET /admin/alerts — derived "attention bell" for the admin top bar
# ---------------------------------------------------------------------------


@router.get("/alerts", response_model=AdminAlertsResponse)
async def get_alerts(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
) -> AdminAlertsResponse:
    """Attention items for the admin bell, DERIVED from current state (not a
    failure-event log) so a job that NEVER RAN — a dead scheduler — is still caught.
    Read-only; self-clears when the underlying condition resolves. RequireAdmin."""
    alerts = await _derive_admin_alerts(db)
    return AdminAlertsResponse(count=len(alerts), alerts=alerts)


# ---------------------------------------------------------------------------
# GET /admin/sources
# ---------------------------------------------------------------------------


@router.get("/sources", response_model=list[SourceRow])
async def list_sources(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
) -> list[SourceRow]:
    """Return source catalog joined with last run from ingestion_runs + paused state."""
    redis = get_redis()
    paused_set = await redis.smembers(_PAUSED_SOURCES_KEY)

    # Latest run per source: subquery max(started_at)
    subq = (
        select(
            MfIngestionRun.source,
            func.max(MfIngestionRun.started_at).label("max_started"),
        )
        .group_by(MfIngestionRun.source)
        .subquery()
    )
    latest_runs = (
        await db.scalars(
            select(MfIngestionRun).join(
                subq,
                (MfIngestionRun.source == subq.c.source)
                & (MfIngestionRun.started_at == subq.c.max_started),
            )
        )
    ).all()
    run_by_source: dict[str, MfIngestionRun] = {r.source: r for r in latest_runs}

    result: list[SourceRow] = []
    for src in _SOURCE_CATALOG:
        sk = src["source_key"]
        run = run_by_source.get(sk)
        paused = sk in paused_set

        if paused:
            computed_status = "Paused"
        elif run is None:
            computed_status = "Planned"
        elif run.status in ("failed", "partial"):
            computed_status = "Failed"
        elif run.status == "running":
            computed_status = "Healthy"
        else:
            computed_status = "Healthy"

        result.append(
            SourceRow(
                source_key=sk,
                name=src["name"],
                tier=src["tier"],
                description=src["description"],
                method=src["method"],
                schedule_display=src["schedule_display"],
                cost=src["cost"],
                last_success_at=_iso(
                    run.finished_at
                    if run and run.status == "success"
                    else None
                ),
                last_records=run.records_written if run else None,
                status=computed_status,
                paused=paused,
            )
        )
    result.sort(key=lambda r: _STATUS_ORDER.get(r.status, 99))
    return result


# ---------------------------------------------------------------------------
# POST /admin/sources/{source_key}/sync
# ---------------------------------------------------------------------------


@router.post("/sources/{source_key}/sync", response_model=SyncResponse)
async def sync_source(
    source_key: str,
    request: Request,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> SyncResponse:
    """Trigger the Celery task mapped to source_key immediately."""
    task_name = _SOURCE_TO_TASK.get(source_key)
    if not task_name:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="source_not_found_or_no_task",
        )

    from dhanradar.celery_app import celery_app

    result = celery_app.send_task(task_name)
    # Fire-and-forget audit
    await record_admin_action(
        admin_id=admin.user_id,
        action="sync_source",
        target_type="source",
        target_id=source_key,
        result="triggered",
        request_id=getattr(request.state, "request_id", None),
    )
    return SyncResponse(task_id=str(result.id))


# ---------------------------------------------------------------------------
# POST /admin/sources/{source_key}/pause|resume
# ---------------------------------------------------------------------------


@router.post("/sources/{source_key}/pause", response_model=OkResponse)
async def pause_source(
    source_key: str,
    request: Request,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> OkResponse:
    """Add source_key to the Redis paused_sources set. Celery tasks check this set."""
    _assert_source_exists(source_key)
    redis = get_redis()
    await redis.sadd(_PAUSED_SOURCES_KEY, source_key)
    await record_admin_action(
        admin_id=admin.user_id,
        action="pause_source",
        target_type="source",
        target_id=source_key,
        result="paused",
        request_id=getattr(request.state, "request_id", None),
    )
    return OkResponse()


@router.post("/sources/{source_key}/resume", response_model=OkResponse)
async def resume_source(
    source_key: str,
    request: Request,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> OkResponse:
    """Remove source_key from the Redis paused_sources set."""
    _assert_source_exists(source_key)
    redis = get_redis()
    await redis.srem(_PAUSED_SOURCES_KEY, source_key)
    await record_admin_action(
        admin_id=admin.user_id,
        action="resume_source",
        target_type="source",
        target_id=source_key,
        result="resumed",
        request_id=getattr(request.state, "request_id", None),
    )
    return OkResponse()


def _assert_source_exists(source_key: str) -> None:
    keys = {s["source_key"] for s in _SOURCE_CATALOG}
    if source_key not in keys:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="source_not_found",
        )


# ---------------------------------------------------------------------------
# GET /admin/tasks
# ---------------------------------------------------------------------------


@router.get("/tasks", response_model=list[TaskRow])
async def list_tasks(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
) -> list[TaskRow]:
    """Return all beat-schedule tasks with last run data from ingestion_runs."""
    redis = get_redis()
    paused_set = await redis.smembers(_PAUSED_TASKS_KEY)

    # Latest run per task_name
    subq = (
        select(
            MfIngestionRun.task_name,
            func.max(MfIngestionRun.started_at).label("max_started"),
        )
        .group_by(MfIngestionRun.task_name)
        .subquery()
    )
    latest_runs = (
        await db.scalars(
            select(MfIngestionRun).join(
                subq,
                (MfIngestionRun.task_name == subq.c.task_name)
                & (MfIngestionRun.started_at == subq.c.max_started),
            )
        )
    ).all()
    run_by_task: dict[str, MfIngestionRun] = {r.task_name: r for r in latest_runs}

    result: list[TaskRow] = []
    for t in _BEAT_TASKS:
        task_name = t["task_name"]
        run = run_by_task.get(task_name)
        paused = t["task_name"] in paused_set

        result.append(
            TaskRow(
                task_name=task_name,
                schedule_display=t["schedule_display"],
                last_run_at=_iso(run.started_at) if run else None,
                next_run_at=_next_run_at(t.get("cron"), _CELERY_TZ),
                last_status=run.status if run else None,
                last_duration_s=(
                    _duration_s(run.started_at, run.finished_at) if run else None
                ),
                last_rows=run.records_written if run else None,
                paused=paused,
            )
        )
    return result


# ---------------------------------------------------------------------------
# POST /admin/tasks/{task_name}/trigger
# ---------------------------------------------------------------------------


@router.post("/tasks/{task_name}/trigger", response_model=SyncResponse)
async def trigger_task(
    task_name: str,
    request: Request,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> SyncResponse:
    """Trigger a Celery task by its dotted task name or beat key."""
    resolved = _resolve_task(task_name)

    from dhanradar.celery_app import celery_app

    result = celery_app.send_task(resolved)
    await record_admin_action(
        admin_id=admin.user_id,
        action="trigger_task",
        target_type="task",
        target_id=resolved,
        result="triggered",
        request_id=getattr(request.state, "request_id", None),
    )
    return SyncResponse(task_id=str(result.id))


# ---------------------------------------------------------------------------
# POST /admin/tasks/{task_name}/pause|resume
# ---------------------------------------------------------------------------


@router.post("/tasks/{task_name}/pause", response_model=OkResponse)
async def pause_task(
    task_name: str,
    request: Request,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> OkResponse:
    """Pause a task: store its CANONICAL dotted name in the Redis paused_tasks set.

    Accepts a beat_key or a dotted task name; both normalize to the dotted task
    name (mirrors trigger_task) so the set is single-form and matches what the
    Celery consumer checks — preventing a stale entry that never resume-clears.
    """
    resolved = _resolve_task(task_name)
    redis = get_redis()
    await redis.sadd(_PAUSED_TASKS_KEY, resolved)
    await record_admin_action(
        admin_id=admin.user_id,
        action="pause_task",
        target_type="task",
        target_id=resolved,
        result="paused",
        request_id=getattr(request.state, "request_id", None),
    )
    return OkResponse()


@router.post("/tasks/{task_name}/resume", response_model=OkResponse)
async def resume_task(
    task_name: str,
    request: Request,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
) -> OkResponse:
    """Resume a task: remove its CANONICAL dotted name from the paused_tasks set."""
    resolved = _resolve_task(task_name)
    redis = get_redis()
    await redis.srem(_PAUSED_TASKS_KEY, resolved)
    await record_admin_action(
        admin_id=admin.user_id,
        action="resume_task",
        target_type="task",
        target_id=resolved,
        result="resumed",
        request_id=getattr(request.state, "request_id", None),
    )
    return OkResponse()


def _resolve_task(task_name: str) -> str:
    """Normalize a beat_key OR dotted task name to the canonical dotted task name.

    Raises 404 if the (resolved) name is not in the beat registry. Single source
    of validation+normalization for trigger/pause/resume so the paused set and
    the Celery consumer agree on one form.
    """
    resolved = _BEAT_KEY_TO_TASK.get(task_name, task_name)
    if resolved not in {t["task_name"] for t in _BEAT_TASKS}:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="task_not_found",
        )
    return resolved


# ---------------------------------------------------------------------------
# GET /admin/runs
# ---------------------------------------------------------------------------


@router.get("/runs", response_model=list[RunListRow])
async def list_runs(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
    source: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[RunListRow]:
    """Return ingestion_runs ordered by started_at desc with optional filters."""
    q = select(MfIngestionRun).order_by(MfIngestionRun.started_at.desc())
    if source:
        q = q.where(MfIngestionRun.source == source)
    if status:
        q = q.where(MfIngestionRun.status == status)
    q = q.limit(limit).offset(offset)
    rows = (await db.scalars(q)).all()

    return [
        RunListRow(
            run_id=r.run_id,
            source=r.source,
            task_name=r.task_name,
            started_at=_iso(r.started_at) or "",
            finished_at=_iso(r.finished_at),
            duration_s=_duration_s(r.started_at, r.finished_at),
            records_written=r.records_written,
            records_failed=r.records_failed,
            status=r.status,
            error_class=r.error_class,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /admin/runs/{run_id}
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: int,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
) -> RunDetailResponse:
    """Return full detail for a single ingestion run."""
    r = await db.get(MfIngestionRun, run_id)
    if r is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="run_not_found",
        )
    return RunDetailResponse(
        run_id=r.run_id,
        source=r.source,
        task_name=r.task_name,
        started_at=_iso(r.started_at) or "",
        finished_at=_iso(r.finished_at),
        duration_s=_duration_s(r.started_at, r.finished_at),
        records_written=r.records_written,
        records_failed=r.records_failed,
        status=r.status,
        error_class=r.error_class,
        error_detail=r.error_detail,
        raw_file_path=r.raw_file_path,
        run_metadata=r.run_metadata,
    )


# ---------------------------------------------------------------------------
# GET /admin/quality
# ---------------------------------------------------------------------------


@router.get("/quality", response_model=list[QualityRow])
async def list_quality(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
) -> list[QualityRow]:
    """Return active data quality issues from mf.data_quality_issues.

    Returns [] when the table is empty (no quality evaluations have run yet).
    The quality evaluation job (which populates this table) is a Phase 5/6 task.
    """
    from dhanradar.models.mf import MfDataQualityIssue

    now = datetime.now(UTC)
    rows = (
        await db.scalars(
            select(MfDataQualityIssue)
            .where(MfDataQualityIssue.status.in_(["warning", "critical"]))
            .order_by(MfDataQualityIssue.evaluated_at.desc())
        )
    ).all()

    # Metric key → human label mapping (from Admin.md §6 Section D)
    _LABELS: dict[str, dict[str, str]] = {
        "missing_nav": {"label": "Missing NAV (schemes, last 2 days)", "unit": "schemes"},
        "holdings_coverage": {"label": "Holdings coverage (% top-100)", "unit": "%"},
        "duplicate_scheme_codes": {"label": "Duplicate scheme codes", "unit": "count"},
        "nav_out_of_range": {"label": "NAV out of range (NAV ≤ 0)", "unit": "count"},
        "expense_ratio_out_of_range": {"label": "Expense ratio out of range (>10%)", "unit": "count"},
        "holdings_weight_deviation": {"label": "Holdings weight sum deviation (>5%)", "unit": "count"},
        "aum_data_age": {"label": "AUM data age", "unit": "months"},
        "scheme_master_age": {"label": "Scheme master age", "unit": "days"},
    }

    result: list[QualityRow] = []
    for r in rows:
        meta = _LABELS.get(r.metric_key, {"label": r.metric_key, "unit": ""})
        # acknowledged_until: if set and in the future, the issue is suppressed
        ack_until_str: str | None = None
        if r.acknowledged_until is not None:
            ack_dt = (
                r.acknowledged_until.replace(tzinfo=UTC)
                if r.acknowledged_until.tzinfo is None
                else r.acknowledged_until
            )
            if ack_dt > now:
                ack_until_str = _iso(r.acknowledged_until)

        result.append(
            QualityRow(
                metric_key=r.metric_key,
                label=meta["label"],
                current_value=float(r.current_value) if r.current_value is not None else None,
                threshold=float(r.threshold) if r.threshold is not None else None,
                unit=meta["unit"],
                status=r.status,
                acknowledged_until=ack_until_str,
            )
        )
    return result


# ---------------------------------------------------------------------------
# POST /admin/quality/{metric_key}/acknowledge
# ---------------------------------------------------------------------------


@router.post("/quality/{metric_key}/acknowledge", response_model=OkResponse)
async def acknowledge_quality(
    metric_key: str,
    body: AcknowledgeRequest,
    request: Request,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
) -> OkResponse:
    """Suppress a quality issue for duration_days (sets acknowledged_until)."""
    from dhanradar.models.mf import MfDataQualityIssue

    # Find the most recent row for this metric_key
    row = await db.scalar(
        select(MfDataQualityIssue)
        .where(MfDataQualityIssue.metric_key == metric_key)
        .order_by(MfDataQualityIssue.evaluated_at.desc())
        .limit(1)
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="quality_issue_not_found",
        )

    if body.duration_days < 1 or body.duration_days > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="duration_days must be between 1 and 365",
        )

    row.acknowledged_until = datetime.now(UTC) + timedelta(days=body.duration_days)
    try:
        row.acknowledged_by = UUID(admin.user_id)
    except (ValueError, TypeError):
        pass  # malformed uuid — still set the time, just skip the FK

    await db.commit()

    await record_admin_action(
        admin_id=admin.user_id,
        action="acknowledge_quality_issue",
        target_type="data_quality",
        target_id=metric_key,
        result=f"acknowledged_{body.duration_days}d",
        request_id=getattr(request.state, "request_id", None),
    )
    return OkResponse()


# ---------------------------------------------------------------------------
# GET /admin/mood-status
# ---------------------------------------------------------------------------


@router.get("/mood-status", response_model=MoodStatus)
async def get_mood_status(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
) -> MoodStatus:
    """Latest Market-Mood snapshot coverage for the admin Operations page.

    Returns how many of the 11 signals fed the latest read, data_quality, and
    which signals were present in the input_vector — highlighting the 3
    Upstox-sourced ones (fii_flows, dii_flows, put_call_ratio).

    Read-only; RequireAdmin. Returns a zero/None shape when no snapshot exists.
    """
    from dhanradar.models.mood import MarketMood

    _EMPTY = MoodStatus(
        snapshot_at=None,
        regime=None,
        inputs_available=0,
        data_quality=None,
        signals_present=[],
        upstox_fii_flows=False,
        upstox_dii_flows=False,
        upstox_put_call_ratio=False,
    )

    row = (
        await db.execute(
            select(
                MarketMood.snapshot_time,
                MarketMood.regime,
                MarketMood.inputs_available,
                MarketMood.data_quality,
                MarketMood.input_vector,
            )
            .order_by(MarketMood.snapshot_date.desc(), MarketMood.snapshot_time.desc())
            .limit(1)
        )
    ).first()

    if row is None:
        return _EMPTY

    snap_time, regime, inputs_available, data_quality, input_vector = row

    # input_vector is JSONB dict of signal_key -> value (None means not fed).
    vec: dict = input_vector or {}
    signals_present = sorted(k for k, v in vec.items() if v is not None)

    return MoodStatus(
        snapshot_at=_iso(snap_time),
        regime=regime,
        inputs_available=inputs_available,
        data_quality=data_quality,
        signals_present=signals_present,
        upstox_fii_flows="fii_flows" in signals_present,
        upstox_dii_flows="dii_flows" in signals_present,
        upstox_put_call_ratio="put_call_ratio" in signals_present,
    )
