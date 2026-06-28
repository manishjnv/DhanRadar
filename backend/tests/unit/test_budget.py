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
    now_ts = int(datetime.datetime.now(datetime.UTC).timestamp())
    assert ts > now_ts, "Next UTC midnight must be in the future"


def test_next_utc_midnight_is_exactly_midnight():
    from dhanradar.budget import _next_utc_midnight_ts

    ts = _next_utc_midnight_ts()
    dt = datetime.datetime.fromtimestamp(ts, tz=datetime.UTC)
    assert dt.hour == 0, f"Expected hour=0 but got {dt.hour}"
    assert dt.minute == 0, f"Expected minute=0 but got {dt.minute}"
    assert dt.second == 0, f"Expected second=0 but got {dt.second}"
    assert dt.microsecond == 0


def test_next_utc_midnight_is_at_most_24h_away():
    from dhanradar.budget import _next_utc_midnight_ts

    ts = _next_utc_midnight_ts()
    now_ts = int(datetime.datetime.now(datetime.UTC).timestamp())
    assert ts - now_ts <= 86400, "Next UTC midnight must be at most 24 hours away"


# ---------------------------------------------------------------------------
# budget_guard: key initialisation on first call
# ---------------------------------------------------------------------------

async def test_budget_guard_free_initialises_key(patch_redis):
    """
    On first entry, budget_guard("free") must create the Redis key with a TTL
    set to expire at next UTC midnight.
    """
    from dhanradar.budget import _REDIS_KEYS, budget_guard

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
    from dhanradar.budget import _REDIS_KEYS, budget_guard

    key = _REDIS_KEYS["premium"]

    async with budget_guard("premium"):
        pass

    val = await patch_redis.get(key)
    assert val is not None
    ttl = await patch_redis.ttl(key)
    assert ttl > 0


