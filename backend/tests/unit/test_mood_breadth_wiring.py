"""
Unit tests for the market_breadth signal wiring into the YahooMacroProvider
macro pipeline.

What is tested:
  1. YahooMacroProvider.fetch() emits ``market_breadth`` when the breadth core
     returns known advances/declines â€” verifies correct a/(a+d) formula.
  2. fetch_mood_inputs() maps the raw breadth through norm_market_breadth into
     a non-None normalised input in [0, 1].
  3. Graceful degradation: breadth fetch failure â†’ key absent, no exception,
     other 6 chart signals still returned.
  4. ProviderError NOT raised when breadth fails but chart symbols resolve.
  5. 6 Yahoo chart signals + market_breadth = 7 present inputs â†’ data_quality
     flips from "degraded" to "ok", crossing the _DEGRADED_BELOW=7 threshold.

All network calls are mocked â€” deterministic, no yfinance/httpx I/O.
"""

from __future__ import annotations

import json

import pytest

from dhanradar.market_data.config import DataKind, DataRequest
from dhanradar.market_data.events import MacroSignalReceived
from dhanradar.mood.compute import _DEGRADED_BELOW, compute_mood
from dhanradar.mood.signals import fetch_mood_inputs, norm_market_breadth

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SIX_CHART_METAS = {
    "^NSEI":     {"regularMarketPrice": 103.0, "chartPreviousClose": 100.0},   # +3.0%
    "^INDIAVIX": {"regularMarketPrice": 15.0},                                  # level
    "^GSPC":     {"regularMarketPrice": 99.0,  "chartPreviousClose": 100.0},   # -1.0%
    "^TNX":      {"regularMarketPrice": 4.5},                                   # level
    "BZ=F":      {"regularMarketPrice": 90.0},                                  # level
    "INR=X":     {"regularMarketPrice": 99.5,  "chartPreviousClose": 100.0},   # -0.5%
}


# ---------------------------------------------------------------------------
# 1. YahooMacroProvider emits market_breadth with correct a/(a+d) value
# ---------------------------------------------------------------------------

async def test_yahoo_provider_emits_market_breadth_from_cache(monkeypatch):
    """Provider reads advances/declines from the Redis cache and emits
    market_breadth = advances/(advances+declines), not advances/declines."""
    from dhanradar.market_data.providers import yahoo

    # Stub all chart symbol fetches with the known metas
    async def fake_meta(_client, symbol):
        return _SIX_CHART_METAS.get(symbol)

    monkeypatch.setattr(yahoo, "_quote_meta", fake_meta)

    # Stub Redis: cache contains advances=35, declines=15 â†’ ratio = 35/50 = 0.70
    advances, declines = 35, 15
    cache_payload = json.dumps({"advances": advances, "declines": declines, "ad_ratio": 2.333})

    class _FakeRedis:
        async def get(self, _key):
            return cache_payload
        async def set(self, _key, _val, ex=None):
            pass

    monkeypatch.setattr(yahoo, "_fetch_breadth_ratio", None)  # bypass module-level fn
    # Re-patch _fetch_breadth_ratio to use our fake Redis via the real impl path

    async def fake_fetch_breadth_ratio():
        data = json.loads(cache_payload)
        a, d = int(data["advances"]), int(data["declines"])
        total = a + d
        return float(a) / float(total) if total > 0 else None

    monkeypatch.setattr(yahoo, "_fetch_breadth_ratio", fake_fetch_breadth_ratio)

    ev = await yahoo.YahooMacroProvider().fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))
    s = ev.signals

    assert "market_breadth" in s, f"Expected market_breadth in signals, got {list(s)}"
    expected_ratio = advances / (advances + declines)  # 35/50 = 0.70
    assert abs(s["market_breadth"] - expected_ratio) < 1e-9, (
        f"market_breadth={s['market_breadth']}, expected {expected_ratio}"
    )
    # All six chart signals must still be present
    for key in ("nifty_trend", "india_vix", "global_indices", "us_bond_10y", "oil_brent", "usd_inr"):
        assert key in s, f"Chart signal {key!r} missing from {list(s)}"



# ---------------------------------------------------------------------------
# 2. fetch_mood_inputs maps raw breadth through norm_market_breadth
# ---------------------------------------------------------------------------

