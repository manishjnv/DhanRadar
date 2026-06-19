"""Unit tests for the server-side signal scoring engine.

Pure module tests — no DB, no network, no FastAPI test client.
Verifies:
  - Per-axis scoring bands (nifty_score, vix_score, breadth_score)
  - compute_signal_state boundary cases (triggered / watch / no_signal)
  - The return tuple is EXACTLY 4 elements (3 ints + a state str) — weighted
    aggregate and factor weights are NEVER returned (non-neg #2)
"""

from __future__ import annotations

import pytest

from dhanradar.signal.scoring import (
    breadth_score,
    compute_signal_state,
    nifty_score,
    vix_score,
)


# ---------------------------------------------------------------------------
# nifty_score bands
# ---------------------------------------------------------------------------

class TestNiftyScore:
    def test_positive_change_is_zero(self):
        assert nifty_score(0.5) == 0
        assert nifty_score(1.0) == 0

    def test_zero_exactly_is_one(self):
        # change_pct > 0 → 0; change_pct == 0 falls to next band (> -2)
        assert nifty_score(0.0) == 1

    def test_band_1(self):
        # -2 < change_pct < 0
        assert nifty_score(-0.01) == 1
        assert nifty_score(-1.99) == 1

    def test_boundary_minus_2_is_band_2(self):
        # -2.0 is NOT > -2, so falls to next band (> -5) → 2
        assert nifty_score(-2.0) == 2

    def test_band_2(self):
        assert nifty_score(-2.01) == 2
        assert nifty_score(-4.99) == 2

    def test_boundary_minus_5_is_band_3(self):
        assert nifty_score(-5.0) == 3

    def test_band_3(self):
        assert nifty_score(-5.01) == 3
        assert nifty_score(-7.99) == 3

    def test_boundary_minus_8_is_band_4(self):
        assert nifty_score(-8.0) == 4

    def test_extreme_decline_is_4(self):
        assert nifty_score(-10.0) == 4
        assert nifty_score(-20.0) == 4


# ---------------------------------------------------------------------------
# vix_score bands
# ---------------------------------------------------------------------------

class TestVixScore:
    def test_calm_below_15(self):
        assert vix_score(14.99) == 0
        assert vix_score(10.0) == 0

    def test_boundary_15_is_band_1(self):
        # < 15 → 0; 15 is NOT < 15 → band 1
        assert vix_score(15.0) == 1

    def test_band_1(self):
        assert vix_score(15.5) == 1
        assert vix_score(16.99) == 1

    def test_boundary_17_is_band_2(self):
        assert vix_score(17.0) == 2

    def test_band_2(self):
        assert vix_score(17.5) == 2
        assert vix_score(18.99) == 2

    def test_boundary_19_is_band_3(self):
        assert vix_score(19.0) == 3

    def test_band_3(self):
        assert vix_score(19.5) == 3
        assert vix_score(21.99) == 3

    def test_boundary_22_is_band_4(self):
        assert vix_score(22.0) == 4

    def test_extreme_fear_is_4(self):
        assert vix_score(30.0) == 4
        assert vix_score(50.0) == 4


# ---------------------------------------------------------------------------
# breadth_score bands
# ---------------------------------------------------------------------------

class TestBreadthScore:
    def test_broad_advance_above_1_5(self):
        assert breadth_score(1.51) == 0
        assert breadth_score(3.0) == 0

    def test_boundary_1_5_is_band_1(self):
        # > 1.5 → 0; 1.5 is NOT > 1.5 → band 1
        assert breadth_score(1.5) == 1

    def test_band_1(self):
        assert breadth_score(1.49) == 1
        assert breadth_score(1.21) == 1

    def test_boundary_1_2_is_band_2(self):
        assert breadth_score(1.2) == 2

    def test_band_2(self):
        assert breadth_score(1.19) == 2
        assert breadth_score(0.81) == 2

    def test_boundary_0_8_is_band_3(self):
        assert breadth_score(0.8) == 3

    def test_band_3(self):
        assert breadth_score(0.79) == 3
        assert breadth_score(0.51) == 3

    def test_boundary_0_5_is_band_4(self):
        assert breadth_score(0.5) == 4

    def test_broad_decline_is_4(self):
        assert breadth_score(0.3) == 4
        assert breadth_score(0.0) == 4


# ---------------------------------------------------------------------------
# compute_signal_state — return shape + correctness
# ---------------------------------------------------------------------------

