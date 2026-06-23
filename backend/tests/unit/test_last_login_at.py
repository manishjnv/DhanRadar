"""Unit tests for last_login_at stamping on genuine logins.

Covers:
  (1) Successful password login stamps last_login_at (was None → not None).
  (2) Refresh does NOT touch last_login_at (the rotate_refresh_token path
      has no DB write beyond storing the new jti — verified structurally here).
  (3) authenticate_totp stamps last_login_at.
  (4) authenticate_email_otp stamps last_login_at.

These tests run fully in-process with fakeredis and a mock AsyncSession —
they do NOT require Postgres (CI-only integration tests are in
test_admin_phase2.py / test_auth_flow.py).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(
    hashed_password: str | None = "hashed",
    totp_secret: str | None = None,
    totp_verified: bool = False,
    deletion_requested_at=None,
    suspended_at=None,
    last_login_at=None,
) -> MagicMock:
    """Return a MagicMock that quacks like a User ORM row."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.hashed_password = hashed_password
    user.totp_secret = totp_secret
    user.totp_verified = totp_verified
    user.deletion_requested_at = deletion_requested_at
    user.suspended_at = suspended_at
    user.last_login_at = last_login_at
    return user


def _make_db(user: MagicMock) -> AsyncMock:
    """Return an AsyncMock db session that returns *user* from scalar()."""
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=user)
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# (1) authenticate_user stamps last_login_at
# ---------------------------------------------------------------------------


async def test_authenticate_user_stamps_last_login_at(patch_redis):
    """A successful password login must call db.execute (the UPDATE for last_login_at)
    and db.commit before returning the user."""
    from dhanradar.auth import service as svc
    from dhanradar.auth.security import hash_password

    password = "GoodP@ssw0rd1!"
    user = _make_user(hashed_password=hash_password(password))
    db = _make_db(user)

    result = await svc.authenticate_user("test@example.com", password, db)

    assert result is user
    # record_login issues an UPDATE via db.execute + db.add (INSERT), then db.commit
    db.execute.assert_called_once()
    db.add.assert_called_once()
    db.commit.assert_called_once()


async def test_authenticate_user_wrong_password_does_not_stamp(patch_redis):
    """A failed password login must NOT call db.execute or db.commit."""
    from fastapi import HTTPException

    from dhanradar.auth import service as svc
    from dhanradar.auth.security import hash_password

    user = _make_user(hashed_password=hash_password("correct"))
    db = _make_db(user)

    with pytest.raises(HTTPException) as exc_info:
        await svc.authenticate_user("test@example.com", "wrong_password", db)

    assert exc_info.value.status_code == 401
    db.execute.assert_not_called()
    db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# (2) rotate_refresh_token does NOT touch auth.users at all
# ---------------------------------------------------------------------------


async def test_rotate_refresh_token_does_not_write_last_login_at(patch_redis):
    """Token refresh must not call record_login or write last_login_at.

    rotate_refresh_token only reads/writes Redis (GETDEL + SET).  It never
    issues a DB UPDATE on auth.users.  We verify no db session is passed to it.
    """
    from dhanradar.auth import service as svc
    from dhanradar.auth.security import create_refresh_token

    uid = str(uuid.uuid4())
    _, old_jti = create_refresh_token(uid)
    # Pre-seed the refresh jti in fakeredis
    await svc.store_refresh_jti(old_jti, uid)

    # rotate_refresh_token takes no db parameter — confirming structurally
    # that it cannot write last_login_at
    import inspect
    sig = inspect.signature(svc.rotate_refresh_token)
    assert "db" not in sig.parameters, (
        "rotate_refresh_token must not accept a db parameter — it must not write last_login_at"
    )

    # Functional check: it rotates cleanly
    access, _, refresh, _ = await svc.rotate_refresh_token(old_jti, uid)
    assert access
    assert refresh


# ---------------------------------------------------------------------------
# (3) authenticate_totp stamps last_login_at
# ---------------------------------------------------------------------------


async def test_authenticate_totp_stamps_last_login_at(patch_redis):
    """Successful TOTP login must call db.execute (UPDATE) and db.commit."""
    import pyotp

    from dhanradar.auth import service as svc

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    code = totp.now()

    user = _make_user(totp_secret=secret, totp_verified=True)
    db = _make_db(user)

    # Also mock the replay-guard Redis SET NX to return True (code not replayed)
    # and the brute-force counter to 0 (no prior failures).
    # patch_redis fixture gives us a real fakeredis, so the SET NX will work.

    result = await svc.authenticate_totp("test@example.com", code, db)

    assert result is user
    db.execute.assert_called_once()
    db.add.assert_called_once()
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# (4) authenticate_email_otp stamps last_login_at
# ---------------------------------------------------------------------------


async def test_authenticate_email_otp_stamps_last_login_at(patch_redis):
    """Successful email-OTP login must call db.execute (UPDATE) and db.commit."""
    from dhanradar.auth import email_otp as _otp
    from dhanradar.auth import service as svc

    uid = str(uuid.uuid4())
    user = _make_user()
    user.id = uuid.UUID(uid)
    db = _make_db(user)

    # Generate and store a real OTP code so the service can verify it
    code = _otp.generate_code()
    await _otp.store_code(uid, code)

    result = await svc.authenticate_email_otp("test@example.com", code, db)

    assert result is user
    db.execute.assert_called_once()
    db.add.assert_called_once()
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# (5) record_login issues UPDATE + INSERT (activity log)
# ---------------------------------------------------------------------------


async def test_record_login_issues_update_and_insert(patch_redis):
    """record_login must:
    - call db.execute once with an UPDATE targeting auth.users
    - call db.add once with a UserActivityLog row carrying the supplied method
    - call db.commit once
    """
    from dhanradar.auth import service as svc
    from dhanradar.models.auth import UserActivityLog

    user = _make_user()
    db = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()  # db.add is synchronous in SQLAlchemy async
    db.commit = AsyncMock()

    await svc.record_login(user, db, method="password")

    # UPDATE was issued
    db.execute.assert_called_once()
    update_stmt = db.execute.call_args[0][0]
    assert hasattr(update_stmt, "table"), "execute() was not called with an UPDATE statement"
    assert update_stmt.table.name == "users"

    # UserActivityLog row was added
    db.add.assert_called_once()
    added_obj = db.add.call_args[0][0]
    assert isinstance(added_obj, UserActivityLog), (
        f"db.add() received {type(added_obj)}, expected UserActivityLog"
    )
    assert added_obj.event_type == "login"
    assert added_obj.method == "password"
    assert added_obj.user_id == user.id

    # Single commit covers both writes
    db.commit.assert_called_once()


async def test_record_login_method_propagated(patch_redis):
    """The method argument is stored on the inserted UserActivityLog row."""
    from dhanradar.auth import service as svc
    from dhanradar.models.auth import UserActivityLog

    for method in ("password", "totp", "email_otp", "sso"):
        user = _make_user()
        db = AsyncMock()
        db.execute = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()

        await svc.record_login(user, db, method=method)

        added_obj = db.add.call_args[0][0]
        assert isinstance(added_obj, UserActivityLog)
        assert added_obj.method == method, f"method mismatch for {method}"


async def test_record_login_non_fatal_on_db_error(patch_redis):
    """record_login must not raise even when db.execute raises."""
    from dhanradar.auth import service as svc

    user = _make_user()
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("DB exploded"))
    db.rollback = AsyncMock()

    # Must not raise — login continues
    await svc.record_login(user, db, method="password")
    db.rollback.assert_called_once()
