"""
Unit tests for the numberless driver-bar magnitude tiers (mood).

Covers:
  - factor_tier: a high-contribution factor → "strong", a tiny one → "slight",
    a mid one → "moderate"; a missing value → "slight" (safe fallback)
  - the public MoodPublic factor objects carry ONLY {label, tier} — never a
    numeric contribution / weight / value (non-neg #2)
"""

from __future__ import annotations

from dhanradar.mood.compute import FACTOR_TIERS, factor_tier
from dhanradar.mood.schemas import MoodFactor, MoodPublic
from dhanradar.mood.service import _factor_objs


def test_factor_tier_buckets_by_strength():
    # nifty_trend weight 0.15: strongly directional value → strong.
    assert factor_tier(0.95, 0.15) == "strong"
    # mid deviation on the top-weight factor → moderate.
    assert factor_tier(0.65, 0.15) == "moderate"
    # tiny deviation / low weight → slight.
    assert factor_tier(0.52, 0.06) == "slight"
    # exactly neutral contributes nothing → slight.
    assert factor_tier(0.5, 0.15) == "slight"
    # missing value → safe lowest tier.
    assert factor_tier(None, 0.15) == "slight"
    # symmetric for counterweights (bearish value, high weight) → strong.
    assert factor_tier(0.05, 0.15) == "strong"


def test_factor_tier_only_returns_known_tiers():
    for value in (0.0, 0.1, 0.5, 0.7, 0.95, 1.0, None):
        assert factor_tier(value, 0.15) in FACTOR_TIERS
        assert factor_tier(value, 0.06) in FACTOR_TIERS


def test_factor_objs_shape_and_tiers():
    keys = ["nifty_trend", "news_sentiment"]
    iv = {"nifty_trend": 0.95, "news_sentiment": 0.52}
    objs = _factor_objs(keys, iv)
    assert objs[0] == {"label": "Nifty Trend", "tier": "strong"}
    assert objs[1] == {"label": "News Sentiment", "tier": "slight"}
    # missing input_vector → still builds, tiers fall back safely.
    fallback = _factor_objs(["india_vix"], None)
    assert fallback[0]["label"] == "India VIX"
    assert fallback[0]["tier"] in FACTOR_TIERS


def test_mood_public_factor_objects_carry_no_numeric():
    """The serialized public payload exposes ONLY {label, tier} per factor — no
    weight, contribution, value, or score field (non-neg #2)."""
    pub = MoodPublic(
        snapshot_date="2026-06-21",
        regime="greed",
        confidence_band="medium",
        data_quality="ok",
        contributing_factors=_factor_objs(["nifty_trend"], {"nifty_trend": 0.95}),
        contradicting_factors=_factor_objs(["india_vix"], {"india_vix": 0.1}),
        commentary=None,
        disclosure="x",
        not_advice="NOT_ADVICE",
        disclaimer_version="v1",
    )
    dumped = pub.model_dump()
    for factor in dumped["contributing_factors"] + dumped["contradicting_factors"]:
        assert set(factor.keys()) == {"label", "tier"}, "only label + tier may be exposed"
        assert factor["tier"] in FACTOR_TIERS
        for banned in ("weight", "contribution", "value", "score", "strength"):
            assert banned not in factor
        # the tier is a STRING, never a number
        assert isinstance(factor["tier"], str)
        assert isinstance(factor["label"], str)

    # MoodFactor default tier is the safe lowest bucket.
    assert MoodFactor(label="X").tier == "slight"
