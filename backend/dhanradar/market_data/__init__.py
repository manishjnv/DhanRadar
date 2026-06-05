"""
DhanRadar — Market Data Adapter package.

Public surface consumed by domain modules.  Domain modules import only
from here — never from sub-modules directly.

Architecture §B4: provider-agnostic gateway with config-driven ladder
routing, circuit breaker, and ordered fallback.  Domain modules never call
a data vendor directly; a provider swap is config-only.
"""

from __future__ import annotations

from dhanradar.market_data.adapter import MarketDataAdapter
from dhanradar.market_data.circuit_breaker import CircuitBreaker
from dhanradar.market_data.config import DataKind, DataRequest, load_ladders
from dhanradar.market_data.events import (
    EVENT_AA_HOLDINGS_RECEIVED,
    EVENT_BROKER_POSITIONS_RECEIVED,
    EVENT_MFCENTRAL_HOLDINGS_RECEIVED,
    EVENT_NAV_REFRESHED,
    EVENT_PRICE_REFRESHED,
    HoldingsReceived,
    NavRefreshed,
    PriceRefreshed,
)
from dhanradar.market_data.exceptions import AllProvidersFailedError, ProviderError
from dhanradar.market_data.providers.base import MarketDataProvider

__all__ = [
    # Adapter
    "MarketDataAdapter",
    # Config
    "DataKind",
    "DataRequest",
    "load_ladders",
    # Events
    "NavRefreshed",
    "PriceRefreshed",
    "HoldingsReceived",
    "EVENT_MFCENTRAL_HOLDINGS_RECEIVED",
    "EVENT_AA_HOLDINGS_RECEIVED",
    "EVENT_BROKER_POSITIONS_RECEIVED",
    "EVENT_NAV_REFRESHED",
    "EVENT_PRICE_REFRESHED",
    # Exceptions
    "ProviderError",
    "AllProvidersFailedError",
    # Provider base (for typing in domain modules)
    "MarketDataProvider",
    # Circuit breaker (for health checks / testing)
    "CircuitBreaker",
]
