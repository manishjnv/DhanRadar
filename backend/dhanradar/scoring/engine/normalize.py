"""
DhanRadar — normalization + aggregation (spec §3.1 / §3.2).

Pure functions (no I/O), so they are golden-set testable. Two layers:

  * Sub-factor normalization helpers (winsorize → z-score → clamp → map to 0–100)
    for upstream pipelines that turn raw values into the 0–100 inputs the engine
    consumes.
  * Aggregation the engine itself uses: per-axis weighted mean with MISSING-DATA
    drop-and-renormalize (never impute), per-axis coverage, and the composite
    that reweights the remaining axes proportionally when a whole axis is
    uncomputable (flagging partial_coverage).
"""

from __future__ import annotations

import statistics

from dhanradar.scoring.engine.schemas import Axis, SubFactor

# ---------------------------------------------------------------------------
# Sub-factor normalization helpers (spec §3.1)
# ---------------------------------------------------------------------------

def winsorize(values: list[float], p_low: float = 1.0, p_high: float = 99.0) -> list[float]:
    """Clip values to the [p_low, p_high] percentiles of the peer set."""
    if not values:
        return []
    s = sorted(values)
    lo = _percentile(s, p_low)
    hi = _percentile(s, p_high)
    return [min(max(v, lo), hi) for v in values]


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        raise ValueError("empty")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def zscore(x: float, mean: float, std: float) -> float:
    if std == 0:
        return 0.0
    return (x - mean) / std


def clamp(z: float, lo: float = -3.0, hi: float = 3.0) -> float:
    return min(max(z, lo), hi)


def map_to_100(z: float, direction: int = 1) -> float:
    """Map a clamped z-score to 0–100 (50 = sector median). dir = +1 or -1."""
    return 50.0 + (z * (50.0 / 3.0)) * direction


def normalize_subfactor(x: float, peer_values: list[float], direction: int = 1) -> float:
    """Full pipeline: winsorize peer set → z-score x → clamp → map to 0–100."""
    w = winsorize(peer_values)
    mean = statistics.fmean(w)
    std = statistics.pstdev(w) if len(w) > 1 else 0.0
    return map_to_100(clamp(zscore(x, mean, std)), direction)


# ---------------------------------------------------------------------------
# Aggregation used by the engine (spec §3.2 missing-data handling)
# ---------------------------------------------------------------------------

def aggregate_axis(subfactors: list[SubFactor]) -> tuple[float | None, float]:
    """Return (axis_score 0–100 | None, coverage_fraction 0–1).

    Missing (value=None) sub-factors are DROPPED and the remaining within-axis
    weights renormalized — never imputed. Coverage = present_weight / total_weight.
    All missing → (None, 0.0) (axis uncomputable)."""
    total_w = sum(sf.weight for sf in subfactors)
    present = [sf for sf in subfactors if sf.value is not None]
    present_w = sum(sf.weight for sf in present)
    if present_w <= 0 or total_w <= 0:
        return None, 0.0
    score = sum(sf.value * sf.weight for sf in present) / present_w  # type: ignore[operator]
    coverage = present_w / total_w
    return score, coverage


def composite(
    axis_scores: dict[Axis, float | None],
    axis_weights: dict[Axis, float],
) -> tuple[int | None, bool, list[Axis]]:
    """Weighted composite over PRESENT axes, reweighted proportionally.

    Returns (unified_score 0–100 int | None, partial_coverage, present_axes).
    A whole-axis None drops that axis and renormalizes the remaining axis
    weights (spec §3.2.4) and sets partial_coverage=True. No present axis → None."""
    present = {a: s for a, s in axis_scores.items() if s is not None}
    if not present:
        return None, True, []
    w_present = sum(axis_weights[a] for a in present)
    if w_present <= 0:
        return None, True, []
    raw = sum(present[a] * axis_weights[a] for a in present) / w_present
    partial = len(present) < len(axis_scores)
    return round(raw), partial, list(present.keys())
