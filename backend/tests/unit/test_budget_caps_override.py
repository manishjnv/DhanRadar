"""
Unit tests for dhanradar.budget.get_effective_caps and compute_budget_state.

Pure unit tests — no real Redis instance required.  A minimal async fake is
provided inline so the module does NOT depend on fakeredis being installed
(fakeredis is only a dev/test dep, but we avoid the import here to keep this
test self-contained and insulated from the fakeredis import path in conftest).

Key names verified against dhanradar/budget.py _CAP_OVERRIDE_KEYS:
  "ai:budget:cap:free"          → overrides _CAPS["free"]        (int)
  "ai:budget:cap:premium_soft"  → overrides _CAPS["premium_soft"] (float)
  "ai:budget:cap:premium_hard"  → overrides _CAPS["premium_hard"] (float)

_CAPS defaults (from budget.py at time of writing):
  free          = 1000
  premium_soft  = 0.50
  premium_hard  = 9.50
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Minimal async fake-Redis stub
# ---------------------------------------------------------------------------


class _FakeRedis:
    """Minimal async-compatible Redis stub for get_effective_caps tests.

    Stores preset string/bytes values per key.  Only implements `get()`.
    """

    def __init__(self, store: dict[str, bytes | str | None]) -> None:
        self._store = store

    async def get(self, key: str) -> bytes | str | None:
        return self._store.get(key)


# ---------------------------------------------------------------------------
# get_effective_caps — Redis override resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_effective_caps_returns_defaults_when_no_overrides():
    """When no override keys are present in Redis, defaults are returned."""
    from dhanradar.budget import _CAPS, get_effective_caps

    redis = _FakeRedis({})  # all keys return None → no overrides
    result = await get_effective_caps(redis)  # type: ignore[arg-type]

    assert result["free"] == int(_CAPS["free"])
    assert result["premium_soft"] == float(_CAPS["premium_soft"])
    assert result["premium_hard"] == float(_CAPS["premium_hard"])


@pytest.mark.asyncio
async def test_get_effective_caps_honours_valid_overrides():
    """Valid positive override values for all three keys are applied."""
    from dhanradar.budget import get_effective_caps

    redis = _FakeRedis({
        "ai:budget:cap:free": b"2000",
        "ai:budget:cap:premium_soft": b"1.25",
        "ai:budget:cap:premium_hard": b"19.99",
    })
    result = await get_effective_caps(redis)  # type: ignore[arg-type]

    assert result["free"] == 2000
    assert result["premium_soft"] == pytest.approx(1.25)
    assert result["premium_hard"] == pytest.approx(19.99)


@pytest.mark.asyncio
async def test_get_effective_caps_falls_back_on_malformed_value():
    """A non-numeric override value ('abc') must fall back to the default,
    not raise. All three fallback independently."""
    from dhanradar.budget import _CAPS, get_effective_caps

    redis = _FakeRedis({
        "ai:budget:cap:free": b"abc",           # malformed
        "ai:budget:cap:premium_soft": b"xyz",   # malformed
        "ai:budget:cap:premium_hard": b"bad",   # malformed
    })
    result = await get_effective_caps(redis)  # type: ignore[arg-type]

    # Must not raise; must return defaults
    assert result["free"] == int(_CAPS["free"])
    assert result["premium_soft"] == float(_CAPS["premium_soft"])
    assert result["premium_hard"] == float(_CAPS["premium_hard"])


@pytest.mark.asyncio
async def test_get_effective_caps_falls_back_on_zero_override():
    """A zero override for free cap falls back to default (zero cap would block all AI calls)."""
    from dhanradar.budget import _CAPS, get_effective_caps

    redis = _FakeRedis({"ai:budget:cap:free": b"0"})
    result = await get_effective_caps(redis)  # type: ignore[arg-type]

    # Zero is non-positive → must use hardcoded default
    assert result["free"] == int(_CAPS["free"])


@pytest.mark.asyncio
async def test_get_effective_caps_falls_back_on_negative_override():
    """Negative override values fall back to defaults."""
    from dhanradar.budget import _CAPS, get_effective_caps

    redis = _FakeRedis({
        "ai:budget:cap:premium_hard": b"-5.0",
    })
    result = await get_effective_caps(redis)  # type: ignore[arg-type]

    assert result["premium_hard"] == float(_CAPS["premium_hard"])


@pytest.mark.asyncio
async def test_get_effective_caps_partial_override_only_replaces_set_keys():
    """Only the keys that have valid overrides are replaced; others use defaults."""
    from dhanradar.budget import _CAPS, get_effective_caps

    redis = _FakeRedis({
        "ai:budget:cap:free": b"500",
        # premium_soft and premium_hard are absent (None)
    })
    result = await get_effective_caps(redis)  # type: ignore[arg-type]

    assert result["free"] == 500
    assert result["premium_soft"] == float(_CAPS["premium_soft"])
    assert result["premium_hard"] == float(_CAPS["premium_hard"])


# ---------------------------------------------------------------------------
# compute_budget_state — pure computation (no I/O)
# ---------------------------------------------------------------------------


def test_compute_budget_state_defaults_no_raw_values():
    """Both raw values None (key not yet set) → all today values are 0."""
    from dhanradar.budget import _CAPS, compute_budget_state

    result = compute_budget_state(None, None)

    assert result["free_calls_today"] == 0
    assert result["premium_usd_today"] == pytest.approx(0.0)
    assert result["free_cap"] == int(_CAPS["free"])
    assert result["premium_soft_cap"] == pytest.approx(float(_CAPS["premium_soft"]))
    assert result["premium_hard_cap"] == pytest.approx(float(_CAPS["premium_hard"]))
    assert result["free_remaining"] == int(_CAPS["free"])
    assert result["premium_remaining_usd"] == pytest.approx(float(_CAPS["premium_hard"]))


def test_compute_budget_state_honours_override_kwargs():
    """Explicit override kwargs are applied as caps."""
    from dhanradar.budget import compute_budget_state

    result = compute_budget_state(
        b"10",
        b"1.50",
        free_cap=500,
        premium_soft=0.75,
        premium_hard=5.00,
    )

    assert result["free_calls_today"] == 10
    assert result["free_cap"] == 500
    assert result["free_remaining"] == 490
    assert result["premium_usd_today"] == pytest.approx(1.50)
    assert result["premium_soft_cap"] == pytest.approx(0.75)
    assert result["premium_hard_cap"] == pytest.approx(5.00)
    assert result["premium_remaining_usd"] == pytest.approx(3.50)


def test_compute_budget_state_remaining_never_negative():
    """When today's spend exceeds the cap, remaining is 0 (not negative)."""
    from dhanradar.budget import compute_budget_state

    # Free calls today = 2000, cap = 1000 → remaining is clamped to 0.
    result = compute_budget_state(b"2000", b"0", free_cap=1000)

    assert result["free_calls_today"] == 2000
    assert result["free_remaining"] == 0
