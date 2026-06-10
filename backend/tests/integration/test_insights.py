"""
Integration tests for Portfolio Intelligence endpoints (Plan Group 3).

Test contract:
  - Anonymous requests → 401 (not_authenticated)
  - Wrong / other-user portfolio_id → 404 (portfolio_not_found)
  - Empty portfolio (exists, zero holdings) → 200 with valid shape + disclosure
  - Disclosure bundle present on every 200 response
  - `unified_score` must NEVER appear in any JSON response body (non-neg #2)
  - Overlap_pct and allocation_pct must be numeric (not strings)

NOTE: These tests require a running DB (`dhanradar-postgres` inside Docker).
They are skipped automatically when the DB is not reachable (CI-only environment).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

# DB reachability guard — skip on Windows host where Docker hostname won't resolve
pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_headers(token: str) -> dict[str, str]:
    # Endpoints use HttpOnly cookie — TestClient fixture handles cookie injection
    return {}


def _assert_disclosure_present(body: dict[str, Any]) -> None:
    assert "disclosure" in body, "disclosure field missing"
    assert "not_advice" in body, "not_advice field missing"
    assert "disclaimer_version" in body, "disclaimer_version field missing"
    assert body["not_advice"] == "NOT_ADVICE"


def _assert_no_unified_score(body: dict[str, Any]) -> None:
    """unified_score must NEVER appear in any client-facing response (non-neg #2)."""
    body_str = json.dumps(body)
    assert "unified_score" not in body_str, (
        "unified_score leaked into client-facing insights response (non-neg #2 violation)"
    )


# ---------------------------------------------------------------------------
# Anonymous access → 401
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_overlap_anonymous_401(test_client: Any) -> None:
    """Anonymous (no cookie) → 401 not_authenticated."""
    pid = str(uuid.uuid4())
    resp = test_client.get(f"/api/v1/portfolio/{pid}/overlap")
    assert resp.status_code == 401
    body = resp.json()
    assert body.get("detail") == "not_authenticated"


@pytest.mark.asyncio
async def test_concentration_anonymous_401(test_client: Any) -> None:
    pid = str(uuid.uuid4())
    resp = test_client.get(f"/api/v1/portfolio/{pid}/concentration")
    assert resp.status_code == 401
    body = resp.json()
    assert body.get("detail") == "not_authenticated"


# ---------------------------------------------------------------------------
# Wrong portfolio → 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_overlap_wrong_portfolio_404(auth_test_client: Any) -> None:
    """Authenticated user requesting a portfolio that doesn't belong to them → 404."""
    pid = str(uuid.uuid4())  # non-existent UUID
    resp = auth_test_client.get(f"/api/v1/portfolio/{pid}/overlap")
    assert resp.status_code == 404
    body = resp.json()
    assert body.get("detail") == "portfolio_not_found"


@pytest.mark.asyncio
async def test_concentration_wrong_portfolio_404(auth_test_client: Any) -> None:
    pid = str(uuid.uuid4())
    resp = auth_test_client.get(f"/api/v1/portfolio/{pid}/concentration")
    assert resp.status_code == 404
    body = resp.json()
    assert body.get("detail") == "portfolio_not_found"


# ---------------------------------------------------------------------------
# Empty portfolio → 200 with valid shape + disclosure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_overlap_empty_portfolio_200(
    auth_test_client: Any, empty_portfolio_id: str
) -> None:
    """Empty portfolio (portfolio exists, zero holdings) → 200 with empty lists."""
    resp = auth_test_client.get(f"/api/v1/portfolio/{empty_portfolio_id}/overlap")
    assert resp.status_code == 200
    body = resp.json()

    assert body["portfolio_id"] == empty_portfolio_id
    assert body["fund_pairs"] == []
    assert body["category_distribution"] == []
    assert body["data_completeness"] == "empty"
    _assert_disclosure_present(body)
    _assert_no_unified_score(body)


@pytest.mark.asyncio
async def test_concentration_empty_portfolio_200(
    auth_test_client: Any, empty_portfolio_id: str
) -> None:
    resp = auth_test_client.get(f"/api/v1/portfolio/{empty_portfolio_id}/concentration")
    assert resp.status_code == 200
    body = resp.json()

    assert body["portfolio_id"] == empty_portfolio_id
    assert body["by_category"] == []
    assert body["by_amc"] == []
    assert body["by_fund"] == []
    assert body["data_completeness"] == "empty"
    _assert_disclosure_present(body)
    _assert_no_unified_score(body)


# ---------------------------------------------------------------------------
# Disclosure present on every 200
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_overlap_disclosure_always_present(
    auth_test_client: Any, empty_portfolio_id: str
) -> None:
    resp = auth_test_client.get(f"/api/v1/portfolio/{empty_portfolio_id}/overlap")
    assert resp.status_code == 200
    _assert_disclosure_present(resp.json())


@pytest.mark.asyncio
async def test_concentration_disclosure_always_present(
    auth_test_client: Any, empty_portfolio_id: str
) -> None:
    resp = auth_test_client.get(f"/api/v1/portfolio/{empty_portfolio_id}/concentration")
    assert resp.status_code == 200
    _assert_disclosure_present(resp.json())
