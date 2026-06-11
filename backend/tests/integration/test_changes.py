"""
Integration tests for the What Changed module (Plan Group 2).

Endpoint covered:
  GET /api/v1/portfolio/{portfolio_id}/changes

Infrastructure contract (same as test_transparency):
  - async_client        — httpx.AsyncClient over ASGITransport(app); no lifespan.
  - db_session          — function-scoped AsyncSession.
  - patch_redis         — fakeredis.aioredis.FakeRedis.
  - patch_settings_keys — ephemeral RSA keypair; COOKIE_SECURE=False.

AUTH strategy: override `current_user_or_anonymous` via
  `app.dependency_overrides[current_user_or_anonymous]`.
  Always pop overrides in teardown (try/finally).

Test coverage:
  1. improved           — two snapshots: off_track→on_track → change_kind=="improved"
  2. weakened           — two snapshots: on_track→out_of_form → change_kind=="weakened"
  3. unchanged          — two snapshots: same label → change_kind=="unchanged"
  4. new (single)       — one snapshot only → change_kind=="new", label_from/as_of_from None
  5. insufficient_to    — latest snapshot is insufficient_data → change_kind=="insufficient_data"
  6. owned_empty        — portfolio exists, no history → 200 and changes==[]
  7. other_user_404     — user B requests user A portfolio → 404
  8. anonymous_401      — no auth override → 401
  9. no_numeric_leak    — unified_score / score floats absent from response body
  10. advisory_verb_scan — forbidden advisory verbs absent from full response body
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
    MfUserFundScoreHistory,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Teardown: truncate mf.* between tests (mirrors test_transparency.py)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _truncate_mf(db_session):
    yield
    await db_session.rollback()
    await db_session.execute(
        text(
            "TRUNCATE TABLE "
            "mf.mf_user_fund_score_history, "
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
    email = email or f"changes_{uid.hex[:8]}@example.com"
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


async def _seed_portfolio_and_fund(db_session, user_id: str, isin: str = "INF001A01017") -> tuple[_uuid.UUID, str]:
    """Seed a User's portfolio and one MfFund row. Returns (uid, portfolio_id str)."""
    uid = _uuid.UUID(user_id)
    fund = MfFund(isin=isin, scheme_name="Test Fund Alpha", category="Equity")
    db_session.add(fund)
    await db_session.flush()

    portfolio = MfPortfolio(user_id=uid, name="Test Portfolio")
    db_session.add(portfolio)
    await db_session.commit()
    return uid, str(portfolio.id)


async def _seed_history_rows(
    db_session,
    user_id: str,
    portfolio_id: str,
    isin: str,
    snapshots: list[tuple[date, str, str]],  # (snapshot_date, verb_label, band)
) -> None:
    """Seed MfUserFundScoreHistory rows for the given isin."""
    uid = _uuid.UUID(user_id)
    pid = _uuid.UUID(portfolio_id)
    for snap_date, verb_label, band in snapshots:
        row = MfUserFundScoreHistory(
            user_id=uid,
            portfolio_id=pid,
            isin=isin,
            snapshot_date=snap_date,
            verb_label=verb_label,
            confidence_band=band,
            model_version="v1",
            source="monthly_rescore",
        )
        db_session.add(row)
    await db_session.commit()


# ---------------------------------------------------------------------------
# 1. improved — off_track → on_track
# ---------------------------------------------------------------------------


async def test_changes_improved(async_client, db_session, patch_redis):
    """Two snapshots where off_track (prior) → on_track (latest): change_kind=='improved'."""
    user_id = await _seed_user(db_session)
    uid, pid = await _seed_portfolio_and_fund(db_session, user_id)

    today = datetime.now(tz=UTC).date()
    await _seed_history_rows(
        db_session, user_id, pid, "INF001A01017",
        [
            (today - timedelta(days=30), "off_track", "low"),   # prior
            (today - timedelta(days=1), "on_track", "medium"),  # latest
        ],
    )

    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get(f"/api/v1/portfolio/{pid}/changes")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["portfolio_id"] == pid
    assert len(body["changes"]) == 1
    change = body["changes"][0]
    assert change["change_kind"] == "improved"
    assert change["label_from"] == "off_track"
    assert change["label_to"] == "on_track"
    assert change["changed"] is True
    assert change["as_of_from"] is not None
    assert change["as_of_to"] is not None
    # Disclosure bundle present
    assert body["disclosure"]
    assert body["not_advice"] == "NOT_ADVICE"
    assert body["disclaimer_version"]


# ---------------------------------------------------------------------------
# 2. weakened — on_track → out_of_form
# ---------------------------------------------------------------------------


