"""
DhanRadar — Stub implementations for every provider ladder rung.

ALL providers here are stubs.  No real network calls are made anywhere in
this file.  Each stub raises ``ProviderError("not_configured")`` by default
(no vendor keys / partnerships in place) EXCEPT:
  - ``amfi_nav``  → reads the latest NAV for the requested scheme from the DB
                    (mf_nav_history joined via mf_funds.amfi_code when only a
                    scheme_code is given).  Raises ProviderError if no row found.
  - ``nse_dump``  → returns canned ``PriceRefreshed`` so the EQUITY_PRICE happy path works.

Replace each stub's ``fetch()`` with a real implementation once the vendor
key / partnership is established and move it to a separate module.
"""

from __future__ import annotations

import datetime

from dhanradar.market_data.config import DataKind, DataRequest
from dhanradar.market_data.events import (
    NavRefreshed,
    PriceRefreshed,
)
from dhanradar.market_data.exceptions import ProviderError
from dhanradar.market_data.providers.base import MarketDataProvider


def _now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


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
    AMFI public NAV feed — DB-backed (reads mf_nav_history).

    ``request.params`` must carry either ``isin`` (direct lookup) or
    ``scheme_code`` (AMFI code; joined via mf_funds.amfi_code).  Returns the
    most recent ``NavRefreshed`` event for the scheme.  Raises
    ``ProviderError(self.name, "no_nav_data")`` when no row exists yet.

    DB imports are deferred to ``fetch()`` to keep module-level imports light
    and to avoid engine initialisation at import time (mirrors tasks/mf.py).
    """

    name = "amfi_nav"

    def supports(self, kind: DataKind) -> bool:
        return kind in (DataKind.FUND_NAV,)

    async def fetch(self, request: DataRequest) -> object:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from dhanradar.db import engine
        from dhanradar.models.mf import MfFund, MfNavHistory

        isin: str | None = request.params.get("isin")
        scheme_code: str | None = request.params.get("scheme_code")

        if not isin and not scheme_code:
            raise ProviderError(self.name, "request must include 'isin' or 'scheme_code'")

        SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with SessionLocal() as db:
            if isin:
                # Direct lookup by ISIN.
                stmt = (
                    select(MfNavHistory.nav, MfNavHistory.nav_date)
                    .where(MfNavHistory.isin == isin)
                    .order_by(MfNavHistory.nav_date.desc())
                    .limit(1)
                )
                row = (await db.execute(stmt)).one_or_none()
                if row is None:
                    raise ProviderError(self.name, "no_nav_data")
                return NavRefreshed(
                    scheme_code=isin,
                    nav=float(row.nav),
                    nav_date=row.nav_date.isoformat(),
                    source=self.name,
                )
            else:
                # scheme_code (amfi_code) → resolve ISIN via mf_funds then fetch NAV.
                isin_stmt = (
                    select(MfFund.isin)
                    .where(MfFund.amfi_code == str(scheme_code))
                    .limit(1)
                )
                isin_row = (await db.execute(isin_stmt)).one_or_none()
                if isin_row is None:
                    raise ProviderError(self.name, "no_nav_data")
                resolved_isin: str = isin_row.isin
                nav_stmt = (
                    select(MfNavHistory.nav, MfNavHistory.nav_date)
                    .where(MfNavHistory.isin == resolved_isin)
                    .order_by(MfNavHistory.nav_date.desc())
                    .limit(1)
                )
                nav_row = (await db.execute(nav_stmt)).one_or_none()
                if nav_row is None:
                    raise ProviderError(self.name, "no_nav_data")
                return NavRefreshed(
                    scheme_code=str(scheme_code),
                    nav=float(nav_row.nav),
                    nav_date=nav_row.nav_date.isoformat(),
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