class TestComputeSignalState:
    def test_returns_exactly_4_elements(self):
        """Non-neg #2: tuple must be (nifty_score, vix_score, breadth_score, state) — no extras."""
        result = compute_signal_state(nifty_change_pct=-1.0, vix_value=16.0, ad_ratio=1.3)
        assert len(result) == 4, "compute_signal_state must return exactly 4 elements"

    def test_return_types(self):
        ns, vs, bs, state = compute_signal_state(-1.0, 16.0, 1.3)
        assert isinstance(ns, int)
        assert isinstance(vs, int)
        assert isinstance(bs, int)
        assert isinstance(state, str)

    def test_no_weighted_score_in_result(self):
        """The weighted aggregate must not appear in the return value."""
        result = compute_signal_state(-3.0, 20.0, 0.6)
        # Result is (ns, vs, bs, state) — none of them should be a float
        ns, vs, bs, state = result
        assert not isinstance(ns, float), "nifty_score must be int, not float"
        assert not isinstance(vs, float), "vix_score must be int, not float"
        assert not isinstance(bs, float), "breadth_score must be int, not float"

    def test_state_values_are_valid(self):
        valid_states = {"triggered", "watch", "no_signal"}
        for nifty_pct, vix, ad in [
            (1.0, 13.0, 2.0),   # calm — no_signal
            (-3.0, 18.5, 0.9),  # moderate stress — watch
            (-9.0, 25.0, 0.4),  # extreme stress — triggered
        ]:
            _, _, _, state = compute_signal_state(nifty_pct, vix, ad)
            assert state in valid_states, f"Unexpected state: {state!r}"

    # --- no_signal case ---
    def test_no_signal_calm_market(self):
        # nifty=+1% (ns=0), vix=13 (vs=0), ad=2.0 (bs=0)
        # weighted = 0*0.20 + 0*0.40 + 0*0.40 = 0.0 → no_signal
        ns, vs, bs, state = compute_signal_state(
            nifty_change_pct=1.0,
            vix_value=13.0,
            ad_ratio=2.0,
        )
        assert state == "no_signal"
        assert ns == 0
        assert vs == 0
        assert bs == 0

    # --- watch case ---
    def test_watch_moderate_stress(self):
        # nifty=-1% (ns=1), vix=19.5 (vs=3), ad=0.65 (bs=3)
        # weighted = 1*0.20 + 3*0.40 + 3*0.40 = 0.20 + 1.20 + 1.20 = 2.60 → watch
        ns, vs, bs, state = compute_signal_state(
            nifty_change_pct=-1.0,
            vix_value=19.5,
            ad_ratio=0.65,
        )
        assert state == "watch"
        assert ns == 1
        assert vs == 3
        assert bs == 3

    # --- triggered case ---
    def test_triggered_extreme_stress(self):
        # nifty=-9% (ns=4), vix=25 (vs=4), ad=0.4 (bs=4)
        # weighted = 4*0.20 + 4*0.40 + 4*0.40 = 0.80 + 1.60 + 1.60 = 4.0 → triggered
        ns, vs, bs, state = compute_signal_state(
            nifty_change_pct=-9.0,
            vix_value=25.0,
            ad_ratio=0.4,
        )
        assert state == "triggered"
        assert ns == 4
        assert vs == 4
        assert bs == 4

    def test_triggered_boundary_exactly_3(self):
        # Design: find inputs giving weighted == 3.0 exactly.
        # ns=3 (nifty=-6%), vs=3 (vix=19.5), bs=3 (ad=0.65)
        # weighted = 3*0.20 + 3*0.40 + 3*0.40 = 0.60 + 1.20 + 1.20 = 3.0 → triggered
        _, _, _, state = compute_signal_state(
            nifty_change_pct=-6.0,
            vix_value=19.5,
            ad_ratio=0.65,
        )
        assert state == "triggered"

    def test_watch_boundary_exactly_2(self):
        # ns=0 (nifty=+1%), vs=2 (vix=17.5), bs=3 (ad=0.65)
        # weighted = 0*0.20 + 2*0.40 + 3*0.40 = 0.0 + 0.80 + 1.20 = 2.0 → watch
        _, _, _, state = compute_signal_state(
            nifty_change_pct=1.0,
            vix_value=17.5,
            ad_ratio=0.65,
        )
        assert state == "watch"

    def test_watch_just_below_triggered(self):
        # ns=2 (nifty=-3%), vs=2 (vix=17.5), bs=3 (ad=0.65)
        # weighted = 2*0.20 + 2*0.40 + 3*0.40 = 0.40 + 0.80 + 1.20 = 2.40 → watch
        _, _, _, state = compute_signal_state(
            nifty_change_pct=-3.0,
            vix_value=17.5,
            ad_ratio=0.65,
        )
        assert state == "watch"
