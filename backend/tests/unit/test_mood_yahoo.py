"""
Unit tests for the Yahoo-Finance macro provider + its new signal normalizers.

Why this exists: NSE 403-blocks the prod server, so the Mood Compass had zero
signals and never stored a snapshot. Yahoo is the server-reachable replacement;
these tests pin the raw→normalised mapping and that 6 signals yield a real
(degraded, medium-confidence) regime rather than the all-missing skip path.
"""

from __future__ import annotations

import pytest

from dhanradar.market_data.config import DataKind, DataRequest
from dhanradar.market_data.events import MacroSignalReceived
from dhanradar.mood.compute import compute_mood
from dhanradar.mood.signals import (
    fetch_mood_inputs,
    norm_global_indices,
    norm_oil_brent,
    norm_us_bond_10y,
    norm_usd_inr,
)


# --- normalizers (1 = greed/bullish, 0 = fear/bearish; mood_v2: inputs are
# --- deviations from the signal's own moving average, not raw levels) ---------
def test_norm_global_indices_bounds():
    assert norm_global_indices(6.0) == 1.0     # +6% above 125-DMA → greed
    assert norm_global_indices(-6.0) == 0.0    # −6% below 125-DMA → fear
    assert norm_global_indices(0.0) == 0.5     # on the MA


def test_norm_us_bond_10y_inverts_yield_deviation():
    assert norm_us_bond_10y(-0.5) == 1.0       # 0.5 pp below 50-DMA (easing) → greed
    assert norm_us_bond_10y(0.5) == 0.0        # 0.5 pp above 50-DMA (tightening) → fear
    assert norm_us_bond_10y(0.0) == 0.5
    assert norm_us_bond_10y(1.5) == 0.0        # clamped


def test_norm_oil_brent_inverts_price_deviation():
    assert norm_oil_brent(-15.0) == 1.0        # 15% below 50-DMA → greed (India importer)
    assert norm_oil_brent(15.0) == 0.0         # 15% above 50-DMA → fear
    assert norm_oil_brent(0.0) == 0.5


def test_norm_usd_inr_rewards_inr_strength():
    assert norm_usd_inr(-2.0) == 1.0           # USD/INR 2% below 50-DMA (INR strong) → greed
    assert norm_usd_inr(2.0) == 0.0            # USD/INR 2% above 50-DMA (INR weak) → fear
    assert norm_usd_inr(0.0) == 0.5


# --- quote helper (still used by dashboard/indices.py) -----------------------
def test_signal_value_pct_and_level():
    from dhanradar.market_data.providers import yahoo

    # pct: (103 − 100)/100 * 100 = +3.0
    assert yahoo._signal_value({"regularMarketPrice": 103.0, "chartPreviousClose": 100.0}, "pct") == 3.0
    # level: returned as-is
    assert yahoo._signal_value({"regularMarketPrice": 15.5}, "level") == 15.5
    # missing price → None
    assert yahoo._signal_value({}, "level") is None
    # pct with no/zero prev close → None (can't divide)
    assert yahoo._signal_value({"regularMarketPrice": 10.0, "chartPreviousClose": 0}, "pct") is None


# --- mood_v2 raw-value derivation: deviation from the moving average ----------
def test_ma_deviation_pct_and_abs():
    from dhanradar.market_data.providers.yahoo import _ma_deviation

    closes = [100.0] * 50
    # pct: last 106 vs 50-day MA of 100 → +6.0 %
    assert round(_ma_deviation({"regularMarketPrice": 106.0}, closes, "ma_dev_pct", 50), 2) == 6.0
    # abs: last 4.5 vs MA 4.0 → +0.5 points
    assert round(_ma_deviation({"regularMarketPrice": 4.5}, [4.0] * 50, "ma_dev_abs", 50), 2) == 0.5
    # no meta price → falls back to the last close (deviation 0)
    assert _ma_deviation(None, closes, "ma_dev_pct", 50) == 0.0


def test_ma_deviation_short_history_returns_none():
    """Fewer valid closes than the MA window → None (signal omitted, never imputed)."""
    from dhanradar.market_data.providers.yahoo import _ma_deviation

    assert _ma_deviation({"regularMarketPrice": 100.0}, [100.0] * 49, "ma_dev_pct", 50) is None
    assert _ma_deviation({"regularMarketPrice": 100.0}, [], "ma_dev_pct", 125) is None


