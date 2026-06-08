"""Unit tests for the B43 onboarding risk-quiz scoring logic.

Pure tests — no DB, no network, no fixtures. Verifies:
  - Happy-path boundary values (conservative, moderate, aggressive).
  - Guard: wrong length raises ValueError.
  - Guard: out-of-range option index raises ValueError.
  - Every returned value is in RISK_PROFILES (never an advisory verb or number).
"""

from __future__ import annotations

import pytest

from dhanradar.onboarding.quiz import RISK_PROFILES, score_answers

# ---------------------------------------------------------------------------
# Happy-path boundary values
# ---------------------------------------------------------------------------


def test_all_zeros_is_conservative():
    assert score_answers([0, 0, 0, 0, 0]) == "conservative"


def test_all_threes_is_aggressive():
    assert score_answers([3, 3, 3, 3, 3]) == "aggressive"


def test_mid_answers_is_moderate():
    # total = 1+2+1+2+1 = 7; pct = round(7/15*100) = round(46.7) = 47 → moderate
    assert score_answers([1, 2, 1, 2, 1]) == "moderate"


# ---------------------------------------------------------------------------
# Boundary precision: exactly pct=35 → conservative; pct=36 → moderate
# ---------------------------------------------------------------------------


def test_boundary_conservative_at_pct33():
    # total=5 → round(5/15*100) = round(33.33) = 33 → pct<=35 → conservative
    assert score_answers([1, 1, 1, 1, 1]) == "conservative"


def test_boundary_aggressive_at_pct66():
    # total=10 → round(10/15*100) = round(66.67) = 67 → aggressive
    assert score_answers([2, 2, 2, 2, 2]) == "aggressive"


# ---------------------------------------------------------------------------
# Guard: wrong number of answers
# ---------------------------------------------------------------------------


def test_wrong_length_raises_value_error():
    with pytest.raises(ValueError):
        score_answers([0, 0, 0])


def test_empty_list_raises_value_error():
    with pytest.raises(ValueError):
        score_answers([])


def test_too_many_answers_raises_value_error():
    with pytest.raises(ValueError):
        score_answers([0, 0, 0, 0, 0, 0])


# ---------------------------------------------------------------------------
# Guard: out-of-range option index
# ---------------------------------------------------------------------------


def test_out_of_range_high_raises_value_error():
    with pytest.raises(ValueError):
        score_answers([0, 0, 0, 0, 4])


def test_out_of_range_negative_raises_value_error():
    with pytest.raises(ValueError):
        score_answers([-1, 0, 0, 0, 0])


# ---------------------------------------------------------------------------
# Invariant: all returned values are in RISK_PROFILES (no advisory verbs)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "answers",
    [
        [0, 0, 0, 0, 0],
        [1, 1, 1, 1, 1],
        [1, 2, 1, 2, 1],
        [2, 2, 2, 2, 2],
        [3, 3, 3, 3, 3],
        [0, 1, 2, 3, 0],
        [3, 0, 3, 0, 3],
    ],
)
def test_result_is_always_in_risk_profiles(answers: list[int]):
    result = score_answers(answers)
    assert result in RISK_PROFILES, (
        f"score_answers({answers!r}) returned {result!r}, "
        f"which is not in RISK_PROFILES={RISK_PROFILES}"
    )
