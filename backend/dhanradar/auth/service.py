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

import secrets
from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import UUID

import pyotp
from fastapi import HTTPException, status
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
from dhanradar.models.auth import Subscription, User, UserTierEnum
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
    from dhanradar.config import settings as _settings

    founding_until = _settings.FOUNDING_ACCESS_UNTIL
    if founding_until is not None and datetime.now(UTC) < founding_until:
        user.pro_access_until = founding_until
        user.pro_access_reason = "founding"

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
    """
    normalised_email = email.strip().lower()
    user: Optional[User] = await db.scalar(
        select(User).where(User.email == normalised_email)
    )

    if user is None:
        # Equalise timing: run verify against dummy hash even though we know
        # the user doesn't exist.
        verify_password(_DUMMY_HASH, password)
        _raise_invalid_credentials()

    # mypy: user is User here
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

    return user  # type: ignore[return-value]


def _raise_invalid_credentials() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid_credentials",
    )


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

    user: Optional[User] = await db.scalar(
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
    user: Optional[User] = await db.scalar(
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
