"""
Integration tests for the Transparency module (Plan Group 9 / PU2).

Endpoint covered:
  GET /api/v1/portfolio/{portfolio_id}/transparency

Infrastructure contract (same as test_dashboard / test_insights):
  - async_client        — httpx.AsyncClient over ASGITransport(app); no lifespan.
  - db_session          — function-scoped AsyncSession.
  - patch_redis         — fakeredis.aioredis.FakeRedis.
  - patch_settings_keys — ephemeral RSA keypair; COOKIE_SECURE=False.

AUTH strategy: override `current_user_or_anonymous` via
  `app.dependency_overrides[current_user_or_anonymous]`.
  Always pop overrides in teardown (try/finally).

Test coverage:
  1. happy_path         — portfolio with high/medium/low bands → 200; confidence_band,
                          drivers, sources, freshness all present; refusal null.
  2. insufficient_data  — fund scored insufficient_data → refusal block non-null,
                          explicit educational message, label == insufficient_data.
  3. wrong_user_404     — other user's portfolio_id → 404.
  4. no_numeric_leak    — unified_score absent from response body (non-neg #2).
  5. freshness_stale    — nav_date 7 days ago → is_stale=True, nav_days_ago=7.
  6. anonymous_401      — no auth override → 401.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import text

from dhanradar.deps import UserContext, current_user_or_anonymous
from dhanradar.main import app
from dhanradar.models.auth import User, UserTierEnum
from dhanradar.models.mf import (
    MfFund,
    MfNavHistory,
    MfPortfolio,
    MfUserHolding,
    UserFundScore,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Teardown: truncate mf.* between tests
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
            "mf.mf_nav_history, "
            "mf.mf_portfolios, "
            "mf.mf_funds "
            "RESTART IDENTITY CASCADE"
        )
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_user(db_session, email: str | None = None) -> str:
    uid = _uuid.uuid4()
    email = email or f"trans_{uid.hex[:8]}@example.com"
    user = User(
        id=uid,
        email=email,
        hashed_password="$2b$12$placeholder_hash_for_testing_only",
        tier=UserTierEnum.free,
    )
    db_session.add(user)
    await db_session.commit()
    return str(uid)


def _auth_override(user_id: str):
    def _dep() -> UserContext:
        return UserContext(user_id=user_id, tier="free", is_anonymous=False)
    return _dep


async def _seed_base(db_session, user_id: str, fund_count: int = 2):
    """
    Seed: User portfolio + MfFund rows + MfUserHolding rows.
    Returns (uid, portfolio_id) as UUID objects.
    """
    uid = _uuid.UUID(user_id)
    funds = [
        MfFund(
            isin=f"INF{i:03d}A01017",
            scheme_name=f"Test Fund {i}",
            category="Equity" if i % 2 == 0 else "Debt",
        )
        for i in range(1, fund_count + 1)
    ]
    db_session.add_all(funds)
    await db_session.flush()

    portfolio = MfPortfolio(user_id=uid, name="Test Portfolio")
    db_session.add(portfolio)
    await db_session.flush()

    holdings = [
        MfUserHolding(
            user_id=uid,
            portfolio_id=portfolio.id,
            isin=f"INF{i:03d}A01017",
            folio_number=f"F{i:05d}",
            units=100.0,
            source="cas",
            as_of_date=date(2026, 6, 1),
        )
        for i in range(1, fund_count + 1)
    ]
    db_session.add_all(holdings)
    await db_session.commit()
    return uid, portfolio.id


# ---------------------------------------------------------------------------
# 1. Happy path — high/medium/low bands
# ---------------------------------------------------------------------------


async def test_transparency_happy_path(async_client, db_session, patch_redis):
    """Portfolio with three funds (high/medium/low bands) → 200 with correct shape.

    Assertions:
    - 200 status
    - portfolio_id, generated_at, funds, disclosure, not_advice, disclaimer_version present
    - each fund has: isin, scheme_name, label, confidence_band, drivers, sources, freshness
    - refusal is null for non-insufficient_data funds
    - sources list non-empty
    - freshness.nav_as_of present when NAV seeded
    """
    user_id = await _seed_user(db_session)
    uid, pid = await _seed_base(db_session, user_id, fund_count=3)

    # Seed NAV history for all 3 funds (fresh — today minus 1 day)
    today = datetime.now(tz=UTC).date()
    nav_rows = [
        MfNavHistory(isin=f"INF{i:03d}A01017", nav_date=today - timedelta(days=1), nav=100.0)
        for i in range(1, 4)
    ]
    db_session.add_all(nav_rows)

    bands = ["high", "medium", "low"]
    labels = ["in_form", "on_track", "off_track"]
    score_rows = [
        UserFundScore(
            user_id=uid,
            portfolio_id=pid,
            isin=f"INF{i:03d}A01017",
            unified_score=80 - i * 10,  # server-side only; must not leak
            confidence_band=bands[i - 1],
            verb_label=labels[i - 1],
            model_version="v1",
            scored_at=datetime(2026, 6, 10, tzinfo=UTC),
        )
        for i in range(1, 4)
    ]
    db_session.add_all(score_rows)
    await db_session.commit()

    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get(f"/api/v1/portfolio/{pid}/transparency")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 200, r.text
    body = r.json()

    assert body["portfolio_id"] == str(pid)
    assert body["generated_at"]
    assert len(body["funds"]) == 3

    # Disclosure bundle present (non-neg #9)
    assert body["disclosure"]
    assert body["not_advice"] == "NOT_ADVICE"
    assert body["disclaimer_version"]

    for fund in body["funds"]:
        assert fund["isin"]
        assert fund["scheme_name"]
        valid_labels = {"in_form", "on_track", "off_track", "out_of_form", "insufficient_data"}
        assert fund["label"] in valid_labels
        assert fund["confidence_band"] in {"high", "medium", "low", "insufficient_data"}
        assert isinstance(fund["drivers"], list)
        assert fund["refusal"] is None, "Non-insufficient_data fund must have refusal=null"
        assert len(fund["sources"]) >= 1
        assert fund["freshness"]["nav_as_of"] is not None  # NAV was seeded
        assert fund["freshness"]["nav_days_ago"] is not None
        assert fund["model_version"] == "v1"


# ---------------------------------------------------------------------------
# 2. insufficient_data fund → explicit refusal block
# ---------------------------------------------------------------------------


async def test_transparency_insufficient_data_refusal(async_client, db_session, patch_redis):
    """A fund scored insufficient_data must surface an explicit refusal block (PU2).

    Assertions:
    - fund.confidence_band == "insufficient_data"
    - fund.label == "insufficient_data"
    - fund.refusal is non-null and contains reason + detail strings
    - fund.drivers is empty list
    - refusal.reason is non-empty educational text (no advisory verbs)
    """
    user_id = await _seed_user(db_session)
    uid, pid = await _seed_base(db_session, user_id, fund_count=1)

    db_session.add(
        UserFundScore(
            user_id=uid,
            portfolio_id=pid,
            isin="INF001A01017",
            unified_score=None,
            confidence_band="insufficient_data",
            verb_label="insufficient_data",
            model_version="v1",
            scored_at=datetime(2026, 6, 10, tzinfo=UTC),
        )
    )
    await db_session.commit()

    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get(f"/api/v1/portfolio/{pid}/transparency")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["funds"]) == 1
    fund = body["funds"][0]

    assert fund["confidence_band"] == "insufficient_data"
    assert fund["label"] == "insufficient_data"
    assert fund["drivers"] == []

    refusal = fund["refusal"]
    assert refusal is not None, "insufficient_data fund must have a non-null refusal block (PU2)"
    assert refusal["reason"], "refusal.reason must be non-empty"
    assert refusal["detail"], "refusal.detail must be non-empty"

    # Verify educational framing — no advisory verbs (full SEBI non-neg list)
    _advisory_verbs = (
        "buy", "sell", "hold", "switch", "invest", "redeem", "avoid", "consider", "suggest"
    )
    for advisory_verb in _advisory_verbs:
        assert advisory_verb not in refusal["reason"].lower(), (
            f"Advisory verb '{advisory_verb}' found in refusal.reason"
        )
        assert advisory_verb not in refusal["detail"].lower(), (
            f"Advisory verb '{advisory_verb}' found in refusal.detail"
        )


# ---------------------------------------------------------------------------
# 3. Wrong user's portfolio → 404
# ---------------------------------------------------------------------------


async def test_transparency_wrong_user_404(async_client, db_session, patch_redis):
    """Portfolio belonging to user_a, requested by user_b → 404 (IDOR guard)."""
    user_a = await _seed_user(db_session, email="user_a@example.com")
    user_b = await _seed_user(db_session, email="user_b@example.com")
    uid_a, pid_a = await _seed_base(db_session, user_a, fund_count=1)

    # user_b requests user_a's portfolio
    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_b)
        r = await async_client.get(f"/api/v1/portfolio/{pid_a}/transparency")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 4. No numeric leak — unified_score absent from response body
# ---------------------------------------------------------------------------


async def test_transparency_no_numeric_leak(async_client, db_session, patch_redis):
    """unified_score must NOT appear anywhere in the response body (non-neg #2)."""
    user_id = await _seed_user(db_session)
    uid, pid = await _seed_base(db_session, user_id, fund_count=1)

    db_session.add(
        UserFundScore(
            user_id=uid,
            portfolio_id=pid,
            isin="INF001A01017",
            unified_score=87,   # server-side only; must never reach the client
            confidence_band="high",
            verb_label="in_form",
            model_version="v1",
            scored_at=datetime(2026, 6, 10, tzinfo=UTC),
        )
    )
    await db_session.commit()

    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get(f"/api/v1/portfolio/{pid}/transparency")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 200, r.text
    raw = r.text

    # The numeric score value MUST NOT appear in the body
    assert "unified_score" not in raw, "unified_score must not appear in transparency response"
    # Also assert raw confidence float doesn't appear (only band strings allowed)
    assert "0.87" not in raw, "Raw numeric confidence float must not appear in response"
    # Check bare integer form too; nav_days_ago is None in this fixture so 87 cannot
    # appear via any other path. Pydantic allowlist is the structural guard; this is
    # defense-in-depth.
    # Check bare integer form too; nav_days_ago is None in this fixture so
    # 87 cannot appear via any other path.
    assert '"87"' not in raw, "Numeric score must not appear as JSON string"
    assert " 87," not in raw and " 87}" not in raw, "Numeric score must not appear as JSON int"


# ---------------------------------------------------------------------------
# 5. Freshness — stale NAV → is_stale=True + correct nav_days_ago
# ---------------------------------------------------------------------------


async def test_transparency_freshness_stale(async_client, db_session, patch_redis):
    """NAV data 7 days old → is_stale=True, nav_days_ago=7."""
    user_id = await _seed_user(db_session)
    uid, pid = await _seed_base(db_session, user_id, fund_count=1)

    today = datetime.now(tz=UTC).date()
    stale_nav_date = today - timedelta(days=7)

    db_session.add(
        MfNavHistory(isin="INF001A01017", nav_date=stale_nav_date, nav=95.50)
    )
    db_session.add(
        UserFundScore(
            user_id=uid,
            portfolio_id=pid,
            isin="INF001A01017",
            unified_score=60,
            confidence_band="medium",
            verb_label="on_track",
            model_version="v1",
            scored_at=datetime(2026, 6, 3, tzinfo=UTC),
        )
    )
    await db_session.commit()

    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get(f"/api/v1/portfolio/{pid}/transparency")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 200, r.text
    fund = r.json()["funds"][0]

    assert fund["freshness"]["is_stale"] is True, "Expected is_stale=True for 7-day-old NAV"
    assert fund["freshness"]["nav_days_ago"] == 7, (
        f"Expected nav_days_ago=7, got {fund['freshness']['nav_days_ago']}"
    )
    assert fund["freshness"]["nav_as_of"] == stale_nav_date.isoformat()


# ---------------------------------------------------------------------------
# 6. Anonymous → 401
# ---------------------------------------------------------------------------


async def test_transparency_anonymous_401(async_client, patch_redis):
    """No auth cookie → real dep returns anonymous → _require_auth → 401."""
    dummy_pid = str(_uuid.uuid4())
    r = await async_client.get(f"/api/v1/portfolio/{dummy_pid}/transparency")
    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# Owned-but-empty portfolio → 200 with empty funds list (cold-start, not 404) [B60]
# ---------------------------------------------------------------------------


async def test_transparency_owned_empty_portfolio_200(async_client, db_session, patch_redis):
    """A portfolio that exists and belongs to the user but has zero scored funds
    returns 200 with funds=[] (cold-start), never 404; disclosure bundle present."""
    user_id = await _seed_user(db_session)
    portfolio = MfPortfolio(user_id=_uuid.UUID(user_id), name="Empty Portfolio")
    db_session.add(portfolio)
    await db_session.commit()
    pid = str(portfolio.id)

    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get(f"/api/v1/portfolio/{pid}/transparency")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["portfolio_id"] == pid
    assert body["funds"] == []
    assert body["disclosure"], "disclosure must be present"
    assert body["not_advice"], "not_advice must be present"
    assert body["disclaimer_version"], "disclaimer_version must be present"
    assert "unified_score" not in r.text
