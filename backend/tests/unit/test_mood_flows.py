"""
Unit tests for the FII/DII flows cache + endpoint (Tasks B, C, D, A).

No live network, no real Redis, no real DB.

Covers:
  1. cache_market_flows + get_flows round-trip (in-memory Redis stub).
  2. get_flows returns all-None FlowsOut when the cache key is absent.
  3. _PrefetchedAdapter.fetch returns the injected event unchanged.
  4. cache_market_flows handles a Redis failure gracefully (no raise).
"""

from __future__ import annotations

import pytest

from dhanradar.market_data.config import DataKind, DataRequest
from dhanradar.market_data.events import MacroSignalReceived
from dhanradar.mood.schemas import FlowsOut
from dhanradar.tasks.mood import _PrefetchedAdapter

# ---------------------------------------------------------------------------
# In-memory Redis stub — mirrors the pattern in test_mood_breadth_wiring.py
# ---------------------------------------------------------------------------

class _FakeRedis:
    """Minimal async Redis stub: get/set backed by a plain dict."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:  # noqa: ARG002
        self._store[key] = value


# ---------------------------------------------------------------------------
# 1. cache_market_flows + get_flows round-trip
# ---------------------------------------------------------------------------

async def test_cache_and_get_flows_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Writing raw signals via cache_market_flows and then reading via get_flows
    must return a FlowsOut with the expected values."""
    import dhanradar.mood.service as svc

    fake_redis = _FakeRedis()
    monkeypatch.setattr(svc, "get_redis", lambda: fake_redis, raising=False)
    # get_redis is imported inside the functions, so patch the module attr they use.
    import dhanradar.redis_client as rc
    monkeypatch.setattr(rc, "get_redis", lambda: fake_redis)

    raw_signals = {
        "fii_flows": 6200.25,
        "dii_flows": -7500.0,
        "put_call_ratio": 0.6162,
    }

    await svc.cache_market_flows(raw_signals)
    result = await svc.get_flows()

    assert isinstance(result, FlowsOut)
    assert result.fii_cr == pytest.approx(6200.25)
    assert result.dii_cr == pytest.approx(-7500.0)
    assert result.pcr == pytest.approx(0.6162)
    assert result.as_of is not None  # ISO timestamp was written


# ---------------------------------------------------------------------------
# 2. get_flows returns all-None when the cache is cold (key absent)
# ---------------------------------------------------------------------------

async def test_get_flows_cold_cache_returns_all_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_flows must return FlowsOut(fii_cr=None, dii_cr=None, pcr=None, as_of=None)
    when the Redis key is absent."""
    import dhanradar.mood.service as svc
    import dhanradar.redis_client as rc

    fake_redis = _FakeRedis()  # empty store → key absent
    monkeypatch.setattr(rc, "get_redis", lambda: fake_redis)

    result = await svc.get_flows()

    assert isinstance(result, FlowsOut)
    assert result.fii_cr is None
    assert result.dii_cr is None
    assert result.pcr is None
    assert result.as_of is None


# ---------------------------------------------------------------------------
# 3. _PrefetchedAdapter.fetch returns the injected event unchanged
# ---------------------------------------------------------------------------

async def test_prefetched_adapter_returns_injected_event() -> None:
    """_PrefetchedAdapter must replay exactly the event it was given, without any
    network call and regardless of the _request argument."""
    event = MacroSignalReceived(
        source="upstox_analytics",
        signals={"fii_flows": 6200.25, "dii_flows": -7500.0, "put_call_ratio": 0.6162},
        fetched_at="2026-06-22T10:00:00Z",
    )
    adapter = _PrefetchedAdapter(event)

    # _request is ignored — pass anything
    returned = await adapter.fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))

    assert returned is event  # same object, not a copy
    assert returned.signals == {
        "fii_flows": 6200.25,
        "dii_flows": -7500.0,
        "put_call_ratio": 0.6162,
    }


# ---------------------------------------------------------------------------
# 4. cache_market_flows swallows a Redis failure (best-effort, never raises)
# ---------------------------------------------------------------------------

async def test_cache_market_flows_redis_failure_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When Redis.set raises, cache_market_flows must log a warning and return
    normally — it must never propagate the exception."""
    import dhanradar.mood.service as svc
    import dhanradar.redis_client as rc

    class _BrokenRedis:
        async def set(self, *_args: object, **_kwargs: object) -> None:
            raise ConnectionError("Redis is down")

        async def get(self, _key: str) -> None:
            return None

    monkeypatch.setattr(rc, "get_redis", lambda: _BrokenRedis())

    # Must not raise
    await svc.cache_market_flows({"fii_flows": 1000.0, "dii_flows": -500.0, "put_call_ratio": 0.8})


# ---------------------------------------------------------------------------
# 5. get_flows with partial signals (only some keys present in raw_signals)
# ---------------------------------------------------------------------------

async def test_get_flows_partial_signals(monkeypatch: pytest.MonkeyPatch) -> None:
    """cache_market_flows must handle missing keys in raw_signals gracefully
    (storing None for absent keys), and get_flows returns those as None."""
    import dhanradar.mood.service as svc
    import dhanradar.redis_client as rc

    fake_redis = _FakeRedis()
    monkeypatch.setattr(rc, "get_redis", lambda: fake_redis)

    # Only fii_flows present; dii_flows and put_call_ratio are absent
    await svc.cache_market_flows({"fii_flows": 3000.0})
    result = await svc.get_flows()

    assert isinstance(result, FlowsOut)
    assert result.fii_cr == pytest.approx(3000.0)
    assert result.dii_cr is None
    assert result.pcr is None
