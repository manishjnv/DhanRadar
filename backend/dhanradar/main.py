"""
DhanRadar — FastAPI application entry point.

Uses the modern lifespan context manager pattern (NOT @app.on_event).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from dhanradar.admin.aiops_router import router as admin_aiops_router
from dhanradar.admin.billing_router import router as admin_billing_router
from dhanradar.admin.manual_ingest_router import router as admin_manual_ingest_router
from dhanradar.admin.ops_router import router as admin_ops_router
from dhanradar.admin.platform_router import router as admin_platform_router
from dhanradar.admin.router import router as admin_router
from dhanradar.admin.scoring_router import router as admin_scoring_router
from dhanradar.admin.users_router import router as admin_users_router
from dhanradar.ai_feedback.router import router as ai_feedback_router
from dhanradar.auth.router import router as auth_router
from dhanradar.billing.router import router as billing_router
from dhanradar.bse.router import router as bse_router
from dhanradar.changes.router import router as changes_router
from dhanradar.compliance.router import router as compliance_router
from dhanradar.concepts.router import router as concepts_router
from dhanradar.consent.router import router as consent_router
from dhanradar.core.logging import configure_logging
from dhanradar.dashboard.router import router as dashboard_router
from dhanradar.db import engine
from dhanradar.education.router import router as education_router
from dhanradar.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from dhanradar.insights.router import router as insights_router
from dhanradar.mf.router import router as mf_router
from dhanradar.middleware import RequestIDMiddleware
from dhanradar.mood.router import router as mood_router
from dhanradar.news.admin_router import router as news_admin_router
from dhanradar.news.router import router as news_router
from dhanradar.notifications.router import router as notifications_router
from dhanradar.observability import PrometheusMiddleware, init_sentry, metrics_endpoint
from dhanradar.onboarding.router import router as onboarding_router
from dhanradar.redis_client import close_redis, get_redis
from dhanradar.routers import health
from dhanradar.scoring.engine.router import router as internal_scoring_router
from dhanradar.signal.router import router as signal_router
from dhanradar.subscriptions.router import router as subscriptions_router
from dhanradar.transparency.router import router as transparency_router

# ---------------------------------------------------------------------------
# Structured JSON logging — must run BEFORE init_sentry() so all startup logs
# (including Sentry's own initialisation) are emitted as JSON.
# ---------------------------------------------------------------------------
configure_logging()

# ---------------------------------------------------------------------------
# Observability: Sentry (B38). Called ONCE at module load, before app = FastAPI().
# No-op when SENTRY_DSN is unset (the default); activates when DSN is configured.
# ---------------------------------------------------------------------------
init_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.
    - Startup: verify DB connectivity, initialise Redis client.
    - Shutdown: close Redis connection pool.
    """
    # Startup
    # Warm up the async engine (connection pool) by making one lightweight call
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    # Ensure Redis client is initialised
    get_redis()

    yield

    # Shutdown
    await close_redis()
    await engine.dispose()


app = FastAPI(
    lifespan=lifespan,
    title="DhanRadar API",
    version="0.1.0",
    description="AI-powered Indian mutual fund & stock radar — backend API",
)

