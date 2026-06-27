"""B85 — RLS commit-then-read 500 in the mf portfolio handlers, + the harness gap that hid it.

Three request handlers (`mf/router.py` create_portfolio / rename_portfolio / upload_cas default-create)
`await db.commit()` (which RESETS the SET LOCAL `app.user_id` GUC) then `await db.refresh(portfolio)`
on the now-FORCE-RLS `mf.mf_portfolios` → under the reset GUC the refresh re-SELECTs → 0 rows →
`InvalidRequestError` → HTTP 500, the moment RLS is active. Fix = delete the 3 refreshes (id/created_at
are RETURNING-populated + kept by `expire_on_commit=False`).

These tests MUST run AS dhanradar_app (the real RLS-bound role) — the default HTTP harness
(`async_client`/`override_get_db`) routes get_db → the OWNER session → RLS-INERT, so an HTTP POST test
would pass even with the bug. So: (a) call the real handlers on `app_session` with the per-request GUC
set, and (b) one end-to-end test via the NEW `rls_async_client` harness (get_db → app_session) that
genuinely exercises RLS. Each catches a reintroduced refresh; the class guard prevents the whole class.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select, text

from dhanradar.db_security import set_rls_user
from dhanradar.deps import UserContext
from dhanradar.mf.router import create_portfolio, rename_portfolio
from dhanradar.mf.schemas import PortfolioCreateRequest
from dhanradar.models.auth import User
from dhanradar.models.mf import MfPortfolio

pytestmark = pytest.mark.integration


async def _seed_user(db_session, email: str) -> str:
    u = User(email=email)
    db_session.add(u)
    await db_session.flush()
    uid = str(u.id)
    await db_session.commit()
    return uid


# --- service/app_session-level regression for the 3 handlers (real dhanradar_app role) ------------


async def test_create_portfolio_succeeds_under_rls(db_session, app_session):
    """create_portfolio commits then (before the fix) refreshed mf_portfolios — the commit reset the
    GUC, so under FORCE RLS the refresh 0-rowed → 500. With the refresh gone it returns the row.
    Calling the REAL handler AS dhanradar_app catches a reintroduced refresh."""
    uid = await _seed_user(db_session, "b85-create@test.dev")
    await set_rls_user(app_session, uid)  # simulate current_user_or_anonymous's per-request GUC
    ctx = UserContext(user_id=uid, tier="free", is_anonymous=False)

    result = await create_portfolio(
        db=app_session, user=ctx, body=PortfolioCreateRequest(name="RLS PF")
    )
    assert result.name == "RLS PF"
    assert uuid.UUID(result.id)  # id RETURNING-populated post-commit (no refresh needed)
    assert result.created_at  # created_at RETURNING-populated → isoformat() didn't AttributeError
    await app_session.rollback()


async def test_rename_portfolio_succeeds_under_rls(db_session, app_session):
    """rename_portfolio loads → renames → commit → (before the fix) refresh → 500 under RLS."""
    uid = await _seed_user(db_session, "b85-rename@test.dev")
    pf_id = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'orig') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()
    await db_session.commit()

    await set_rls_user(app_session, uid)
    ctx = UserContext(user_id=uid, tier="free", is_anonymous=False)
    result = await rename_portfolio(
        portfolio_id=str(pf_id), db=app_session, user=ctx, body=PortfolioCreateRequest(name="renamed")
    )
    assert result.name == "renamed"
    assert result.id == str(pf_id)
    assert result.created_at
    await app_session.rollback()


async def test_upload_cas_default_create_succeeds_under_rls(db_session, app_session):
    """The upload_cas first-upload default-portfolio create does add+commit then accesses
    portfolio.id; the deleted refresh would have 0-rowed under RLS. Mirror that exact branch AS
    dhanradar_app: id is available post-commit and the row persists for the owner."""
    uid = await _seed_user(db_session, "b85-cas-default@test.dev")
    await set_rls_user(app_session, uid)

    pf = MfPortfolio(user_id=uuid.UUID(uid), name="Default")
    app_session.add(pf)
    await app_session.commit()  # resets the SET LOCAL GUC — exactly the B85 hazard
    pid = str(pf.id)  # id RETURNING-populated; available WITHOUT a refresh
    assert uuid.UUID(pid)

    # Re-establish the GUC and confirm the row is a real persisted owner row.
    await set_rls_user(app_session, uid)
    got = await app_session.scalar(select(MfPortfolio.id).where(MfPortfolio.id == pf.id))
    assert got == pf.id
    await app_session.rollback()


# --- PR-2 fix that the same RLS-inert harness left untested: upsert_preferences read-back -----------


async def test_upsert_preferences_returns_saved_values_under_rls(db_session, app_session):
    """upsert_preferences commits then reads back via get_preferences; the PR-2 fix re-sets the GUC
    before that read (else FORCE RLS 0-rows → an all-default response after every save). AS
    dhanradar_app, assert the SAVED values come back — fails if the GUC re-set is removed."""
    from dhanradar.notifications import service as notif

    uid = await _seed_user(db_session, "b85-prefs@test.dev")
    await set_rls_user(app_session, uid)

    result = await notif.upsert_preferences(app_session, uid, {"channels_enabled": {"email": True}})
    # The PR-2 fix re-sets the GUC before upsert's internal read-back; without it that read 0-rows and
    # returns all-defaults — so a saved value here proves the re-set is present.
    assert result["channels_enabled"] == {"email": True}, (
        "post-commit read returned defaults → the GUC was not re-set before get_preferences"
    )
    # Independent confirmation the row actually PERSISTED under RLS WITH CHECK (not merely echoed from
    # the input dict): read it back via the OWNER session (RLS-bypassing).
    persisted = await db_session.scalar(
        text("SELECT channels_enabled FROM notify.notification_preferences WHERE user_id = :u"),
        {"u": uid},
    )
    assert persisted == {"email": True}
    await app_session.rollback()


# --- end-to-end via the NEW RLS-capable HTTP harness (proves the systemic gap is closed) -----------


async def test_create_portfolio_http_under_rls(db_session, rls_async_client):
    """The RLS-capable harness routes get_db → the dhanradar_app session, so an authenticated POST runs
    under FORCE RLS exactly like prod: current_user_or_anonymous sets the per-request GUC, the handler
    commits, and a reintroduced post-commit refresh would 500 HERE (the owner-session async_client is
    RLS-inert and would not). Validates both the B85 fix end-to-end and the harness itself."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "b85-http@test.dev")
    token, _ = create_access_token(uid)

    r = await rls_async_client.post(
        "/api/v1/mf/portfolios",
        json={"name": "RLS HTTP PF"},
        headers=make_auth_headers(access_token=token),
    )
    assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"
    assert r.json()["name"] == "RLS HTTP PF"


