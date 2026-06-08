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


# ---------------------------------------------------------------------------
# Adapter-based fetch
# ---------------------------------------------------------------------------

_NORMALIZERS: dict[str, object] = {
    "nifty_trend": norm_nifty_trend,
    "india_vix": norm_india_vix,
    "market_breadth": norm_market_breadth,
    "put_call_ratio": norm_put_call_ratio,
}


async def fetch_mood_inputs(adapter: object) -> dict[str, float | None]:
    """
    Fetch macro signals via the adapter and normalise them into the 11-key
    dict expected by ``compute_mood``.

    The four signals fetched (nifty_trend, india_vix, market_breadth,
    put_call_ratio) are normalised to [0, 1]; the remaining 7 keys stay None.

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
        "mood signals: normalised %d/4 macro signals",
        sum(1 for k in _NORMALIZERS if inputs.get(k) is not None),
    )
    return inputs
