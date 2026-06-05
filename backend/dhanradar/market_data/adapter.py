"""
DhanRadar — Market Data Adapter.

The single entry-point domain modules use to fetch market data.
Walks the provider ladder in order, skipping any provider whose circuit
breaker is OPEN.  On success it optionally emits the normalised event to a
pluggable async sink.  On exhausting all rungs it raises
``AllProvidersFailedError``.

Domain modules call only ``adapter.fetch(request)`` — never a provider.
A provider swap is config-only (arch §B4).

No imports from auth / billing / scoring.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from dhanradar.market_data.circuit_breaker import CircuitBreaker
from dhanradar.market_data.config import DataKind, DataRequest
from dhanradar.market_data.exceptions import AllProvidersFailedError, ProviderError
from dhanradar.market_data.providers.base import MarketDataProvider


class MarketDataAdapter:
    """
    Provider-agnostic gateway with circuit-breaker-backed ordered fallback.

    Parameters
    ----------
    providers:
        Map of provider-name → provider instance.
    ladders:
        Map of DataKind → ordered list of provider names (the fallback ladder).
    event_sink:
        Optional async callable invoked with the normalised event on each
        successful fetch.  Pluggable — wire to a message bus, an audit log,
        or a Celery task in production; leave None in tests that don't care.
    breaker_factory:
        Callable that returns a fresh ``CircuitBreaker``.  One breaker is
        created per provider name on first access.  Override in tests to
        inject a fake-clock breaker.
    """

    def __init__(
        self,
        providers: dict[str, MarketDataProvider],
        ladders: dict[DataKind, list[str]],
        event_sink: Callable[[object], Awaitable[None]] | None = None,
        breaker_factory: Callable[[], CircuitBreaker] | None = None,
    ) -> None:
        self._providers = providers
        self._ladders = ladders
        self._event_sink = event_sink
        self._breaker_factory = breaker_factory or (lambda: CircuitBreaker())
        self._breakers: dict[str, CircuitBreaker] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch(self, request: DataRequest) -> object:
        """
        Walk the ladder for ``request.kind`` and return the first successful
        normalised event.

        Raises
        ------
        KeyError
            If ``request.kind`` has no ladder defined.
        AllProvidersFailedError
            If every provider in the ladder failed (or was skipped due to an
            open circuit breaker and no un-broken provider succeeded).
        """
        ladder = self._ladders[request.kind]
        errors: list[tuple[str, ProviderError]] = []

        for name in ladder:
            breaker = self._get_breaker(name)

            if not breaker.allow():
                # Circuit is OPEN — skip entirely, do not call the provider.
                continue

            provider = self._providers.get(name)
            if provider is None:
                # Provider not registered — treat as a configuration failure
                # and record so AllProvidersFailedError carries the gap.
                err = ProviderError(name, "provider not registered in adapter")
                errors.append((name, err))
                breaker.record_failure()
                continue

            try:
                result = await provider.fetch(request)
            except ProviderError as exc:
                breaker.record_failure()
                errors.append((name, exc))
                continue

            # Success path
            breaker.record_success()
            if self._event_sink is not None:
                await self._event_sink(result)
            return result

        raise AllProvidersFailedError(request.kind, errors)

    def get_breaker(self, provider_name: str) -> CircuitBreaker:
        """Expose breaker for inspection (e.g., health-check endpoints)."""
        return self._get_breaker(provider_name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_breaker(self, provider_name: str) -> CircuitBreaker:
        if provider_name not in self._breakers:
            self._breakers[provider_name] = self._breaker_factory()
        return self._breakers[provider_name]
