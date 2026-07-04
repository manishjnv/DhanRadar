"""
DhanRadar — global ticker-bar quotes (top status strip, all pages).

Mirrors `dashboard/indices.py`: REUSES the Yahoo provider helpers
(`_quote_meta` / `_signal_value`) — no new fetcher, no new dependency. Read-through
Redis cache (60s) keyed `dashboard:ticker` + a 24h last-known-good fallback, so the
public strip costs at most one Yahoo sweep per minute regardless of traffic.
FII/DII/PCR ride along from the EXISTING `signal:flows:last` cache (written by the
twice-daily mood snapshot) — read-only here, never fetched, all-None when cold.

Everything served is RAW public market data (levels + % change, and NSE/Upstox
flow figures) — DOM-allowed like /market/vix and /market/quotes; nothing computed
or scored.
"""

from __future__ import annotations

import json
import logging

import httpx

from dhanradar.dashboard.schemas import TickerItem, TickerOut
from dhanradar.market_data.providers.yahoo import _quote_meta, _signal_value

logger = logging.getLogger(__name__)

_CACHE_KEY = "dashboard:ticker"
_FALLBACK_KEY = "dashboard:ticker:fallback"
_TTL_SECONDS = 60
_FALLBACK_TTL = 86400  # 24 h — last-known-good when Yahoo is unavailable
_FLOWS_CACHE_KEY = "signal:flows:last"  # written by mood/service.cache_market_flows

# (key, display label, Yahoo symbol) — strip render order. Indian indices first,
# then FX/commodities, then global indices (matches the founder's requested set).
_TICKER_SYMBOLS: list[tuple[str, str, str]] = [
    ("nifty50", "NIFTY 50", "^NSEI"),
    ("sensex", "SENSEX", "^BSESN"),
    ("niftybank", "NIFTY BANK", "^NSEBANK"),
    ("midcap150", "MIDCAP 150", "NIFTYMIDCAP150.NS"),
    ("indiavix", "INDIA VIX", "^INDIAVIX"),
    ("usdinr", "USD/INR", "INR=X"),
    ("gold", "GOLD", "GC=F"),
    ("silver", "SILVER", "SI=F"),
    ("brent", "BRENT", "BZ=F"),
    ("sp500", "S&P 500", "^GSPC"),
    ("dow", "DOW", "^DJI"),
    ("nasdaq", "NASDAQ", "^IXIC"),
    ("nikkei", "NIKKEI 225", "^N225"),
    ("hangseng", "HANG SENG", "^HSI"),
]


async def _fetch_items() -> list[TickerItem]:
    """Fetch each symbol's level + daily % change from Yahoo. Per-symbol failures
    are skipped (the rest proceed); an empty result is a valid degraded outcome."""
    out: list[TickerItem] = []
    async with httpx.AsyncClient() as client:
        for key, label, symbol in _TICKER_SYMBOLS:
            meta = await _quote_meta(client, symbol)
            if meta is None:
                continue
            level = _signal_value(meta, "level")
            if level is None:
                continue
            pct = _signal_value(meta, "pct")
            out.append(
                TickerItem(
                    key=key, label=label, value=round(level, 2), change_pct=round(pct or 0.0, 2)
                )
            )
    return out


async def _read_flows() -> dict:
    """Read the cached FII/DII/PCR snapshot — cache-only (the mood pipeline owns the
    fetch); all-None when cold so the strip renders em-dashes, never an error."""
    from dhanradar.redis_client import get_redis

    try:
        raw = await get_redis().get(_FLOWS_CACHE_KEY)
        if raw:
            data = json.loads(raw if isinstance(raw, str) else raw.decode())
            return {
                "fii_cr": data.get("fii_cr"),
                "dii_cr": data.get("dii_cr"),
                "pcr": data.get("pcr"),
                "flows_as_of": data.get("as_of"),
            }
    except Exception:  # noqa: BLE001 — flows are a best-effort garnish on the strip
        logger.debug("ticker: flows cache read failed")
    return {"fii_cr": None, "dii_cr": None, "pcr": None, "flows_as_of": None}


async def get_ticker() -> TickerOut:
    """Return the cached ticker strip, refreshing quote items from Yahoo on a miss."""
    from dhanradar.redis_client import get_redis

    redis = get_redis()
    items: list[TickerItem] | None = None
    try:
        cached = await redis.get(_CACHE_KEY)
        if cached:
            raw = cached if isinstance(cached, str) else cached.decode()
            items = [TickerItem(**d) for d in json.loads(raw)]
    except Exception:  # noqa: BLE001 — a cache miss/parse error just triggers a fresh fetch
        logger.debug("ticker: cache read failed; fetching fresh")

    if items is None:
        items = await _fetch_items()
        if items:
            payload = json.dumps([i.model_dump() for i in items])
            try:
                await redis.set(_CACHE_KEY, payload, ex=_TTL_SECONDS)
                await redis.set(_FALLBACK_KEY, payload, ex=_FALLBACK_TTL)
            except Exception:  # noqa: BLE001 — cache write is best-effort
                logger.debug("ticker: cache write failed")
        else:
            # Yahoo unavailable — serve last-known-good rather than an empty strip.
            try:
                fallback = await redis.get(_FALLBACK_KEY)
                if fallback:
                    raw = fallback if isinstance(fallback, str) else fallback.decode()
                    logger.debug("ticker: returning stale fallback")
                    items = [TickerItem(**d) for d in json.loads(raw)]
            except Exception:  # noqa: BLE001
                logger.debug("ticker: fallback cache read failed")

    return TickerOut(items=items or [], **(await _read_flows()))
