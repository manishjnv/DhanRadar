"""
DhanRadar — Mood Compass signal normalization and adapter-based fetch.

Normalisation helpers: each function maps a raw domain value to [0, 1]
where 1 = greed/bullish and 0 = fear/bearish, matching the convention used
by compute.py.  Formulas are documented inline and in ADR-0023.

Module isolation: this module reaches macro data ONLY via the Market Data
Adapter (never calls a vendor directly).

Usage in tasks/mood.py:
    adapter = build_macro_adapter()
    inputs  = await fetch_mood_inputs(adapter)          # async
    result  = await compute_and_store(..., fetch=lambda: inputs)
"""

from __future__ import annotations

import logging

from dhanradar.market_data.config import DataKind, DataRequest
from dhanradar.market_data.events import MacroSignalReceived
from dhanradar.market_data.exceptions import AllProvidersFailedError
from dhanradar.mood.compute import WEIGHTS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalization helpers (each clamps to [0, 1]; 1 = greed/bullish)
# ---------------------------------------------------------------------------


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def norm_nifty_trend(pct_change: float) -> float:
    """
    Map NIFTY % daily change to [0, 1].

    Formula: clamp((pct + 3) / 6, 0, 1)
    - +3 % → 1.0 (strong bullish)
    - −3 % → 0.0 (strong bearish)
    - 0 % → 0.5 (flat/neutral)
    """
    return _clamp((pct_change + 3.0) / 6.0)


def norm_india_vix(vix: float) -> float:
    """
    Map India VIX to [0, 1].  High VIX = fear → low value.

    Formula: clamp((30 − vix) / 20, 0, 1)
    - VIX = 10 → 1.0 (low fear = greed zone)
    - VIX = 30 → 0.0 (high fear)
    - VIX = 20 → 0.5
    """
    return _clamp((30.0 - vix) / 20.0)


def norm_market_breadth(ratio: float) -> float:
    """
    Market breadth = advances / (advances + declines).

    Already in [0, 1]; 1 = all advancing (pure bullish).
    Clamped defensively in case of rounding.
    """
    return _clamp(ratio)


def norm_put_call_ratio(pcr: float) -> float:
    """
    Map Put-Call Ratio to [0, 1].  High PCR = fear → low value.

    Formula: clamp((1.3 − pcr) / 0.6, 0, 1)
    - PCR = 0.7 → 1.0 (low PCR = greed)
    - PCR = 1.3 → 0.0 (high PCR = fear)
    - PCR = 1.0 → 0.5
    """
    return _clamp((1.3 - pcr) / 0.6)


def norm_global_indices(pct_change: float) -> float:
    """
    Map a global benchmark's (S&P 500) % daily change to [0, 1] — same
    risk-on/off convention as NIFTY: global strength lifts EM sentiment.

    Formula: clamp((pct + 3) / 6, 0, 1)  (+3 % → 1.0, −3 % → 0.0, 0 → 0.5)
    """
    return _clamp((pct_change + 3.0) / 6.0)


def norm_us_bond_10y(yield_pct: float) -> float:
    """
    Map the US 10-year Treasury yield LEVEL (in %, e.g. 4.55) to [0, 1].
    Higher US yields tighten global liquidity and pull capital from EM
    equities → risk-off (fear); lower yields → risk-on (greed).

    Formula: clamp((5.0 − yield) / 2.0, 0, 1)
    - 3.0 % → 1.0 (easy liquidity = greed)
    - 5.0 % → 0.0 (tight liquidity = fear)
    - 4.0 % → 0.5
    """
    return _clamp((5.0 - yield_pct) / 2.0)


def norm_oil_brent(price_usd: float) -> float:
    """
    Map Brent crude price LEVEL (USD/bbl) to [0, 1].  India is a large net
    oil importer, so high oil = trade-deficit / inflation pressure (fear);
    low oil = tailwind (greed).

    Formula: clamp((100 − price) / 40, 0, 1)
    - $60 → 1.0 (cheap oil = greed)
    - $100 → 0.0 (expensive oil = fear)
    - $80 → 0.5
    """
    return _clamp((100.0 - price_usd) / 40.0)


def norm_usd_inr(pct_change: float) -> float:
    """
    Map the USD/INR pair's % daily change to [0, 1].  INR appreciation
    (USD/INR falling → negative %) signals capital inflows / risk-on (greed);
    INR depreciation (USD/INR rising → positive %) signals outflows (fear).

    Formula: clamp((−pct + 1.0) / 2.0, 0, 1)
    - USD/INR −1 % (INR strengthens) → 1.0 (greed)
    - USD/INR +1 % (INR weakens)    → 0.0 (fear)
    - 0 % → 0.5
    """
    return _clamp((-pct_change + 1.0) / 2.0)


# ---------------------------------------------------------------------------
# Adapter-based fetch
# ---------------------------------------------------------------------------

_NORMALIZERS: dict[str, object] = {
    "nifty_trend": norm_nifty_trend,
    "india_vix": norm_india_vix,
    "market_breadth": norm_market_breadth,
    "put_call_ratio": norm_put_call_ratio,
    "global_indices": norm_global_indices,
    "us_bond_10y": norm_us_bond_10y,
    "oil_brent": norm_oil_brent,
    "usd_inr": norm_usd_inr,
}


async def fetch_mood_inputs(adapter: object) -> dict[str, float | None]:
    """
    Fetch macro signals via the adapter and normalise them into the 11-key
    dict expected by ``compute_mood``.

    Whichever of the normalisable signals the active provider returns are mapped
    to [0, 1] (Yahoo primary supplies nifty_trend, india_vix, global_indices,
    us_bond_10y, oil_brent, usd_inr; the NSE fallback supplies nifty_trend,
    india_vix, market_breadth, put_call_ratio). Any signal the provider omits
    stays None and is dropped by compute_mood (never imputed).

    On AllProvidersFailedError or any unexpected error the all-None dict is
    returned — compute_and_store handles this as the data_unavailable path
    (graceful degradation, no exception propagates).

    ``adapter`` is typed as ``object`` to avoid a hard import of
    MarketDataAdapter here; duck-typing is fine since tests can pass any
    object with an async ``.fetch(request)`` method.
    """
    inputs: dict[str, float | None] = {k: None for k in WEIGHTS}

    try:
        event = await adapter.fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))
    except AllProvidersFailedError as exc:
        logger.warning("mood signals: all macro providers failed — %s", exc)
        return inputs
    except Exception as exc:  # noqa: BLE001 — best-effort, never crashes the task
        logger.warning("mood signals: unexpected error fetching macro signals — %s", exc)
        return inputs

    if not isinstance(event, MacroSignalReceived):
        logger.warning("mood signals: unexpected event type %s", type(event))
        return inputs

    raw_signals: dict = event.signals
    for key, normalizer in _NORMALIZERS.items():
        raw = raw_signals.get(key)
        if raw is not None:
            try:
                inputs[key] = normalizer(float(raw))  # type: ignore[operator]
            except Exception as exc:  # noqa: BLE001
                logger.warning("mood signals: normalisation failed for %s: %s", key, exc)

    logger.info(
        "mood signals: normalised %d/%d macro signals",
        sum(1 for k in _NORMALIZERS if inputs.get(k) is not None),
        len(_NORMALIZERS),
    )
    return inputs
