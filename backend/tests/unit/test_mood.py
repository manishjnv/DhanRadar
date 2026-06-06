"""
Unit tests for the Mood Compass compute module (pure, no DB, no Redis).

Covered:
  * WEIGHTS — 11 keys, sums to 1.0 within tolerance.
  * compute_mood(all-None) → None.
  * All inputs 0.9 → extreme_greed, correct aggregates.
  * All inputs 0.1 → extreme_fear.
  * All inputs 0.5 → neutral.
  * regime_for() bucket boundaries (19/20/40/59/60/79/80/100).
  * Degraded: <7 present inputs → data_quality="degraded", commentary_allowed=False,
    confidence_score ≤ 0.40.
  * Contributing/contradicting factor separation.
  * post_public_card() returns False when TELEGRAM_PUBLIC_CHANNEL_ID is empty.
"""

from __future__ import annotations

import pytest

from dhanradar.mood.compute import WEIGHTS, compute_mood, regime_for

# ---------------------------------------------------------------------------
# 1. WEIGHTS integrity
# ---------------------------------------------------------------------------


def test_weights_key_count():
    """WEIGHTS must have exactly 11 keys (architecture Mood Compass pipeline)."""
    assert len(WEIGHTS) == 11, f"Expected 11 WEIGHTS keys, got {len(WEIGHTS)}: {list(WEIGHTS)}"


def test_weights_sum_to_one():
    """Sum of all 11 weights must equal 1.0 within floating-point tolerance."""
    total = sum(WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9, f"WEIGHTS sum = {total}, expected 1.0"


# ---------------------------------------------------------------------------
# 2. All-None → None
# ---------------------------------------------------------------------------


def test_compute_mood_all_none_returns_none():
    """When every input is None compute_mood must return None (all-missing path)."""
    inputs = {k: None for k in WEIGHTS}
    result = compute_mood(inputs)
    assert result is None


# ---------------------------------------------------------------------------
# 3. All 0.9 → extreme_greed
# ---------------------------------------------------------------------------


def test_compute_mood_all_greed():
    """All inputs = 0.9 → extreme_greed regime, mood_score ≈ 90.0, 11 inputs,
    confidence_band 'high', data_quality 'ok', commentary_allowed True."""
    inputs = {k: 0.9 for k in WEIGHTS}
    result = compute_mood(inputs)
    assert result is not None
    assert result.regime == "extreme_greed"
    assert abs(result.mood_score - 90.0) < 0.01, f"mood_score={result.mood_score}"
    assert result.inputs_available == 11
    assert result.confidence_band == "high"
    assert result.data_quality == "ok"
    assert result.commentary_allowed is True


# ---------------------------------------------------------------------------
# 4. All 0.1 → extreme_fear
# ---------------------------------------------------------------------------


def test_compute_mood_all_fear():
    """All inputs = 0.1 → extreme_fear regime, mood_score ≈ 10.0."""
    inputs = {k: 0.1 for k in WEIGHTS}
    result = compute_mood(inputs)
    assert result is not None
    assert result.regime == "extreme_fear"
    assert abs(result.mood_score - 10.0) < 0.01, f"mood_score={result.mood_score}"


# ---------------------------------------------------------------------------
# 5. All 0.5 → neutral
# ---------------------------------------------------------------------------


def test_compute_mood_all_neutral():
    """All inputs = 0.5 → neutral regime, mood_score ≈ 50.0."""
    inputs = {k: 0.5 for k in WEIGHTS}
    result = compute_mood(inputs)
    assert result is not None
    assert result.regime == "neutral"
    assert abs(result.mood_score - 50.0) < 0.01, f"mood_score={result.mood_score}"


# ---------------------------------------------------------------------------
# 6. regime_for() bucket boundaries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "score, expected",
    [
        (0.0, "extreme_fear"),
        (19.0, "extreme_fear"),
        (20.0, "fear"),
        (39.0, "fear"),
        (40.0, "neutral"),
        (59.0, "neutral"),
        (60.0, "greed"),
        (79.0, "greed"),
        (80.0, "extreme_greed"),
        (100.0, "extreme_greed"),
    ],
)
def test_regime_for_boundaries(score: float, expected: str):
    """regime_for must map every bucket boundary to its correct label."""
    assert regime_for(score) == expected, f"regime_for({score}) = {regime_for(score)!r}, want {expected!r}"


