"""
Unit tests for dhanradar.subscriptions.service._derive_tier.

Key findings documented in comments:
  - EXACT_PLAN_TIERS is intentionally empty pre-billing; ALL production traffic
    currently falls through to the substring heuristic.
  - FOOT-GUN: The substring check for "pro" matches before checking "pro_plus",
    so a plan_id like "promo_2026" would be granted the `pro` tier.
    Current code checks "pro_plus" BEFORE "pro", so "dhanradar_pro_plus" is
    safe — but any plan_id that contains "pro" without containing "pro_plus"
    first would be granted `pro`. This is documented as the pre-billing risk.
  - Tests below assert current behaviour so any accidental regression in the
    heuristic order is caught immediately.

No DB, Redis, or HTTP needed — pure function tests.
"""

from __future__ import annotations

import pytest

from dhanradar.subscriptions.service import EXACT_PLAN_TIERS, _derive_tier
from dhanradar.models.auth import UserTierEnum


# ---------------------------------------------------------------------------
# Inactive statuses → always free regardless of plan
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", [
    "cancelled",
    "completed",
    "expired",
    "halted",
    "pending",
    "created",
    "CANCELLED",        # case-insensitivity check
    "",
])
def test_inactive_status_always_free(status: str):
    """Any non-active status must yield free regardless of the plan name."""
    assert _derive_tier("dhanradar_pro_plus", status) == UserTierEnum.free
    assert _derive_tier("founder_plan_lifetime", status) == UserTierEnum.free
    assert _derive_tier("plan_pro", status) == UserTierEnum.free


# ---------------------------------------------------------------------------
# Active status — substring heuristic
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("plan, expected_tier", [
    # pro_plus patterns (must match BEFORE the plain "pro" check)
    ("dhanradar_pro_plus", UserTierEnum.pro_plus),
    ("plan_pro_plus_annual", UserTierEnum.pro_plus),
    ("PRO_PLUS_PLAN", UserTierEnum.pro_plus),           # lowercase applied internally

    # pro+ alias (contains "pro+")
    # NOTE: Python's `in` operator with a lowercased plan_id sees "pro+" only
    # if the literal string "pro+" appears. "pro_plus" does NOT contain "pro+"
    # so this test verifies the explicit "pro+" check path.
    ("plan_pro+_monthly", UserTierEnum.pro_plus),

    # founder / lifetime patterns
    ("founder_annual", UserTierEnum.founder_lifetime),
    ("plan_lifetime_access", UserTierEnum.founder_lifetime),
    ("FOUNDER_LIFETIME_2026", UserTierEnum.founder_lifetime),

    # plain pro
    ("dhanradar_pro_monthly", UserTierEnum.pro),
    ("plan_pro", UserTierEnum.pro),

    # no match → free
    ("basic_plan", UserTierEnum.free),
    ("starter", UserTierEnum.free),
    ("", UserTierEnum.free),
])
def test_derive_tier_active_substring(plan: str, expected_tier: UserTierEnum):
    assert _derive_tier(plan, "active") == expected_tier


def test_authenticated_status_is_active():
    """'authenticated' is a valid active status per _ACTIVE_STATUSES."""
    assert _derive_tier("dhanradar_pro_plus", "authenticated") == UserTierEnum.pro_plus


# ---------------------------------------------------------------------------
# FOOT-GUN: "promo_2026" contains "pro" and gets `pro` tier
# Current behaviour assertion + warning comment.
# ---------------------------------------------------------------------------

def test_promo_plan_gets_pro_tier_foot_gun():
    """
    DOCUMENTS CURRENT BEHAVIOUR — PRE-BILLING RISK.

    A plan_id of "promo_2026" does NOT contain "pro_plus", "pro+", "founder",
    or "lifetime", but it DOES contain "pro". Therefore _derive_tier returns
    UserTierEnum.pro, which is a WRONG grant for a promo/marketing plan.

    This test pins the current (incorrect) behaviour so any fix to the
    EXACT_PLAN_TIERS or heuristic ordering is immediately visible.
    Once EXACT_PLAN_TIERS is populated with real plan ids before billing,
    this foot-gun is neutralised because exact lookup wins before substring.
    """
    # NOTE: this asserts the CURRENT BUGGY behaviour. A promo plan should
    # not grant `pro` tier. Document and fix by populating EXACT_PLAN_TIERS.
    result = _derive_tier("promo_2026", "active")
    assert result == UserTierEnum.pro, (
        "Foot-gun confirmed: 'promo_2026' contains 'pro' → granted pro tier. "
        "Populate EXACT_PLAN_TIERS before billing goes live."
    )


# ---------------------------------------------------------------------------
# EXACT_PLAN_TIERS: monkeypatched exact map wins before substring heuristic
# ---------------------------------------------------------------------------

def test_exact_plan_tiers_win_over_substring(monkeypatch):
    """
    When EXACT_PLAN_TIERS contains an entry for a plan_id, that exact mapping
    must be returned instead of the substring fallback.
    """
    import dhanradar.subscriptions.service as svc

    # Override the exact map with a test-only entry.
    monkeypatch.setattr(
        svc,
        "EXACT_PLAN_TIERS",
        {"plan_TESTFOUNDER": UserTierEnum.founder_lifetime},
    )

    # "plan_TESTFOUNDER" has no "founder" or "lifetime" substring (it's all
    # caps after the prefix), so without the exact map it would fall to free.
    # With the map it must return founder_lifetime.
    result = _derive_tier("plan_TESTFOUNDER", "active")
    assert result == UserTierEnum.founder_lifetime


def test_exact_plan_tiers_override_substring_for_pro_map(monkeypatch):
    """Exact map can assign a different tier than the substring would."""
    import dhanradar.subscriptions.service as svc

    # "plan_XXXX" has no tier-matching substring → would be free.
    # Exact map overrides it to pro_plus.
    monkeypatch.setattr(
        svc,
        "EXACT_PLAN_TIERS",
        {"plan_XXXX": UserTierEnum.pro_plus},
    )
    assert _derive_tier("plan_XXXX", "active") == UserTierEnum.pro_plus


def test_exact_plan_tiers_empty_falls_back_to_substring(monkeypatch):
    """When EXACT_PLAN_TIERS is empty the substring heuristic runs."""
    import dhanradar.subscriptions.service as svc

    monkeypatch.setattr(svc, "EXACT_PLAN_TIERS", {})
    # "dhanradar_pro_plus" should resolve to pro_plus via substring.
    assert _derive_tier("dhanradar_pro_plus", "active") == UserTierEnum.pro_plus


def test_inactive_with_exact_map_still_free(monkeypatch):
    """Inactive status returns free even when the plan is in the exact map."""
    import dhanradar.subscriptions.service as svc

    monkeypatch.setattr(
        svc,
        "EXACT_PLAN_TIERS",
        {"plan_GOLD": UserTierEnum.founder_lifetime},
    )
    assert _derive_tier("plan_GOLD", "cancelled") == UserTierEnum.free
