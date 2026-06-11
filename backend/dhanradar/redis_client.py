"""
DhanRadar — Async Redis client factory.

Returns a shared client instance initialised from settings.REDIS_URL, cached
PER EVENT LOOP. Call `await close_redis()` on application shutdown.

Why loop-aware (RCA 2026-06-11, "Event loop is closed"): on the web tier one
loop lives for the whole process, so the cache behaves like a plain singleton.
Celery tasks, however, each run under their own ``asyncio.run()`` — the FIRST
task in a prefork child created the client bound to its loop, ``asyncio.run``
closed that loop on exit, and every SUBSEQUENT task in the same child then
failed its first Redis call with ``RuntimeError: Event loop is closed``
(every 2nd+ CAS upload in a worker child failed; masked for days because
OOM-kills/deploys kept recycling children). Same cross-loop-global disease the
SEV2 NullPool migration fixed for asyncpg — Redis was the remaining global.

The stale client's sockets cannot be closed (their loop is gone); they are
abandoned to TCP cleanup. That is bounded: one client per task loop, and
Celery pipelines are infrequent.
"""

from __future__ import annotations

import asyncio

import redis.asyncio as aioredis

from dhanradar.config import settings

_client: aioredis.Redis | None = None
_client_loop: asyncio.AbstractEventLoop | None = None


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:  # called outside any event loop (import time, sync code)
        return None


def get_redis() -> aioredis.Redis:
    """Return the shared async Redis client for the CURRENT event loop,
    creating a fresh one when the cached client belongs to another (closed)
    loop. No-loop callers reuse whatever is cached (legacy behaviour)."""
    global _client, _client_loop
    loop = _running_loop()
    if _client is None or (loop is not None and _client_loop is not loop):
        _client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        _client_loop = loop
    return _client


async def close_redis() -> None:
    """Close the Redis connection pool — call from lifespan shutdown."""
    global _client, _client_loop
    if _client is not None:
        await _client.aclose()
        _client = None
        _client_loop = None
