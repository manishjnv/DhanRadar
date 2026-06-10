"""
DhanRadar — Async SQLAlchemy engine + session factory.

Usage in FastAPI route handlers:
    async def my_route(db: AsyncSession = Depends(get_db)): ...
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from dhanradar.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
    echo=settings.ENV == "development",
    future=True,
)

SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with SessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Celery / asyncio.run() engine — NullPool, safe across repeated event loops.
# ---------------------------------------------------------------------------
# The pooled `engine` above is for FastAPI ONLY: one long-lived event loop, where
# a QueuePool is correct and fast. It MUST NOT be used from a Celery task. Celery
# tasks run their async pipelines via asyncio.run(), which creates a FRESH event
# loop on every call. A QueuePool caches asyncpg connections across those calls,
# but an asyncpg connection is bound to the loop that created it — so the 2nd+
# asyncio.run() on a worker checks out a connection whose loop is dead and raises
# `InterfaceError: another operation is in progress` (prod SEV2 2026-06-10: only
# the FIRST task per worker boot succeeded; every task after it failed, leaving
# CAS jobs stuck at status='queued'). NullPool caches nothing — each session opens
# a fresh connection on the CURRENT loop and fully closes it on release — so no
# asyncpg connection ever crosses an asyncio.run() (or fork) boundary.
#
# Use `TaskSessionLocal` / `task_session()` for EVERY DB session opened inside a
# Celery task or a standalone asyncio.run() script — never the pooled `engine`.
# Enforced by scripts/ci_guards.py. See docs/rca/README.md (2026-06-10).
task_engine = create_async_engine(
    settings.database_url,
    poolclass=NullPool,
    echo=settings.ENV == "development",
    future=True,
)

TaskSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    task_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


@asynccontextmanager
async def task_session() -> AsyncGenerator[AsyncSession, None]:
    """Async session for Celery tasks / asyncio.run() scripts. Backed by the
    NullPool `task_engine` (see the note above), so it is safe to reuse across the
    fresh event loop that every asyncio.run() creates — unlike the pooled FastAPI
    `engine`, whose cached asyncpg connections become bound to a dead loop."""
    async with TaskSessionLocal() as session:
        yield session
