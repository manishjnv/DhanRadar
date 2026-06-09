"""
DhanRadar — Dashboard market-index levels (B56).

REUSES the existing Yahoo provider helpers (`_quote_meta` / `_signal_value`) — does
NOT build a new fetcher. NSE geo-blocks KVM4 (RCA 2026-06-09), so Yahoo's public
chart API is the only server-reachable source. Read-through Redis cache (60s) keyed
`dashboard:indices`; on a Yahoo outage we return whatever resolved (possibly an
empty list → the widget shows its empty state), never a stale-as-fresh fabrication.
"""

from __future__ import annotations

import json
import logging

import httpx

from dhanradar.dashboard.schemas import MarketIndex
from dhanradar.market_data.providers.yahoo import _quote_meta, _signal_value

logger = logging.getLogger(__name__)

_CACHE_KEY = "dashboard:indices"
_TTL_SECONDS = 60

# Display name → Yahoo symbol. Indian indices on Yahoo (server-reachable, unlike NSE).
_INDICES: list[tuple[str, str]] = [
    ("NIFTY 50", "^NSEI"),
    ("SENSEX", "^BSESN"),
    ("NIFTY Bank", "^NSEBANK"),
    ("NIFTY Midcap 150", "NIFTYMIDCAP150.NS"),
]


async def _fetch_indices() -> list[MarketIndex]:
    """Fetch each index's level + daily % change from Yahoo. Per-symbol failures are
    skipped (the rest proceed); an empty result is a valid degraded outcome."""
    out: list[MarketIndex] = []
    async with httpx.AsyncClient() as client:
        for name, symbol in _INDICES:
            meta = await _quote_meta(client, symbol)
            if meta is None:
                continue
            level = _signal_value(meta, "level")
            if level is None:
                continue
            pct = _signal_value(meta, "pct")
            out.append(
                MarketIndex(name=name, value=round(level, 2), change_pct=round(pct or 0.0, 2))
            )
    return out


async def get_indices() -> list[MarketIndex]:
    """Return cached index levels, refreshing from Yahoo on a cache miss."""
    from dhanradar.redis_client import get_redis

    redis = get_redis()
    try:
        cached = await redis.get(_CACHE_KEY)
        if cached:
            raw = cached if isinstance(cached, str) else cached.decode()
            return [MarketIndex(**d) for d in json.loads(raw)]
    except Exception:  # noqa: BLE001 — a cache miss/parse error just triggers a fresh fetch
        logger.debug("dashboard: indices cache read failed; fetching fresh")

    indices = await _fetch_indices()
    if indices:
        try:
            await redis.set(
                _CACHE_KEY, json.dumps([i.model_dump() for i in indices]), ex=_TTL_SECONDS
            )
        except Exception:  # noqa: BLE001 — cache write is best-effort
            logger.debug("dashboard: indices cache write failed")
    return indices
