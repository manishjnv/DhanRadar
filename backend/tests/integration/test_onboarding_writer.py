"""Integration tests for the B43 onboarding risk-quiz service writer.

Verifies that set_risk_profile persists the computed profile to auth.users.risk_profile
and that onboarding is the sole writer of that column.

Fixtures used: db_session, db_tables (from conftest.py).
The db_session teardown truncates auth.users CASCADE — no explicit row cleanup needed.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text

from dhanradar.models.auth import User
from dhanradar.onboarding.service import set_risk_profile

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helper — insert a bare User row with risk_profile=None
# ---------------------------------------------------------------------------


async def _insert_user(db_session) -> User:
    """Insert a minimal User row; return the ORM object."""
    uid = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO auth.users (id, email, hashed_password, tier) "
            "VALUES (:id, :email, 'x', 'free')"
        ),
        {"id": uid, "email": f"quiz_{uid.hex[:8]}@example.com"},
    )
    await db_session.commit()

    user = await db_session.scalar(select(User).where(User.id == uid))
    assert user is not None
    assert user.risk_profile is None
    return user


# ---------------------------------------------------------------------------
# (a) Normal write — returns "aggressive", persists to DB
# ---------------------------------------------------------------------------


async def test_set_risk_profile_persists_aggressive(db_session, db_tables):
    user = await _insert_user(db_session)

    result = await set_risk_profile(db_session, str(user.id), [3, 3, 3, 3, 3])

    assert result == "aggressive"

    # Re-read from DB to confirm persistence (bypass any ORM cache).
    persisted = await db_session.scalar(
        select(User.risk_profile).where(User.id == user.id)
    )
    assert persisted == "aggressive"


# ---------------------------------------------------------------------------
# (b) Conservative write
# ---------------------------------------------------------------------------


async def test_set_risk_profile_persists_conservative(db_session, db_tables):
    user = await _insert_user(db_session)

    result = await set_risk_profile(db_session, str(user.id), [0, 0, 0, 0, 0])

    assert result == "conservative"

    persisted = await db_session.scalar(
        select(User.risk_profile).where(User.id == user.id)
    )
    assert persisted == "conservative"


# ---------------------------------------------------------------------------
# (c) Overwrite — a second call updates the value
# ---------------------------------------------------------------------------


async def test_set_risk_profile_overwrites_existing(db_session, db_tables):
    user = await _insert_user(db_session)

    await set_risk_profile(db_session, str(user.id), [0, 0, 0, 0, 0])
    result = await set_risk_profile(db_session, str(user.id), [3, 3, 3, 3, 3])

    assert result == "aggressive"

    persisted = await db_session.scalar(
        select(User.risk_profile).where(User.id == user.id)
    )
    assert persisted == "aggressive"


# ---------------------------------------------------------------------------
# (d) Invalid answers — raises ValueError, no DB commit
# ---------------------------------------------------------------------------


async def test_set_risk_profile_invalid_answers_raises(db_session, db_tables):
    user = await _insert_user(db_session)

    with pytest.raises(ValueError):
        await set_risk_profile(db_session, str(user.id), [0, 0, 0])  # wrong length

    # risk_profile must still be None (no partial write committed)
    persisted = await db_session.scalar(
        select(User.risk_profile).where(User.id == user.id)
    )
    assert persisted is None


# ---------------------------------------------------------------------------
# (e) Malformed user_id — raises ValueError
# ---------------------------------------------------------------------------


async def test_set_risk_profile_bad_uuid_raises(db_session, db_tables):
    with pytest.raises(ValueError):
        await set_risk_profile(db_session, "not-a-uuid", [1, 1, 1, 1, 1])
