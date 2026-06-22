"""
DhanRadar — Auth service layer.

Contains all business logic for:
  - signup / login / logout / refresh
  - TOTP setup & verify (with brute-force guard)
  - Tier resolution (DB + Redis cache, 15 min TTL)
  - Refresh token storage / rotation / reuse detection in Redis

Security invariants:
  - signup: email lowercased before write; duplicate email → 409 (documented
    tradeoff: 409 leaks email existence on signup but not on login; the login
    path is uniformly 401 {"detail":"invalid_credentials"} regardless of
    whether the email exists, which is the higher-risk enumeration surface).
  - login: both "unknown email" and "wrong password" return generic 401 with
    the same error body. Argon2 verify is called even on unknown-email path
    via a dummy hash to equalise timing (belt-and-suspenders; bcrypt timing
    equalisation is less critical with Argon2id but we do it anyway).
  - Refresh reuse detection per invariant #4 in the spec.
  - TOTP brute-force: Redis INCR counter auth:totp_attempts:{user_id},
    TTL 900s; ≥5 → 429.
  - No SQL string interpolation — all queries use SQLAlchemy parameterized ORM.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

import pyotp
from fastapi import HTTPException, status
from sqlalchemy import func as sa_func
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.audit.service import record_security_event
from dhanradar.auth.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from dhanradar.config import settings
from dhanradar.models.auth import User, UserTierEnum
from dhanradar.redis_client import get_redis

# ---------------------------------------------------------------------------
# Redis key helpers
# ---------------------------------------------------------------------------

REFRESH_KEY_PREFIX = "auth:refresh:"       # auth:refresh:{jti} → user_id
TIER_CACHE_PREFIX = "auth:tier:"           # auth:tier:{user_id} → tier string
TOTP_ATTEMPTS_PREFIX = "auth:totp_attempts:"  # auth:totp_attempts:{user_id} → count
ACCESS_REVOKED_PREFIX = "auth:access_revoked:"  # auth:access_revoked:{jti} → "1"

TIER_TTL = 900       # 15 minutes
REFRESH_TTL = settings.REFRESH_TTL_DAYS * 86400
TOTP_LOCK_LIMIT = 5
TOTP_LOCK_TTL = 900  # matches brute-force window

# A dummy Argon2 hash used to equalise timing on unknown-email login attempts.
# Pre-computed once at import time so it doesn't add startup cost per request.
_DUMMY_HASH = hash_password("DummyP@ssw0rd_timing_equaliser_not_a_real_account")

# Fire-and-forget task set for email OTP delivery (R3 — timing-oracle fix).
# Keeps strong references to in-flight send tasks so they are not GC'd before
# they complete; the done-callback discards the reference on completion.
_send_tasks: set[asyncio.Task] = set()


# ---------------------------------------------------------------------------
# Tier hierarchy
# ---------------------------------------------------------------------------

TIER_ORDER: dict[str, int] = {
    "anonymous": 0,
    "free": 1,
    "pro": 2,
    "pro_plus": 3,
    "founder_lifetime": 4,  # ≥ pro_plus
}


def tier_rank(tier: str) -> int:
    return TIER_ORDER.get(tier, 0)


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Founding-access stamp helper (shared by signup_user and get_or_create_google_user)
# ---------------------------------------------------------------------------


def _apply_founding_access(user: User) -> None:
    """Stamp pro_access_until / pro_access_reason if within the founding window."""
    founding_until = settings.FOUNDING_ACCESS_UNTIL
    if founding_until is not None and datetime.now(UTC) < founding_until:
        user.pro_access_until = founding_until
        user.pro_access_reason = "founding"


async def signup_user(email: str, password: str, db: AsyncSession) -> User:
    """
    Create a new free-tier user.

    Tradeoff note: returns HTTP 409 on duplicate email (leaks existence on
    signup path).  This is intentional — it gives UX feedback to the user
    trying to sign up with an already-registered email.  The LOGIN path
    (higher risk enumeration surface) is uniformly 401 regardless of whether
    the email exists.
    """
    normalised_email = email.strip().lower()

    # Check for existing user — parameterized ORM query (no f-string SQL).
    existing = await db.scalar(
        select(User).where(User.email == normalised_email)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email_already_registered",
        )

    hashed = hash_password(password)
    user = User(
        email=normalised_email,
        hashed_password=hashed,
        tier=UserTierEnum.free,
    )

    # PHASE 5M Founding Access — stamp the configured window onto new signups.
    _apply_founding_access(user)

    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # Concurrent signup with the same email lost the race to the unique
        # constraint. The constraint protected data integrity; return the
        # same 409 the pre-check would have, not a 500.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email_already_registered",
        )
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

async def authenticate_user(email: str, password: str, db: AsyncSession) -> User:
    """
    Authenticate by email + password.

    Returns the User on success.  Raises HTTP 401 with a generic
    "invalid_credentials" detail on ANY failure — unknown email, wrong
    password, or deactivated account.  Argon2 verify is called on unknown-
    email paths against a dummy hash to avoid timing-based enumeration.

    SSO-only accounts (hashed_password is None): the dummy hash is verified for
    timing equalisation, then the same generic 401 is raised so an SSO-only
    account is indistinguishable from an unknown email on the password path.
    """
    normalised_email = email.strip().lower()
    user: User | None = await db.scalar(
        select(User).where(User.email == normalised_email)
    )

    if user is None:
        # Equalise timing: run verify against dummy hash even though we know
        # the user doesn't exist.
        verify_password(_DUMMY_HASH, password)
        _raise_invalid_credentials()

    # mypy: user is User here.
    # SSO-only users have hashed_password=None — run dummy verify for timing
    # then reject.  The caller must not learn whether the account exists.
    if user.hashed_password is None:  # type: ignore[union-attr]
        verify_password(_DUMMY_HASH, password)
        _raise_invalid_credentials()

    ok = verify_password(user.hashed_password, password)  # type: ignore[union-attr]
    if not ok:
        _raise_invalid_credentials()

    # B4 (DPDP): a user who has requested erasure must not be able to start a new
    # session. Checked AFTER password verify (so it is not an enumeration oracle —
    # the caller already proved the credentials) and fail-closed. Tearing down
    # EXISTING sessions (revoke refresh jtis + flush auth:tier cache) is the
    # erasure module's responsibility at the point it SETS deletion_requested_at.
    if user.deletion_requested_at is not None:  # type: ignore[union-attr]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account_deletion_pending",
        )
    if user.suspended_at is not None:  # type: ignore[union-attr]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account_suspended",
        )

    await record_login(user, db)  # type: ignore[arg-type]
    return user  # type: ignore[return-value]


def _raise_invalid_credentials() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid_credentials",
    )


logger = logging.getLogger(__name__)


async def record_login(user: User, db: AsyncSession) -> None:
    """Best-effort stamp of ``last_login_at`` (server NOW()) on a genuine login.

    Called from every successful authenticate_* path (password, TOTP, email-OTP)
    and the Google SSO path. Must NOT be called from the refresh-token path.

    NEVER raises: ``last_login_at`` is an observational column, so a failure here
    — a transient DB error, or migration lag where the column does not exist yet
    during a rolling deploy — must never break the login. On error it logs and
    rolls back, and the login proceeds. Commits its own UPDATE; it does not assume
    an open caller transaction (the SSO path has already committed by this point).
    """
    try:
        await db.execute(
            update(User)
            .where(User.id == user.id)
            .values(last_login_at=sa_func.now())
        )
        await db.commit()
    except Exception:  # noqa: BLE001 — observational; must never break login
        logger.warning("auth: failed to stamp last_login_at — login continues")
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Refresh token — Redis storage, rotation, reuse detection
# ---------------------------------------------------------------------------

async def store_refresh_jti(jti: str, user_id: str) -> None:
    """Persist allowed refresh jti → user_id in Redis with REFRESH_TTL."""
    redis = get_redis()
    await redis.set(f"{REFRESH_KEY_PREFIX}{jti}", user_id, ex=REFRESH_TTL)


async def rotate_refresh_token(
    old_jti: str, user_id: str
) -> tuple[str, str, str, str]:
    """
    Refresh token rotation with reuse detection (invariant #4).

    Atomically:
      1. Check old_jti exists in Redis.
      2. If NOT exists but token was otherwise valid → REUSE detected:
         delete key (best-effort), return 401.
      3. If exists: delete old key, issue new access + refresh pair,
         store new jti, return new tokens.

    Returns (access_token, access_jti, refresh_token, refresh_jti).
    """
    redis = get_redis()
    key = f"{REFRESH_KEY_PREFIX}{old_jti}"
    # ATOMIC consume: GETDEL returns the value and deletes the key in a single
    # operation. Under a concurrent double-refresh of the same jti, exactly one
    # caller gets the user_id; every other caller gets None and is treated as
    # reuse. A non-atomic GET-then-DELETE would let both racers rotate (auth
    # bypass) — Redis 7 (our pinned container) supports GETDEL.
    stored_uid = await redis.getdel(key)

    if stored_uid is None:
        # Token reuse detected — old jti already consumed or never existed.
        # Fire-and-forget security audit before raising (user_id from JWT sub).
        await record_security_event(
            event_type="refresh_reuse_detected",
            user_id=user_id,
            request_id=None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token_reuse_detected",
        )

    # Defense-in-depth: the JWT signature already binds `sub`, but if the
    # Redis-recorded owner of this jti disagrees with the token's subject,
    # something is wrong — refuse rather than mint a token for a mismatch.
    if stored_uid != user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token_owner_mismatch",
        )

    # Issue new pair
    access_token, access_jti = create_access_token(user_id)
    refresh_token, refresh_jti = create_refresh_token(user_id)
    await store_refresh_jti(refresh_jti, user_id)

    return access_token, access_jti, refresh_token, refresh_jti


async def revoke_refresh_jti(jti: str) -> None:
    """Delete a refresh jti from Redis (used on logout)."""
    redis = get_redis()
    await redis.delete(f"{REFRESH_KEY_PREFIX}{jti}")


# ---------------------------------------------------------------------------
# Access-token revocation (real logout)
#
# Access tokens are stateless RS256 JWTs, so a plain cookie-clear on logout
# would leave a captured access token usable until exp (≤15 min). We keep a
# short Redis denylist of revoked access jtis (TTL = the token's own remaining
# lifetime, so it self-expires and never grows unbounded) and reject them in
# current_user_or_anonymous.
# ---------------------------------------------------------------------------

async def revoke_access_jti(jti: str, ttl_seconds: int) -> None:
    """Denylist an access jti until it would have expired anyway."""
    if ttl_seconds <= 0:
        return
    redis = get_redis()
    await redis.set(f"{ACCESS_REVOKED_PREFIX}{jti}", "1", ex=ttl_seconds)


async def is_access_revoked(jti: str) -> bool:
    """True if this access jti was revoked by an explicit logout."""
    redis = get_redis()
    return bool(await redis.exists(f"{ACCESS_REVOKED_PREFIX}{jti}"))


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

async def logout_user(refresh_jti: str) -> None:
    """Revoke the refresh jti so the token can never be rotated again."""
    await revoke_refresh_jti(refresh_jti)


# ---------------------------------------------------------------------------
# TOTP
# ---------------------------------------------------------------------------

async def totp_setup(user: User, db: AsyncSession) -> tuple[str, str]:
    """
    Generate a new TOTP secret and provisioning URI.

    Only callable if TOTP is not yet verified (totp_verified=False).
    Returns (provisioning_uri, secret).

    Note: totp_secret stored in plaintext for this slice.
    TODO Phase: encrypt totp_secret at rest.
    """
    if user.totp_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="totp_already_verified",
        )

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user.email, issuer_name="DhanRadar")

    # Persist secret to user row (parameterized ORM, no f-string SQL).
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(totp_secret=secret)
    )
    await db.commit()

    return uri, secret


async def totp_verify(user_id: UUID, code: str, db: AsyncSession) -> None:
    """
    Verify a TOTP code and mark totp_verified=True on success.

    Brute-force guard: ≥5 failed attempts within 900s → HTTP 429.
    Uses Redis INCR + TTL.
    """
    redis = get_redis()
    attempts_key = f"{TOTP_ATTEMPTS_PREFIX}{user_id}"

    user: User | None = await db.scalar(
        select(User).where(User.id == user_id)
    )
    if user is None or user.totp_secret is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="totp_not_configured",
        )

    # Check brute-force counter before attempting verify.
    current_attempts = await redis.get(attempts_key)
    if current_attempts is not None and int(current_attempts) >= TOTP_LOCK_LIMIT:
        # Fire-and-forget security audit before raising.
        await record_security_event(
            event_type="totp_locked",
            user_id=str(user_id),
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="totp_locked",
        )

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(code):
        # Increment failure counter; set TTL only on first failure.
        count = await redis.incr(attempts_key)
        if count == 1:
            await redis.expire(attempts_key, TOTP_LOCK_TTL)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="totp_invalid",
        )

    # Success — clear counter and mark verified.
    await redis.delete(attempts_key)
    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(totp_verified=True)
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Google SSO — user resolution
# ---------------------------------------------------------------------------

# Sentinel exceptions raised inside get_or_create_google_user so the router
# can map them to the correct RedirectResponse without importing HTTPException
# at the service layer.

class _DeletionPendingError(Exception):
    """User exists but has requested account erasure."""


class _SuspendedError(Exception):
    """User account is administratively suspended."""


class _SubConflictError(Exception):
    """Email is linked to a different google_sub."""


class _AccountExistsError(Exception):
    """A password-bearing account already exists for this email — no auto-link."""


async def get_or_create_google_user(
    google_sub: str,
    email: str,
    db: AsyncSession,
) -> User:
    """
    Resolve (or create) a User for a verified Google identity.

    Resolution order:
      a) SELECT by google_sub → exists:
         - deletion_requested_at set → raise _DeletionPendingError.
         - else return user.
      b) SELECT by email → exists: apply _resolve_existing_email_user (sub
         conflict → _SubConflictError; deletion pending → _DeletionPendingError;
         password account → _AccountExistsError — auto-link is forbidden because
         local emails are never verified).
      c) No match → create new free-tier user with founding-access stamp.
         IntegrityError race on email/sub constraint → re-select and apply the
         same policy as (b).
    """
    # --- a) Lookup by google_sub ---
    user: User | None = await db.scalar(
        select(User).where(User.google_sub == google_sub)
    )
    if user is not None:
        if user.deletion_requested_at is not None:
            raise _DeletionPendingError()
        if user.suspended_at is not None:
            raise _SuspendedError()
        return user

    # --- b) Lookup by email ---
    user = await db.scalar(
        select(User).where(User.email == email)
    )
    if user is not None:
        return await _resolve_existing_email_user(user, google_sub, db)

    # --- c) Create new user ---
    new_user = User(
        email=email,
        hashed_password=None,     # SSO-only — no password
        google_sub=google_sub,
        tier=UserTierEnum.free,
    )
    _apply_founding_access(new_user)
    db.add(new_user)
    try:
        await db.commit()
    except IntegrityError:
        # Concurrent creation with the same email or google_sub lost the race.
        # Roll back, re-select, and apply the SAME linking policy as path (b).
        await db.rollback()
        user = await db.scalar(
            select(User).where(User.google_sub == google_sub)
        )
        if user is not None:
            if user.deletion_requested_at is not None:
                raise _DeletionPendingError()
            if user.suspended_at is not None:
                raise _SuspendedError()
            return user
        user = await db.scalar(
            select(User).where(User.email == email)
        )
        if user is None:
            # Should not happen; surface as an unexpected error.
            raise
        return await _resolve_existing_email_user(user, google_sub, db)

    await db.refresh(new_user)
    return new_user


async def _resolve_existing_email_user(
    user: User, google_sub: str, db: AsyncSession
) -> User:
    """
    Apply the linking policy to an existing row found by email.

    SECURITY (Tier-B review finding): DhanRadar never verifies local emails, so
    a Google identity for the same address must NOT silently take over a
    password account — an attacker who controls the address on Google's side
    (e.g. a Workspace admin for that domain) could otherwise hijack the local
    account.  Password accounts raise _AccountExistsError; explicit linking can
    be added later behind a logged-in settings flow.
    """
    if user.google_sub is not None and user.google_sub != google_sub:
        # A different Google account already owns this email row — security event.
        await record_security_event(
            event_type="google_sub_conflict",
            user_id=str(user.id),
        )
        raise _SubConflictError()
    if user.deletion_requested_at is not None:
        raise _DeletionPendingError()
    if user.suspended_at is not None:
        raise _SuspendedError()
    if user.google_sub == google_sub:
        # Concurrent-creation race: another request already linked this sub.
        return user
    if user.hashed_password is not None:
        raise _AccountExistsError()
    # Passwordless, unlinked row (not creatable today; future-proof): link it.
    await db.execute(
        update(User).where(User.id == user.id).values(google_sub=google_sub)
    )
    await db.commit()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# TOTP standalone login (Feature 2)
# ---------------------------------------------------------------------------

# Module-level dummy TOTP instance for timing equalisation on unknown-email /
# not-enrolled paths.  Constructed once at import time.
_DUMMY_TOTP = pyotp.TOTP(pyotp.random_base32())

# Redis key prefix for per-code replay guard.
TOTP_USED_KEY_PREFIX = "auth:totp_used:"

# Separate from TOTP_ATTEMPTS_PREFIX (enrolment verify) so an unauthenticated
# attacker spraying /totp/login cannot lock a victim out of completing
# enrolment on /totp/verify (cross-surface DoS — Tier-B review finding).
TOTP_LOGIN_ATTEMPTS_PREFIX = "auth:totp_login_attempts:"


async def authenticate_totp(email: str, code: str, db: AsyncSession) -> User:
    """
    Authenticate a user by TOTP code (standalone — not a second factor).

    Security invariants:
      1. Unknown email, not-enrolled (totp_secret None or totp_verified False),
         and wrong code are ALL indistinguishable: same generic 401.
      2. Brute-force lock (≥TOTP_LOCK_LIMIT failed attempts) → generic 401.
         Deliberately NOT 429 on this unauthenticated surface: a 429 would reveal
         that the account exists AND is enrolled, leaking information to an
         attacker.  The per-IP RateLimit dependency on the router already applies
         its own 429 at the transport level.
      3. Replay guard: successful codes are SET NX in Redis for 90s; a duplicate
         use within that window is treated as failure and increments the counter.
      4. deletion_requested_at → 403 (checked AFTER successful code verify so it
         is not an enumeration oracle — the caller proved knowledge of the secret).
    """
    normalised = email.strip().lower()
    redis = get_redis()

    user: User | None = await db.scalar(
        select(User).where(User.email == normalised)
    )

    # Guard: unknown email, not enrolled (secret absent or not yet verified).
    # Run dummy verify on every failure path for timing equalisation.
    if user is None or user.totp_secret is None or not user.totp_verified:
        _DUMMY_TOTP.verify(code)
        _raise_invalid_credentials()

    # mypy: user is User here
    attempts_key = f"{TOTP_LOGIN_ATTEMPTS_PREFIX}{user.id}"  # type: ignore[union-attr]

    # Brute-force lock check.
    current_attempts = await redis.get(attempts_key)
    if current_attempts is not None and int(current_attempts) >= TOTP_LOCK_LIMIT:
        # See docstring: intentionally generic 401, not 429.
        await record_security_event(
            event_type="totp_locked",
            user_id=str(user.id),  # type: ignore[union-attr]
        )
        _raise_invalid_credentials()

    # Verify TOTP code (default valid_window=0 — strict).
    totp = pyotp.TOTP(user.totp_secret)  # type: ignore[union-attr]
    if not totp.verify(code):
        count = await redis.incr(attempts_key)
        if count == 1:
            await redis.expire(attempts_key, TOTP_LOCK_TTL)
        _raise_invalid_credentials()

    # Replay guard: SET NX the used code for 90s (one TOTP step + margin).
    # If the code was already used (SET NX returns falsy) → treat as failure.
    replay_key = f"{TOTP_USED_KEY_PREFIX}{user.id}:{code}"  # type: ignore[union-attr]
    placed = await redis.set(replay_key, "1", ex=90, nx=True)
    if not placed:
        count = await redis.incr(attempts_key)
        if count == 1:
            await redis.expire(attempts_key, TOTP_LOCK_TTL)
        _raise_invalid_credentials()

    # deletion_requested_at — checked after successful verify (not an enumeration oracle).
    if user.deletion_requested_at is not None:  # type: ignore[union-attr]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account_deletion_pending",
        )
    if user.suspended_at is not None:  # type: ignore[union-attr]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account_suspended",
        )

    # Success — clear failure counter, stamp last_login_at.
    await redis.delete(attempts_key)
    await record_login(user, db)  # type: ignore[arg-type]
    return user  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Email OTP login (Feature 3 — standalone email OTP auth)
# ---------------------------------------------------------------------------

async def request_email_otp(email: str, db: AsyncSession) -> None:
    """
    Generate, store, and deliver a 6-digit OTP to the given email address.

    Security invariants:
      - ALWAYS returns silently regardless of whether the account exists,
        whether the cooldown is active, or whether the daily cap is hit.
        The caller must always respond 202 so this endpoint cannot be used
        as a user-existence oracle.
      - deletion_requested_at: silently suppressed (same silent-202 path).
      - Raw OTP code is never logged (enforced in email_otp.send_otp_email).
    """
    from dhanradar.auth import email_otp as _otp

    normalised = email.strip().lower()

    user: User | None = await db.scalar(
        select(User).where(User.email == normalised)
    )

    # Unknown email, deletion pending, suspended, cooldown active, or daily cap
    # hit → all return silently. The caller MUST always send 202.
    if user is None:
        return
    if user.deletion_requested_at is not None:
        return
    if user.suspended_at is not None:
        return

    uid = str(user.id)

    # Cooldown: one send per minute per account.
    cooldown_ok = await _otp.check_and_set_cooldown(uid)
    if not cooldown_ok:
        return

    # Daily cap: at most EMAIL_OTP_DAILY_CAP sends per account per day.
    # NOTE: we already incremented the counter inside check_and_increment_daily_cap;
    # if over cap we just return (the increment is a minor over-count on the cap
    # boundary, which is acceptable — it prevents a cap-bypass race).
    cap_ok = await _otp.check_and_increment_daily_cap(uid)
    if not cap_ok:
        return

    code = _otp.generate_code()
    await _otp.store_code(uid, code)
    # Fire-and-forget the Resend HTTP call so that known-email requests and
    # unknown-email requests (which return immediately above) take the same
    # wall-clock time and this endpoint cannot be used as a timing oracle for
    # user existence.  send_otp_email already catches/logs all delivery
    # failures internally (including transport errors — DeliveryResult is
    # returned, never raised), so the task cannot die with an unobserved
    # exception.
    task = asyncio.create_task(_otp.send_otp_email(normalised, code))
    _send_tasks.add(task)
    task.add_done_callback(_send_tasks.discard)


async def authenticate_email_otp(email: str, code: str, db: AsyncSession) -> User:
    """
    Authenticate a user by email + one-time OTP code (standalone — not 2FA).

    Security invariants (mirror authenticate_totp exactly):
      1. Unknown email and any verification failure are ALL indistinguishable:
         same generic 401 "invalid_credentials" detail.
      2. Brute-force lock (≥EMAIL_OTP_LOCK_LIMIT failed attempts) → generic 401,
         NOT 429 — a 429 on this unauthenticated surface would leak account existence.
         The per-IP RateLimit on the router already issues 429 at the transport level.
      3. Code absent/expired → increment attempts, generic 401.
      4. Wrong code → increment attempts, generic 401.
         If this increment crosses the lock threshold, fire record_security_event.
      5. Atomic consume (SET NX used-marker): exactly one concurrent request
         per code can reach session issuance; the loser gets generic 401.
      6. deletion_requested_at: refused (403) only AFTER verify + consume —
         reachable only with a proven code, same as authenticate_totp.
      7. Success: delete the code key and attempts key (single-use), return user.
    """
    from dhanradar.auth import email_otp as _otp

    normalised = email.strip().lower()

    user: User | None = await db.scalar(
        select(User).where(User.email == normalised)
    )

    # Unknown email → generic 401 (no timing equalisation needed here since
    # we are not doing a slow hash comparison, but we exit immediately).
    if user is None:
        _raise_invalid_credentials()

    # mypy: user is User here
    uid = str(user.id)  # type: ignore[union-attr]

    # Brute-force lock check.
    # The security event was already fired exactly once when the counter
    # crossed the threshold (in the increment branches below).  Do NOT fire
    # again here — repeated events on every locked attempt flood the audit log
    # and differ from the TOTP discipline where the event is transition-only.
    current_attempts = await _otp.get_attempt_count(uid)
    if current_attempts >= _otp.EMAIL_OTP_LOCK_LIMIT:
        _raise_invalid_credentials()

    # Fetch stored hash. Absent or expired → increment attempts, generic 401.
    stored_hash = await _otp.get_stored_hash(uid)
    if stored_hash is None:
        new_count = await _otp.increment_attempts(uid)
        if new_count >= _otp.EMAIL_OTP_LOCK_LIMIT:
            await record_security_event(event_type="email_otp_locked", user_id=uid)
        _raise_invalid_credentials()

    # Timing-safe code comparison.
    if not _otp._verify_code(uid, code, stored_hash):  # type: ignore[arg-type]
        new_count = await _otp.increment_attempts(uid)
        if new_count >= _otp.EMAIL_OTP_LOCK_LIMIT:
            await record_security_event(event_type="email_otp_locked", user_id=uid)
        _raise_invalid_credentials()

    # Atomic single-use consume (SET NX on a per-code marker) — closes the
    # TOCTOU where two concurrent requests with the same correct code both
    # pass the hash check above and each mint a session. Exactly one wins;
    # the loser is treated as a failed attempt. Mirrors the TOTP replay
    # guard. Per-code keying means a new code is never blocked by an old
    # marker (no post-login lockout window).
    if not await _otp.consume_code(uid, stored_hash):  # type: ignore[arg-type]
        new_count = await _otp.increment_attempts(uid)
        if new_count >= _otp.EMAIL_OTP_LOCK_LIMIT:
            await record_security_event(event_type="email_otp_locked", user_id=uid)
        _raise_invalid_credentials()

    # deletion_requested_at — checked after successful verify + consume, so
    # the 403 is only reachable by a caller who proved knowledge of the OTP
    # (mirrors authenticate_totp; NOT an unauthenticated enumeration oracle).
    if user.deletion_requested_at is not None:  # type: ignore[union-attr]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account_deletion_pending",
        )
    if user.suspended_at is not None:  # type: ignore[union-attr]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account_suspended",
        )

    # Success: single-use enforcement — delete code key + attempts key, stamp last_login_at.
    await _otp.delete_code_and_attempts(uid)
    await record_login(user, db)  # type: ignore[arg-type]
    return user  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Tier resolution
# ---------------------------------------------------------------------------

async def resolve_tier_with_db(user_id: str, db: AsyncSession) -> str:
    """
    Resolve tier with Redis cache + DB fallback in one call.

    Cache: reads auth:tier:{user_id} (TTL 900s). On miss: reads users.tier
    from Postgres and repopulates the cache. This is the single tier-resolution
    entry point used by deps.py and the webhook service (it always has a
    session in scope, so there is no session-less variant).
    """
    redis = get_redis()
    cache_key = f"{TIER_CACHE_PREFIX}{user_id}"

    cached = await redis.get(cache_key)
    if cached is not None:
        return cached

    # DB read — parameterized ORM
    user: User | None = await db.scalar(
        select(User).where(User.id == user_id)
    )
    if user is None:
        return "anonymous"

    tier_str = user.tier.value if isinstance(user.tier, UserTierEnum) else str(user.tier)
    await redis.set(cache_key, tier_str, ex=TIER_TTL)
    return tier_str


async def flush_tier_cache(user_id: str) -> None:
    """Invalidate the tier cache entry for *user_id* (called by webhook)."""
    redis = get_redis()
    await redis.delete(f"{TIER_CACHE_PREFIX}{user_id}")
