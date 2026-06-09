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


# --- normalizers (1 = greed/bullish, 0 = fear/bearish) -----------------------
def test_norm_global_indices_bounds():
    assert norm_global_indices(3.0) == 1.0     # +3% → greed
    assert norm_global_indices(-3.0) == 0.0    # −3% → fear
    assert norm_global_indices(0.0) == 0.5


def test_norm_us_bond_10y_inverts_yield():
    assert norm_us_bond_10y(3.0) == 1.0        # low yield → greed
    assert norm_us_bond_10y(5.0) == 0.0        # high yield → fear
    assert norm_us_bond_10y(4.0) == 0.5
    assert norm_us_bond_10y(6.0) == 0.0        # clamped


def test_norm_oil_brent_inverts_price():
    assert norm_oil_brent(60.0) == 1.0         # cheap oil → greed (India importer)
    assert norm_oil_brent(100.0) == 0.0        # expensive oil → fear
    assert norm_oil_brent(80.0) == 0.5


def test_norm_usd_inr_rewards_inr_strength():
    assert norm_usd_inr(-1.0) == 1.0           # USD/INR down (INR strong) → greed
    assert norm_usd_inr(1.0) == 0.0            # USD/INR up (INR weak) → fear
    assert norm_usd_inr(0.0) == 0.5


# --- provider raw-value derivation (pct vs level) ----------------------------
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


async def test_yahoo_provider_builds_signals(monkeypatch):
    from dhanradar.market_data.providers import yahoo

    metas = {
        "^NSEI": {"regularMarketPrice": 103.0, "chartPreviousClose": 100.0},   # +3.0%
        "^INDIAVIX": {"regularMarketPrice": 15.0},                              # level
        "^GSPC": {"regularMarketPrice": 99.0, "chartPreviousClose": 100.0},    # −1.0%
        "^TNX": {"regularMarketPrice": 4.5},                                    # level
        "BZ=F": {"regularMarketPrice": 90.0},                                   # level
        "INR=X": {"regularMarketPrice": 99.5, "chartPreviousClose": 100.0},    # −0.5%
    }

    async def fake_meta(_client, symbol):
        return metas.get(symbol)

    monkeypatch.setattr(yahoo, "_quote_meta", fake_meta)

    ev = await yahoo.YahooMacroProvider().fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))
    s = ev.signals
    assert round(s["nifty_trend"], 2) == 3.0
    assert s["india_vix"] == 15.0
    assert round(s["global_indices"], 2) == -1.0
    assert s["us_bond_10y"] == 4.5
    assert s["oil_brent"] == 90.0
    assert round(s["usd_inr"], 2) == -0.5
    assert ev.source == "yahoo_macro"


async def test_yahoo_provider_omits_failed_symbols(monkeypatch):
    from dhanradar.market_data.providers import yahoo

    async def fake_meta(_client, symbol):
        # Only NIFTY resolves; everything else fails → omitted, no crash.
        return {"regularMarketPrice": 100.0, "chartPreviousClose": 100.0} if symbol == "^NSEI" else None

    monkeypatch.setattr(yahoo, "_quote_meta", fake_meta)
    ev = await yahoo.YahooMacroProvider().fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))
    assert list(ev.signals.keys()) == ["nifty_trend"]


async def test_yahoo_provider_raises_when_all_blank(monkeypatch):
    """Every symbol blank → ProviderError, so the adapter ladder falls through to
    the fallback instead of recording a false 'success' on an empty result."""
    from dhanradar.market_data.exceptions import ProviderError
    from dhanradar.market_data.providers import yahoo

    async def fake_meta(_client, _symbol):
        return None

    monkeypatch.setattr(yahoo, "_quote_meta", fake_meta)
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
