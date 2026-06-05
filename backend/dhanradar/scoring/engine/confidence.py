"""
DhanRadar — confidence model (spec §5).

confidence (0–1) = 0.30*freshness + 0.25*coverage + 0.20*factor_agreement
                 + 0.15*retrieval_relevance + 0.10*model_signal   (weights from config)

Then structural rules (spec §5.2), all fail-safe (only ever LOWER confidence):
  * partial_coverage ⇒ capped at `medium` (≤0.69)
  * illiquid ⇒ capped at `low` (≤0.49)
  * stale ⇒ reduced (×0.9)
  * high-confidence guard: >0.70 requires ≥3 contributing signals AND
    high-reliability sources — else capped to 0.69 (band = medium)
  * floor: <0.30 ⇒ band = insufficient_data (caller refuses to label)
"""

from __future__ import annotations

import statistics
from typing import Optional

from dhanradar.scoring.engine.schemas import Axis, ConfidenceBand

_HIGH = 0.70
_MEDIUM = 0.50
_FLOOR = 0.30


def factor_agreement(axis_scores: dict[Axis, Optional[float]]) -> float:
    """1 − normalized dispersion of the present axis scores (spec §5)."""
    present = [s for s in axis_scores.values() if s is not None]
    if len(present) < 2:
        return 1.0  # single axis cannot disagree with itself
    dispersion = statistics.pstdev(present) / 50.0  # 0–100 scale, 50 = median
    return max(0.0, 1.0 - min(dispersion, 1.0))


def compute_confidence(
    *,
    freshness: float,
    coverage: float,
    agreement: float,
    retrieval_relevance: float,
    model_signal: float,
    weights: dict[str, float],
) -> float:
    raw = (
        weights["freshness"] * _c01(freshness)
        + weights["coverage"] * _c01(coverage)
        + weights["factor_agreement"] * _c01(agreement)
        + weights["retrieval_relevance"] * _c01(retrieval_relevance)
        + weights["model_signal"] * _c01(model_signal)
    )
    return _c01(raw)


def apply_structural_caps(
    confidence: float,
    *,
    partial_coverage: bool,
    liquid: bool,
    stale: bool,
    contributing_count: int,
    sources_reliable: bool,
) -> float:
    c = confidence
    if stale:
        c *= 0.9
    if partial_coverage:
        c = min(c, 0.69)  # cap at medium
    if not liquid:
        c = min(c, 0.49)  # cap at low
    # High-confidence guard: structurally prevent high-confidence low-evidence.
    if c > _HIGH and (contributing_count < 3 or not sources_reliable):
        c = 0.69
    return _c01(c)


def band_for(confidence: float) -> ConfidenceBand:
    if confidence < _FLOOR:
        return ConfidenceBand.insufficient_data
    if confidence >= _HIGH:
        return ConfidenceBand.high
    if confidence >= _MEDIUM:
        return ConfidenceBand.medium
    return ConfidenceBand.low


def _c01(x: float) -> float:
    return min(max(float(x), 0.0), 1.0)
