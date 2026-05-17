"""
DhanRadar — FastAPI application entry point.

Uses the modern lifespan context manager pattern (NOT @app.on_event).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from sqlalchemy import text

from dhanradar.db import engine
from dhanradar.redis_client import close_redis, get_redis
from dhanradar.routers import health


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
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router, prefix="/api/v1")
