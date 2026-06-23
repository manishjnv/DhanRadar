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
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from openai import APIStatusError, RateLimitError
from structlog.contextvars import bind_contextvars

from dhanradar.ai_gateway.errors import (
    AllFreeModelsFailedError,
    ConsentNotVerifiedError,
    CreditExhaustedError,
    QualityValidationError,
    ThreeStrikeSkipError,
)
from dhanradar.ai_gateway.metrics import record_latency, record_model_spend
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
    model: str


@dataclass(frozen=True)
class CompletionResult:
    """Returned by ``OpenRouterGateway.complete()``: the validated output and the
    model that served it (needed by audit/compliance consumers — B21)."""

    output: AIOutputBase
    model_used: str


def _parse_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


class OpenRouterGateway:
    """Round-robin free-model gateway with Sonnet spillover and budget guard."""

    def __init__(
        self,
        *,
        client: Any = None,
        free_models: Sequence[str] | None = None,
        sonnet_model: str | None = None,
        high_stakes_tasks: Iterable[str] | None = None,
        task_model_preferences: dict[str, list[str]] | None = None,
        paid_fallback_models: Sequence[str] | None = None,
        paid_fallback_tasks: Iterable[str] | None = None,
        redis: Any = None,
    ) -> None:
        self._client = client  # injected (tests) or lazily built
        self._free_models = (
            list(free_models) if free_models is not None else _parse_csv(settings.AI_FREE_MODELS)
        )
        self._sonnet_model = sonnet_model or settings.AI_SONNET_MODEL
        self._high_stakes = frozenset(high_stakes_tasks) if high_stakes_tasks else HIGH_STAKES_TASKS
        # Cheap NON-premium paid fallback (non-Claude) for the listed low-volume tasks.
        self._paid_fallback_models = (
            list(paid_fallback_models)
            if paid_fallback_models is not None
            else _parse_csv(settings.AI_PAID_FALLBACK_MODELS)
        )
        self._paid_fallback_tasks = (
            frozenset(paid_fallback_tasks)
            if paid_fallback_tasks is not None
            else frozenset(_parse_csv(settings.AI_PAID_FALLBACK_TASKS))
        )
        self._paid_fallback_usd_per_1m = settings.AI_PAID_FALLBACK_USD_PER_1M
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
        ticker: str | None = None,
        contains_personal_data: bool = True,
        cross_border_consent_verified: bool = False,
        request_id: str | None = None,
    ) -> CompletionResult:
        """Return a ``CompletionResult`` for ``task_type`` or raise.

        Args:
            task_type: Routing key used to select the model pool.
            messages: Prompt messages sourced from the Admin module's versioned
                prompt templates.
            schema: Pydantic schema (subclass of AIOutputBase) for validation.
            ticker: Optional ticker symbol; used for 3-strike-per-(ticker, day)
                tracking.
            contains_personal_data: Set to ``False`` only for anonymous /
                aggregate calls (e.g. public market data, Mood Compass) that carry
                no user PII. Defaults to ``True`` (fail-closed). When ``True``,
                ``cross_border_consent_verified`` must also be ``True`` or this
                method raises ``ConsentNotVerifiedError`` before any payload
                reaches OpenRouter.
            cross_border_consent_verified: Must be ``True`` when
                ``contains_personal_data=True``. The call site is responsible for
                calling ``assert_consent(user_id, "cross_border_ai", db)``
                (deps.py) before invoking the gateway; the gateway is
                module-isolated and cannot read consent itself.
            request_id: Correlation id threaded from the originating HTTP request;
                bound into the gateway's log context and forwarded to audit/ledger
                writes (P1 logging).

        Raises:
            ConsentNotVerifiedError: if ``contains_personal_data=True`` and
                ``cross_border_consent_verified=False`` (default-deny, B20).
            CreditExhaustedError: OpenRouter returned HTTP 402.
            ThreeStrikeSkipError: 3 consecutive quality failures for this
                ticker/day.
            QualityValidationError: LLM response failed schema or advisory screen.
            AllFreeModelsFailedError: every free model was rate-limited.
            BudgetExhaustedError: daily budget cap reached.
        """
        # B20 — cross-border DPDP defense-in-depth (default-deny). A payload that
        # carries user personal data must have had cross_border_ai consent verified
        # at the call site (assert_consent); the gateway is module-isolated and
        # cannot read consent itself. Refuse BEFORE any payload reaches OpenRouter.
        if contains_personal_data and not cross_border_consent_verified:
            raise ConsentNotVerifiedError("cross_border_ai")

        # Bind the correlation id into the structlog context so every log line
        # emitted inside this call (budget guard, quality validator, spillover)
        # carries the originating request id without callers threading it manually.
        if request_id is not None:
            bind_contextvars(request_id=request_id)

        validator = QualityValidator(schema)
        models = self._models_for(task_type)
        last_quality_error: QualityValidationError | None = None
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
                return CompletionResult(output=result, model_used=model)

        # --- Cheap paid fallback for configured low-volume tasks ----------
        # (e.g. mood news-sentiment / commentary). Runs when the free pool yields
        # nothing usable — all rate-limited OR responded-but-failed-quality — and
        # retries on a cheap NON-premium, non-Claude paid model under the premium
        # USD cap, so the signal survives free-tier 429 weather without premium
        # spend. These tasks are OWNED by this fallback: they skip the Sonnet
        # spillover below. On no usable output it returns None and we fall through.
        if task_type in self._paid_fallback_tasks and self._paid_fallback_models:
            fb = await self._paid_fallback(messages, validator)
            if fb is not None:
                return fb

        # --- Escalation: free pool produced no valid output ---------------
        if (
            last_quality_error is not None
            and task_type in self._high_stakes
            and task_type not in self._paid_fallback_tasks
        ):
            # Premium Sonnet spillover — but bound it with the SAME 3-strike skip
            # so a persistently-bad high-stakes ticker cannot loop premium spend.
            try:
                return await self._spillover_to_sonnet(messages, validator)  # returns CompletionResult
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
        started = time.monotonic()
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        # Record the wall-clock latency of this served response (non-fatal). A
        # rate-limited / 402 call raises inside create() above and never reaches
        # here, so only genuine model responses are timed. record_latency NEVER
        # raises — an observational metric must not break an AI call.
        await record_latency((time.monotonic() - started) * 1000.0, redis=self._redis)
        # Record one billed call against this model (non-fatal). USD is recorded
        # separately at the paid/sonnet sites (calls=0 there) so the per-model
        # call tally is counted exactly once, here, for every served response.
        await record_model_spend(model, calls=1, redis=self._redis)
        # Empty choices (e.g. content-filtered) → treat as a malformed response,
        # not an unhandled IndexError that would bypass the gateway taxonomy.
        if not getattr(resp, "choices", None):
            raise json.JSONDecodeError("empty choices from model", "", 0)
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)  # may raise JSONDecodeError
        usage = getattr(resp, "usage", None)
        total = int(getattr(usage, "total_tokens", 0) or 0)
        return _LLMResult(data=data, total_tokens=total, model=model)

    async def _spillover_to_sonnet(
        self, messages: list[dict[str, str]], validator: QualityValidator
    ) -> CompletionResult:
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
        # Per-model USD for the sonnet spend (call already tallied in _call).
        await record_model_spend(res.model, usd=meter.cost_usd, redis=self._redis)
        output = validator.validate(res.data)  # raises QualityValidationError if Sonnet also fails
        # Audit the model that actually served (res.model == self._sonnet_model here,
        # but use the threaded field so provenance stays symmetric with the free pool).
        return CompletionResult(output=output, model_used=res.model)

    async def _paid_fallback(
        self, messages: list[dict[str, str]], validator: QualityValidator
    ) -> CompletionResult | None:
        """Cheap NON-premium, non-Claude paid-model fallback for low-volume tasks.

        Tries each configured model in order under the PREMIUM USD budget cap and
        returns the first schema-valid, advisory-clean result. Returns None when no
        model produced usable output (429 / upstream error / non-JSON / quality
        fail) — the caller then falls through to the standard error handling. 402
        (credit exhausted) propagates as CreditExhaustedError; the premium hard cap
        raises BudgetExhaustedError before any call. Cost is debited even for a
        response that then fails validation (the model billed on response)."""
        async with budget_guard("premium") as meter:
            for model in self._paid_fallback_models:
                try:
                    res = await self._call(model, messages)
                except RateLimitError:
                    continue  # 429 → try the next fallback model
                except APIStatusError as exc:
                    if getattr(exc, "status_code", None) == 402:
                        raise CreditExhaustedError(
                            "OpenRouter returned 402 on paid fallback — credit exhausted; top up."
                        ) from exc
                    continue  # other upstream error → try next model
                except json.JSONDecodeError:
                    continue  # billed but unusable → try next model
                call_usd = (res.total_tokens / 1_000_000) * self._paid_fallback_usd_per_1m
                meter.cost_usd += call_usd
                # Per-model USD for this paid response (call already tallied in _call).
                await record_model_spend(res.model, usd=call_usd, redis=self._redis)
                try:
                    output = validator.validate(res.data)
                except QualityValidationError:
                    continue  # quality fail → try the next fallback model
                return CompletionResult(output=output, model_used=res.model)
        return None

    async def _record_strike(self, task_type: str, ticker: str | None) -> int:
        """Increment and return the 3-strike-per-(ticker, day) counter."""
        redis = self._redis or get_redis()
        day = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d")
        key = f"ai:strike:{ticker or task_type}:{day}"
        strikes = int(await redis.incr(key))
        if strikes == 1:
            # Expire at next UTC midnight (daily reset of the strike window).
            now = datetime.datetime.now(datetime.UTC)
            midnight = (now + datetime.timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            await redis.expireat(key, int(midnight.timestamp()))
        return strikes
