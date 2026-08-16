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


def norm_nifty_trend(dev_pct_vs_125dma: float) -> float:
    """
    Map NIFTY 50 momentum — the % deviation of the latest price from its
    125-day moving average — to [0, 1] (industry-standard fear/greed momentum
    component; mood_v2, MOOD_IMPROVEMENT_PLAN §11).

    Formula: clamp((dev + 6) / 12, 0, 1)
    - +6 % above the 125-DMA → 1.0 (strong bullish momentum)
    - −6 % below the 125-DMA → 0.0 (strong bearish momentum)
    - on the 125-DMA → 0.5 (flat/neutral)
    """
    return _clamp((dev_pct_vs_125dma + 6.0) / 12.0)


def norm_india_vix(dev_pct_vs_50dma: float) -> float:
    """
    Map India VIX RELATIVE to its own 50-day moving average to [0, 1] —
    volatility above its recent norm = rising fear → low value (mood_v2).
    A fixed-level anchor (the v1 formula) sat at ~0.5 whenever VIX hovered
    near 20 regardless of regime; the relative form moves with the market.

    Formula: clamp((25 − dev) / 50, 0, 1)
    - VIX 25 % ABOVE its 50-DMA → 0.0 (fear spike)
    - VIX 25 % BELOW its 50-DMA → 1.0 (unusually calm = greed zone)
    - VIX on its 50-DMA → 0.5
    """
    return _clamp((25.0 - dev_pct_vs_50dma) / 50.0)


def norm_market_breadth(ratio: float) -> float:
    """
    Market breadth = advances / (advances + declines).

    Already in [0, 1]; 1 = all advancing (pure bullish).
    Clamped defensively in case of rounding.
    """
    return _clamp(ratio)


def norm_put_call_ratio(pcr_5d_avg: float) -> float:
    """
    Map the Put-Call Ratio — as a 5-day average (industry standard; a
    single-day PCR is noise-dominated) — to [0, 1]. High PCR = hedging /
    fear → low value. When fewer than 5 days of history exist the caller
    passes the mean of the days available (≥ 1 = today; documented
    short-history fallback, mood_v2 plan §11.3).

    Formula: clamp((1.3 − pcr) / 0.6, 0, 1)
    - PCR = 0.7 → 1.0 (low PCR = greed)
    - PCR = 1.3 → 0.0 (high PCR = fear)
    - PCR = 1.0 → 0.5
    """
    return _clamp((1.3 - pcr_5d_avg) / 0.6)


def norm_global_indices(dev_pct_vs_125dma: float) -> float:
    """
    Map the global benchmark's (S&P 500) momentum — % deviation of the latest
    price from its 125-day moving average — to [0, 1]; same risk-on/off
    convention and scale as NIFTY momentum (mood_v2).

    Formula: clamp((dev + 6) / 12, 0, 1)  (+6 % → 1.0, −6 % → 0.0, on-MA → 0.5)
    """
    return _clamp((dev_pct_vs_125dma + 6.0) / 12.0)


def norm_us_bond_10y(dev_pp_vs_50dma: float) -> float:
    """
    Map the US 10-year Treasury yield's deviation — in percentage POINTS from
    its own 50-day moving average — to [0, 1] (mood_v2). Yields rising above
    their recent norm = tightening global liquidity → risk-off; falling below
    = easing → risk-on. The v1 fixed 4 %-anchor barely moved day to day.

    Formula: clamp((0.5 − dev) / 1.0, 0, 1)
    - 0.5 pp ABOVE the 50-DMA → 0.0 (tightening = fear)
    - 0.5 pp BELOW the 50-DMA → 1.0 (easing = greed)
    - on the 50-DMA → 0.5
    """
    return _clamp((0.5 - dev_pp_vs_50dma) / 1.0)