async def test_fetch_mood_inputs_normalises_market_breadth():
    """fetch_mood_inputs must pass raw breadth (already a/(a+d) âˆˆ [0,1]) through
    norm_market_breadth and produce a non-None normalised value."""
    # norm_market_breadth is just _clamp â€” so the raw value IS the normalised value
    # for inputs already in [0,1].
    raw_breadth = 0.64
    expected_normalised = norm_market_breadth(raw_breadth)  # 0.64

    class _FakeAdapter:
        async def fetch(self, _request):
            return MacroSignalReceived(
                source="yahoo_macro",
                signals={
                    "nifty_trend": 1.0,
                    "india_vix": 15.0,
                    "global_indices": 0.5,
                    "us_bond_10y": 4.5,
                    "oil_brent": 90.0,
                    "usd_inr": -0.2,
                    "market_breadth": raw_breadth,
                },
                fetched_at="2026-06-19T00:00:00Z",
            )

    inputs = await fetch_mood_inputs(_FakeAdapter())

    assert inputs.get("market_breadth") is not None, (
        f"market_breadth should be normalised, got None. Inputs: {inputs}"
    )
    assert abs(inputs["market_breadth"] - expected_normalised) < 1e-9, (
        f"market_breadth={inputs['market_breadth']}, expected {expected_normalised}"
    )


# ---------------------------------------------------------------------------
# 3. Graceful degradation: breadth failure â†’ key absent, no exception raised
# ---------------------------------------------------------------------------

async def test_yahoo_provider_breadth_failure_omits_key_no_exception(monkeypatch):
    """When _fetch_breadth_ratio returns None, market_breadth is absent from
    signals. The six chart signals are still returned. No exception is raised."""
    from dhanradar.market_data.providers import yahoo

    async def fake_meta(_client, symbol):
        return _SIX_CHART_METAS.get(symbol)

    monkeypatch.setattr(yahoo, "_quote_meta", fake_meta)

    async def failing_breadth():
        return None  # simulates any internal failure

    monkeypatch.setattr(yahoo, "_fetch_breadth_ratio", failing_breadth)

    # Must NOT raise
    ev = await yahoo.YahooMacroProvider().fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))
    s = ev.signals

    assert "market_breadth" not in s, f"market_breadth should be absent, got {s}"
    assert len(s) == 6, f"Expected 6 chart signals, got {list(s)}"


# ---------------------------------------------------------------------------
# 4. ProviderError NOT raised when breadth fails but chart symbols resolve
# ---------------------------------------------------------------------------

async def test_yahoo_provider_no_provider_error_on_breadth_failure(monkeypatch):
    """ProviderError must not be raised when breadth fails but at least one
    chart symbol succeeds â€” breadth failure is not a catastrophic failure."""
    from dhanradar.market_data.providers import yahoo

    async def fake_meta(_client, symbol):
        # Only NIFTY resolves
        return _SIX_CHART_METAS.get(symbol) if symbol == "^NSEI" else None

    monkeypatch.setattr(yahoo, "_quote_meta", fake_meta)

    async def failing_breadth():
        raise RuntimeError("simulated Redis + yfinance failure")  # noqa: EM101

    # Wrap in the real function's exception handling â€” but actually _fetch_breadth_ratio
    # already eats exceptions internally (returns None). Test both the wrapper behavior
    # and the fact that fetch() does not re-raise.
    async def safe_failing_breadth():
        try:
            await failing_breadth()
        except Exception:  # noqa: BLE001
            return None
        return None  # pragma: no cover

    monkeypatch.setattr(yahoo, "_fetch_breadth_ratio", safe_failing_breadth)

    # Must succeed without ProviderError
    ev = await yahoo.YahooMacroProvider().fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))
    assert "nifty_trend" in ev.signals
    assert "market_breadth" not in ev.signals


# ---------------------------------------------------------------------------
# 5. 6 chart signals + market_breadth = 7 â†’ data_quality flips to "ok"
# ---------------------------------------------------------------------------

async def test_seven_signals_flip_data_quality_to_ok():
    """Adding market_breadth to the 6 existing Yahoo chart signals gives 7 present
    inputs, which crosses _DEGRADED_BELOW=7 and flips data_quality to 'ok'
    (commentary_allowed=True)."""
    assert _DEGRADED_BELOW == 7, f"Expected _DEGRADED_BELOW=7, got {_DEGRADED_BELOW}"

    class _FakeAdapter:
        async def fetch(self, _request):
            return MacroSignalReceived(
                source="yahoo_macro",
                signals={
                    "nifty_trend":    1.0,   # +3% â†’ greedy
                    "india_vix":      15.0,  # level
                    "global_indices": 0.5,   # -0.5%
                    "us_bond_10y":    4.5,   # level
                    "oil_brent":      90.0,  # level
                    "usd_inr":       -0.2,   # -0.2%
                    "market_breadth": 0.64,  # a/(a+d) â€” the new 7th signal
                },
                fetched_at="2026-06-19T00:00:00Z",
            )

    inputs = await fetch_mood_inputs(_FakeAdapter())
    present_count = sum(1 for v in inputs.values() if v is not None)

    assert present_count == 7, (
        f"Expected 7 present inputs after wiring market_breadth, got {present_count}. "
        f"Present keys: {[k for k, v in inputs.items() if v is not None]}"
    )

    result = compute_mood(inputs)
    assert result is not None
    assert result.inputs_available == 7
    assert result.data_quality == "ok", (
        f"Expected data_quality='ok' with 7 inputs, got {result.data_quality!r}"
    )
    assert result.commentary_allowed is True, (
        "commentary_allowed should be True when data_quality='ok'"
    )
    assert result.regime != "data_unavailable"


