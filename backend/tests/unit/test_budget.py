"""
Unit tests for dhanradar.budget.

Covers:
  - _next_utc_midnight_ts() returns a future Unix timestamp that is exactly UTC midnight.
  - Entering budget_guard("free") on a fresh Redis initialises the key with a TTL.
  - Exceeding the free cap raises BudgetExhaustedError before yielding.
  - Premium hard-cap exceeded raises BudgetExhaustedError.
  - budget_guard does NOT increment the counter on yield (stub behaviour for Phase 3).

No DB or HTTP needed. Uses the patch_redis fixture from conftest to wire fakeredis.
"""

from __future__ import annotations

import datetime

import pytest

# NOTE: do NOT apply `patch_redis` module-wide. The pure-sync tests below
# (_next_utc_midnight_ts / error-message) must not pull the async fakeredis
# fixture — a sync test driving an async fixture binds FakeRedis to a transient
# event loop and corrupts it for the later async tests (writes become invisible
# even though it is the same object). The async tests request `patch_redis`
# explicitly via their parameter list, which is the correct wiring.


# ---------------------------------------------------------------------------
# _next_utc_midnight_ts
# ---------------------------------------------------------------------------

def test_next_utc_midnight_is_in_the_future():
    from dhanradar.budget import _next_utc_midnight_ts

    ts = _next_utc_midnight_ts()
    now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    assert ts > now_ts, "Next UTC midnight must be in the future"


def test_next_utc_midnight_is_exactly_midnight():
    from dhanradar.budget import _next_utc_midnight_ts

    ts = _next_utc_midnight_ts()
    dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    assert dt.hour == 0, f"Expected hour=0 but got {dt.hour}"
    assert dt.minute == 0, f"Expected minute=0 but got {dt.minute}"
    assert dt.second == 0, f"Expected second=0 but got {dt.second}"
    assert dt.microsecond == 0


def test_next_utc_midnight_is_at_most_24h_away():
    from dhanradar.budget import _next_utc_midnight_ts

    ts = _next_utc_midnight_ts()
    now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    assert ts - now_ts <= 86400, "Next UTC midnight must be at most 24 hours away"


# ---------------------------------------------------------------------------
# budget_guard: key initialisation on first call
# ---------------------------------------------------------------------------

async def test_budget_guard_free_initialises_key(patch_redis):
    """
    On first entry, budget_guard("free") must create the Redis key with a TTL
    set to expire at next UTC midnight.
    """
    from dhanradar.budget import budget_guard, _REDIS_KEYS

    key = _REDIS_KEYS["free"]

    async with budget_guard("free"):
        pass  # Should not raise — fresh fakeredis has no count yet.

    # Key must exist after the context manager exits.
    val = await patch_redis.get(key)
    assert val is not None, "Redis key must exist after budget_guard entry"
    assert int(val) == 0, f"Expected counter=0 (stub Phase 3), got {val!r}"

    # TTL must be set (not -1 which means no TTL).
    ttl = await patch_redis.ttl(key)
    assert ttl > 0, f"Key must have a TTL; got {ttl}"


async def test_budget_guard_premium_initialises_key(patch_redis):
    """Same initialisation check for the premium budget."""
    from dhanradar.budget import budget_guard, _REDIS_KEYS

    key = _REDIS_KEYS["premium"]

    async with budget_guard("premium"):
        pass

    val = await patch_redis.get(key)
    assert val is not None
    ttl = await patch_redis.ttl(key)
    assert ttl > 0


async def test_budget_guard_free_does_not_increment_counter(patch_redis):
    """
    Phase 3 stub: budget_guard does NOT increment the counter post-yield.
    Counter must still be 0 after the context manager exits.
    """
    from dhanradar.budget import budget_guard, _REDIS_KEYS

    key = _REDIS_KEYS["free"]
    async with budget_guard("free"):
        pass

    val = await patch_redis.get(key)
    assert int(val) == 0, (
        "budget_guard is a Phase-3 stub and must NOT increment the counter. "
        f"Got {val!r}"
    )


# ---------------------------------------------------------------------------
# budget_guard: free cap exceeded raises BudgetExhaustedError
# ---------------------------------------------------------------------------