async def test_changes_weakened(async_client, db_session, patch_redis):
    """Two snapshots where on_track → out_of_form: change_kind=='weakened'."""
    user_id = await _seed_user(db_session)
    uid, pid = await _seed_portfolio_and_fund(db_session, user_id)

    today = datetime.now(tz=UTC).date()
    await _seed_history_rows(
        db_session, user_id, pid, "INF001A01017",
        [
            (today - timedelta(days=30), "on_track", "medium"),   # prior
            (today - timedelta(days=1), "out_of_form", "low"),    # latest
        ],
    )

    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get(f"/api/v1/portfolio/{pid}/changes")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 200, r.text
    change = r.json()["changes"][0]
    assert change["change_kind"] == "weakened"
    assert change["changed"] is True


# ---------------------------------------------------------------------------
# 3. unchanged — on_track → on_track
# ---------------------------------------------------------------------------


async def test_changes_unchanged(async_client, db_session, patch_redis):
    """Two snapshots with the same label: change_kind=='unchanged'."""
    user_id = await _seed_user(db_session)
    uid, pid = await _seed_portfolio_and_fund(db_session, user_id)

    today = datetime.now(tz=UTC).date()
    await _seed_history_rows(
        db_session, user_id, pid, "INF001A01017",
        [
            (today - timedelta(days=30), "on_track", "medium"),  # prior
            (today - timedelta(days=1), "on_track", "medium"),   # latest
        ],
    )

    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get(f"/api/v1/portfolio/{pid}/changes")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 200, r.text
    change = r.json()["changes"][0]
    assert change["change_kind"] == "unchanged"
    assert change["changed"] is False


# ---------------------------------------------------------------------------
# 4. new (single snapshot) — label_from and as_of_from are None
# ---------------------------------------------------------------------------


async def test_changes_new_single_snapshot(async_client, db_session, patch_redis):
    """Single history row: change_kind=='new', label_from is None, as_of_from is None."""
    user_id = await _seed_user(db_session)
    uid, pid = await _seed_portfolio_and_fund(db_session, user_id)

    today = datetime.now(tz=UTC).date()
    await _seed_history_rows(
        db_session, user_id, pid, "INF001A01017",
        [
            (today - timedelta(days=1), "on_track", "medium"),  # only snapshot
        ],
    )

    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get(f"/api/v1/portfolio/{pid}/changes")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 200, r.text
    change = r.json()["changes"][0]
    assert change["change_kind"] == "new"
    assert change["label_from"] is None
    assert change["as_of_from"] is None
    assert change["changed"] is False


# ---------------------------------------------------------------------------
# 5. insufficient_data on latest side
# ---------------------------------------------------------------------------


async def test_changes_insufficient_data_latest(async_client, db_session, patch_redis):
    """Prior snapshot real, latest is insufficient_data → change_kind=='insufficient_data',
    honest educational reason in body."""
    user_id = await _seed_user(db_session)
    uid, pid = await _seed_portfolio_and_fund(db_session, user_id)

    today = datetime.now(tz=UTC).date()
    await _seed_history_rows(
        db_session, user_id, pid, "INF001A01017",
        [
            (today - timedelta(days=30), "on_track", "medium"),             # prior
            (today - timedelta(days=1), "insufficient_data", "insufficient_data"),  # latest
        ],
    )

    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get(f"/api/v1/portfolio/{pid}/changes")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 200, r.text
    change = r.json()["changes"][0]
    assert change["change_kind"] == "insufficient_data"
    assert len(change["reasons"]) >= 1
    combined_reasons = " ".join(change["reasons"]).lower()
    # Honest reason present
    assert "data" in combined_reasons or "enough" in combined_reasons


# ---------------------------------------------------------------------------
# 6. owned_empty — portfolio exists but no history → 200 + changes==[]
# ---------------------------------------------------------------------------


async def test_changes_owned_empty_portfolio_200(async_client, db_session, patch_redis):
    """Portfolio exists and belongs to user, but zero history rows → 200 with changes=[]."""
    user_id = await _seed_user(db_session)
    uid = _uuid.UUID(user_id)
    portfolio = MfPortfolio(user_id=uid, name="Empty Portfolio")
    db_session.add(portfolio)
    await db_session.commit()
    pid = str(portfolio.id)

    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get(f"/api/v1/portfolio/{pid}/changes")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["portfolio_id"] == pid
    assert body["changes"] == []
    assert body["disclosure"]
    assert body["not_advice"]
    assert body["disclaimer_version"]


# ---------------------------------------------------------------------------
# 7. other_user_404 — user B requests user A portfolio → 404 (IDOR guard)
# ---------------------------------------------------------------------------


async def test_changes_other_user_404(async_client, db_session, patch_redis):
    """Portfolio belonging to user_a, requested by user_b → 404."""
    user_a = await _seed_user(db_session, email="changes_user_a@example.com")
    user_b = await _seed_user(db_session, email="changes_user_b@example.com")
    uid_a, pid_a = await _seed_portfolio_and_fund(db_session, user_a)

    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_b)
        r = await async_client.get(f"/api/v1/portfolio/{pid_a}/changes")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 8. anonymous_401 — no auth override → 401