# --- class guard: no post-commit refresh on a per-user (get_db) router (pure text, no DB) ----------


def test_no_personal_table_refresh_in_per_user_routers():
    """B85 class guard: a request handler on the per-user app engine (`Depends(get_db)`) must NOT
    `db.refresh()` — its commit resets the SET LOCAL GUC, so a post-commit refresh re-SELECTs under
    FORCE RLS → 0 rows → 500. Admin routers (`Depends(get_admin_db)` → BYPASSRLS) legitimately refresh
    and are exempt. Build responses from RETURNING-populated ORM attributes instead. (Text scan: the
    exemption holds only while admin refreshes live in handlers that don't ALSO declare Depends(get_db);
    a future mixed router would be flagged — refactor or allowlist it then.)"""
    backend = Path(__file__).resolve().parents[2]
    offenders = []
    for f in (backend / "dhanradar").rglob("*router.py"):
        src = f.read_text(encoding="utf-8")
        if "Depends(get_db)" in src and re.search(r"\.refresh\(", src):
            offenders.append(str(f.relative_to(backend)))
    assert not offenders, (
        "post-commit .refresh() in a per-user (get_db) router resets the SET LOCAL GUC → RLS 0-row "
        f"500 (B85); build the response from ORM attributes instead: {offenders}"
    )
