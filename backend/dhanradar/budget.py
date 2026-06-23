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
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Literal

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

# Redis keys used by the admin cap-override endpoint (POST /admin/ai/cost/caps).
# When present, these override the _CAPS hardcoded defaults without a redeploy.
# When absent / malformed, budget_guard falls back to _CAPS silently.
_CAP_OVERRIDE_KEYS: dict[str, str] = {
    "free": "ai:budget:cap:free",
    "premium_soft": "ai:budget:cap:premium_soft",
    "premium_hard": "ai:budget:cap:premium_hard",
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
    now_utc = datetime.datetime.now(datetime.UTC)
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
# Effective cap resolution (Phase 5 admin override support)
# ---------------------------------------------------------------------------


async def get_effective_caps(redis: aioredis.Redis) -> dict[str, int | float]:
    """Return the effective AI budget caps, honouring any admin Redis overrides.

    Reads the three admin override keys (``ai:budget:cap:{free,premium_soft,
    premium_hard}``).  On key miss OR any parse / Redis error, falls back to
    the corresponding ``_CAPS`` hardcoded default.  NEVER raises — any failure
    degrades silently to the hardcoded default so the hot path is never broken
    by a bad Redis state or a transient connection error.

    Returns dict with keys: ``free`` (int), ``premium_soft`` (float),
    ``premium_hard`` (float).
    """
    result: dict[str, int | float] = {
        "free": int(_CAPS["free"]),
        "premium_soft": float(_CAPS["premium_soft"]),
        "premium_hard": float(_CAPS["premium_hard"]),
    }
    for cap_name, redis_key in _CAP_OVERRIDE_KEYS.items():
        try:
            raw = await redis.get(redis_key)
            if raw is None:
                continue  # no override set — keep default
            raw_str = raw.decode() if isinstance(raw, bytes) else str(raw)
            if cap_name == "free":
                parsed: int | float = int(float(raw_str))
            else:
                parsed = float(raw_str)
            if parsed <= 0:
                # Sanity guard: a zero/negative cap would block all AI calls
                # immediately; treat as a misconfigured override and fall back.
                logger.warning(
                    "AI cap override for %r is non-positive (value=%s) — "
                    "ignoring and using hardcoded default.",
                    cap_name,
                    raw_str,
                )
                continue
            result[cap_name] = parsed
        except Exception:  # noqa: BLE001 — failure → fallback, never raise
            logger.warning(
                "AI cap override read failed for key=%r — using hardcoded default.",
                redis_key,
                exc_info=True,
            )
    return result


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
    # Resolve caps from admin Redis override keys; any failure falls back to
    # _CAPS defaults (get_effective_caps is defensive and never raises).
    effective = await get_effective_caps(redis)
    cap: int | float = effective["free"] if kind == "free" else effective["premium_hard"]
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
        # Use the admin-override value if set; effective was resolved above.
        soft_cap = float(effective["premium_soft"])
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


# ---------------------------------------------------------------------------
# Read-only budget snapshot for admin monitoring (Phase 4 AI Ops console)
# ---------------------------------------------------------------------------


def get_budget_state(redis_client) -> dict:  # type: ignore[type-arg]
    """Synchronous read-only budget snapshot for the Admin AI Ops console.

    Reads both Redis daily counters and returns the current spend + cap info.
    Tolerates a Redis miss (key not yet initialised → returns 0).

    This is intentionally synchronous so it can be called from within an async
    endpoint via ``await asyncio.to_thread(get_budget_state, redis_client)`` or
    directly from a regular context. The admin endpoint calls it inside the
    async path using the async redis client's ``get`` method — see
    ``aiops_router.py`` for the await pattern.

    Returns a dict with keys:
        free_calls_today     : int   — calls consumed today
        free_cap             : int   — daily hard cap (from _CAPS["free"])
        premium_usd_today    : float — USD spent today
        premium_soft_cap     : float — soft warning threshold
        premium_hard_cap     : float — hard stop cap
        free_remaining       : int   — remaining calls
        premium_remaining_usd: float — remaining premium budget (vs hard cap)
    """
    # NOTE: callers in the async aiops_router use ``await redis.get(key)``
    # directly for the two reads, then pass the raw values here.  This function
    # is therefore a pure computation helper, not an I/O function.
    raise NotImplementedError(
        "get_budget_state is a helper contract; use get_budget_state_from_values() "
        "with pre-fetched Redis values, or call the async helper in aiops_router."
    )


def _decode_counter(raw: bytes | str | None) -> str:
    """Normalise a raw Redis counter to a numeric string.

    The shared client runs with ``decode_responses=True`` so ``redis.get`` returns
    ``str`` in production, but unit tests (and a client without decode) pass
    ``bytes``. Accept both (and None → "0") so the snapshot never crashes on the
    type the real client actually returns. Mirrors the existing guard at
    ``get_effective_caps`` (``raw.decode() if isinstance(raw, bytes) else ...``).
    """
    if not raw:
        return "0"
    return raw.decode() if isinstance(raw, bytes) else str(raw)


def compute_budget_state(
    free_raw: bytes | str | None,
    premium_raw: bytes | str | None,
    *,
    free_cap: int | None = None,
    premium_soft: float | None = None,
    premium_hard: float | None = None,
) -> dict:
    """Pure computation: derive the budget snapshot from raw Redis counter values.

    Separated from I/O so it is trivially unit-testable without a Redis instance.

    Args:
        free_raw:     raw value from ``redis.get(_REDIS_KEYS["free"])`` — ``str``
                      under decode_responses (prod) or ``bytes``; None if key absent.
        premium_raw:  raw value from ``redis.get(_REDIS_KEYS["premium"])`` — ``str``
                      or ``bytes``; None if key absent.
        free_cap:     optional override for the free call-count cap (from admin Redis key).
                      Defaults to ``_CAPS["free"]``.
        premium_soft: optional override for the premium soft-cap USD (from admin Redis key).
                      Defaults to ``_CAPS["premium_soft"]``.
        premium_hard: optional override for the premium hard-cap USD (from admin Redis key).
                      Defaults to ``_CAPS["premium_hard"]``.

    Returns:
        dict with the same shape as the docstring above (for get_budget_state).

    Backward-compatible: existing callers that pass no kwargs receive the hardcoded defaults.
    """
    _free_cap: int = int(free_cap) if free_cap is not None else int(_CAPS["free"])
    _premium_soft_cap: float = float(premium_soft) if premium_soft is not None else float(_CAPS["premium_soft"])
    _premium_hard_cap: float = float(premium_hard) if premium_hard is not None else float(_CAPS["premium_hard"])

    free_calls_today: int = int(float(_decode_counter(free_raw)))
    premium_usd_today: float = round(float(_decode_counter(premium_raw)), 6)

    return {
        "free_calls_today": free_calls_today,
        "free_cap": _free_cap,
        "premium_usd_today": premium_usd_today,
        "premium_soft_cap": _premium_soft_cap,
        "premium_hard_cap": _premium_hard_cap,
        "free_remaining": max(0, _free_cap - free_calls_today),
        "premium_remaining_usd": round(max(0.0, _premium_hard_cap - premium_usd_today), 6),
    }
