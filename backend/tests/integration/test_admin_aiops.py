"""
Integration tests for Admin Console Phase 4 — AI Ops console (read-only).

Covers all 7 GET endpoints:
    GET /api/v1/admin/ai              — AiDashboardResponse
    GET /api/v1/admin/ai/versions     — AiVersionsResponse
    GET /api/v1/admin/ai/prompts      — AiPromptsResponse
    GET /api/v1/admin/ai/eval         — AiEvalResponse
    GET /api/v1/admin/ai/safety       — AiSafetyResponse
    GET /api/v1/admin/ai/feedback     — AiFeedbackResponse
    GET /api/v1/admin/ai/cost         — AiCostResponse

Surface-hiding: every endpoint returns 404 to anonymous callers and to
authenticated non-admins (RequireAdmin gate).  These tests mirror the patterns
in test_admin_phase3.py exactly.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# All 7 AI Ops endpoint paths
# ---------------------------------------------------------------------------

_AIOPS_PATHS = [
    "/api/v1/admin/ai",
    "/api/v1/admin/ai/versions",
    "/api/v1/admin/ai/prompts",
    "/api/v1/admin/ai/eval",
    "/api/v1/admin/ai/safety",
    "/api/v1/admin/ai/feedback",
    "/api/v1/admin/ai/cost",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _signup(client, email: str) -> tuple[str, str]:
    from tests.conftest import extract_cookie

    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "AdminAIOpsTest42!"},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["user"]["id"]), extract_cookie(r, "__Host-access")


def _make_fake_budget_snapshot() -> dict:
    return {
        "free_calls_today": 42,
        "free_cap": 1000,
        "premium_usd_today": 0.15,
        "premium_soft_cap": 0.50,
        "premium_hard_cap": 9.50,
        "free_remaining": 958,
        "premium_remaining_usd": 9.35,
    }


def _make_fake_churn() -> dict:
    return {
        "recommendation_type": "educational_label",
        "previous_day": None,
        "current_day": None,
        "universe": 0,
        "changed": 0,
        "churn": 0.0,
        "threshold": 0.05,
        "decision": "insufficient_data",
        "requires_human_review": False,
        "distribution_violations": [],
        "reason": "need >=2 batch days of audited labels",
    }


# ---------------------------------------------------------------------------
# 1. 404 for anonymous callers on all AI Ops endpoints
# ---------------------------------------------------------------------------


async def test_aiops_endpoints_404_for_anonymous(async_client):
    """No cookie → 404 for every AI Ops endpoint."""
    for path in _AIOPS_PATHS:
        r = await async_client.get(path)
        assert r.status_code == 404, (
            f"Expected 404 on {path} for anonymous, got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 2. 404 for authenticated non-admins on all AI Ops endpoints
# ---------------------------------------------------------------------------


async def test_aiops_endpoints_404_for_non_admin(async_client, monkeypatch):
    """Authenticated non-admin → 404 on all AI Ops endpoints."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")

    user_id, access = await _signup(async_client, "nonadmin_aiops@example.com")
    headers = make_auth_headers(access_token=access)

    for path in _AIOPS_PATHS:
        r = await async_client.get(path, headers=headers)
        assert r.status_code == 404, (
            f"Expected 404 on {path} for non-admin, got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 3. GET /admin/ai — dashboard happy path
# ---------------------------------------------------------------------------


async def test_aiops_dashboard_200(async_client, monkeypatch):
    """Admin → 200 with expected top-level fields on /admin/ai."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_aiops_dash@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    with (
        patch(
            "dhanradar.admin.aiops_router._read_budget_snapshot",
            new=AsyncMock(return_value=_make_fake_budget_snapshot()),
        ),
        patch(
            "dhanradar.admin.aiops_router.label_churn_review",
            new=AsyncMock(return_value=_make_fake_churn()),
        ),
        patch(
            "dhanradar.admin.aiops_router.is_engine_version_activated",
            new=AsyncMock(return_value=True),
        ),
    ):
        r = await async_client.get("/api/v1/admin/ai", headers=headers)

    assert r.status_code == 200, r.text
    data = r.json()

    for field in ["model_version", "activated", "budget", "served_7d", "low_confidence_7d",
                  "label_churn", "avg_latency_ms", "eval_score"]:
        assert field in data, f"Missing field '{field}' in /admin/ai response"

    assert isinstance(data["model_version"], str) and data["model_version"]
    assert isinstance(data["activated"], bool)
    assert isinstance(data["served_7d"], int)
    assert data["served_7d"] >= 0
    assert isinstance(data["low_confidence_7d"], int)
    assert data["low_confidence_7d"] >= 0

    # budget sub-object
    budget = data["budget"]
    for bfield in ["free_calls_today", "free_cap", "premium_usd_today",
                   "premium_soft_cap", "premium_hard_cap",
                   "free_remaining", "premium_remaining_usd"]:
        assert bfield in budget, f"Missing budget field '{bfield}'"

    # absent/instrumented:false fields
    assert data["avg_latency_ms"]["instrumented"] is False
    assert data["eval_score"]["instrumented"] is False

    # label_churn
    churn = data["label_churn"]
    assert "decision" in churn
    assert "churn" in churn
    assert "requires_human_review" in churn


# ---------------------------------------------------------------------------
# 4. GET /admin/ai/versions — versions registry happy path
# ---------------------------------------------------------------------------


async def test_aiops_versions_200(async_client, monkeypatch):
    """Admin → 200 with versions list and instrumented:false for backtest/drift."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_aiops_ver@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    with patch(
        "dhanradar.admin.aiops_router.list_engine_versions",
        new=AsyncMock(return_value=[]),
    ):
        r = await async_client.get("/api/v1/admin/ai/versions", headers=headers)

    assert r.status_code == 200, r.text
    data = r.json()

    assert "versions" in data, "Missing field 'versions'"
    assert isinstance(data["versions"], list)

    assert "backtest" in data
    assert data["backtest"]["instrumented"] is False

    assert "drift" in data
    assert data["drift"]["instrumented"] is False


