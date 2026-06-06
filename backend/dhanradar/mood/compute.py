"""
DhanRadar — Mood Compass pure compute (architecture Mood Compass pipeline).

Pure + unit-testable: takes the 11 pre-normalized (0–1, 1 = greed/bullish) inputs
(missing → None) and produces the regime, server-side numerics, confidence band, and
the contributing/contradicting evidence. No DB/Redis/AI here.

Weighted score = Σ(value·weight over PRESENT inputs) / Σ(present weight) · 100, then
bucketed. Missing inputs are dropped (never imputed) and decrement `inputs_available`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# 11 inputs/weights — architecture Mood Compass pipeline (Σ = 1.00).
WEIGHTS: dict[str, float] = {
    "nifty_trend": 0.15,
    "market_breadth": 0.12,
    "india_vix": 0.10,
    "fii_flows": 0.10,
    "global_indices": 0.10,
    "dii_flows": 0.08,
    "us_bond_10y": 0.08,
    "oil_brent": 0.07,
    "usd_inr": 0.07,
    "put_call_ratio": 0.07,
    "news_sentiment": 0.06,
}

# Regime buckets by 0–100 score (architecture: extreme_fear 0-19 / fear 20-39 /
# neutral 40-59 / greed 60-79 / extreme_greed 80-100). Implemented with contiguous
# half-open upper bounds so a NON-integer score (e.g. 19.5) cannot fall into a gap.
_BUCKET_BOUNDS = [(20.0, "extreme_fear"), (40.0, "fear"), (60.0, "neutral"), (80.0, "greed")]

# Refuse floor (non-neg #4): below this confidence the regime is not asserted — the
# served regime is coerced to `insufficient_data` (band already degrades there too).
_REFUSE_CONFIDENCE = 0.30
INSUFFICIENT = "insufficient_data"

# Below this many present inputs, the snapshot is degraded: confidence capped and
# AI commentary withheld (architecture failure modes: inputs_available < 7).
_DEGRADED_BELOW = 7
_DEGRADED_CONF_CAP = 0.40


@dataclass(frozen=True)
class MoodResult:
    mood_score: float           # 0–100, server-side
    regime: str                 # bucket label (public)
    confidence_score: float     # 0–1, server-side
    confidence_band: str        # high|medium|low|insufficient_data (public)
    inputs_available: int
    data_quality: str           # ok | degraded
    input_vector: dict          # the present normalized inputs (server-side evidence)
    contributing_factors: list = field(default_factory=list)
    contradicting_factors: list = field(default_factory=list)
    commentary_allowed: bool = True


def regime_for(score: float) -> str:
    """Map a 0–100 score to its regime bucket. Half-open upper bounds → no gaps for
    non-integer scores; 80–100 is the final (extreme_greed) bucket."""
    for upper, name in _BUCKET_BOUNDS:
        if score < upper:
            return name
    return "extreme_greed"


def _band_for(conf: float) -> str:
    if conf >= 0.70:
        return "high"
    if conf >= 0.40:
        return "medium"
    if conf >= 0.30:
        return "low"
    return "insufficient_data"


def compute_mood(inputs: dict[str, Optional[float]]) -> Optional[MoodResult]:
    """Compute the regime snapshot. Returns None if ALL inputs are missing (the
    caller skips + retries — architecture all-missing failure mode)."""
    present = {
        k: float(v)
        for k, v in inputs.items()
        if k in WEIGHTS and v is not None
    }
    inputs_available = len(present)
    if inputs_available == 0:
        return None

    present_weight = sum(WEIGHTS[k] for k in present)
    weighted = sum(present[k] * WEIGHTS[k] for k in present)
    mood_score = round((weighted / present_weight) * 100.0, 2)
    regime = regime_for(mood_score)

    # Confidence = coverage (Σ present weight, since Σ all = 1.0). Degraded snapshots
    # (<7 inputs) are capped and flagged; commentary is then withheld.
    confidence = present_weight
    data_quality = "ok"
    commentary_allowed = True
    if inputs_available < _DEGRADED_BELOW:
        confidence = min(confidence, _DEGRADED_CONF_CAP)
        data_quality = "degraded"
        commentary_allowed = False
    confidence = round(confidence, 4)
    if confidence < 0.40:
        commentary_allowed = False

    # Refuse floor (non-neg #4): below 0.30 confidence the regime is NOT asserted —
    # coerce the served label to `insufficient_data` so a snapshot built from a few
    # low-weight signals cannot broadcast a confident directional regime (the band
    # already degrades here; this degrades the LABEL too, matching the rating engine).
    if confidence < _REFUSE_CONFIDENCE:
        regime = INSUFFICIENT
        commentary_allowed = False

    # Contributing vs contradicting: each present input either agrees with the regime
    # direction (>0.5 when greedy, <0.5 when fearful) or disagrees (disagreement
    # disclosure is mandatory — architecture). Stored greed-weight-ordered.
    greedy = mood_score >= 50.0
    contributing, contradicting = [], []
    for k, v in sorted(present.items(), key=lambda kv: -WEIGHTS[kv[0]]):
        agrees = (v >= 0.5) if greedy else (v < 0.5)
        (contributing if agrees else contradicting).append(k)

    return MoodResult(
        mood_score=mood_score,
        regime=regime,
        confidence_score=confidence,
        confidence_band=_band_for(confidence),
        inputs_available=inputs_available,
        data_quality=data_quality,
        input_vector=present,
        contributing_factors=contributing,
        contradicting_factors=contradicting,
        commentary_allowed=commentary_allowed,
    )
