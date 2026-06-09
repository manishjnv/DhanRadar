"""
Integration tests for the Dashboard module (B56).

Endpoints covered:
  GET /api/v1/portfolio/summary
  GET /api/v1/indices
  GET /api/v1/instruments/top-scored?type=fund

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

Non-numeric-leak invariant (non-neg #2): assert "unified_score" never appears
anywhere in the raw response body JSON.

Covered:
  1. portfolio/summary happy: seeded user with portfolio + holdings + scores → 200,
     fund_count, label+band in funds, no unified_score leak, disclosure bundle present.
  2. portfolio/summary cold-start: authed user with no portfolio → 404 RFC7807.
  3. portfolio/summary anonymous → 401.
  4. indices happy (Yahoo mocked) → 200, 4 entries, name/value/change_pct.
  5. indices anonymous → 401.
  6. top-scored happy: 3 scores seeded → 200, ranked in_form first, no unified_score.
  7. top-scored anonymous → 401.
  8. top-scored type!=fund → 200 empty list.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from dhanradar.deps import UserContext, current_user_or_anonymous
from dhanradar.main import app
from dhanradar.models.auth import User, UserTierEnum
from dhanradar.models.mf import (
    MfFund,
    MfPortfolio,
    MfUserHolding,
    UserFundScore,
)

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
# 1. portfolio/summary — happy path
# ---------------------------------------------------------------------------


async def test_portfolio_summary_happy(async_client, db_session, patch_redis):
    """Seeded user with portfolio + 2 holdings + 2 scores → 200 with correct shape;
    unified_score must NOT appear anywhere in the JSON response body."""
    user_id = await _seed_user(db_session)
    uid = _uuid.UUID(user_id)

    # Seed MfFund rows (left-joined in the service)
    fund1 = MfFund(isin="INF111A01017", scheme_name="Alpha Equity Fund", category="Equity")
    fund2 = MfFund(isin="INF222B01025", scheme_name="Beta Debt Fund", category="Debt")
    db_session.add_all([fund1, fund2])
    await db_session.flush()

    # Seed portfolio container
    portfolio = MfPortfolio(user_id=uid, name="My Portfolio")
    db_session.add(portfolio)
    await db_session.flush()

    # Seed two holdings (minimal required fields)
    h1 = MfUserHolding(
        user_id=uid,
        portfolio_id=portfolio.id,
        isin="INF111A01017",
        folio_number="12345",
        units=100.0,
    )
    h2 = MfUserHolding(
        user_id=uid,
        portfolio_id=portfolio.id,
        isin="INF222B01025",
        folio_number="67890",
        units=50.0,
    )
    db_session.add_all([h1, h2])
    await db_session.flush()

    # Seed UserFundScore rows (unified_score stored server-side only)
    s1 = UserFundScore(
        user_id=uid,
        portfolio_id=portfolio.id,
        isin="INF111A01017",
        unified_score=72,
        confidence_band="high",
        verb_label="in_form",
        model_version="v1",
        scored_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    s2 = UserFundScore(
        user_id=uid,
        portfolio_id=portfolio.id,
        isin="INF222B01025",
        unified_score=45,
        confidence_band="medium",
        verb_label="on_track",
        model_version="v1",
        scored_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    db_session.add_all([s1, s2])
    await db_session.commit()

    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get("/api/v1/portfolio/summary")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 200, r.text
    body = r.json()

    # fund_count must match the 2 distinct ISINs we seeded
    assert body["fund_count"] == 2, f"Expected fund_count=2, got {body['fund_count']}"

    # Each fund must carry label and confidence_band
    fund_isins = {f["isin"] for f in body["funds"]}
    assert "INF111A01017" in fund_isins
    assert "INF222B01025" in fund_isins
    for fund in body["funds"]:
        assert "label" in fund, f"Missing 'label' in fund: {fund}"
        assert "confidence_band" in fund, f"Missing 'confidence_band' in fund: {fund}"

    # Disclosure bundle must be present
    assert body.get("disclosure"), "disclosure must be present and non-empty"
    assert body.get("not_advice"), "not_advice must be present and non-empty"
    assert body.get("disclaimer_version"), "disclaimer_version must be present"

    # CRITICAL: unified_score must NOT leak into the client JSON (non-neg #2)
    raw_body = r.text
    assert "unified_score" not in raw_body, (
        "unified_score must NOT appear in the portfolio/summary response body"
    )


# ---------------------------------------------------------------------------
# 2. portfolio/summary — cold-start (no portfolio) → 404 RFC7807
# ---------------------------------------------------------------------------


async def test_portfolio_summary_cold_start_404(async_client, db_session, patch_redis):
    """Authed user with no portfolio row → 404 with RFC7807 problem+json fields."""
    user_id = await _seed_user(db_session)

    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get("/api/v1/portfolio/summary")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 404, r.text
    # FastAPI default exception handler wraps to {"detail": ...}; the router raises
    # HTTPException(404, detail="no_portfolio") which becomes {"detail": "no_portfolio"}.
    body = r.json()
    assert body.get("detail") == "no_portfolio", (
        f"Expected detail='no_portfolio', got {body!r}"
    )


# ---------------------------------------------------------------------------
# 3. portfolio/summary — anonymous → 401
# ---------------------------------------------------------------------------


async def test_portfolio_summary_anonymous_401(async_client, patch_redis):
    """No auth cookie → real dep returns anonymous → _require_auth → 401."""
    r = await async_client.get("/api/v1/portfolio/summary")
    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# 4. indices — happy path (Yahoo mocked)
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
# 5. indices — anonymous → 401
# ---------------------------------------------------------------------------


async def test_indices_anonymous_401(async_client, patch_redis):
    """No auth cookie → 401."""
    r = await async_client.get("/api/v1/indices")
    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# 6. top-scored — happy path with label ranking
# ---------------------------------------------------------------------------


async def test_top_scored_happy_ranked(async_client, db_session, patch_redis):
    """Seed 3 UserFundScore rows with labels in_form/on_track/off_track; GET
    /instruments/top-scored?type=fund must return 200, ranked in_form first, and
    must NOT expose unified_score in the response body."""
    user_id = await _seed_user(db_session)
    uid = _uuid.UUID(user_id)

    # Seed MfFund rows
    funds = [
        MfFund(isin="INF001A01011", scheme_name="Alpha Fund", category="Equity"),
        MfFund(isin="INF002B01012", scheme_name="Beta Fund", category="Hybrid"),
        MfFund(isin="INF003C01013", scheme_name="Gamma Fund", category="Debt"),
    ]
    db_session.add_all(funds)
    await db_session.flush()

    portfolio = MfPortfolio(user_id=uid, name="Top Scored Portfolio")
    db_session.add(portfolio)
    await db_session.flush()

    scores = [
        UserFundScore(
            user_id=uid,
            portfolio_id=portfolio.id,
            isin="INF001A01011",
            unified_score=80,
            confidence_band="high",
            verb_label="in_form",
            model_version="v1",
            scored_at=datetime(2026, 6, 1, tzinfo=UTC),
        ),
        UserFundScore(
            user_id=uid,
            portfolio_id=portfolio.id,
            isin="INF002B01012",
            unified_score=55,
            confidence_band="medium",
            verb_label="on_track",
            model_version="v1",
            scored_at=datetime(2026, 6, 1, tzinfo=UTC),
        ),
        UserFundScore(
            user_id=uid,
            portfolio_id=portfolio.id,
            isin="INF003C01013",
            unified_score=30,
            confidence_band="low",
            verb_label="off_track",
            model_version="v1",
            scored_at=datetime(2026, 6, 1, tzinfo=UTC),
        ),
    ]
    db_session.add_all(scores)
    await db_session.commit()

    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get("/api/v1/instruments/top-scored?type=fund")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 200, r.text
    body = r.json()
    items = body["funds"]
    assert isinstance(items, list), f"Expected list under 'funds', got {type(items)}"
    assert len(items) == 3, f"Expected 3 top-scored items, got {len(items)}"

    # First item must be the in_form fund (best label rank)
    assert items[0]["isin"] == "INF001A01011", (
        f"Expected in_form fund first, got isin={items[0]['isin']!r}"
    )
    assert items[0]["label"] == "in_form"

    # Each item must carry scheme_name, category, label, confidence_band
    for item in items:
        assert "isin" in item
        assert "scheme_name" in item
        assert "category" in item
        assert "label" in item
        assert "confidence_band" in item

    # Label surface → disclosure bundle must ride along (non-neg #9).
    assert body.get("disclosure"), "disclosure must be present on the top-scored surface"
    assert body.get("not_advice"), "not_advice must be present on the top-scored surface"
    assert body.get("disclaimer_version"), "disclaimer_version must be present"

    # CRITICAL: unified_score must NOT leak into the response (non-neg #2)
    raw_body = r.text
    assert "unified_score" not in raw_body, (
        "unified_score must NOT appear in the top-scored response body"
    )


# ---------------------------------------------------------------------------
# 7. top-scored — anonymous → 401
# ---------------------------------------------------------------------------


async def test_top_scored_anonymous_401(async_client, patch_redis):
    """No auth cookie → 401."""
    r = await async_client.get("/api/v1/instruments/top-scored?type=fund")
    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# 8. top-scored — type!=fund → 200 empty list
# ---------------------------------------------------------------------------


async def test_top_scored_unknown_type_returns_empty(async_client, db_session, patch_redis):
    """GET /instruments/top-scored?type=stock (non-fund) must return 200 with an
    empty list — not a 4xx — so the widget renders its empty state cleanly."""
    user_id = await _seed_user(db_session)

    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get("/api/v1/instruments/top-scored?type=stock")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["funds"] == [], f"Expected empty funds for type=stock, got {body['funds']!r}"