# ---------------------------------------------------------------------------
# 5. GET /admin/ai/prompts — prompts endpoint happy path
# ---------------------------------------------------------------------------


async def test_aiops_prompts_200(async_client, monkeypatch):
    """Admin → 200 with registry:false and prompt_versions_seen list."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_aiops_prompt@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    with patch(
        "dhanradar.admin.aiops_router.list_distinct_prompt_versions",
        new=AsyncMock(return_value=["v1.0", "v1.1"]),
    ):
        r = await async_client.get("/api/v1/admin/ai/prompts", headers=headers)

    assert r.status_code == 200, r.text
    data = r.json()

    assert data["registry"] is False
    assert "note" in data and data["note"]
    assert "prompt_versions_seen" in data
    assert isinstance(data["prompt_versions_seen"], list)


# ---------------------------------------------------------------------------
# 6. GET /admin/ai/eval — eval endpoint happy path
# ---------------------------------------------------------------------------


async def test_aiops_eval_200(async_client, monkeypatch):
    """Admin → 200 with quality_issues list and groundedness instrumented:false."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_aiops_eval@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/ai/eval", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()

    assert "quality_issues" in data
    assert isinstance(data["quality_issues"], list)

    assert "groundedness" in data
    assert data["groundedness"]["instrumented"] is False


# ---------------------------------------------------------------------------
# 7. GET /admin/ai/safety — safety monitor happy path
# ---------------------------------------------------------------------------


async def test_aiops_safety_200(async_client, monkeypatch):
    """Admin → 200 with safety snapshot fields; advice_boundary_breaches.value == 0."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_aiops_safety@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    fake_summary = {
        "days": 7,
        "served_by_type": {},
        "by_confidence_band": {},
        "low_confidence_count": 0,
        "recent_audit_rows": [],
        "recent_low_confidence": [],
    }

    with (
        patch(
            "dhanradar.admin.aiops_router.safety_monitor_summary",
            new=AsyncMock(return_value=fake_summary),
        ),
        patch(
            "dhanradar.admin.aiops_router.label_churn_review",
            new=AsyncMock(return_value=_make_fake_churn()),
        ),
    ):
        r = await async_client.get("/api/v1/admin/ai/safety", headers=headers)

    assert r.status_code == 200, r.text
    data = r.json()

    for field in [
        "days", "served_by_type", "by_confidence_band",
        "low_confidence_count", "recent_audit_rows", "recent_low_confidence",
        "label_churn_educational", "label_churn_mood",
        "advice_boundary_breaches", "groundedness",
    ]:
        assert field in data, f"Missing field '{field}' in /admin/ai/safety"

    # advisory-verb breaches: always 0 + instrumented:false (violations rejected at gateway)
    abr = data["advice_boundary_breaches"]
    assert abr["value"] == 0
    assert abr["instrumented"] is False

    # groundedness absent
    assert data["groundedness"]["instrumented"] is False


# ---------------------------------------------------------------------------
# 8. GET /admin/ai/feedback — feedback placeholder
# ---------------------------------------------------------------------------


async def test_aiops_feedback_200(async_client, monkeypatch):
    """Admin → 200 with available:false (no feedback table yet)."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_aiops_fb@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/ai/feedback", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["available"] is False
    assert "note" in data and data["note"]


# ---------------------------------------------------------------------------
# 9. GET /admin/ai/cost — cost snapshot happy path
# ---------------------------------------------------------------------------


async def test_aiops_cost_200(async_client, monkeypatch):
    """Admin → 200 with budget snapshot; per_model + latency instrumented:false."""
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    user_id, access = await _signup(async_client, "admin_aiops_cost@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    with patch(
        "dhanradar.admin.aiops_router._read_budget_snapshot",
        new=AsyncMock(return_value=_make_fake_budget_snapshot()),
    ):
        r = await async_client.get("/api/v1/admin/ai/cost", headers=headers)

    assert r.status_code == 200, r.text
    data = r.json()

    assert "budget" in data
    budget = data["budget"]
    for bfield in ["free_calls_today", "free_cap", "premium_usd_today",
                   "premium_soft_cap", "premium_hard_cap",
                   "free_remaining", "premium_remaining_usd"]:
        assert bfield in budget, f"Missing budget field '{bfield}'"

    assert data["per_model"]["instrumented"] is False
    assert data["latency"]["instrumented"] is False
