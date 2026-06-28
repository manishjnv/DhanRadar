"""
Unit tests for dhanradar.subscriptions.service._derive_tier.

B2 (fail-safe): tier is derived ONLY from the exact EXACT_PLAN_TIERS map. The
old substring heuristic was REMOVED — it was a privilege foot-gun (e.g.
"promo_2026" contains "pro" and was wrongly granted `pro`). Now:
  - inactive status → free, always;
  - active + UNMAPPED plan → free (no guessing);
  - active + MAPPED plan → exactly the mapped tier.

No DB, Redis, or HTTP needed — pure function tests.
"""

from __future__ import annotations

import pytest

from dhanradar.models.auth import UserTierEnum
from dhanradar.subscriptions.service import _derive_tier

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
    """Any non-active status yields free regardless of the plan name."""
    assert _derive_tier("dhanradar_pro_plus", status) == UserTierEnum.free
    assert _derive_tier("founder_plan_lifetime", status) == UserTierEnum.free
    assert _derive_tier("plan_pro", status) == UserTierEnum.free


# ---------------------------------------------------------------------------
# B2 fail-safe: active + UNMAPPED plan → free (NO substring guessing)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("plan", [
    "dhanradar_pro_plus",
    "plan_pro_plus_annual",
    "founder_annual",
    "plan_lifetime_access",
    "dhanradar_pro_monthly",
    "plan_pro",
    "basic_plan",
    "starter",
    "",
])
def test_unmapped_active_plan_grants_no_paid_tier(plan: str):
    """EXACT_PLAN_TIERS is empty by default; any active plan — even one whose
    name contains 'pro'/'founder'/'lifetime' — must grant NO paid tier. Only an
    exact map entry can grant a tier (no substring fallback)."""
    assert _derive_tier(plan, "active") == UserTierEnum.free


def test_promo_plan_no_longer_gets_pro_tier():
    """REGRESSION GUARD (B2): the old foot-gun granted 'promo_2026' the `pro`
    tier because it contains 'pro'. With the substring heuristic removed, an
    unmapped promo plan now correctly grants free."""
    assert _derive_tier("promo_2026", "active") == UserTierEnum.free


# ---------------------------------------------------------------------------
# EXACT_PLAN_TIERS is the ONLY source of a paid tier
# ---------------------------------------------------------------------------

def test_exact_map_grants_the_mapped_tier(monkeypatch):
    """A plan_id present in EXACT_PLAN_TIERS gets exactly its mapped tier — even
    when its name has no tier-matching substring."""
    import dhanradar.subscriptions.service as svc

    monkeypatch.setattr(
        svc,
        "EXACT_PLAN_TIERS",
        {
            "plan_XXXX": UserTierEnum.pro_plus,
            "plan_F": UserTierEnum.founder_lifetime,
        },
    )
    assert _derive_tier("plan_XXXX", "active") == UserTierEnum.pro_plus
    assert _derive_tier("plan_F", "active") == UserTierEnum.founder_lifetime


def test_authenticated_status_is_active(monkeypatch):
    """'authenticated' is a valid active status; with a mapped plan it grants
    the mapped tier."""
    import dhanradar.subscriptions.service as svc

    monkeypatch.setattr(svc, "EXACT_PLAN_TIERS", {"plan_pp": UserTierEnum.pro_plus})
    assert _derive_tier("plan_pp", "authenticated") == UserTierEnum.pro_plus


def test_unmapped_with_nonempty_map_still_free(monkeypatch):
    """A plan_id NOT in a populated map → free (no fallback guessing), even if
    its name contains a tier substring."""
    import dhanradar.subscriptions.service as svc

    monkeypatch.setattr(svc, "EXACT_PLAN_TIERS", {"plan_pro": UserTierEnum.pro})
    assert _derive_tier("dhanradar_pro_plus", "active") == UserTierEnum.free


def test_inactive_with_exact_map_still_free(monkeypatch):
    """Inactive status returns free even when the plan is in the exact map."""
    import dhanradar.subscriptions.service as svc

    monkeypatch.setattr(
        svc,
        "EXACT_PLAN_TIERS",
        {"plan_GOLD": UserTierEnum.founder_lifetime},
    )
    assert _derive_tier("plan_GOLD", "cancelled") == UserTierEnum.free
