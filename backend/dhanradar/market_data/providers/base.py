"""
DhanRadar — Abstract base class for all market-data providers.

Domain modules never call a provider directly — they call
``MarketDataAdapter.fetch()``, which walks the ladder and calls providers
via this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from dhanradar.market_data.config import DataKind, DataRequest


class MarketDataProvider(ABC):
    """Abstract base for every provider stub / implementation."""

    # Subclasses MUST set a unique lowercase name used in ladder config.
    name: str

    @abstractmethod
    def supports(self, kind: DataKind) -> bool:
        """Return True if this provider can serve requests of *kind*."""

    @abstractmethod
    async def fetch(self, request: DataRequest) -> object:
        """
        Fetch data and return a normalised event from ``events.py``.

        Raises ``ProviderError`` on any failure (network, auth, simulated 5xx,
        or not-configured).  Must never raise a bare ``Exception`` — wrap it.
        """