# ---------------------------------------------------------------------------
# Cross-cutting: request-id + RFC7807 problem+json error contract
# (docs/project-state/CANONICAL_OPENAPI_ALIGNMENT.md §4)
# StarletteHTTPException covers FastAPI's HTTPException (a subclass).
# ---------------------------------------------------------------------------
app.add_middleware(RequestIDMiddleware)
app.add_middleware(PrometheusMiddleware)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# ---------------------------------------------------------------------------
# Metrics scrape endpoint — intentionally OUTSIDE /api/v1.
# The Cloudflare tunnel ingress routes only ^/api/.* to FastAPI, so /metrics
# is NOT reachable through the public tunnel. It is scraped server-to-server
# on the Docker network by the prometheus container. include_in_schema=False
# keeps it out of the OpenAPI docs. (B38)
# ---------------------------------------------------------------------------
app.add_api_route(
    "/metrics",
    metrics_endpoint,
    methods=["GET"],
    include_in_schema=False,
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(subscriptions_router, prefix="/api/v1")  # legacy /subscriptions/webhook alias
app.include_router(billing_router, prefix="/api/v1")
app.include_router(bse_router, prefix="/api/v1")  # BSE Star MF 2.0 webhook receiver (JOSE-verified, LOAD-BEARING)
app.include_router(mf_router, prefix="/api/v1")  # Phase 5 — MF CAS→report (consent-gated)
app.include_router(notifications_router, prefix="/api/v1")  # Phase 6 — Notification prefs + test
app.include_router(compliance_router, prefix="/api/v1")  # §4 — public disclaimer read
app.include_router(admin_router, prefix="/api/v1")  # B26 — admin compliance (disclaimer activate, label-churn); RequireAdmin-gated
app.include_router(admin_ops_router, prefix="/api/v1")  # Admin ops — health/sources/tasks/runs/quality; RequireAdmin-gated
app.include_router(admin_manual_ingest_router, prefix="/api/v1")  # Manual disclosure inbox — upload + recent-files read; RequireAdmin-gated
app.include_router(admin_users_router, prefix="/api/v1")  # Admin Phase 2 — user summary/list/detail + audit log; RequireAdmin-gated
app.include_router(admin_billing_router, prefix="/api/v1")  # Admin Phase 2 — billing overview/subs/payments; RequireAdmin-gated
app.include_router(admin_scoring_router, prefix="/api/v1")  # Admin Phase 3 — scoring model read (TIER-C LOAD-BEARING); RequireAdmin-gated
app.include_router(admin_platform_router, prefix="/api/v1")  # Admin Phase 3 — flags/support/analytics/notifications; RequireAdmin-gated
app.include_router(admin_aiops_router, prefix="/api/v1")  # Admin Phase 4 — AI Ops console (READ-ONLY, LOAD-BEARING Tier-B); RequireAdmin-gated
app.include_router(mood_router, prefix="/api/v1")  # Mood Compass — anon market regime
app.include_router(signal_router, prefix="/api/v1")  # Signal — dip-buy rules + dip-fund + deployments
app.include_router(consent_router, prefix="/api/v1")  # B44 — DPDP consent grant/revoke writer
app.include_router(onboarding_router, prefix="/api/v1")  # B43 — risk-profile quiz (sole writer of users.risk_profile)
app.include_router(dashboard_router, prefix="/api/v1")  # B56 — market indices (/dashboard decommissioned)
app.include_router(education_router, prefix="/api/v1")  # G8 — public tax-education (anonymous-read, crawlable)
app.include_router(news_router, prefix="/api/v1")  # B56 — curated headline metadata (anonymous-read)
app.include_router(news_admin_router, prefix="/api/v1")  # B56-f4 — admin news CRUD ops workflow (RequireAdmin-gated)
app.include_router(insights_router, prefix="/api/v1")  # Plan Group 3 — portfolio intelligence (overlap + concentration)
app.include_router(transparency_router, prefix="/api/v1")  # Plan Group 9 — data transparency + explainability (PU2)
app.include_router(changes_router, prefix="/api/v1")  # Plan Group 2 — What Changed explainability (read-only)
app.include_router(concepts_router, prefix="/api/v1")  # C1 — public concept explainers (anonymous-read, crawlable)
app.include_router(ai_feedback_router, prefix="/api/v1")  # PR-6 — user AI-output feedback (RequireAuth; DPDP B64 pending)
# INTERNAL ONLY — mounted at /internal/v1 (no /api prefix). The cloudflared
# ingress routes only ^/api/.* to FastAPI, so this is not reachable through the
# public tunnel — server-to-server score reads (numerics are tier-gated here).
app.include_router(internal_scoring_router)
