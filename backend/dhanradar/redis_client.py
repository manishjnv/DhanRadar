"""
DhanRadar — Async Redis client factory.

Returns a single shared client instance initialised from settings.REDIS_URL.
Call `await close_redis()` on application shutdown.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from dhanradar.config import settings

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Return (or lazily create) the shared async Redis client."""
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _client


async def close_redis() -> None:
    """Close the Redis connection pool — call from lifespan shutdown."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
