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

LIVE smoke-tested 2026-06-22 with the real Analytics Token: FII + DII returned
plausible daily net flows; PCR now returns data after the expiry resolver was
switched from a Thursday guess to a real expiry lookup (NSE Nifty weekly options
expire on TUESDAY, not Thursday — see _fetch_nearest_expiry). Pending scoring +
compliance sign-off before it lands.

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

# FII/DII daily cash-market flow query (dig §2). These params are correct as-is
# (verified against the Upstox get-fii / get-dii docs: data_type + interval).
_FLOW_PARAMS = {"data_type": "NSE_EQ|CASH", "interval": "1D"}
# The flow records are keyed under this exact string in the response `data` map.
_FLOW_DATA_KEY = "NSE_EQ|CASH"

# Nifty-50 instrument key for the PCR endpoint. VERIFIED 2026-06-22 against the
# Upstox instruments docs + community (the canonical NSE index key is exactly this).
_NIFTY50_INSTRUMENT_KEY = "NSE_INDEX|Nifty 50"

# Option-contract endpoint — lists every live Nifty option contract with its
# `expiry` (ISO YYYY-MM-DD). Used to resolve the REAL nearest expiry for the PCR
# call instead of guessing a weekday (the weekly expiry day has changed over time;
# verified live 2026-06-22 — Nifty weekly now expires on Tuesday, not Thursday).
_CONTRACT_URL = "https://api.upstox.com/v2/option/contract"

# PCR intraday bucket granularity (minutes). The twice-daily snapshot only needs a
# single read, so the bucket size is immaterial to the final data.pcr; 60 is a safe
# coarse value.
_PCR_BUCKET_INTERVAL = "60"

_IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

_TIMEOUT = httpx.Timeout(15.0, connect=8.0)


def _now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


def _ist_today() -> datetime.date:
    """Today's date in IST — the trading date used for the PCR `date` param."""
    return datetime.datetime.now(_IST).date()


def _parse_expiries(payload: dict | None) -> list[str]:
    """Distinct ISO ``YYYY-MM-DD`` expiry dates from an option/contract response
    (``data[].expiry``), sorted ascending. [] on any structural gap."""
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    found = {
        rec["expiry"]
        for rec in data
        if isinstance(rec, dict) and isinstance(rec.get("expiry"), str)
    }
    return sorted(found)


def _nearest_expiry(expiries: list[str], today: datetime.date) -> str | None:
    """Nearest option expiry on/after ``today`` from a list of ISO date strings.

    ISO ``YYYY-MM-DD`` sorts lexicographically == chronologically, so a plain
    string comparison is correct. Returns None if the list is empty or every
    expiry is in the past (→ PCR omitted, fails soft; FII/DII unaffected).
    """
    iso_today = today.isoformat()
    upcoming = sorted(e for e in expiries if e >= iso_today)
    return upcoming[0] if upcoming else None


async def _fetch_nearest_expiry(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    today: datetime.date,
) -> str | None:
    """Resolve the real nearest Nifty option expiry by querying the live
    option/contract list. None on any error (→ PCR omitted, never raises).

    Replaces the old Thursday-guess heuristic: the NSE weekly expiry weekday has
    changed (it is Tuesday as of 2026-06, confirmed live), and exchange holidays
    shift it further, so a fixed weekday is unreliable. The exchange's own
    contract list is the source of truth.
    """
    payload = await _get_json(
        client, _CONTRACT_URL, headers, {"instrument_key": _NIFTY50_INSTRUMENT_KEY}
    )
    return _nearest_expiry(_parse_expiries(payload), today)


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
                # PCR requires ALL FOUR params (verified live against the get-pcr
                # endpoint 2026-06-22): instrument_key + expiry + date +
                # bucket_interval. The `expiry` MUST be a real, currently-listed
                # option expiry — a wrong date returns HTTP 200 with data=null. We
                # resolve it from the live contract list rather than guessing a
                # weekday; if it cannot be resolved, PCR is skipped (fails soft,
                # FII/DII unaffected).
                today = _ist_today()
                pcr_payload = None
                expiry = await _fetch_nearest_expiry(client, headers, today)
                if expiry is not None:
                    pcr_payload = await _get_json(
                        client,
                        _PCR_URL,
                        headers,
                        {
                            "instrument_key": _NIFTY50_INSTRUMENT_KEY,
                            "expiry": expiry,
                            "date": today.isoformat(),
                            "bucket_interval": _PCR_BUCKET_INTERVAL,
                        },
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
