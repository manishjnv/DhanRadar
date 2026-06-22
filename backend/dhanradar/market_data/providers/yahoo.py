"""
DhanRadar -- Yahoo Finance Macro Signal Provider (best-effort, server-reachable).

NSE's public JSON endpoints geo-/bot-block datacenter IPs (they return HTTP 403
from the KVM4 server), so the Mood Compass got zero signals and never stored a
snapshot. Yahoo Finance's public chart API is reachable from servers worldwide
with no auth and serves the India symbols we need, so it is the Mood Compass's
primary macro source.

Signals fetched (raw values; normalisation lives in mood/signals.py):
  - nifty_trend    : NIFTY 50 (^NSEI)      -- % daily change
  - india_vix      : India VIX (^INDIAVIX) -- level
  - global_indices : S&P 500 (^GSPC)       -- % daily change
  - us_bond_10y    : US 10Y yield (^TNX)   -- level, in percent
  - oil_brent      : Brent crude (BZ=F)    -- price level, USD/bbl
  - usd_inr        : USD/INR (INR=X)       -- % daily change
  - market_breadth : NIFTY-50 constituent A/D -- advances/(advances+declines) [0,1]

Each symbol is fetched independently -- a per-symbol failure yields None for that
signal (omitted from the payload); the rest proceed. ProviderError is raised only
on a catastrophic structural failure (httpx unavailable). The Mood Compass
degrades gracefully to 'data_unavailable' when all signals are None.

market_breadth is a PURE CACHE CONSUMER -- it reads ``signal:breadth:last`` from
Redis only.  The heavy NIFTY-50 download (``fetch_nifty50_advances_declines_sync``
via yfinance) belongs to the ``market_data_refresh`` pre-warm task (every 15 min
during market hours) which populates that key.  Doing the live download here
OOM-kills the 192 MB celery-mood worker (WorkerLostError: signal 9 SIGKILL).
A cache miss or any error simply omits ``market_breadth`` (graceful degradation to
6/11 signals); ProviderError is never raised solely because breadth is absent.
"""

from __future__ import annotations

import datetime
import json
import logging
from urllib.parse import quote

import httpx

from dhanradar.market_data.config import DataKind, DataRequest
from dhanradar.market_data.events import MacroSignalReceived
from dhanradar.market_data.exceptions import ProviderError
from dhanradar.market_data.providers.base import MarketDataProvider

# Redis key written by the market_data_refresh pre-warm task every 15 min.
# This module only reads it -- never writes.
_BREADTH_CACHE_KEY = "signal:breadth:last"

logger = logging.getLogger(__name__)

_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
# Yahoo rejects an empty/unknown User-Agent; any browser-ish UA is accepted.
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DhanRadar/1.0; +https://dhanradar.com)"}
_TIMEOUT = httpx.Timeout(15.0, connect=8.0)

# signal-key -> (yahoo symbol, mode) where mode is "pct" (daily % change) or
# "level" (the latest price/level as-is).
_SYMBOLS: dict[str, tuple[str, str]] = {
    "nifty_trend": ("^NSEI", "pct"),
    "india_vix": ("^INDIAVIX", "level"),
    "global_indices": ("^GSPC", "pct"),
    "us_bond_10y": ("^TNX", "level"),
    "oil_brent": ("BZ=F", "level"),
    "usd_inr": ("INR=X", "pct"),
}


def _now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


async def _quote_meta(client: httpx.AsyncClient, symbol: str) -> dict | None:
    """Return the Yahoo chart 'meta' block for a symbol, or None on any error."""
    url = _CHART_URL.format(symbol=quote(symbol))
    try:
        resp = await client.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code != 200:
            logger.debug("yahoo_macro: HTTP %s for %s", resp.status_code, symbol)
            return None
        result = resp.json().get("chart", {}).get("result") or []
        if not result:
            return None
        meta = result[0].get("meta")
        return meta if isinstance(meta, dict) else None
    except Exception as exc:  # noqa: BLE001 -- each symbol is independent best-effort
        logger.debug("yahoo_macro: fetch failed for %s: %s", symbol, exc)
        return None


def _signal_value(meta: dict, mode: str) -> float | None:
    """Derive the raw signal from a chart meta block: a % daily change or a level."""
    price = meta.get("regularMarketPrice")
    if not price:  # None or 0 -- a 0 price/level is meaningless, treat as missing
        return None
    if mode == "level":
        return float(price)
    # mode == "pct": percent change vs the previous close.
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    if not prev:  # None or 0 -> can't compute a % change
        return None
    return (float(price) - float(prev)) / float(prev) * 100.0


# Public quotes endpoint metadata. The mood signals are derived from RAW PUBLIC
# market data (Yahoo) with NO DhanRadar transform — both the level and the % change
# are public facts, allowed in the DOM (unlike the proprietary mood score).
_MACRO_QUOTES_CACHE_KEY = "signal:macro_quotes:last"
_MACRO_QUOTES_TTL = 300  # 5 min — public hits serve from cache, not live Yahoo.
_MACRO_DISPLAY: dict[str, str] = {
    "nifty_trend": "Nifty 50",
    "india_vix": "India VIX",
    "global_indices": "S&P 500",
    "us_bond_10y": "US 10Y Yield",
    "oil_brent": "Brent Crude",
    "usd_inr": "USD/INR",
}