def norm_oil_brent(dev_pct_vs_50dma: float) -> float:
    """
    Map Brent crude's % deviation from its own 50-day moving average to
    [0, 1] (mood_v2). India is a large net oil importer, so oil spiking above
    its recent norm = trade-deficit / inflation pressure (fear); oil sliding
    below it = tailwind (greed). The v1 fixed $80 anchor was static ballast.

    Formula: clamp((15 − dev) / 30, 0, 1)
    - 15 % ABOVE the 50-DMA → 0.0 (importer stress = fear)
    - 15 % BELOW the 50-DMA → 1.0 (tailwind = greed)
    - on the 50-DMA → 0.5
    """
    return _clamp((15.0 - dev_pct_vs_50dma) / 30.0)


def norm_usd_inr(dev_pct_vs_50dma: float) -> float:
    """
    Map USD/INR's % deviation from its own 50-day moving average to [0, 1]
    (mood_v2). The pair ABOVE its recent norm = INR weaker than trend =
    outflows (fear); BELOW it = INR stronger than trend = inflows (greed).
    The v1 one-day % change (typical day ±0.2 %) pinned this signal at ~0.5.

    Formula: clamp((2 − dev) / 4, 0, 1)
    - USD/INR 2 % ABOVE its 50-DMA → 0.0 (fear)
    - USD/INR 2 % BELOW its 50-DMA → 1.0 (greed)
    - on the 50-DMA → 0.5
    """
    return _clamp((2.0 - dev_pct_vs_50dma) / 4.0)


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


# Institutional net-flow saturation thresholds (₹Cr) — mood_v2: the input is the
# 5-DAY MEAN of daily net flows (rolling Redis history, plan §11.3), not a single
# day. A sustained streak averaging this magnitude maps to ≈0.88 (greed) /
# ≈0.12 (fear) via tanh; larger streaks asymptote toward 1 / 0 without pegging.
#
# FII vs DII are differentiated: a sustained FII streak runs larger (±4–6k ₹Cr/day
# over a week is a strong conviction move) than the steadier SIP-driven DII flow.
# The v1 single-day constants (15k/10k) mapped a normal ±3k ₹Cr day to ~0.52 and
# were the flows half of the structural-neutral bug (plan §11.1).
#
# When history is short (< 5 entries, e.g. after a Redis restart) the caller
# passes the mean of the days available — same formula, graceful convergence.
_FII_FLOW_SATURATION_CR = 4_000.0
_DII_FLOW_SATURATION_CR = 3_000.0


def norm_fii_flows(mean_flow_cr_5d: float) -> float:
    """
    Map the FII 5-day mean net cash-market flow (₹Cr) to [0, 1]; 1 = greed.

    Each day's net = buy_amount − sell_amount; the input is the mean of the
    last ≤ 5 daily nets. Sustained inflow → toward 1, sustained outflow →
    toward 0. Formula: clamp(0.5 + 0.5·tanh(mean / S)), S = 4,000 ₹Cr.
    - 0 ₹Cr mean       → 0.50 (neutral)
    - +4,000 ₹Cr mean  → ≈0.88 (greed)
    - −4,000 ₹Cr mean  → ≈0.12 (fear)
    """
    return _clamp(0.5 + 0.5 * math.tanh(mean_flow_cr_5d / _FII_FLOW_SATURATION_CR))


def norm_dii_flows(mean_flow_cr_5d: float) -> float:
    """
    Map the DII 5-day mean net cash-market flow (₹Cr) to [0, 1]; 1 = greed.

    Same convention/formula as norm_fii_flows with the DII saturation constant
    (S = 3,000 ₹Cr): clamp(0.5 + 0.5·tanh(mean / S)); 0 ₹Cr → 0.50.
    """
    return _clamp(0.5 + 0.5 * math.tanh(mean_flow_cr_5d / _DII_FLOW_SATURATION_CR))


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
    nifty_trend, india_vix, global_indices, us_bond_10y, oil_brent, usd_inr as
    MA-deviation raws — mood_v2; the NSE fallback supplies market_breadth and
    put_call_ratio only, its quote endpoints can't compute MA deviations).

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
