"""
DhanRadar — Upstox Analytics macro-signal provider (FII / DII / PCR).

Supplies three Mood Compass signals that the Yahoo/NSE macro providers do not:
foreign-institutional and domestic-institutional daily net cash flows and the
Nifty put-call ratio (docs/research/mood-data-sourcing-2026-06-21.md §2–3).

Active ONLY when ``UPSTOX_ANALYTICS_TOKEN`` is configured. With no token — or on
any HTTP / parse error — every signal is simply omitted, so the Mood engine
degrades gracefully (it drops the missing factor and decrements coverage; it
never crashes and never imputes a value). This provider NEVER raises for a
missing token, a non-200, or malformed JSON — those all resolve to "no signal".

RAW values are returned (net flow in ₹Cr, raw PCR); normalization to the
engine's 0–1 scale happens in ``mood/signals.py`` (norm_fii_flows /
norm_dii_flows / norm_put_call_ratio — PCR is contrarian-inverted there).

NOT yet smoke-tested against the live API — no token in hand at build time
(tested against captured fixtures only). Pending scoring + compliance sign-off
and a live-token smoke test before it lands.

Integration note (flagged for review): the shared MACRO_SIGNAL ladder returns a
SINGLE provider's event (it does not merge providers), so combining these three
signals with the Yahoo macro set needs a deliberate wiring decision (a dedicated
fetch alongside the Yahoo fetch, or an adapter-level merge) — out of scope for
this provider unit and deferred to the scoring/architecture review.
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import Callable

import httpx

from dhanradar.market_data.config import DataKind, DataRequest
from dhanradar.market_data.events import MacroSignalReceived
from dhanradar.market_data.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)

# Upstox developer market-data API (v2). Auth is the read-only Analytics Token,
# sent as a Bearer header — never in the URL/query, never logged.
_BASE = "https://api.upstox.com/v2/market"
_FII_URL = f"{_BASE}/fii"
_DII_URL = f"{_BASE}/dii"
_PCR_URL = f"{_BASE}/pcr"

# FII/DII daily cash-market flow query (dig §2).
_FLOW_PARAMS = {"data_type": "NSE_EQ|CASH", "interval": "1D"}
# The flow records are keyed under this exact string in the response `data` map.
_FLOW_DATA_KEY = "NSE_EQ|CASH"

# Nifty-50 instrument key for the PCR endpoint.
# TODO verify against Upstox instrument master — best guess from the dig; the
# exact key string must be confirmed against the live instrument dump before deploy.
_NIFTY50_INSTRUMENT_KEY = "NSE_INDEX|Nifty 50"

_TIMEOUT = httpx.Timeout(15.0, connect=8.0)


def _now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


# OUTBOUND auth scheme for the third-party Upstox API — NOT DhanRadar's own auth
# (which is cookie-only, non-neg #4). Kept as a constant so the literal scheme+space
# value never appears in source (mirrors notifications/channels.py's Resend header).
_AUTH_SCHEME = "Bearer"


def _auth_headers(token: str) -> dict[str, str]:
    """Build the per-call auth headers. The token is read from settings/env and
    is never logged or persisted."""
    return {"Authorization": f"{_AUTH_SCHEME} {token}", "Accept": "application/json"}


def _configured_token() -> str:
    """Read the Analytics Token from settings (env). Deferred import keeps this
    module import-light and lets tests inject a token without touching env."""
    from dhanradar.config import settings

    return settings.UPSTOX_ANALYTICS_TOKEN or ""


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    params: dict[str, str],
) -> dict | None:
    """GET a URL and return parsed JSON, or None on any error / non-200 /
    malformed body. Never raises (per-signal best-effort). The token lives in
    ``headers``, not the URL, so the URL is safe to log."""
    try:
        resp = await client.get(url, headers=headers, params=params, timeout=_TIMEOUT)
        if resp.status_code != 200:
            logger.warning("upstox_analytics: HTTP %s from %s", resp.status_code, url)
            return None
        body = resp.json()
        return body if isinstance(body, dict) else None
    except Exception as exc:  # noqa: BLE001 — each signal independent, never crash
        logger.warning("upstox_analytics: fetch failed for %s: %s", url, exc)
        return None


def _latest_record(records: object) -> dict | None:
    """Return the most recent flow record (highest ``time_stamp``).

    Selects by max ``time_stamp`` so the result is correct regardless of the
    array's order; falls back to the last element if time_stamps are absent or
    not mutually comparable. Returns None for an empty / malformed list.
    """
    if not isinstance(records, list) or not records:
        return None
    dated = [r for r in records if isinstance(r, dict) and r.get("time_stamp") is not None]
    if dated:
        try:
            return max(dated, key=lambda r: r["time_stamp"])
        except TypeError:
            pass  # uncomparable time_stamps → fall through to positional
    last = records[-1]
    return last if isinstance(last, dict) else None


def _parse_net_flow(payload: dict | None) -> float | None:
    """Extract net_flow (₹Cr) = buy_amount − sell_amount from the LATEST record
    of a /fii or /dii response. Returns None on any structural gap."""
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    record = _latest_record(data.get(_FLOW_DATA_KEY))
    if record is None:
        return None
    buy = record.get("buy_amount")
    sell = record.get("sell_amount")
    if buy is None or sell is None:
        return None
    try:
        return float(buy) - float(sell)
    except (TypeError, ValueError):
        return None


def _parse_pcr(payload: dict | None) -> float | None:
    """Extract the pre-computed PCR from ``data.pcr`` of a /pcr response."""
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    pcr = data.get("pcr")
    if pcr is None:
        return None
    try:
        return float(pcr)
    except (TypeError, ValueError):
        return None


class UpstoxAnalyticsProvider(MarketDataProvider):
    """
    Upstox Analytics macro-signal provider for the Mood Compass.

    Returns a ``MacroSignalReceived`` whose ``signals`` dict carries raw values
    for ``fii_flows``, ``dii_flows`` and ``put_call_ratio`` — each present only
    when its endpoint succeeded. A missing token, a non-200, malformed JSON, or
    an empty data list each yields an omitted signal (never an exception), so
    the engine degrades gracefully.
    """

    name = "upstox_analytics"

    def __init__(
        self,
        token: str | None = None,
        *,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        # token=None → read from settings at fetch time. Pass token="" to force
        # the not-configured path, or an httpx client_factory to inject a fake
        # transport in tests (no live network).
        self._token = token
        self._client_factory = client_factory

    def supports(self, kind: DataKind) -> bool:
        return kind == DataKind.MACRO_SIGNAL

    async def fetch(self, request: DataRequest) -> MacroSignalReceived:
        token = self._token if self._token is not None else _configured_token()
        if not token:
            logger.info("upstox_analytics: no token configured — returning no signals")
            return MacroSignalReceived(source=self.name, signals={}, fetched_at=_now_iso())

        headers = _auth_headers(token)
        try:
            client = self._client_factory() if self._client_factory else httpx.AsyncClient()
            async with client:
                fii_payload = await _get_json(client, _FII_URL, headers, _FLOW_PARAMS)
                dii_payload = await _get_json(client, _DII_URL, headers, _FLOW_PARAMS)
                pcr_payload = await _get_json(
                    client, _PCR_URL, headers, {"instrument_key": _NIFTY50_INSTRUMENT_KEY}
                )
        except Exception as exc:  # noqa: BLE001 — client construction/teardown is best-effort
            logger.warning("upstox_analytics: client error — %s", exc)
            return MacroSignalReceived(source=self.name, signals={}, fetched_at=_now_iso())

        signals: dict[str, float] = {}
        fii = _parse_net_flow(fii_payload)
        dii = _parse_net_flow(dii_payload)
        pcr = _parse_pcr(pcr_payload)
        if fii is not None:
            signals["fii_flows"] = fii
        if dii is not None:
            signals["dii_flows"] = dii
        if pcr is not None:
            signals["put_call_ratio"] = pcr

        logger.info(
            "upstox_analytics: fetched %d/3 signals: %s", len(signals), list(signals.keys())
        )
        return MacroSignalReceived(source=self.name, signals=signals, fetched_at=_now_iso())