# ---------------------------------------------------------------------------


async def test_changes_anonymous_401(async_client, patch_redis):
    """No auth cookie → anonymous UserContext → 401."""
    dummy_pid = str(_uuid.uuid4())
    r = await async_client.get(f"/api/v1/portfolio/{dummy_pid}/changes")
    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# 8b. bad_uuid_404 — malformed portfolio_id → 404 (no existence leak, never 422)
# ---------------------------------------------------------------------------


async def test_changes_bad_uuid_404(async_client, db_session, patch_redis):
    """An authed request with a non-UUID portfolio_id → 404 (not 422/500); the
    parse error must look identical to a missing/other-user portfolio (no leak)."""
    user_id = await _seed_user(db_session)
    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get("/api/v1/portfolio/not-a-uuid/changes")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 9. no_numeric_leak — unified_score and raw floats absent from response body
# ---------------------------------------------------------------------------


async def test_changes_no_numeric_leak(async_client, db_session, patch_redis):
    """unified_score and raw numeric floats must not appear in the response body (non-neg #2)."""
    user_id = await _seed_user(db_session)
    uid, pid = await _seed_portfolio_and_fund(db_session, user_id)

    today = datetime.now(tz=UTC).date()
    # Seed a NAV row with a distinctive value that must NOT appear as a score
    db_session.add(
        MfNavHistory(isin="INF001A01017", nav_date=today - timedelta(days=1), nav=150.25)
    )
    await _seed_history_rows(
        db_session, user_id, pid, "INF001A01017",
        [
            (today - timedelta(days=30), "off_track", "low"),
            (today - timedelta(days=1), "on_track", "medium"),
        ],
    )

    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get(f"/api/v1/portfolio/{pid}/changes")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 200, r.text
    raw = r.text

    # Structural guard: key must never appear
    assert "unified_score" not in raw, "unified_score must not appear in changes response"
    # No raw confidence float (a score like 0.87 or 87 must not appear)
    assert "0.87" not in raw
    assert "0.75" not in raw
    # The nav value 150.25 is a freshness metadata field (nav_as_of date string only);
    # the actual nav float itself must not appear
    assert "150.25" not in raw, "Raw NAV float must not appear in the response"


# ---------------------------------------------------------------------------
# 10. advisory_verb_scan — no forbidden advisory verb in full response body
# ---------------------------------------------------------------------------


_ADVISORY_VERBS = (
    "buy",
    "sell",
    "hold",
    "switch",
    "reduce",
    "rebalance",
    "redeem",
    "exit",
    "book",
    "consider",
    "recommend",
    "should",
    "suggest",
    "avoid",
    "caution",
    "opportunity",
    "take action",
)


async def test_changes_no_advisory_verb_in_response(async_client, db_session, patch_redis):
    """No SEBI-forbidden advisory verb may appear in the module-GENERATED copy
    (reasons / change_kind / labels). The disclosure bundle is exempt: it legitimately
    negates those verbs and is a separately-trusted imported constant."""
    user_id = await _seed_user(db_session)
    uid, pid = await _seed_portfolio_and_fund(db_session, user_id)

    today = datetime.now(tz=UTC).date()
    await _seed_history_rows(
        db_session, user_id, pid, "INF001A01017",
        [
            (today - timedelta(days=30), "off_track", "low"),
            (today - timedelta(days=1), "on_track", "medium"),
        ],
    )

    try:
        app.dependency_overrides[current_user_or_anonymous] = _auth_override(user_id)
        r = await async_client.get(f"/api/v1/portfolio/{pid}/changes")
    finally:
        app.dependency_overrides.pop(current_user_or_anonymous, None)

    assert r.status_code == 200, r.text
    body = r.json()

    # Scan only MODULE-GENERATED educational copy: reasons + change_kind + labels.
    # The disclosure bundle is deliberately EXCLUDED — it is an imported, separately
    # trusted constant that legitimately negates advisory verbs (the canonical
    # DISCLOSURE_BUNDLE ends with a non-recommendation clause naming the four verbs),
    # so scanning the full body would false-positive on that mandated negation (same
    # rationale as the transparency suite). Fund scheme names are excluded too — a
    # fund may legally carry any name.
    generated: list[str] = []
    for c in body["changes"]:
        generated.extend(c["reasons"])
        generated.append(c["change_kind"])
        generated.append(c["label_to"])
        if c["label_from"]:
            generated.append(c["label_from"])
    scan_text = " ".join(generated).lower()

    for verb in _ADVISORY_VERBS:
        assert verb not in scan_text, (
            f"Advisory verb '{verb}' found in module-generated changes copy"
        )

    # The disclosure bundle MUST still be present — it is the ONLY place the
    # negated verbs may legitimately appear.
    assert body["disclosure"]
    assert body["not_advice"] == "NOT_ADVICE"
