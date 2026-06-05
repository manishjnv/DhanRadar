"""
DhanRadar — AI budget guard.

Manages per-day Redis counters for free and premium AI spend.
Keys expire at UTC midnight to reset daily.

IMPORTANT — OpenRouter error semantics:
    HTTP 402 = balance/credit exhausted → ALERT the team, do NOT retry.
    HTTP 429 = rate-limited            → rotate key / back-off and retry.
    Never treat a 402 as a transient retry condition.
"""

from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Literal

import redis.asyncio as aioredis

from dhanradar.redis_client import get_redis

# ---------------------------------------------------------------------------
# Budget kinds and caps
# ---------------------------------------------------------------------------
BudgetKind = Literal["free", "premium"]

_CAPS: dict[str, int | float] = {
    "free": 1000,          # integer call count cap
    "premium_soft": 0.50,  # USD — warn threshold (Phase 3 TODO: emit metric)
    "premium_hard": 9.50,  # USD — hard stop
}

_REDIS_KEYS: dict[str, str] = {
    "free": "ai:budget:free:today",
    "premium": "ai:budget:premium:today",
}


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------
class BudgetExhaustedError(Exception):
    """Raised before yielding when the per-day AI budget cap is exceeded."""

    def __init__(self, kind: BudgetKind, current: int | float, cap: int | float) -> None:
        self.kind = kind
        self.current = current
        self.cap = cap
        super().__init__(
            f"AI budget exhausted for kind={kind!r}: current={current} >= cap={cap}. "
            "Resets at next UTC midnight."
        )


class BudgetMeter:
    """Records the spend of one guarded AI operation.

    The caller sets the actuals ONLY on success; on failure it leaves them at
    zero so a rate-limited / errored attempt does not consume the daily budget.

      - free:    ``units``    — integer call count (default 0; gateway sets 1).
      - premium: ``cost_usd`` — float USD cost   (default 0.0; gateway sets it).

    Defaulting to zero keeps ``budget_guard`` backward-compatible: a caller that
    records nothing increments nothing.
    """

    __slots__ = ("units", "cost_usd")

    def __init__(self) -> None:
        self.units: int = 0
        self.cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _next_utc_midnight_ts() -> int:
    """Return the Unix timestamp of the next UTC midnight (as integer seconds)."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    next_midnight = (now_utc + datetime.timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return int(next_midnight.timestamp())


async def _init_key_if_missing(redis: aioredis.Redis, key: str, initial: str = "0") -> None:
    """SET key initial EX (seconds until next midnight) only if the key does not exist."""
    exists = await redis.exists(key)
    if not exists:
        await redis.set(key, initial)
        await redis.expireat(key, _next_utc_midnight_ts())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
@asynccontextmanager
async def budget_guard(kind: BudgetKind) -> AsyncGenerator[BudgetMeter, None]:
    """
    Async context manager that enforces per-day AI budget caps and records spend.

    Usage::

        async with budget_guard("free") as meter:
            response = await call_openrouter_free_model(...)
            meter.units = 1            # one successful free call

        async with budget_guard("premium") as meter:
            response = await call_sonnet(...)
            meter.cost_usd = 0.0031    # actual USD cost

    Behaviour:
      - Raises BudgetExhaustedError BEFORE yielding if the cap is already met
        (free: call-count cap; premium: USD hard cap). The premium SOFT cap is a
        warn threshold, not a stop (logged by callers/metrics).
      - On first call of the day the Redis key is initialised to 0 with EXPIREAT
        at the next UTC midnight (daily reset).
      - On CLEAN exit, increments the counter by what the caller recorded on the
        meter (free → INCRBY units; premium → INCRBYFLOAT cost_usd). Defaults are
        zero, so an attempt that raised (e.g. 429/402) consumes nothing — the
        increment only runs on the no-exception path.
    """
    redis = get_redis()
    key = _REDIS_KEYS[kind]

    await _init_key_if_missing(redis, key, initial="0")

    raw = await redis.get(key)
    current: int | float

    if kind == "free":
        current = int(raw or 0)
        cap: int | float = _CAPS["free"]
        if current >= cap:
            raise BudgetExhaustedError(kind, current, cap)
    else:
        # premium: check hard cap (float USD)
        current = float(raw or 0.0)
        hard_cap = _CAPS["premium_hard"]
        if current >= hard_cap:
            raise BudgetExhaustedError(kind, current, hard_cap)

    meter = BudgetMeter()
    yield meter

    # Reached only when the guarded block did NOT raise — record actual spend.
    if kind == "free":
        if meter.units:
            await redis.incrby(key, int(meter.units))
    else:
        if meter.cost_usd:
            await redis.incrbyfloat(key, float(meter.cost_usd))