# ---------------------------------------------------------------------------
# 7. Degraded: <7 present inputs
# ---------------------------------------------------------------------------


def test_compute_mood_degraded():
    """Exactly 3 present inputs → data_quality='degraded', commentary_allowed=False,
    confidence_score ≤ 0.40, inputs_available=3."""
    inputs: dict = {k: None for k in WEIGHTS}
    inputs["nifty_trend"] = 0.8
    inputs["market_breadth"] = 0.7
    inputs["india_vix"] = 0.6

    result = compute_mood(inputs)
    assert result is not None
    assert result.data_quality == "degraded"
    assert result.commentary_allowed is False
    assert result.confidence_score <= 0.40, f"confidence_score={result.confidence_score}"
    assert result.inputs_available == 3


# ---------------------------------------------------------------------------
# 8. Contributing vs contradicting factors
# ---------------------------------------------------------------------------


def test_compute_mood_contributing_contradicting():
    """In a mostly-greedy snapshot (all inputs 0.9 except india_vix=0.1):
    - 'india_vix' must appear in contradicting_factors.
    - Other inputs must appear in contributing_factors.
    """
    inputs = {k: 0.9 for k in WEIGHTS}
    inputs["india_vix"] = 0.1  # lone bearish signal

    result = compute_mood(inputs)
    assert result is not None
    assert "india_vix" in result.contradicting_factors, (
        f"Expected india_vix in contradicting_factors, got {result.contradicting_factors}"
    )
    # All 10 other keys should appear in contributing_factors
    for k in WEIGHTS:
        if k != "india_vix":
            assert k in result.contributing_factors, (
                f"Expected {k!r} in contributing_factors, got {result.contributing_factors}"
            )


# ---------------------------------------------------------------------------
# 9. post_public_card returns False when channel ID is empty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_public_card_no_channel_id(monkeypatch):
    """post_public_card must return False (no-op) when TELEGRAM_PUBLIC_CHANNEL_ID is
    empty — ensures the notification stub does not raise or attempt a network call."""
    from dhanradar.config import settings
    from dhanradar.notifications.service import post_public_card

    # Patch the settings attribute directly to ensure the empty-channel path is taken.
    object.__setattr__(settings, "TELEGRAM_PUBLIC_CHANNEL_ID", "")

    result = await post_public_card("Market Mood today: neutral (medium confidence).")
    assert result is False


# --- Phase: governance fixes (floor coercion + bucket-gap) --------------------

def test_regime_for_non_integer_scores_have_no_gap():
    # Contiguous buckets — a non-integer score between old integer ranges must NOT
    # fall through to neutral (the pre-fix bug).
    assert regime_for(19.5) == "extreme_fear"
    assert regime_for(39.9) == "fear"
    assert regime_for(59.5) == "neutral"
    assert regime_for(79.99) == "greed"
    assert regime_for(80.0) == "extreme_greed"
    assert regime_for(0.0) == "extreme_fear"
    assert regime_for(100.0) == "extreme_greed"


def test_sub_030_confidence_coerces_regime_to_insufficient_data():
    # A single low-weight signal → confidence < 0.30 → the served regime is refused
    # (insufficient_data), not a confident directional bucket (non-neg #4).
    r = compute_mood({"news_sentiment": 0.95})  # weight 0.06 → confidence 0.06
    assert r is not None
    assert r.confidence_score < 0.30
    assert r.regime == "insufficient_data"
    assert r.confidence_band == "insufficient_data"
    assert r.commentary_allowed is False
    # The server-side numeric is still computed (just never asserted as a regime).
    assert r.mood_score is not None


def test_at_floor_confidence_keeps_directional_regime():
    # ≥0.30 confidence (3 mid-weight inputs) keeps a real regime (only <0.30 refuses).
    r = compute_mood({"nifty_trend": 0.8, "market_breadth": 0.8, "india_vix": 0.8})
    assert r is not None
    assert r.confidence_score >= 0.30
    assert r.regime in {"greed", "extreme_greed", "neutral"}
    assert r.regime != "insufficient_data"