async def test_budget_guard_free_raises_when_cap_exceeded(patch_redis):
    """
    Pre-set the free counter to the cap value (1000). Entering budget_guard
    must raise BudgetExhaustedError before yielding.
    """
    from dhanradar.budget import budget_guard, BudgetExhaustedError, _REDIS_KEYS, _CAPS

    key = _REDIS_KEYS["free"]
    cap = int(_CAPS["free"])

    # Simulate a day where all 1000 free calls have been consumed.
    await patch_redis.set(key, str(cap))

    with pytest.raises(BudgetExhaustedError) as exc_info:
        async with budget_guard("free"):
            pytest.fail("Should not have yielded — cap exceeded")

    err = exc_info.value
    assert err.kind == "free"
    assert err.current >= cap
    assert err.cap == cap


async def test_budget_guard_free_at_cap_minus_one_does_not_raise(patch_redis):
    """One below the free cap must NOT raise."""
    from dhanradar.budget import budget_guard, _REDIS_KEYS, _CAPS

    key = _REDIS_KEYS["free"]
    cap = int(_CAPS["free"])

    await patch_redis.set(key, str(cap - 1))

    # Should not raise.
    async with budget_guard("free"):
        pass


# ---------------------------------------------------------------------------
# budget_guard: premium hard-cap exceeded raises BudgetExhaustedError
# ---------------------------------------------------------------------------

async def test_budget_guard_premium_raises_when_hard_cap_exceeded(patch_redis):
    """
    Set premium counter to >= 9.50 (hard cap). Must raise BudgetExhaustedError.
    """
    from dhanradar.budget import budget_guard, BudgetExhaustedError, _REDIS_KEYS, _CAPS

    key = _REDIS_KEYS["premium"]
    hard_cap = float(_CAPS["premium_hard"])

    await patch_redis.set(key, str(hard_cap))

    with pytest.raises(BudgetExhaustedError) as exc_info:
        async with budget_guard("premium"):
            pytest.fail("Should not have yielded — hard cap exceeded")

    err = exc_info.value
    assert err.kind == "premium"
    assert err.current >= hard_cap
    assert err.cap == hard_cap


async def test_budget_guard_premium_below_hard_cap_does_not_raise(patch_redis):
    """Just below the premium hard cap (9.49) must NOT raise."""
    from dhanradar.budget import budget_guard, _REDIS_KEYS, _CAPS

    key = _REDIS_KEYS["premium"]
    hard_cap = float(_CAPS["premium_hard"])

    await patch_redis.set(key, str(hard_cap - 0.01))

    async with budget_guard("premium"):
        pass


# ---------------------------------------------------------------------------
# BudgetExhaustedError message
# ---------------------------------------------------------------------------

def test_budget_exhausted_error_message():
    from dhanradar.budget import BudgetExhaustedError

    err = BudgetExhaustedError("free", 1000, 1000)
    msg = str(err)
    assert "free" in msg
    assert "1000" in msg
    assert "UTC midnight" in msg


# ---------------------------------------------------------------------------
# budget_guard: meter-based increment (Phase 3)
# ---------------------------------------------------------------------------

async def test_budget_guard_free_increments_by_meter_units(patch_redis):
    """Setting meter.units increments the free counter by that amount on clean exit."""
    from dhanradar.budget import budget_guard, _REDIS_KEYS

    key = _REDIS_KEYS["free"]
    async with budget_guard("free") as meter:
        meter.units = 1
    assert int(await patch_redis.get(key)) == 1


async def test_budget_guard_premium_increments_by_meter_cost(patch_redis):
    """Setting meter.cost_usd increments the premium counter by that USD amount."""
    from dhanradar.budget import budget_guard, _REDIS_KEYS

    key = _REDIS_KEYS["premium"]
    async with budget_guard("premium") as meter:
        meter.cost_usd = 0.0031
    assert abs(float(await patch_redis.get(key)) - 0.0031) < 1e-9


async def test_budget_guard_does_not_increment_on_exception(patch_redis):
    """A guarded block that raises consumes NO budget (increment only on clean exit)."""
    from dhanradar.budget import budget_guard, _REDIS_KEYS

    key = _REDIS_KEYS["free"]
    with pytest.raises(RuntimeError):
        async with budget_guard("free") as meter:
            meter.units = 1
            raise RuntimeError("boom")
    assert int(await patch_redis.get(key)) == 0
