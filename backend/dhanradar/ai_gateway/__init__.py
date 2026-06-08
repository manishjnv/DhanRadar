"""
DhanRadar — AI / LLM Gateway (Phase 3, architecture §B3).

The single seam through which any module obtains LLM output. Domain modules call
``OpenRouterGateway.complete(...)`` and never touch a model, a budget counter, or
a prompt-template directly. Every output is validated by ``QualityValidator``
against a Pydantic schema extending ``AIOutputBase`` (non-advisory, signal-backed,
confidence-banded) and carries the SEBI disclaimer.

Public surface:
  - OpenRouterGateway      — round-robin free pool → Sonnet spillover / 3-strike skip
  - AIOutputBase           — the non-advisory output contract (see §S)
  - QualityValidator       — schema + advisory-language screening
  - AI_DISCLAIMER          — the mandatory "not investment advice" label
  - errors                 — CreditExhaustedError / ThreeStrikeSkipError / etc.
"""

from __future__ import annotations

from dhanradar.ai_gateway.errors import (
    AllFreeModelsFailedError,
    ConsentNotVerifiedError,
    CreditExhaustedError,
    GatewayError,
    QualityValidationError,
    ThreeStrikeSkipError,
)
from dhanradar.ai_gateway.gateway import CompletionResult, OpenRouterGateway
from dhanradar.ai_gateway.quality import QualityValidator
from dhanradar.ai_gateway.schemas import AI_DISCLAIMER, AIOutputBase, ConfidenceBand

__all__ = [
    "CompletionResult",
    "OpenRouterGateway",
    "CompletionResult",
    "AIOutputBase",
    "ConfidenceBand",
    "AI_DISCLAIMER",
    "QualityValidator",
    "GatewayError",
    "ConsentNotVerifiedError",
    "CreditExhaustedError",
    "ThreeStrikeSkipError",
    "AllFreeModelsFailedError",
    "QualityValidationError",
]