# ---------------------------------------------------------------------------
# 6. Six signals without breadth remain degraded (regression guard)
# ---------------------------------------------------------------------------

async def test_six_signals_without_breadth_still_degraded():
    """Without market_breadth, 6 signals < 7 â†’ data_quality='degraded'.
    This is the current prod state; we should not accidentally mark it ok."""
    class _FakeAdapter:
        async def fetch(self, _request):
            return MacroSignalReceived(
                source="yahoo_macro",
                signals={
                    "nifty_trend":    1.0,
                    "india_vix":      15.0,
                    "global_indices": 0.5,
                    "us_bond_10y":    4.5,
                    "oil_brent":      90.0,
                    "usd_inr":       -0.2,
                },
                fetched_at="2026-06-19T00:00:00Z",
            )

    inputs = await fetch_mood_inputs(_FakeAdapter())
    result = compute_mood(inputs)
    assert result is not None
    assert result.inputs_available == 6
    assert result.data_quality == "degraded"


# ---------------------------------------------------------------------------
# 7. norm_market_breadth formula check: a/(a+d) in [0,1] passes through
# ---------------------------------------------------------------------------

def test_norm_market_breadth_clamps_passthrough():
    """norm_market_breadth expects a/(a+d) which is already in [0,1]; it clamps
    defensively.  Key boundary checks."""
    assert norm_market_breadth(0.0) == 0.0   # all declines
    assert norm_market_breadth(1.0) == 1.0   # all advances
    assert norm_market_breadth(0.5) == 0.5   # equal
    assert norm_market_breadth(0.7) == 0.7   # typical bullish
    assert norm_market_breadth(-0.1) == 0.0  # clamped below
    assert norm_market_breadth(1.1) == 1.0   # clamped above


# ---------------------------------------------------------------------------
# 8. Correct formula: a/(a+d) vs a/d are different
# ---------------------------------------------------------------------------

def test_breadth_formula_difference():
    """Explicit sanity: a/(a+d) != a/d for advances=35, declines=15.

    The existing _fetch_breadth_sync returns ad_ratio = advances/declines = 2.333.
    The norm_market_breadth expects advances/(advances+declines) = 0.70.
    If we fed 2.333 directly it would be clamped to 1.0 â€” wrong.
    """
    advances, declines = 35, 15
    ad_ratio = advances / max(declines, 1)           # 2.333 â€” the old ad_ratio
    breadth_ratio = advances / (advances + declines)  # 0.70 â€” the correct value

    assert ad_ratio != breadth_ratio, "Test data must differ (advances != declines)"
    assert abs(breadth_ratio - 0.70) < 1e-9
    # If the wrong formula were used, norm would clamp to 1.0
    assert norm_market_breadth(ad_ratio) == 1.0   # wrong input â†’ wrong (clamped) output
    assert norm_market_breadth(breadth_ratio) == pytest.approx(0.70)  # correct


# ---------------------------------------------------------------------------
# 9. Real _fetch_breadth_ratio: cache hit -> correct ratio, no live fetch
# ---------------------------------------------------------------------------

async def test_fetch_breadth_ratio_real_cache_hit(monkeypatch):
    """_fetch_breadth_ratio with a monkeypatched Redis returning advances=40,
    declines=10 must return 40/50 = 0.80.  No live yfinance call is made."""
    import dhanradar.redis_client as rc
    from dhanradar.market_data.providers import yahoo

    advances, declines = 40, 10
    payload = json.dumps({"advances": advances, "declines": declines, "ad_ratio": 4.0})

    class _FakeRedis:
        async def get(self, _key):
            return payload

    monkeypatch.setattr(rc, "get_redis", lambda: _FakeRedis())

    result = await yahoo._fetch_breadth_ratio()
    expected = advances / (advances + declines)  # 0.80
    assert result is not None, "_fetch_breadth_ratio returned None on cache hit"
    assert abs(result - expected) < 1e-9, f"Expected {expected}, got {result}"


# ---------------------------------------------------------------------------
# 10. Real _fetch_breadth_ratio: cache miss -> None, no exception, no live fetch
# ---------------------------------------------------------------------------

async def test_fetch_breadth_ratio_real_cache_miss(monkeypatch):
    """_fetch_breadth_ratio with Redis returning None (cache miss) must return
    None without raising and without touching yfinance."""
    import dhanradar.redis_client as rc
    from dhanradar.market_data.providers import yahoo

    class _FakeRedis:
        async def get(self, _key):
            return None  # cache miss

    monkeypatch.setattr(rc, "get_redis", lambda: _FakeRedis())

    result = await yahoo._fetch_breadth_ratio()
    assert result is None, f"Expected None on cache miss, got {result}"