async def test_yahoo_provider_builds_signals(monkeypatch):
    from dhanradar.market_data.providers import yahoo

    # (meta, closes) per symbol — closes flat at a base so the deviation is exact.
    series = {
        "^NSEI": ({"regularMarketPrice": 106.0}, [100.0] * 130),      # +6.0 % vs 125-DMA
        "^INDIAVIX": ({"regularMarketPrice": 25.0}, [20.0] * 60),     # +25.0 % vs 50-DMA
        "^GSPC": ({"regularMarketPrice": 94.0}, [100.0] * 130),      # −6.0 % vs 125-DMA
        "^TNX": ({"regularMarketPrice": 4.5}, [4.0] * 60),            # +0.5 pp vs 50-DMA
        "BZ=F": ({"regularMarketPrice": 92.0}, [80.0] * 60),          # +15.0 % vs 50-DMA
        "INR=X": ({"regularMarketPrice": 89.76}, [88.0] * 60),        # +2.0 % vs 50-DMA
    }

    async def fake_series(_client, symbol):
        return series.get(symbol, (None, []))

    monkeypatch.setattr(yahoo, "_chart_series", fake_series)

    ev = await yahoo.YahooMacroProvider().fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))
    s = ev.signals
    assert round(s["nifty_trend"], 2) == 6.0
    assert round(s["india_vix"], 2) == 25.0
    assert round(s["global_indices"], 2) == -6.0
    assert round(s["us_bond_10y"], 2) == 0.5
    assert round(s["oil_brent"], 2) == 15.0
    assert round(s["usd_inr"], 2) == 2.0
    assert ev.source == "yahoo_macro"


async def test_yahoo_provider_omits_failed_and_short_symbols(monkeypatch):
    from dhanradar.market_data.providers import yahoo

    async def fake_series(_client, symbol):
        if symbol == "^NSEI":
            return {"regularMarketPrice": 100.0}, [100.0] * 130
        if symbol == "^GSPC":
            # History shorter than the 125-day window → omitted (no impute).
            return {"regularMarketPrice": 100.0}, [100.0] * 60
        return None, []  # everything else fails → omitted, no crash

    # market_breadth is fetched independently (NIFTY-50 A/D cache), not via the
    # chart API — stub it to None here to isolate chart-symbol omission behaviour.
    async def fake_breadth():
        return None

    monkeypatch.setattr(yahoo, "_chart_series", fake_series)
    monkeypatch.setattr(yahoo, "_fetch_breadth_ratio", fake_breadth)
    ev = await yahoo.YahooMacroProvider().fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))
    assert list(ev.signals.keys()) == ["nifty_trend"]


async def test_yahoo_provider_raises_when_all_blank(monkeypatch):
    """Every symbol blank → ProviderError, so the adapter ladder falls through to
    the fallback instead of recording a false 'success' on an empty result."""
    from dhanradar.market_data.exceptions import ProviderError
    from dhanradar.market_data.providers import yahoo

    async def fake_series(_client, _symbol):
        return None, []

    monkeypatch.setattr(yahoo, "_chart_series", fake_series)
    with pytest.raises(ProviderError):
        await yahoo.YahooMacroProvider().fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))


# --- fetch → normalise → compute: a real degraded/medium regime --------------
async def test_six_signals_produce_a_real_medium_regime():
    class _FakeAdapter:
        async def fetch(self, _request):
            return MacroSignalReceived(
                source="yahoo_macro",
                signals={
                    "nifty_trend": 1.0, "india_vix": 15.0, "global_indices": 0.5,
                    "us_bond_10y": 4.5, "oil_brent": 90.0, "usd_inr": -0.2,
                },
                fetched_at="2026-06-09T00:00:00Z",
            )

    inputs = await fetch_mood_inputs(_FakeAdapter())
    present = {k for k, v in inputs.items() if v is not None}
    assert present == {"nifty_trend", "india_vix", "global_indices", "us_bond_10y", "oil_brent", "usd_inr"}

    result = compute_mood(inputs)
    assert result is not None                       # NOT the all-missing skip path
    assert result.inputs_available == 6
    assert result.data_quality == "degraded"        # < 7 inputs
    assert result.confidence_band == "medium"       # weight 0.57 capped to 0.40
    assert result.regime != "data_unavailable"      # a real regime is asserted
