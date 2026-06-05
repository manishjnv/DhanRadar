"""
DhanRadar — Stub implementations for every provider ladder rung.

ALL providers here are stubs.  No real network calls are made anywhere in
this file.  Each stub raises ``ProviderError("not_configured")`` by default
(no vendor keys / partnerships in place) EXCEPT:
  - ``amfi_nav``  → returns canned ``NavRefreshed`` so the FUND_NAV happy path works.
  - ``nse_dump``  → returns canned ``PriceRefreshed`` so the EQUITY_PRICE happy path works.

Replace each stub's ``fetch()`` with a real implementation once the vendor
key / partnership is established and move it to a separate module.
"""

from __future__ import annotations

import datetime

from dhanradar.market_data.config import DataKind, DataRequest
from dhanradar.market_data.events import (
    EVENT_AA_HOLDINGS_RECEIVED,
    EVENT_BROKER_POSITIONS_RECEIVED,
    EVENT_MFCENTRAL_HOLDINGS_RECEIVED,
    HoldingsReceived,
    NavRefreshed,
    PriceRefreshed,
)
from dhanradar.market_data.exceptions import ProviderError
from dhanradar.market_data.providers.base import MarketDataProvider


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Fund providers
# ---------------------------------------------------------------------------


class MFCentralProvider(MarketDataProvider):
    """STUB — MF Central API.  Pending vendor registration / SEBI agreement."""

    name = "mf_central"

    def supports(self, kind: DataKind) -> bool:
        return kind in (DataKind.FUND_NAV, DataKind.FUND_HOLDINGS)

    async def fetch(self, request: DataRequest) -> object:
        # STUB: no credentials configured yet.
        raise ProviderError(self.name, "not_configured")


class AccountAggregatorProvider(MarketDataProvider):
    """
    STUB — Account Aggregator (AA) framework.

    Explicit AA STUB — partner not yet signed.  This rung will be promoted
    to a real implementation once the AA license and FIP integrations are in
    place.  See BLOCKERS.md for tracking.
    """

    name = "account_aggregator"

    def supports(self, kind: DataKind) -> bool:
        return kind in (DataKind.FUND_HOLDINGS, DataKind.EQUITY_HOLDINGS)

    async def fetch(self, request: DataRequest) -> object:
        # EXPLICIT AA STUB — partner not yet signed.
        raise ProviderError(self.name, "not_configured — AA partner not yet signed")


class CASParserProvider(MarketDataProvider):
    """STUB — CAS PDF parser (in-process).  Pending full parser implementation."""

    name = "cas_parser"

    def supports(self, kind: DataKind) -> bool:
        return kind in (DataKind.FUND_HOLDINGS,)

    async def fetch(self, request: DataRequest) -> object:
        # STUB: CAS parser not yet wired to this adapter path.
        raise ProviderError(self.name, "not_configured")


class AMFINavProvider(MarketDataProvider):
    """
    STUB — AMFI public NAV feed (amfiindia.com).

    Returns canned data so the FUND_NAV happy path is demonstrable without
    a live network call.  Replace with a real HTTP fetch when wiring production.
    """

    name = "amfi_nav"

    def supports(self, kind: DataKind) -> bool:
        return kind in (DataKind.FUND_NAV,)

    async def fetch(self, request: DataRequest) -> object:
        # STUB: returns canned NAV data — no real network call.
        scheme_code = request.params.get("scheme_code", "120503")
        return NavRefreshed(
            scheme_code=str(scheme_code),
            nav=82.5432,
            nav_date="2026-06-05",
            source=self.name,
        )


# ---------------------------------------------------------------------------
# Equity / ETF providers
# ---------------------------------------------------------------------------


class UpstoxProvider(MarketDataProvider):
    """STUB — Upstox API v2.  Pending API key and SEBI broker integration."""

    name = "upstox"

    def supports(self, kind: DataKind) -> bool:
        return kind in (DataKind.EQUITY_PRICE, DataKind.EQUITY_HOLDINGS)

    async def fetch(self, request: DataRequest) -> object:
        # STUB: no API key configured.
        raise ProviderError(self.name, "not_configured")


class KiteProvider(MarketDataProvider):
    """STUB — Zerodha Kite Connect API.  Pending API key and broker integration."""

    name = "kite"

    def supports(self, kind: DataKind) -> bool:
        return kind in (DataKind.EQUITY_PRICE, DataKind.EQUITY_HOLDINGS)

    async def fetch(self, request: DataRequest) -> object:
        # STUB: no API key configured.
        raise ProviderError(self.name, "not_configured")


class TwelveDataProvider(MarketDataProvider):
    """STUB — Twelve Data market-data API.  Pending API key."""

    name = "twelvedata"

    def supports(self, kind: DataKind) -> bool:
        return kind in (DataKind.EQUITY_PRICE,)

    async def fetch(self, request: DataRequest) -> object:
        # STUB: no API key configured.
        raise ProviderError(self.name, "not_configured")


class NSEDumpProvider(MarketDataProvider):
    """
    STUB — NSE daily bhavcopy / dump parser (public, no auth).

    Returns canned data so the EQUITY_PRICE happy path is demonstrable without
    a live network call.  Replace with a real bhavcopy fetch when wiring production.
    """

    name = "nse_dump"

    def supports(self, kind: DataKind) -> bool:
        return kind in (DataKind.EQUITY_PRICE,)

    async def fetch(self, request: DataRequest) -> object:
        # STUB: returns canned price data — no real network call.
        symbol = request.params.get("symbol", "NIFTY50")
        return PriceRefreshed(
            symbol=str(symbol),
            price=24_500.00,
            ts=_now_iso(),
            source=self.name,
        )


# ---------------------------------------------------------------------------
# Convenience: all stubs in one list for easy registration
# ---------------------------------------------------------------------------

ALL_STUBS: list[MarketDataProvider] = [
    MFCentralProvider(),
    AccountAggregatorProvider(),
    CASParserProvider(),
    AMFINavProvider(),
    UpstoxProvider(),
    KiteProvider(),
    TwelveDataProvider(),
    NSEDumpProvider(),
]
