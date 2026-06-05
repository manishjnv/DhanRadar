"""
DhanRadar — OpenRouterGateway (architecture §B3).

The only place an LLM is called. Behaviour:

  * Free pool, round-robin. On 429 (RateLimitError) → rotate to the next model
    immediately (NO sleep). On 402 (credit exhausted) → raise CreditExhaustedError
    (alert; never retried as if it were a 429).
  * Every response is validated by QualityValidator (schema + advisory screen).
  * On a quality failure after the free pool is exhausted:
      - high-stakes task types → spill over to Claude Sonnet within the PREMIUM
        budget;
      - otherwise → 3-strike-per-(ticker, day) skip.
  * Budget is enforced INSIDE the gateway via budget_guard(); domain modules
    never see budget logic and never call a model directly.

Prompts/messages are passed IN by the caller (sourced from the Admin module's
versioned prompt templates) — this gateway hardcodes no prompts. Task→model
routing (TASK_MODEL_PREFERENCES) is injected for the same reason.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence

from openai import APIStatusError, RateLimitError

from dhanradar.ai_gateway.errors import (
    AllFreeModelsFailedError,
    CreditExhaustedError,
    QualityValidationError,
    ThreeStrikeSkipError,
)
from dhanradar.ai_gateway.quality import QualityValidator
from dhanradar.ai_gateway.schemas import AIOutputBase
from dhanradar.budget import budget_guard
from dhanradar.config import settings
from dhanradar.redis_client import get_redis

# High-stakes task types eligible for premium Sonnet spillover (architecture §B3).
HIGH_STAKES_TASKS: frozenset[str] = frozenset(
    {"mood_commentary", "earnings_summary", "stock_pick", "mf_pick"}
)

# Rough blended $/1M tokens for the Sonnet spillover — used only to debit the
# premium budget counter (soft $0.50 / hard $9.50); not a billing source of truth.
_SONNET_USD_PER_1M_TOKENS = 6.0
_STRIKE_LIMIT = 3


@dataclass
class _LLMResult:
    data: dict
    total_tokens: int


def _parse_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


class OpenRouterGateway:
    """Round-robin free-model gateway with Sonnet spillover and budget guard."""

    def __init__(
        self,
        *,
        client: Any = None,
        free_models: Optional[Sequence[str]] = None,
        sonnet_model: Optional[str] = None,
        high_stakes_tasks: Optional[Iterable[str]] = None,
        task_model_preferences: Optional[dict[str, list[str]]] = None,
        redis: Any = None,
    ) -> None:
        self._client = client  # injected (tests) or lazily built
        self._free_models = (
            list(free_models) if free_models is not None else _parse_csv(settings.AI_FREE_MODELS)
        )
        self._sonnet_model = sonnet_model or settings.AI_SONNET_MODEL
        self._high_stakes = frozenset(high_stakes_tasks) if high_stakes_tasks else HIGH_STAKES_TASKS
        # Task→model ordering (subset of the free pool), sourced from the Admin
        # module's prompt templates in production. Empty → use the full pool.
        self._task_prefs = task_model_preferences or {}
        self._redis = redis

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def complete(
        self,
        *,
        task_type: str,
        messages: list[dict[str, str]],
        schema: type[AIOutputBase],
        ticker: Optional[str] = None,
    ) -> AIOutputBase:
        """Return a validated AIOutputBase for ``task_type`` or raise.

        Raises CreditExhaustedError (402), ThreeStrikeSkipError, QualityValidationError,
        AllFreeModelsFailedError, or BudgetExhaustedError.
        """
        validator = QualityValidator(schema)
        models = self._models_for(task_type)
        last_quality_error: Optional[QualityValidationError] = None
        got_any_response = False

        # --- Free pool, round-robin, inside the free budget ---------------
        async with budget_guard("free") as meter:
            for model in models:
                try:
                    res = await self._call(model, messages)
                except RateLimitError:
                    continue  # 429 → rotate, NO sleep, no call billed
                except APIStatusError as exc:
                    if getattr(exc, "status_code", None) == 402:
                        raise CreditExhaustedError(
                            "OpenRouter returned 402 — AI credit exhausted; top up (do not retry)."
                        ) from exc
                    continue  # other upstream error → try next model
                except json.JSONDecodeError:
                    # The model returned (and billed) a non-JSON / empty body —
                    # it still consumes a free-quota unit.
                    meter.units += 1
                    last_quality_error = QualityValidationError("model returned non-JSON")
                    continue

                # A response was served → it consumes one free-quota unit whether
                # or not it passes validation (the free cap counts API calls, not
                # only usable ones — closes the under-count abuse vector).
                meter.units += 1
                got_any_response = True
                try:
                    result = validator.validate(res.data)
                except QualityValidationError as qe:
                    last_quality_error = qe
                    continue  # quality fail → try the next free model
                return result

        # --- Escalation: free pool produced no valid output ---------------
        if last_quality_error is not None and task_type in self._high_stakes:
            # Premium Sonnet spillover — but bound it with the SAME 3-strike skip
            # so a persistently-bad high-stakes ticker cannot loop premium spend.
            try:
                return await self._spillover_to_sonnet(messages, validator)
            except QualityValidationError:
                strikes = await self._record_strike(task_type, ticker)
                if strikes >= _STRIKE_LIMIT:
                    raise ThreeStrikeSkipError(ticker or task_type, strikes)
                raise

        if last_quality_error is not None:
            # Non-high-stakes quality failure → 3-strike-per-(ticker, day) skip.
            strikes = await self._record_strike(task_type, ticker)
            if strikes >= _STRIKE_LIMIT:
                raise ThreeStrikeSkipError(ticker or task_type, strikes)
            raise last_quality_error

        # No model produced any response at all (all rate-limited / empty pool).
        raise AllFreeModelsFailedError(
            f"no free model produced output for task={task_type!r} "
            f"(pool size={len(models)}, any_response={got_any_response})"
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _models_for(self, task_type: str) -> list[str]:
        return self._task_prefs.get(task_type) or self._free_models

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                base_url=settings.OPENROUTER_BASE_URL,
                api_key=settings.OPENROUTER_API_KEY,
            )
        return self._client

    async def _call(self, model: str, messages: list[dict[str, str]]) -> _LLMResult:
        """One LLM call. Raises RateLimitError/APIStatusError (handled upstream)
        or json.JSONDecodeError if the content is not JSON."""
        client = self._get_client()
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        # Empty choices (e.g. content-filtered) → treat as a malformed response,
        # not an unhandled IndexError that would bypass the gateway taxonomy.
        if not getattr(resp, "choices", None):
            raise json.JSONDecodeError("empty choices from model", "", 0)
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)  # may raise JSONDecodeError
        usage = getattr(resp, "usage", None)
        total = int(getattr(usage, "total_tokens", 0) or 0)
        return _LLMResult(data=data, total_tokens=total)

    async def _spillover_to_sonnet(
        self, messages: list[dict[str, str]], validator: QualityValidator
    ) -> AIOutputBase:
        """Premium Sonnet spillover. Records the (charged) cost even if the
        response then fails validation — Sonnet bills on response, so the budget
        is debited as soon as we get one; validation runs AFTER the budgeted
        block so a quality failure still propagates with the spend recorded."""
        async with budget_guard("premium") as meter:
            try:
                res = await self._call(self._sonnet_model, messages)
            except APIStatusError as exc:
                if getattr(exc, "status_code", None) == 402:
                    raise CreditExhaustedError(
                        "OpenRouter returned 402 on Sonnet spillover — premium credit exhausted."
                    ) from exc
                raise
            meter.cost_usd = (res.total_tokens / 1_000_000) * _SONNET_USD_PER_1M_TOKENS
        return validator.validate(res.data)  # raises QualityValidationError if Sonnet also fails

    async def _record_strike(self, task_type: str, ticker: Optional[str]) -> int:
        """Increment and return the 3-strike-per-(ticker, day) counter."""
        redis = self._redis or get_redis()
        day = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
        key = f"ai:strike:{ticker or task_type}:{day}"
        strikes = int(await redis.incr(key))
        if strikes == 1:
            # Expire at next UTC midnight (daily reset of the strike window).
            now = datetime.datetime.now(datetime.timezone.utc)
            midnight = (now + datetime.timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            await redis.expireat(key, int(midnight.timestamp()))
        return strikes
