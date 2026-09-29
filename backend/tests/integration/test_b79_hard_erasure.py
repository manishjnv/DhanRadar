"""Integration tests — B79 DPDP hard user-erasure.

Covers:
  - request_user_deletion (auth.erasure): sets deletion_requested_at, revokes
    the user's refresh jtis, flushes the tier cache — other users' Redis keys
    untouched (unit-style, direct call against db_session + fake_redis).
  - hard_erase_user: refuses an active account (no deletion_requested_at);
    once requested, purges the ledger (I12 trigger) + every personal table
    (cascade AND the no-FK signal.*/compliance.ai_output_feedback tables);
    leaves legal-retention rows (consent.consent_audit_log,
    compliance.ai_recommendation_audit, audit.payment_events) untouched;
    returns per-table counts.
  - POST /admin/users/{id}/request-deletion + /erase: 404 surface-hiding for
    anonymous/non-admin, 400 missing Idempotency-Key, 409 not-requested,
    404 unknown user, 200 + admin_actions row on success.

Infrastructure: db_session, fake_redis/patch_redis, async_client. Mirrors
test_portfolio_ledger.py (trigger install) and test_admin_phase5.py (admin
auth pattern).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text

from dhanradar.auth.erasure import (
    DeletionNotRequestedError,
    UserNotFoundError,
    hard_erase_user,
    request_user_deletion,
)
from dhanradar.mf.ledger import APPEND_ONLY_TRIGGER_STATEMENTS
from dhanradar.models.audit import AdminAction, PaymentEvent
from dhanradar.models.auth import User
from dhanradar.models.compliance import AiOutputFeedback, AiRecommendationAudit
from dhanradar.models.consent import ConsentAuditLog
from dhanradar.models.mf import MfPortfolio, MfPortfolioTransaction, MfWatchlistItem
from dhanradar.signal.models import SignalRules

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _signup(client, email: str, password: str = "EraseTest42!") -> tuple[str, str]:
    from tests.conftest import extract_cookie

    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["user"]["id"]), extract_cookie(r, "__Host-access")


async def _seed_personal_and_retention_data(db, user_id) -> None:
    """One row in every table B79's FK-map touches: personal data (to erase,
    both cascade and no-FK) + legal-retention (must survive)."""
    for stmt in APPEND_ONLY_TRIGGER_STATEMENTS:
        await db.execute(text(stmt))

    pf = MfPortfolio(user_id=user_id, name="Erasure Test Portfolio")
    db.add(pf)
    await db.flush()

    db.add(
        MfPortfolioTransaction(
            portfolio_id=pf.id,
            user_id=user_id,
            asset_class="mf",
            instrument_id="INF0009",
            folio_number="F9",
            txn_type="purchase",
            txn_date=datetime(2025, 1, 1, tzinfo=UTC).date(),
            units=Decimal("10"),
            nav_or_price=Decimal("100"),
            amount=Decimal("-1000"),
            source="cas",
            source_ref="erase-stmt-1",
        )
    )
    db.add(MfWatchlistItem(user_id=user_id, isin="INE000A00010"))
    db.add(
        SignalRules(
            user_id=user_id,
            nifty_threshold=Decimal("5.0"),
            vix_threshold=Decimal("20.0"),
            breadth_threshold=Decimal("0.5"),
            deploy_ladder={"steps": []},
        )
    )
    db.add(AiOutputFeedback(audit_id=user_id, user_id=user_id, helpful=True))

    # Legal-retention rows — must survive erasure untouched.
    db.add(
        ConsentAuditLog(
            user_id=user_id, purpose="mf_analytics", action="grant", consent_version="2026-01.v1"
        )
    )
    db.add(
        AiRecommendationAudit(
            user_id=user_id,
            recommendation_type="educational_label",
            content_hash="deadbeef",
            disclaimer_version="2026-01.v1",
        )
    )
    db.add(
        PaymentEvent(user_id=str(user_id), status="captured", row_hash="cafebabe")
    )
    await db.commit()


async def _counts(db, user_id) -> dict[str, int]:
    async def _c(model, col):
        return await db.scalar(select(func.count()).select_from(model).where(col == user_id)) or 0

    return {
        "portfolios": await _c(MfPortfolio, MfPortfolio.user_id),
        "ledger": await _c(MfPortfolioTransaction, MfPortfolioTransaction.user_id),
        "watchlist": await _c(MfWatchlistItem, MfWatchlistItem.user_id),
        "signal_rules": await _c(SignalRules, SignalRules.user_id),
        "ai_feedback": await _c(AiOutputFeedback, AiOutputFeedback.user_id),
        "consent_audit": await _c(ConsentAuditLog, ConsentAuditLog.user_id),
        "recommendation_audit": await _c(AiRecommendationAudit, AiRecommendationAudit.user_id),
        "payment_events": await _c(PaymentEvent, PaymentEvent.user_id),
    }


# ---------------------------------------------------------------------------
# 1. request_user_deletion — B4/B33(b): revokes refresh jtis + flushes tier
# ---------------------------------------------------------------------------


async def test_request_deletion_revokes_sessions(db_session, patch_redis, fake_redis):
    user = User(email="revoke-sessions@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    uid = user.id
    other_uid = "11111111-1111-1111-1111-111111111111"

    await fake_redis.set("auth:refresh:jti-a", str(uid))
    await fake_redis.set("auth:refresh:jti-b", str(uid))
    await fake_redis.set("auth:refresh:jti-other", other_uid)
    await fake_redis.set(f"auth:tier:{uid}", "pro")

    await request_user_deletion(db_session, uid)

    assert await fake_redis.get("auth:refresh:jti-a") is None
    assert await fake_redis.get("auth:refresh:jti-b") is None
    assert await fake_redis.get("auth:refresh:jti-other") == other_uid  # untouched
    assert await fake_redis.get(f"auth:tier:{uid}") is None

    refreshed = await db_session.scalar(select(User).where(User.id == uid))
    assert refreshed.deletion_requested_at is not None


async def test_request_deletion_unknown_user_raises(db_session, patch_redis):
    import uuid

    with pytest.raises(UserNotFoundError):
        await request_user_deletion(db_session, uuid.uuid4())


# ---------------------------------------------------------------------------
# 2. hard_erase_user — refusal + the actual purge
# ---------------------------------------------------------------------------


async def test_erase_refused_without_deletion_requested(db_session, patch_redis):
    user = User(email="active-account@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()

    with pytest.raises(DeletionNotRequestedError):
        await hard_erase_user(db_session, user.id)


async def test_erase_unknown_user_raises(db_session, patch_redis):
    import uuid

    with pytest.raises(UserNotFoundError):
        await hard_erase_user(db_session, uuid.uuid4())


async def test_hard_erase_purges_personal_data_keeps_legal_retention(db_session, patch_redis):
    user = User(email="full-erase@example.com")
    db_session.add(user)
    await db_session.flush()
    uid = user.id
    await _seed_personal_and_retention_data(db_session, uid)

    before = await _counts(db_session, uid)
    assert before["portfolios"] == 1
    assert before["ledger"] == 1
    assert before["watchlist"] == 1
    assert before["signal_rules"] == 1
    assert before["ai_feedback"] == 1
    assert before["consent_audit"] == 1
    assert before["recommendation_audit"] == 1
    assert before["payment_events"] == 1

    await request_user_deletion(db_session, uid)
    counts = await hard_erase_user(db_session, uid)

    assert counts["mf.mf_portfolios"] == 1
    assert counts["mf.portfolio_transactions"] == 1
    assert counts["mf.mf_watchlist_items"] == 1
    assert counts["signal.signal_rules"] == 1
    assert counts["compliance.ai_output_feedback"] == 1
    assert counts["auth.users"] == 1

    remaining_user = await db_session.scalar(select(User).where(User.id == uid))
    assert remaining_user is None

    after = await _counts(db_session, uid)
    assert after["portfolios"] == 0
    assert after["ledger"] == 0
    assert after["watchlist"] == 0
    assert after["signal_rules"] == 0
    assert after["ai_feedback"] == 0
    # Legal-retention rows survive, un-touched.
    assert after["consent_audit"] == 1
    assert after["recommendation_audit"] == 1
    assert after["payment_events"] == 1


async def test_hard_erase_ledger_delete_uses_purge_guc_not_leaked(db_session, patch_redis):
    """Sanity: without allow_ledger_purge the I12 trigger would block the cascade — confirm
    hard_erase_user's own ledger row is really gone (proves allow_ledger_purge was armed) and
    that a later, unrelated DELETE on the same session/connection is blocked again."""
    user = User(email="ledger-guc@example.com")
    db_session.add(user)
    await db_session.flush()
    uid = user.id
    await _seed_personal_and_retention_data(db_session, uid)
    await request_user_deletion(db_session, uid)
    await hard_erase_user(db_session, uid)

    remaining = await db_session.scalar(
        select(func.count()).select_from(MfPortfolioTransaction)
        .where(MfPortfolioTransaction.user_id == uid)
    )
    assert remaining == 0

    # A fresh, unrelated ledger row + DELETE on the same session must be blocked again —
    # proves the SET LOCAL purge GUC from hard_erase_user's commit did not leak forward.
    user2 = User(email="ledger-guc-2@example.com")
    db_session.add(user2)
    await db_session.flush()
    pf2 = MfPortfolio(user_id=user2.id, name="Post-erase")
    db_session.add(pf2)
    await db_session.flush()
    txn2 = MfPortfolioTransaction(
        portfolio_id=pf2.id,
        user_id=user2.id,
        asset_class="mf",
        instrument_id="INF0010",
        folio_number="F10",
        txn_type="purchase",
        txn_date=datetime(2025, 2, 1, tzinfo=UTC).date(),
        units=Decimal("1"),
        nav_or_price=Decimal("100"),
        amount=Decimal("-100"),
        source="cas",
        source_ref="post-erase-stmt",
    )
    db_session.add(txn2)
    await db_session.flush()
    await db_session.delete(txn2)
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError) as exc:
        await db_session.flush()
    assert "append-only" in str(exc.value)
    await db_session.rollback()


# ---------------------------------------------------------------------------
# 3. Admin endpoints
# ---------------------------------------------------------------------------


async def test_erase_endpoints_404_for_anonymous(async_client):
    fake_id = "00000000-0000-0000-0000-000000000001"
    for path in [
        f"/api/v1/admin/users/{fake_id}/request-deletion",
        f"/api/v1/admin/users/{fake_id}/erase",
    ]:
        r = await async_client.post(path, headers={"Idempotency-Key": "k1"})
        assert r.status_code == 404, f"{path}: {r.status_code} {r.text}"


async def test_erase_endpoints_404_for_non_admin(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")
    _uid, access = await _signup(async_client, "nonadmin_erase@example.com")
    headers = make_auth_headers(access_token=access)
    headers["Idempotency-Key"] = "k1"

    fake_id = "00000000-0000-0000-0000-000000000001"
    for path in [
        f"/api/v1/admin/users/{fake_id}/request-deletion",
        f"/api/v1/admin/users/{fake_id}/erase",
    ]:
        r = await async_client.post(path, headers=headers)
        assert r.status_code == 404, f"{path}: {r.status_code} {r.text}"


async def test_erase_requires_idempotency_key(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, admin_access = await _signup(async_client, "admin_erase_idem@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=admin_access)

    target_id, _ = await _signup(async_client, "target_erase_idem@example.com")
    r = await async_client.post(f"/api/v1/admin/users/{target_id}/erase", headers=headers)
    assert r.status_code == 400
    assert r.json()["detail"] == "idempotency_key_required"


async def test_erase_409_when_deletion_not_requested(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, admin_access = await _signup(async_client, "admin_erase_409@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=admin_access)
    headers["Idempotency-Key"] = "k1"

    target_id, _ = await _signup(async_client, "target_erase_409@example.com")
    r = await async_client.post(f"/api/v1/admin/users/{target_id}/erase", headers=headers)
    assert r.status_code == 409
    assert r.json()["detail"] == "deletion_not_requested"


async def test_erase_404_unknown_user(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, admin_access = await _signup(async_client, "admin_erase_404@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=admin_access)
    headers["Idempotency-Key"] = "k1"

    fake_id = "00000000-0000-0000-0000-000000000099"
    r = await async_client.post(f"/api/v1/admin/users/{fake_id}/erase", headers=headers)
    assert r.status_code == 404


async def test_full_flow_request_then_erase_records_admin_action(
    async_client, monkeypatch, db_session
):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, admin_access = await _signup(async_client, "admin_erase_flow@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=admin_access)

    target_id, _ = await _signup(async_client, "target_erase_flow@example.com")

    r = await async_client.post(
        f"/api/v1/admin/users/{target_id}/request-deletion", headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "status": "deletion_requested"}

    erase_headers = dict(headers)
    erase_headers["Idempotency-Key"] = "erase-flow-1"
    r = await async_client.post(
        f"/api/v1/admin/users/{target_id}/erase", headers=erase_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["counts"]["auth.users"] == 1

    action = await db_session.scalar(
        select(AdminAction)
        .where(AdminAction.action == "erase_user", AdminAction.target_id == target_id)
        .order_by(AdminAction.ts.desc())
    )
    assert action is not None
    assert action.result.startswith("erased:")

    # Retry after a successful erase — user is gone, so 404 (no double-erase).
    r = await async_client.post(
        f"/api/v1/admin/users/{target_id}/erase", headers=erase_headers
    )
    assert r.status_code == 404
