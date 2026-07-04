"""
Integration tests for the Dashboard module (B56).

Endpoints covered:
  GET /api/v1/indices

`/portfolio/summary` and `/instruments/top-scored` were decommissioned along with
the old /dashboard page (folded into /mf/portfolio) — their tests were removed.

Infrastructure contract (same as test_mood / test_notifications):
  - async_client      — httpx.AsyncClient over ASGITransport(app); no lifespan.
  - db_session        — function-scoped AsyncSession; conftest truncates auth/billing.
  - patch_redis       — fakeredis.aioredis.FakeRedis; flushed between tests.
  - patch_settings_keys — ephemeral RSA keypair; COOKIE_SECURE=False.

AUTH strategy: override `current_user_or_anonymous` via
  `app.dependency_overrides[current_user_or_anonymous]` to return a UserContext
  pointing at the seeded user. Always pop overrides in teardown (try/finally or
  autouse fixture). For 401 guard tests the override is NOT installed — an absent
  cookie causes the real dep to return anonymous, which the _require_auth gate
  converts to 401.

Covered:
  1. indices happy (Yahoo mocked) → 200, 4 entries, name/value/change_pct.
  2. indices anonymous → 401.
"""

from __future__ import annotations

import uuid as _uuid

import pytest
from sqlalchemy import text

from dhanradar.deps import UserContext, current_user_or_anonymous
from dhanradar.main import app
from dhanradar.models.auth import User, UserTierEnum

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Teardown: truncate mf.* tables between tests (conftest only handles auth/billing).
# Same-connection pattern (avoids TRUNCATE deadlock in CI — see test_mood docstring).
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _truncate_mf(db_session):
    """Truncate mf.* tables after each test via db_session's own connection."""
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
# Helper: seed a User row and return its UUID string
# ---------------------------------------------------------------------------


async def _seed_user(db_session, email: str | None = None) -> str:
    """Insert a free-tier User row and return its id as a str UUID.

    Uses a client-generated UUID so the auth override can reference it before
    the DB round-trip that would generate a server-side uuid.
    """
    uid = _uuid.uuid4()
    email = email or f"dash_{uid.hex[:8]}@example.com"
    user = User(
        id=uid,
        email=email,
        hashed_password="$2b$12$placeholder_hash_for_testing_only",
        tier=UserTierEnum.free,
    )
    db_session.add(user)
    await db_session.commit()
    return str(uid)


# ---------------------------------------------------------------------------
# Helper: build the auth override lambda for a given user_id
# ---------------------------------------------------------------------------


def _auth_override(user_id: str):
    def _dep() -> UserContext:
        return UserContext(user_id=user_id, tier="free", is_anonymous=False)

    return _dep


# ---------------------------------------------------------------------------
# 1. indices — happy path (Yahoo mocked)
# ---------------------------------------------------------------------------


async def test_indices_happy_mocked(async_client, db_session, patch_redis, monkeypatch):
    """GET /indices with _quote_meta monkeypatched returns 4 entries each with
    name, value, and change_pct."""
    import dhanradar.dashboard.indices as _indices_mod

    # Monkeypatch _quote_meta to return a synthetic meta dict for every symbol.
    # `regularMarketPrice` and `chartPreviousClose` are what _signal_value reads for
    # "level" and the pct-change calc respectively.
    async def _fake_quote_meta(client, symbol: str) -> dict:
        return {
            "regularMarketPrice": 100.0,
            "chartPreviousClose": 99.0,
            "regularMarketChangePercent": 1.01,
        }

    monkeypatch.setattr(_indices_mod, "_quote_meta", _fake_quote_meta)

    user_id = await _seed_user(db_session)
    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get("/api/v1/indices")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 200, r.text
    items = r.json()
    assert isinstance(items, list), f"Expected list, got {type(items)}"
    assert len(items) == 4, f"Expected 4 index entries, got {len(items)}"
    for item in items:
        assert "name" in item, f"Missing 'name' in index entry: {item}"
        assert "value" in item, f"Missing 'value' in index entry: {item}"
        assert "change_pct" in item, f"Missing 'change_pct' in index entry: {item}"
        assert isinstance(item["value"], (int, float)), (
            f"'value' must be numeric, got {type(item['value'])}"
        )


# ---------------------------------------------------------------------------
# 2. indices — anonymous → 401
# ---------------------------------------------------------------------------


async def test_indices_anonymous_401(async_client, patch_redis):
    """No auth cookie → 401."""
    r = await async_client.get("/api/v1/indices")
    assert r.status_code == 401, r.text
