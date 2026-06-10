"""
Integration tests for Portfolio Intelligence endpoints (Plan Group 3).

Test contract:
  - Anonymous requests → 401 (not_authenticated)
  - Wrong / other-user / non-existent portfolio_id → 404 (portfolio_not_found)
  - Empty portfolio (exists, zero holdings) → 200 with valid shape + disclosure
  - Disclosure bundle present on every 200 response
  - `unified_score` must NEVER appear in any JSON response body (non-neg #2)

Infrastructure contract (same as test_dashboard / test_mood):
  - async_client      — httpx.AsyncClient over ASGITransport(app); no lifespan.
  - db_session        — function-scoped AsyncSession; conftest truncates auth/billing.
  - patch_redis       — fakeredis.aioredis.FakeRedis; flushed between tests.

AUTH strategy: override `current_user_or_anonymous` via
`app.dependency_overrides[current_user_or_anonymous]` to return a UserContext for
the seeded user; always pop the override in teardown. For the 401 guard tests the
override is NOT installed — the real dep returns anonymous → `_require_auth` → 401.
"""

from __future__ import annotations

import json
import uuid as _uuid
from typing import Any

import pytest
from sqlalchemy import text

from dhanradar.deps import UserContext, current_user_or_anonymous
from dhanradar.main import app
from dhanradar.models.auth import User, UserTierEnum
from dhanradar.models.mf import MfPortfolio

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Teardown: truncate mf.* tables between tests (conftest only handles auth/billing).
# Same-connection pattern (avoids TRUNCATE deadlock in CI — see test_dashboard).
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _truncate_mf(db_session):
    yield
    await db_session.rollback()
    await db_session.execute(
        text(
            "TRUNCATE TABLE "
            "mf.user_fund_scores, "
            "mf.mf_user_holdings, "
            "mf.mf_portfolio_snapshots, "
            "mf.mf_portfolios, "
            "mf.mf_funds "
            "RESTART IDENTITY CASCADE"
        )
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_user(db_session) -> str:
    """Insert a free-tier User and return its id as a str UUID."""
    uid = _uuid.uuid4()
    user = User(
        id=uid,
        email=f"insights_{uid.hex[:8]}@example.com",
        hashed_password="$2b$12$placeholder_hash_for_testing_only",
        tier=UserTierEnum.free,
    )
    db_session.add(user)
    await db_session.commit()
    return str(uid)


async def _seed_empty_portfolio(db_session, user_id: str) -> str:
    """Insert a portfolio (zero holdings) owned by user_id; return its id as str."""
    portfolio = MfPortfolio(user_id=_uuid.UUID(user_id), name="Empty Portfolio")
    db_session.add(portfolio)
    await db_session.commit()
    return str(portfolio.id)


def _auth_override(user_id: str):
    def _dep() -> UserContext:
        return UserContext(user_id=user_id, tier="free", is_anonymous=False)

    return _dep


def _assert_disclosure_present(body: dict[str, Any]) -> None:
    assert "disclosure" in body, "disclosure field missing"
    assert "not_advice" in body, "not_advice field missing"
    assert "disclaimer_version" in body, "disclaimer_version field missing"
    assert body["not_advice"] == "NOT_ADVICE"


def _assert_no_unified_score(body: dict[str, Any]) -> None:
    """unified_score must NEVER appear in any client-facing response (non-neg #2)."""
    assert "unified_score" not in json.dumps(body), (
        "unified_score leaked into client-facing insights response (non-neg #2 violation)"
    )


# ---------------------------------------------------------------------------
# Anonymous access → 401
# ---------------------------------------------------------------------------


async def test_overlap_anonymous_401(async_client, patch_redis) -> None:
    """Anonymous (no cookie) → 401 not_authenticated."""
    pid = str(_uuid.uuid4())
    resp = await async_client.get(f"/api/v1/portfolio/{pid}/overlap")
    assert resp.status_code == 401, resp.text
    assert resp.json().get("detail") == "not_authenticated"


async def test_concentration_anonymous_401(async_client, patch_redis) -> None:
    pid = str(_uuid.uuid4())
    resp = await async_client.get(f"/api/v1/portfolio/{pid}/concentration")
    assert resp.status_code == 401, resp.text
    assert resp.json().get("detail") == "not_authenticated"


# ---------------------------------------------------------------------------
# Wrong / non-existent portfolio → 404
# ---------------------------------------------------------------------------


async def test_overlap_wrong_portfolio_404(async_client, db_session, patch_redis) -> None:
    """Authenticated user requesting a portfolio that isn't theirs → 404."""
    user_id = await _seed_user(db_session)
    pid = str(_uuid.uuid4())  # non-existent UUID
    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        resp = await async_client.get(f"/api/v1/portfolio/{pid}/overlap")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)
    assert resp.status_code == 404, resp.text
    assert resp.json().get("detail") == "portfolio_not_found"


async def test_concentration_wrong_portfolio_404(async_client, db_session, patch_redis) -> None:
    user_id = await _seed_user(db_session)
    pid = str(_uuid.uuid4())
    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        resp = await async_client.get(f"/api/v1/portfolio/{pid}/concentration")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)
    assert resp.status_code == 404, resp.text
    assert resp.json().get("detail") == "portfolio_not_found"


# ---------------------------------------------------------------------------
# Empty portfolio (exists, zero holdings) → 200 with valid shape + disclosure
# ---------------------------------------------------------------------------


async def test_overlap_empty_portfolio_200(async_client, db_session, patch_redis) -> None:
    """Empty portfolio (exists, zero holdings) → 200 with empty lists."""
    user_id = await _seed_user(db_session)
    pid = await _seed_empty_portfolio(db_session, user_id)
    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        resp = await async_client.get(f"/api/v1/portfolio/{pid}/overlap")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["portfolio_id"] == pid
    assert body["fund_pairs"] == []
    assert body["category_distribution"] == []
    assert body["data_completeness"] == "empty"
    _assert_disclosure_present(body)
    _assert_no_unified_score(body)


async def test_concentration_empty_portfolio_200(async_client, db_session, patch_redis) -> None:
    user_id = await _seed_user(db_session)
    pid = await _seed_empty_portfolio(db_session, user_id)
    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        resp = await async_client.get(f"/api/v1/portfolio/{pid}/concentration")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["portfolio_id"] == pid
    assert body["by_category"] == []
    assert body["by_amc"] == []
    assert body["by_fund"] == []
    assert body["data_completeness"] == "empty"
    _assert_disclosure_present(body)
    _assert_no_unified_score(body)


# ---------------------------------------------------------------------------
# Disclosure present on every 200
# ---------------------------------------------------------------------------


async def test_overlap_disclosure_always_present(async_client, db_session, patch_redis) -> None:
    user_id = await _seed_user(db_session)
    pid = await _seed_empty_portfolio(db_session, user_id)
    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        resp = await async_client.get(f"/api/v1/portfolio/{pid}/overlap")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)
    assert resp.status_code == 200, resp.text
    _assert_disclosure_present(resp.json())


async def test_concentration_disclosure_always_present(async_client, db_session, patch_redis) -> None:
    user_id = await _seed_user(db_session)
    pid = await _seed_empty_portfolio(db_session, user_id)
    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        resp = await async_client.get(f"/api/v1/portfolio/{pid}/concentration")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)
    assert resp.status_code == 200, resp.text
    _assert_disclosure_present(resp.json())
