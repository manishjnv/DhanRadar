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
import math

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


# News-sentiment tone → [0, 1] (1 = greed/bullish). The tone is a DESCRIPTIVE
# 5-point label produced by the governed AI gateway (mood/news_sentiment.py) from
# recent headlines — never a raw number from the model. This map turns the
# descriptive label into the engine's 0–1 scale. Unknown labels → None (signal
# absent; never imputed). news_sentiment is NOT registered in _NORMALIZERS below
# because it is AI-derived, not adapter-sourced — it is injected into the inputs
# dict by the mood task after fetch_mood_inputs runs.
_NEWS_TONE_SCORES: dict[str, float] = {
    "negative": 0.1,
    "slightly_negative": 0.3,
    "neutral": 0.5,
    "slightly_positive": 0.7,
    "positive": 0.9,
}


def norm_news_sentiment(tone: str) -> float | None:
    """Map a descriptive news-sentiment tone label to [0, 1]; 1 = greed/bullish.

    negative → 0.1, slightly_negative → 0.3, neutral → 0.5,
    slightly_positive → 0.7, positive → 0.9. Returns None for any unrecognised
    label so the engine drops the signal rather than imputing a value.
    """
    return _NEWS_TONE_SCORES.get(tone)


# Institutional net-flow saturation thresholds (₹Cr). A daily net flow of this
# magnitude maps to ≈0.88 (greed) / ≈0.12 (fear) via tanh; larger days asymptote
# toward 1 / 0 without ever pegging.
#
# FII vs DII are differentiated: FII cash-market days run LARGER and more volatile
# (single-day swings routinely ±10–20k ₹Cr), so FII needs a higher saturation so a
# big-but-ordinary FII day does not peg the signal; DII flows (SIP-driven, steadier)
# saturate sooner. Equal constants over-weighted ordinary DII days and under-reacted
# to large FII days.
#
# PROVISIONAL — normalization curve pending scoring/compliance gate. The dig
# (docs/research/mood-data-sourcing-2026-06-21.md §2) recommends scaling net flow
# against a ROLLING WINDOW rather than a fixed constant; that refinement is a
# Tier-C scoring decision deferred to the gate. These fixed-threshold tanh values
# are a documented first-pass only.
_FII_FLOW_SATURATION_CR = 15_000.0
_DII_FLOW_SATURATION_CR = 10_000.0


def norm_fii_flows(net_flow_cr: float) -> float:
    """
    Map FII daily net cash-market flow (₹Cr) to [0, 1]; 1 = greed/bullish.

    net_flow_cr = buy_amount − sell_amount. Net inflow (buying) → toward 1,
    net outflow (selling) → toward 0. Formula: clamp(0.5 + 0.5·tanh(flow / S))
    with S = 15,000 ₹Cr (FII days run larger than DII; see saturation note above).
    - 0 ₹Cr        → 0.50 (neutral)
    - +15,000 ₹Cr  → ≈0.88 (greed)
    - −15,000 ₹Cr  → ≈0.12 (fear)

    PROVISIONAL — normalization curve pending scoring/compliance gate.
    """
    return _clamp(0.5 + 0.5 * math.tanh(net_flow_cr / _FII_FLOW_SATURATION_CR))


def norm_dii_flows(net_flow_cr: float) -> float:
    """
    Map DII daily net cash-market flow (₹Cr) to [0, 1]; 1 = greed/bullish.

    Same convention/formula as norm_fii_flows with the DII saturation constant:
    net inflow → toward 1, net outflow → toward 0,
    clamp(0.5 + 0.5·tanh(flow / S)); 0 ₹Cr → 0.50.

    PROVISIONAL — normalization curve pending scoring/compliance gate.
    """
    return _clamp(0.5 + 0.5 * math.tanh(net_flow_cr / _DII_FLOW_SATURATION_CR))


# ---------------------------------------------------------------------------
# Adapter-based fetch
# ---------------------------------------------------------------------------

_NORMALIZERS: dict[str, object] = {
    "nifty_trend": norm_nifty_trend,
    "india_vix": norm_india_vix,
    "market_breadth": norm_market_breadth,
    "put_call_ratio": norm_put_call_ratio,
    "fii_flows": norm_fii_flows,
    "dii_flows": norm_dii_flows,
    "global_indices": norm_global_indices,
    "us_bond_10y": norm_us_bond_10y,
    "oil_brent": norm_oil_brent,
    "usd_inr": norm_usd_inr,
}


def _extract_raw_signals(event: object) -> dict:
    """Return the raw signals dict from a MacroSignalReceived, or {} for any
    other / unexpected event type."""
    if not isinstance(event, MacroSignalReceived):
        logger.warning("mood signals: unexpected event type %s", type(event))
        return {}
    return dict(event.signals or {})


async def _fetch_raw_from_adapter(adapter: object) -> dict:
    """Fetch MACRO_SIGNAL from one adapter and return its raw signals dict, or
    {} on AllProvidersFailedError / any unexpected error (best-effort, never
    raises). ``adapter`` is duck-typed: any object with an async ``.fetch``."""
    try:
        event = await adapter.fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))
    except AllProvidersFailedError as exc:
        logger.warning("mood signals: all macro providers failed — %s", exc)
        return {}
    except Exception as exc:  # noqa: BLE001 — best-effort, never crashes the task
        logger.warning("mood signals: unexpected error fetching macro signals — %s", exc)
        return {}
    return _extract_raw_signals(event)


async def fetch_mood_inputs(
    adapter: object,
    *,
    supplemental_adapters: list | None = None,
) -> dict[str, float | None]:
    """
    Fetch macro signals via the adapter(s) and normalise them into the 11-key
    dict expected by ``compute_mood``.

    The PRIMARY adapter runs the MACRO_SIGNAL ladder (Yahoo primary supplies
    nifty_trend, india_vix, global_indices, us_bond_10y, oil_brent, usd_inr; the
    NSE fallback supplies nifty_trend, india_vix, market_breadth, put_call_ratio).

    Each SUPPLEMENTAL adapter is fetched ADDITIVELY and merged in — used for the
    Upstox Analytics provider, which contributes fii_flows / dii_flows /
    put_call_ratio that no Yahoo/NSE provider supplies. This is deliberately NOT
    a ladder entry: the ladder is a fallback chain (first success wins), so an
    Upstox ladder entry would COMPETE with Yahoo instead of adding to it. A
    supplemental only fills a signal the primary did not already set (the primary
    wins the rare overlap, e.g. PCR from the NSE fallback). All access stays via
    adapters, so module isolation is preserved.

    Whichever signals are present are mapped to [0, 1]; any signal omitted by every
    adapter stays None and is dropped by compute_mood (never imputed). If every
    adapter yields nothing, the all-None dict is returned — compute_and_store
    handles that as the data_unavailable path (graceful, no exception propagates).
    """
    inputs: dict[str, float | None] = {k: None for k in WEIGHTS}

    raw_signals: dict = await _fetch_raw_from_adapter(adapter)
    for supplemental in supplemental_adapters or []:
        extra = await _fetch_raw_from_adapter(supplemental)
        for key, value in extra.items():
            raw_signals.setdefault(key, value)  # primary wins on overlap

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
