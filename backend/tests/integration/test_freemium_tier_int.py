"""
Integration tests for PHASE 5M freemium tiering — requires a live Postgres DB.

Acceptance items:
  #4  signup_user stamps pro_access_until == FOUNDING_ACCESS_UNTIL and
      pro_access_reason == "founding" when the founding window is open.
  #6  is_commentary_entitled taster consumption: taster unused → True AND
      ai_taster_used_at is set; taster already set → False.

These tests use the established db_session + async_client fixtures from conftest.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Acceptance #4 — signup_user founding stamp
# ---------------------------------------------------------------------------


async def test_signup_stamps_founding_access(async_client, db_session, monkeypatch):
    """A new signup during the founding window gets pro_access_until and
    pro_access_reason='founding' written to auth.users."""
    from dhanradar.config import settings
    from dhanradar.models.auth import User

    founding_dt = datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC)
    object.__setattr__(settings, "FOUNDING_ACCESS_UNTIL", founding_dt)

    email = f"founder_{uuid.uuid4().hex[:8]}@example.com"
    r = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "FounderPass42!"},
    )
    assert r.status_code == 201, r.text

    user_id = uuid.UUID(r.json()["user"]["id"])
    db_user = await db_session.scalar(select(User).where(User.id == user_id))
    await db_session.refresh(db_user)

    assert db_user is not None
    assert db_user.pro_access_until == founding_dt
    assert db_user.pro_access_reason == "founding"


async def test_signup_no_founding_stamp_when_window_closed(async_client, db_session, monkeypatch):
    """When FOUNDING_ACCESS_UNTIL is in the past, new signups get no pro_access_until."""
    from dhanradar.config import settings
    from dhanradar.models.auth import User

    past_dt = datetime.now(UTC) - timedelta(days=1)
    object.__setattr__(settings, "FOUNDING_ACCESS_UNTIL", past_dt)

    email = f"post_founder_{uuid.uuid4().hex[:8]}@example.com"
    r = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "PostFounderPass42!"},
    )
    assert r.status_code == 201, r.text

    user_id = uuid.UUID(r.json()["user"]["id"])
    db_user = await db_session.scalar(select(User).where(User.id == user_id))
    await db_session.refresh(db_user)

    assert db_user is not None
    assert db_user.pro_access_until is None
    assert db_user.pro_access_reason is None


# ---------------------------------------------------------------------------
# Acceptance #6 — is_commentary_entitled taster consumption (real DB write)
# ---------------------------------------------------------------------------


async def _create_free_user(db_session) -> uuid.UUID:
    """Seed a minimal free user with no pro_access_until and no ai_taster_used_at."""
    from dhanradar.auth.security import hash_password
    from dhanradar.models.auth import User, UserTierEnum

    user = User(
        email=f"taster_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("TestPass42!"),
        tier=UserTierEnum.free,
        pro_access_until=None,
        ai_taster_used_at=None,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user.id


async def test_commentary_taster_consumed_on_first_call(db_session):
    """Free user with taster unused: is_commentary_entitled → True and
    ai_taster_used_at is stamped (re-query after the call proves consumption)."""
    from sqlalchemy import select

    from dhanradar.mf.commentary import is_commentary_entitled
    from dhanradar.models.auth import User

    uid = await _create_free_user(db_session)
    user_id = str(uid)

    result = await is_commentary_entitled(user_id, db_session)
    assert result is True

    # Re-query to confirm the stamp landed.
    refreshed = await db_session.scalar(select(User).where(User.id == uid))
    await db_session.refresh(refreshed)
    assert refreshed.ai_taster_used_at is not None


async def test_commentary_taster_not_entitled_after_consumed(db_session):
    """Free user after taster consumption: is_commentary_entitled → False."""
    from dhanradar.mf.commentary import is_commentary_entitled

    uid = await _create_free_user(db_session)
    user_id = str(uid)

    # First call consumes.
    r1 = await is_commentary_entitled(user_id, db_session)
    assert r1 is True

    # Second call (same session, taster already stamped) → False.
    r2 = await is_commentary_entitled(user_id, db_session)
    assert r2 is False