async def test_budget_guard_free_does_not_increment_counter(patch_redis):
    """
    A guarded block that records nothing on the meter (units=0) must leave the
    counter at 0: the up-front reservation is fully reconciled away on clean exit.
    """
    from dhanradar.budget import _REDIS_KEYS, budget_guard

    key = _REDIS_KEYS["free"]
    async with budget_guard("free"):
        pass

    val = await patch_redis.get(key)
    assert int(float(val)) == 0, (
        "A block that records nothing must reconcile the reservation back to 0. "
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
    from dhanradar.budget import _CAPS, _REDIS_KEYS, BudgetExhaustedError, budget_guard

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
    from dhanradar.budget import _CAPS, _REDIS_KEYS, budget_guard

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
    from dhanradar.budget import _CAPS, _REDIS_KEYS, BudgetExhaustedError, budget_guard

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
    from dhanradar.budget import _CAPS, _REDIS_KEYS, budget_guard

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
    from dhanradar.budget import _REDIS_KEYS, budget_guard

    key = _REDIS_KEYS["free"]
    async with budget_guard("free") as meter:
        meter.units = 1
    assert int(await patch_redis.get(key)) == 1


async def test_budget_guard_premium_increments_by_meter_cost(patch_redis):
    """Setting meter.cost_usd increments the premium counter by that USD amount."""
    from dhanradar.budget import _REDIS_KEYS, budget_guard

    key = _REDIS_KEYS["premium"]
    async with budget_guard("premium") as meter:
        meter.cost_usd = 0.0031
    assert abs(float(await patch_redis.get(key)) - 0.0031) < 1e-9


async def test_budget_guard_does_not_increment_on_exception(patch_redis):
    """A guarded block that raises consumes NO budget (increment only on clean exit)."""
    from dhanradar.budget import _REDIS_KEYS, budget_guard

    key = _REDIS_KEYS["free"]
    with pytest.raises(RuntimeError):
        async with budget_guard("free") as meter:
            meter.units = 1
            raise RuntimeError("boom")
    assert int(await patch_redis.get(key)) == 0


# ---------------------------------------------------------------------------
# B18 — atomic admission (incr-then-rollback). No check-then-act overshoot.
# ---------------------------------------------------------------------------

async def test_premium_reject_does_not_inflate_counter(patch_redis):
    """A rejected premium call must RELEASE its reservation — the counter must
    settle back at the true value, never at value+reserve (else a single rejected
    call would permanently wedge the budget)."""
    from dhanradar.budget import _CAPS, _REDIS_KEYS, BudgetExhaustedError, budget_guard

    key = _REDIS_KEYS["premium"]
    hard_cap = float(_CAPS["premium_hard"])
    await patch_redis.set(key, str(hard_cap))  # already at the cap

    with pytest.raises(BudgetExhaustedError):
        async with budget_guard("premium"):
            pytest.fail("must not yield — cap met")

    # Counter is exactly the hard cap, NOT hard_cap + reserve.
    assert abs(float(await patch_redis.get(key)) - hard_cap) < 1e-9


async def test_free_reject_does_not_inflate_counter(patch_redis):
    """Same release-on-reject invariant for the free count cap."""
    from dhanradar.budget import _CAPS, _REDIS_KEYS, BudgetExhaustedError, budget_guard

    key = _REDIS_KEYS["free"]
    cap = int(_CAPS["free"])
    await patch_redis.set(key, str(cap))

    with pytest.raises(BudgetExhaustedError):
        async with budget_guard("free"):
            pytest.fail("must not yield — cap met")

    assert int(float(await patch_redis.get(key))) == cap


async def test_premium_concurrent_reservation_is_visible(patch_redis):
    """The core B18 fix: a reservation made by an in-flight call is visible to the
    next caller. Simulate an in-flight spillover by reserving manually just below
    the cap; a second budget_guard entry must then be rejected — it cannot read a
    stale pre-reservation value and also pass the cap check."""
    from dhanradar.budget import (
        _CAPS,
        _PREMIUM_RESERVE_USD,
        _REDIS_KEYS,
        BudgetExhaustedError,
        budget_guard,
    )

    key = _REDIS_KEYS["premium"]
    hard_cap = float(_CAPS["premium_hard"])
    # Counter sits one reservation below the cap, and an in-flight call has
    # already reserved — pushing the live value to/over the cap.
    await patch_redis.set(key, str(hard_cap - _PREMIUM_RESERVE_USD))
    await patch_redis.incrbyfloat(key, _PREMIUM_RESERVE_USD)  # in-flight reservation

    with pytest.raises(BudgetExhaustedError):
        async with budget_guard("premium"):
            pytest.fail("second concurrent caller must be rejected")


async def test_premium_reconciles_reservation_to_actual_cost(patch_redis):
    """On clean exit the reservation is reconciled to the actual cost — the final
    counter equals the actual spend, not the (larger) reservation."""
    from dhanradar.budget import _PREMIUM_RESERVE_USD, _REDIS_KEYS, budget_guard

    key = _REDIS_KEYS["premium"]
    actual = 0.012
    assert actual < _PREMIUM_RESERVE_USD  # reserve is larger, must be reconciled down
    async with budget_guard("premium") as meter:
        meter.cost_usd = actual
    assert abs(float(await patch_redis.get(key)) - actual) < 1e-9


async def test_reserve_override_is_applied_in_flight_then_reconciled(patch_redis):
    """An explicit reserve overrides the per-kind default: that amount is held on
    the counter DURING the guarded block (so concurrent callers see it) and is
    reconciled to the actual recorded spend on clean exit. Admission itself keys
    off the pre-reservation value, so the reserve does not move the cap boundary —
    it sizes the in-flight hold."""
    from dhanradar.budget import _REDIS_KEYS, budget_guard

    key = _REDIS_KEYS["premium"]
    async with budget_guard("premium", reserve=0.40) as meter:
        # Mid-flight the override reservation is on the counter.
        assert abs(float(await patch_redis.get(key)) - 0.40) < 1e-9
        meter.cost_usd = 0.05
    # After clean exit the reservation is reconciled down to the actual cost.
    assert abs(float(await patch_redis.get(key)) - 0.05) < 1e-9


async def test_premium_concurrent_gather_admits_exactly_one(patch_redis):
    """The PRIMARY B18 fix, exercised by a real race. Two budget_guard entries run
    concurrently via asyncio.gather from a counter with room for exactly ONE
    reservation. Exactly one must be admitted; the other rejected. This test FAILS
    against the old check-then-act code (both would read the stale pre-value and
    both be admitted)."""
    import asyncio

    from dhanradar.budget import (
        _CAPS,
        _PREMIUM_RESERVE_USD,
        _REDIS_KEYS,
        BudgetExhaustedError,
        budget_guard,
    )

    key = _REDIS_KEYS["premium"]
    hard_cap = float(_CAPS["premium_hard"])
    # Exactly one reservation of headroom remains under the hard cap.
    await patch_redis.set(key, str(hard_cap - _PREMIUM_RESERVE_USD))

    results = {"admitted": 0, "rejected": 0}

    async def attempt() -> None:
        try:
            async with budget_guard("premium") as meter:
                await asyncio.sleep(0)  # yield so the other task races our reservation
                meter.cost_usd = _PREMIUM_RESERVE_USD
        except BudgetExhaustedError:
            results["rejected"] += 1
        else:
            results["admitted"] += 1

    await asyncio.gather(attempt(), attempt())

    assert results["admitted"] == 1, f"expected exactly one admission, got {results}"
    assert results["rejected"] == 1, f"expected exactly one rejection, got {results}"


async def test_redis_failure_on_rollback_does_not_mask_original_error(patch_redis, monkeypatch):
    """A Redis failure while RELEASING a reservation must not mask the guarded
    block's own exception, and must not crash the guard. The leak self-heals at the
    daily TTL; the failure is logged, not raised (Vector 2)."""
    from dhanradar.budget import budget_guard

    real_incr = patch_redis.incrbyfloat

    async def flaky_incr(name, amount, *args, **kwargs):
        if float(amount) < 0:  # the reservation release / rollback
            raise ConnectionError("redis down during rollback")
        return await real_incr(name, amount, *args, **kwargs)

    monkeypatch.setattr(patch_redis, "incrbyfloat", flaky_incr)

    # The ORIGINAL RuntimeError must surface — NOT the ConnectionError from the
    # swallowed rollback.
    with pytest.raises(RuntimeError, match="boom"):
        async with budget_guard("free") as meter:
            meter.units = 1
            raise RuntimeError("boom")