async def fetch_macro_quotes() -> list[dict]:
    """Raw public market quotes (level + daily % change) for the macro mood signals.

    Public Yahoo data, no DhanRadar transform — DOM-allowed. Best-effort and
    Redis-cached (5 min) so the public endpoint never hammers Yahoo. Returns a list
    of {key, name, value, change_pct}; a per-symbol failure is simply omitted."""
    from dhanradar.redis_client import get_redis

    redis = get_redis()
    try:
        cached = await redis.get(_MACRO_QUOTES_CACHE_KEY)
        if cached:
            raw = cached if isinstance(cached, str) else cached.decode()
            return list(json.loads(raw))
    except Exception:  # noqa: BLE001 — cache miss/parse error → fetch fresh
        logger.debug("yahoo_macro.quotes: cache read failed")

    out: list[dict] = []
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        for key, (symbol, _mode) in _SYMBOLS.items():
            meta = await _quote_meta(client, symbol)
            if not meta:
                continue
            price = meta.get("regularMarketPrice")
            prev = meta.get("chartPreviousClose") or meta.get("previousClose")
            if not price or not prev:
                continue
            change_pct = (float(price) - float(prev)) / float(prev) * 100.0
            out.append(
                {
                    "key": key,
                    "name": _MACRO_DISPLAY.get(key, key),
                    "value": round(float(price), 2),
                    "change_pct": round(change_pct, 2),
                }
            )
    if out:
        try:
            await redis.set(_MACRO_QUOTES_CACHE_KEY, json.dumps(out), ex=_MACRO_QUOTES_TTL)
        except Exception:  # noqa: BLE001 — cache write is best-effort
            logger.debug("yahoo_macro.quotes: cache write failed")
    return out


async def _fetch_breadth_ratio() -> float | None:
    """Return market breadth as advances/(advances+declines) in [0,1], or None.

    Pure cache consumer -- reads ``signal:breadth:last`` from Redis only.
    The heavy NIFTY-50 yfinance download belongs to the ``market_data_refresh``
    pre-warm task (runs every 15 min during market hours); doing it here
    OOM-kills the 192 MB celery-mood worker (WorkerLostError: signal 9 SIGKILL).

    On cache miss, missing/invalid fields, total<=0, or ANY exception -> returns
    None.  The caller omits ``market_breadth`` from the signals dict (graceful
    degradation to 6/11 signals).  NEVER imputes a value.
    """
    try:
        from dhanradar.redis_client import get_redis  # noqa: PLC0415
        raw = await get_redis().get(_BREADTH_CACHE_KEY)
        if not raw:
            return None
        data = json.loads(raw if isinstance(raw, str) else raw.decode())
        advances = data.get("advances")
        declines = data.get("declines")
        if advances is None or declines is None:
            return None
        total = int(advances) + int(declines)
        if total <= 0:
            return None
        return float(int(advances)) / float(total)
    except Exception as exc:  # noqa: BLE001 -- cache unavailable -> omit breadth
        logger.debug("yahoo_macro: breadth cache read failed -- %s", exc)
        return None


class YahooMacroProvider(MarketDataProvider):
    """Best-effort macro signals for the Mood Compass via Yahoo Finance's public
    chart API. Server-reachable (unlike NSE). Per-symbol failures degrade to None;
    only a missing httpx raises ProviderError."""

    name = "yahoo_macro"

    def supports(self, kind: DataKind) -> bool:
        return kind == DataKind.MACRO_SIGNAL

    async def fetch(self, request: DataRequest) -> MacroSignalReceived:
        signals: dict[str, float] = {}
        try:
            async with httpx.AsyncClient() as client:
                for key, (symbol, mode) in _SYMBOLS.items():
                    meta = await _quote_meta(client, symbol)
                    if meta is None:
                        continue
                    value = _signal_value(meta, mode)
                    if value is not None:
                        signals[key] = value
        except ImportError as exc:  # pragma: no cover -- httpx is a hard dep
            raise ProviderError(self.name, f"httpx not available: {exc}") from exc

        # An empty result (every symbol blank -- e.g. a Yahoo outage / layout
        # change) MUST raise so the adapter ladder falls through to the fallback
        # provider instead of recording a false "success". A success with an
        # empty signals dict would otherwise silently reproduce the original
        # no-snapshot bug (compute_mood would skip on all-None inputs).
        if not signals:
            raise ProviderError(self.name, "no macro signals resolved from Yahoo")

        # market_breadth -- pure cache read from Redis (pre-warmed by the
        # market_data_refresh task).  A miss or failure only omits the key
        # (NEVER IMPUTE); it does NOT raise ProviderError.
        breadth_ratio = await _fetch_breadth_ratio()
        if breadth_ratio is not None:
            signals["market_breadth"] = breadth_ratio

        logger.info(
            "yahoo_macro: fetched %d/%d signals: %s",
            len(signals),
            len(_SYMBOLS) + 1,  # +1 for market_breadth
            list(signals.keys()),
        )
        return MacroSignalReceived(source=self.name, signals=signals, fetched_at=_now_iso())
