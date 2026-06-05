"""
DhanRadar — Market Data exceptions.

Isolated from auth/billing/scoring — no cross-module imports.
"""

from __future__ import annotations

from dhanradar.market_data.config import DataKind


class ProviderError(Exception):
    """
    A single provider rung in the ladder failed.

    Carries the provider name and the underlying cause so the adapter can
    log a per-rung failure before trying the next rung.
    """

    def __init__(self, provider: str, cause: str | Exception = "") -> None:
        self.provider = provider
        self.cause = cause
        super().__init__(f"Provider {provider!r} failed: {cause}")


class AllProvidersFailedError(Exception):
    """
    Every rung in the ladder for a given DataKind failed OR was skipped.

    ``errors`` is a list of (provider_name, ProviderError) pairs in ladder
    order for rungs that were TRIED and failed. ``skipped`` lists rungs that
    were not tried because their circuit breaker was OPEN — without it, a
    ladder where every breaker is open would raise with an empty ``errors``
    and no diagnostic (the caller couldn't tell "all tried & failed" from
    "none tried — all breakers open").
    """

    def __init__(
        self,
        kind: DataKind,
        errors: list[tuple[str, ProviderError]],
        skipped: list[str] | None = None,
    ) -> None:
        self.kind = kind
        self.errors = errors
        self.skipped = skipped or []
        providers = [name for name, _ in errors]
        super().__init__(
            f"All providers failed for kind={kind!r}. "
            f"Tried: {providers}. "
            f"Skipped (circuit open): {self.skipped}. "
            f"Errors: {[(n, str(e)) for n, e in errors]}"
        )
