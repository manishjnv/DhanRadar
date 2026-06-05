"""
DhanRadar — AI Gateway exceptions.

Distinct types so callers (and tests) can branch on the failure mode and so the
402-credit path is NEVER confused with a 429-retry path.
"""

from __future__ import annotations


class GatewayError(Exception):
    """Base class for all AI-gateway failures."""


class CreditExhaustedError(GatewayError):
    """OpenRouter returned HTTP 402 — account balance/credit is exhausted.

    This is an ALERT condition, NOT a retry condition. The gateway must surface
    it immediately (operator must top up); it must never be treated as a 429.
    """


class AllFreeModelsFailedError(GatewayError):
    """Every model in the free pool failed (rate-limited or produced no valid
    output) and the task was not eligible for premium spillover."""


class QualityValidationError(GatewayError):
    """An LLM response failed schema validation or contained banned advisory
    language. Triggers spillover (high-stakes) or the 3-strike skip."""

    def __init__(self, message: str, *, reasons: list[str] | None = None) -> None:
        super().__init__(message)
        self.reasons = reasons or []


class ThreeStrikeSkipError(GatewayError):
    """A non-high-stakes task hit the 3-strike-per-(ticker, day) skip — the
    gateway gives up for this ticker today rather than burn more budget."""

    def __init__(self, ticker: str, strikes: int) -> None:
        self.ticker = ticker
        self.strikes = strikes
        super().__init__(
            f"3-strike skip for ticker={ticker!r}: {strikes} consecutive quality "
            "failures today; skipping until next UTC day."
        )
