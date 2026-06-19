"""
DhanRadar — Yahoo Finance Macro Signal Provider (best-effort, server-reachable).

NSE's public JSON endpoints geo-/bot-block datacenter IPs (they return HTTP 403
from the KVM4 server), so the Mood Compass got zero signals and never stored a
snapshot. Yahoo Finance's public chart API is reachable from servers worldwide
with no auth and serves the India symbols we need, so it is the Mood Compass's
primary macro source.

Signals fetched (raw values; normalisation lives in mood/signals.py):
  - nifty_trend    : NIFTY 50 (^NSEI)   — % daily change
  - india_vix      : India VIX (^INDIAVIX) — level
  - global_indices : S&P 500 (^GSPC)    — % daily change
  - us_bond_10y    : US 10Y yield (^TNX) — level, in percent
  - oil_brent      : Brent crude (BZ=F)  — price level, USD/bbl
  - usd_inr        : USD/INR (INR=X)     — % daily change
  - market_breadth : NIFTY-50 constituent A/D — advances/(advances+declines) [0,1]

Each symbol is fetched independently — a per-symbol failure yields None for that
signal (omitted from the payload); the rest proceed. ProviderError is raised only
on a catastrophic structural failure (httpx unavailable). The Mood Compass
degrades gracefully to 'data_unavailable' when all signals are None.

market_breadth is derived from the NIFTY-50 constituent advances/declines via the
shared helper in market_data/breadth.py (``fetch_nifty50_advances_declines_sync``). The
Redis breadth cache (``signal:breadth:last``, TTL 3600s) is read-first to avoid a
second slow ~2-5s yfinance download when the Signal-card path already pre-warmed
it. A breadth fetch failure only omits the key; the six chart signals are still
returned normally. ProviderError is never raised solely because breadth failed.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
from urllib.parse import quote

import httpx

from dhanradar.market_data.config import DataKind, DataRequest
from dhanradar.market_data.events import MacroSignalReceived
from dhanradar.market_data.exceptions import ProviderError
from dhanradar.market_data.providers.base import MarketDataProvider

# Breadth cache constants — shared with mood/service.py (via market_data.breadth)
# so the two paths read the same Redis key and the pre-warmed Signal-card fetch is reused here.
_BREADTH_CACHE_KEY = "signal:breadth:last"
_TTL_BREADTH_SEC = 3600

logger = logging.getLogger(__name__)

_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
# Yahoo rejects an empty/unknown User-Agent; any browser-ish UA is accepted.
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DhanRadar/1.0; +https://dhanradar.com)"}
_TIMEOUT = httpx.Timeout(15.0, connect=8.0)

# signal-key → (yahoo symbol, mode) where mode is "pct" (daily % change) or
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
    except Exception as exc:  # noqa: BLE001 — each symbol is independent best-effort
        logger.debug("yahoo_macro: fetch failed for %s: %s", symbol, exc)
        return None


def _signal_value(meta: dict, mode: str) -> float | None:
    """Derive the raw signal from a chart meta block: a % daily change or a level."""
    price = meta.get("regularMarketPrice")
    if not price:  # None or 0 — a 0 price/level is meaningless, treat as missing
        return None
    if mode == "level":
        return float(price)
    # mode == "pct": percent change vs the previous close.
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    if not prev:  # None or 0 → can't compute a % change
        return None
    return (float(price) - float(prev)) / float(prev) * 100.0


async def _fetch_breadth_ratio() -> float | None:
    """Return the market breadth ratio advances/(advances+declines) in [0,1].

    Strategy (cache-first, never imputes):
      1. Try the Redis breadth cache (``signal:breadth:last``, TTL 3600s) — the
         Signal-card Celery task pre-warms this every 15 min, so a live yfinance
         download is usually avoided.
      2. On cache miss, call ``fetch_nifty50_advances_declines_sync`` in a thread.
      3. On ANY error (Redis unavailable, yfinance failure, bad data) return None —
         the key is simply absent from the signals dict (graceful degradation).

    NOTE: the Redis cache stores ``ad_ratio = advances/declines`` (an A/D ratio,
    not a/(a+d)), so we CANNOT derive a/(a+d) from it without the raw counts.
    We use ``advances`` and ``declines`` from the cache directly for the correct
    formula, falling back to a live fetch when the cache is warm but lacks those
    fields (legacy cache entries).
    """
    # --- attempt 1: Redis cache ---
    try:
        from dhanradar.redis_client import get_redis
        raw = await get_redis().get(_BREADTH_CACHE_KEY)
        if raw:
            data = json.loads(raw if isinstance(raw, str) else raw.decode())
            advances = data.get("advances")
            declines = data.get("declines")
            if advances is not None and declines is not None:
                total = int(advances) + int(declines)
                if total > 0:
                    return float(int(advances)) / float(total)
    except Exception:  # noqa: BLE001 — cache unavailable → fall through to live fetch
        pass

    # --- attempt 2: live yfinance fetch ---
    try:
        from dhanradar.market_data.breadth import fetch_nifty50_advances_declines_sync
        advances, declines = await asyncio.to_thread(fetch_nifty50_advances_declines_sync)
        total = advances + declines
        if total <= 0:
            return None
        ratio = float(advances) / float(total)
        # Back-fill the cache so subsequent callers (Signal-card, next run) benefit.
        try:
            from dhanradar.redis_client import get_redis
            cache_payload = json.dumps({"advances": advances, "declines": declines, "ad_ratio": round(advances / max(declines, 1), 3)})
            await get_redis().set(_BREADTH_CACHE_KEY, cache_payload, ex=_TTL_BREADTH_SEC)
        except Exception:  # noqa: BLE001 — cache write is best-effort
            pass
        return ratio
    except Exception as exc:  # noqa: BLE001 — breadth is best-effort
        logger.debug("yahoo_macro: breadth fetch failed — %s", exc)
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
        except ImportError as exc:  # pragma: no cover — httpx is a hard dep
            raise ProviderError(self.name, f"httpx not available: {exc}") from exc

        # An empty result (every symbol blank — e.g. a Yahoo outage / layout
        # change) MUST raise so the adapter ladder falls through to the fallback
        # provider instead of recording a false "success". A success with an
        # empty signals dict would otherwise silently reproduce the original
        # no-snapshot bug (compute_mood would skip on all-None inputs).
        if not signals:
            raise ProviderError(self.name, "no macro signals resolved from Yahoo")

        # market_breadth — derived from NIFTY-50 constituent A/D counts.
        # Read Redis cache first (pre-warmed by the Signal-card Celery task) to
        # avoid a second slow ~2-5s yfinance download.  A failure here only omits
        # the key (NEVER IMPUTE); it does NOT raise ProviderError.
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
