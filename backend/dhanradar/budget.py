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
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Literal

import redis.asyncio as aioredis

from dhanradar.redis_client import get_redis

logger = logging.getLogger(__name__)

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

# Per-call reservation amounts used by the atomic admission (B18).
#
# The premium reserve is a CONSERVATIVE UPPER BOUND on the cost of one Sonnet
# spillover call (≈ $6/1M blended × ~33k tokens). It MUST be ≥ the largest
# plausible single-call cost: the concurrency guarantee is that admitting one
# call pushes the counter from "just under the cap" to "at/over the cap" so the
# next concurrent caller is rejected — that only holds if the reservation is big
# enough to cross the boundary. The reservation is reconciled down to the actual
# cost on clean exit, so over-reserving only briefly (and safely) over-accounts.
_PREMIUM_RESERVE_USD = 0.20

_DEFAULT_RESERVE: dict[str, float] = {
    "free": 1.0,           # one free-quota unit (count cap; money-safe residual)
    "premium": _PREMIUM_RESERVE_USD,
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
    """Atomically create the key=initial with an EXPIREAT at next UTC midnight,
    only if it does not exist (SET ... EXAT NX in one round-trip).

    The previous EXISTS-then-SET-then-EXPIREAT sequence had a crash window that
    could leave the key with no TTL (then it would accumulate across days and the
    daily cap would never reset). A single NX+EXAT set closes that window."""
    await redis.set(key, initial, exat=_next_utc_midnight_ts(), nx=True)


async def _adjust_quietly(
    redis: aioredis.Redis, key: str, amount: float, *, reason: str
) -> None:
    """Best-effort counter adjustment used to RELEASE a reservation (on reject /
    on a failed call) or RECONCILE it to actual spend (on clean exit).

    A Redis failure here must NOT mask the caller's real outcome — the
    BudgetExhaustedError on rejection, the guarded block's own exception on
    failure, or a successful result on reconcile. The daily EXPIREAT is the
    backstop (a leaked reservation self-heals at UTC midnight), so we swallow the
    error and log it loudly enough that a leak is observable. ``CancelledError``
    and ``KeyboardInterrupt`` (BaseException, not Exception) are deliberately NOT
    swallowed."""
    try:
        await redis.incrbyfloat(key, amount)
    except Exception:  # noqa: BLE001 — see docstring: must not mask the real outcome
        logger.error(
            "AI budget %s failed (key=%s, amount=%.6f) — the daily reservation may be "
            "briefly inflated until the UTC-midnight reset; remaining budget may read "
            "low until then.",
            reason,
            key,
            amount,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
@asynccontextmanager
async def budget_guard(
    kind: BudgetKind, *, reserve: int | float | None = None
) -> AsyncGenerator[BudgetMeter, None]:
    """
    Async context manager that enforces per-day AI budget caps and records spend.

    Usage::

        async with budget_guard("free") as meter:
            response = await call_openrouter_free_model(...)
            meter.units = 1            # one successful free call

        async with budget_guard("premium") as meter:
            response = await call_sonnet(...)
            meter.cost_usd = 0.0031    # actual USD cost

    Behaviour (B18 — atomic admission, no check-then-act race):
      - Admission is **incr-then-rollback**: the per-call ``reserve`` is added to
        the counter with an atomic ``INCRBYFLOAT`` FIRST, then we admit only if
        the value that existed BEFORE our reservation was under the cap. Because
        ``INCRBYFLOAT`` is atomic, concurrent callers observe each other's
        reservations and cannot all pass the cap check — at most one call can be
        admitted past the boundary (the irreducible single-call cost), so the
        premium $ hard-cap can no longer be overshot by N concurrent spillovers.
      - On rejection the reservation is released (so a rejected call never leaves
        the counter permanently inflated) and BudgetExhaustedError is raised
        before yielding. The premium SOFT cap is a warn threshold, not a stop.
      - On first call of the day the Redis key is initialised to 0 with EXPIREAT
        at the next UTC midnight (daily reset); INCRBYFLOAT preserves the TTL.
      - On CLEAN exit the reservation is **reconciled** to what the caller
        actually recorded on the meter (free → units; premium → cost_usd). On an
        EXCEPTION the full reservation is rolled back, so an attempt that raised
        (e.g. 429/402) consumes nothing.
    """
    redis = get_redis()
    key = _REDIS_KEYS[kind]
    cap: int | float = _CAPS["free"] if kind == "free" else _CAPS["premium_hard"]
    reserve_amt = float(reserve if reserve is not None else _DEFAULT_RESERVE[kind])

    # Ensure the key exists with a daily-reset TTL, then reserve atomically.
    await _init_key_if_missing(redis, key, initial="0")
    value_after = float(await redis.incrbyfloat(key, reserve_amt))
    current = value_after - reserve_amt  # the counter as it was BEFORE our reserve

    if current >= cap:
        # Already at/over cap before this call — release our reservation so the
        # counter settles back at the true value (a rejected call must not inflate
        # the counter and permanently wedge the budget). Best-effort: a Redis
        # failure on the release must not mask the BudgetExhaustedError.
        await _adjust_quietly(redis, key, -reserve_amt, reason="reservation-release(reject)")
        raise BudgetExhaustedError(kind, current, cap)

    if kind == "premium":
        # Soft cap is a WARN threshold (observability), not a stop.
        soft_cap = float(_CAPS["premium_soft"])
        if current >= soft_cap:
            logger.warning(
                "AI premium budget soft cap crossed: current=$%.4f >= soft=$%.2f "
                "(hard=$%.2f). Resets at next UTC midnight.",
                current,
                soft_cap,
                float(cap),
            )

    meter = BudgetMeter()
    try:
        yield meter
    except BaseException:
        # The guarded call failed — consume nothing: release the reservation.
        # Best-effort so the original (guarded) exception propagates unmasked.
        await _adjust_quietly(redis, key, -reserve_amt, reason="reservation-release(error)")
        raise

    # Clean exit — reconcile the reservation to the actual recorded spend.
    actual = float(meter.units) if kind == "free" else float(meter.cost_usd)

    # Observability: the concurrency guarantee only holds while the per-call
    # reserve is an upper bound on the actual cost. If a premium call cost more
    # than we reserved, the hard-cap's concurrency safety was weakened for this
    # call — surface it so _PREMIUM_RESERVE_USD can be raised.
    if kind == "premium" and actual > reserve_amt:
        logger.warning(
            "AI premium call cost $%.4f exceeded the per-call reserve $%.4f — raise "
            "_PREMIUM_RESERVE_USD; concurrent hard-cap safety is weakened above the reserve.",
            actual,
            reserve_amt,
        )

    delta = actual - reserve_amt
    if delta != 0:
        await _adjust_quietly(redis, key, delta, reason="reservation-reconcile")
