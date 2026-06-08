"""
DhanRadar — NSE Macro Signal Provider (best-effort, NOT deploy-hardened).

Fetches a minimal subset of macro signals for the Mood Compass from NSE
public JSON endpoints.  Each signal is fetched independently so a partial
failure still yields the signals that succeeded.

BEST-EFFORT NOTICE: NSE public endpoints are undocumented, change without
notice, and are rate-limited / geo-blocked in some environments.  This
provider is designed for best-effort data acquisition only.  Any failure per
signal → that signal is returned as None (absent from the payload).
ProviderError is raised ONLY if the whole fetch is structurally broken (e.g.
no httpx available) — a partial result is valid and handled gracefully by
mood/signals.py.

Signals fetched:
  - nifty_trend    : % daily change in NIFTY 50 (NSE quote API)
  - india_vix      : India VIX (NSE VIX quote)
  - market_breadth : advances/(advances+declines) ratio (NSE market-status API)
  - put_call_ratio : total PCR from NSE derivatives data

Raw values are returned as-is; normalization to [0,1] is done in
mood/signals.py per the documented formulas.
"""

from __future__ import annotations

import datetime
import logging

import httpx

from dhanradar.market_data.config import DataKind, DataRequest
from dhanradar.market_data.events import MacroSignalReceived
from dhanradar.market_data.exceptions import ProviderError
from dhanradar.market_data.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)

# NSE requires a browser-like UA; a bare urllib agent gets 403.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nseindia.com/",
}
_TIMEOUT = httpx.Timeout(15.0, connect=8.0)

# NSE public JSON endpoints (undocumented, best-effort)
_NIFTY50_QUOTE_URL = "https://www.nseindia.com/api/quote-equity?symbol=NIFTY%2050&series=EQ"
_VIX_QUOTE_URL = "https://www.nseindia.com/api/quote-equity?symbol=INDIA%20VIX&series=EQ"
_MARKET_STATUS_URL = "https://www.nseindia.com/api/market-status"
_PCR_URL = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


async def _get_json(client: httpx.AsyncClient, url: str) -> dict | list | None:
    """GET a URL and return parsed JSON, or None on any error."""
    try:
        resp = await client.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code != 200:
            logger.debug("nse_macro: HTTP %s from %s", resp.status_code, url)
            return None
        return resp.json()
    except Exception as exc:  # noqa: BLE001 — each signal independent
        logger.debug("nse_macro: fetch failed for %s: %s", url, exc)
        return None


async def _fetch_nifty_trend(client: httpx.AsyncClient) -> float | None:
    """Return NIFTY 50 % daily change (raw, not normalised)."""
    try:
        data = await _get_json(client, _NIFTY50_QUOTE_URL)
        if not isinstance(data, dict):
            return None
        # NSE priceInfo path
        price_info = data.get("priceInfo", {})
        pct = price_info.get("pChange") or price_info.get("change")
        if pct is not None:
            return float(pct)
        return None
    except Exception:  # noqa: BLE001
        return None


async def _fetch_india_vix(client: httpx.AsyncClient) -> float | None:
    """Return India VIX value (raw, not normalised)."""
    try:
        data = await _get_json(client, _VIX_QUOTE_URL)
        if not isinstance(data, dict):
            return None
        price_info = data.get("priceInfo", {})
        vix = price_info.get("lastPrice")
        if vix is not None:
            return float(vix)
        return None
    except Exception:  # noqa: BLE001
        return None


async def _fetch_market_breadth(client: httpx.AsyncClient) -> float | None:
    """Return advances/(advances+declines) ratio (already 0-1, no normalisation needed)."""
    try:
        data = await _get_json(client, _MARKET_STATUS_URL)
        if not isinstance(data, dict):
            return None
        # NSE market status: marketState list or advanceDecline dict
        advances = data.get("advances") or data.get("advancesDeclines", {}).get("advances")
        declines = data.get("declines") or data.get("advancesDeclines", {}).get("declines")
        if advances is not None and declines is not None:
            total = float(advances) + float(declines)
            if total > 0:
                return float(advances) / total
        return None
    except Exception:  # noqa: BLE001
        return None


async def _fetch_put_call_ratio(client: httpx.AsyncClient) -> float | None:
    """Return NIFTY total put-call ratio (raw, not normalised)."""
    try:
        data = await _get_json(client, _PCR_URL)
        if not isinstance(data, dict):
            return None
        filtered = data.get("filtered", {})
        # Try the summary PCR field first
        pcr_val = data.get("filtered", {}).get("pcr")
        if pcr_val is None:
            # Some API versions have it at top level
            pcr_val = data.get("pcr")
        if pcr_val is not None:
            return float(pcr_val)
        # Fall back to computing from total OI
        ce_oi = filtered.get("CE", {}).get("totOI")
        pe_oi = filtered.get("PE", {}).get("totOI")
        if ce_oi and pe_oi and float(ce_oi) > 0:
            return float(pe_oi) / float(ce_oi)
        return None
    except Exception:  # noqa: BLE001
        return None


class NseMacroProvider(MarketDataProvider):
    """
    Best-effort NSE public JSON macro signal provider.

    Fetches {nifty_trend, india_vix, market_breadth, put_call_ratio} from
    NSE public endpoints.  Each signal is fetched independently — a per-signal
    failure yields None for that signal; the rest proceed.  The whole fetch
    raises ProviderError only on a catastrophic structural failure.

    BEST-EFFORT, NOT deploy-hardened: NSE endpoints are undocumented and may
    break without notice.  The Mood Compass degrades gracefully to
    'data_unavailable' when all signals are None.
    """

    name = "nse_macro"

    def supports(self, kind: DataKind) -> bool:
        return kind == DataKind.MACRO_SIGNAL

    async def fetch(self, request: DataRequest) -> MacroSignalReceived:
        """
        Fetch the macro signal subset.  Returns a MacroSignalReceived event
        whose ``signals`` dict contains raw values for each signal that
        succeeded (missing → key absent from dict).

        Raises ProviderError only if httpx itself is unavailable.
        """
        try:
            async with httpx.AsyncClient() as client:
                # Fetch a session cookie first — NSE requires it
                try:
                    await client.get(
                        "https://www.nseindia.com",
                        headers=_HEADERS,
                        timeout=httpx.Timeout(8.0, connect=5.0),
                    )
                except Exception:  # noqa: BLE001 — session warmup is best-effort
                    logger.debug("nse_macro: session warmup failed — proceeding anyway")

                nifty_pct, vix, breadth, pcr = (
                    await _fetch_nifty_trend(client),
                    await _fetch_india_vix(client),
                    await _fetch_market_breadth(client),
                    await _fetch_put_call_ratio(client),
                )
        except ImportError as exc:
            raise ProviderError(self.name, f"httpx not available: {exc}") from exc

        signals: dict[str, float] = {}
        if nifty_pct is not None:
            signals["nifty_trend"] = nifty_pct
        if vix is not None:
            signals["india_vix"] = vix
        if breadth is not None:
            signals["market_breadth"] = breadth
        if pcr is not None:
            signals["put_call_ratio"] = pcr

        logger.info(
            "nse_macro: fetched %d/%d signals: %s",
            len(signals),
            4,
            list(signals.keys()),
        )
        return MacroSignalReceived(
            source=self.name,
            signals=signals,
            fetched_at=_now_iso(),
        )
