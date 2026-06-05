"""
DhanRadar — FastAPI application entry point.

Uses the modern lifespan context manager pattern (NOT @app.on_event).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from dhanradar.auth.router import router as auth_router
from dhanradar.billing.router import router as billing_router
from dhanradar.db import engine
from dhanradar.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from dhanradar.middleware import RequestIDMiddleware
from dhanradar.redis_client import close_redis, get_redis
from dhanradar.routers import health
from dhanradar.subscriptions.router import router as subscriptions_router


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
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(subscriptions_router, prefix="/api/v1")  # legacy /subscriptions/webhook alias
app.include_router(billing_router, prefix="/api/v1")
