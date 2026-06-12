"""
DhanRadar — Email OTP helpers.

Provides the low-level primitives for the email-OTP login flow:
  - Code generation (6-digit, cryptographically random, zero-padded).
  - Redis key management (own prefixes — never shared with TOTP paths).
  - Code storage (sha256 hash), cooldown, daily cap, attempt counter.
  - Code verification (timing-safe compare_digest on hashes).
  - Email delivery via notifications.channels.deliver_email.

Design invariants:
  - The raw OTP code is NEVER logged. Only the opaque DeliveryResult.code
    is logged on failure.
  - All Redis keys carry their own auth:email_otp_* prefix so there is no
    namespace collision with the TOTP keys.
  - Attempt counter is NOT reset by requesting a new code — a new code
    generation does not clear the strike count (prevents cycling codes to
    reset the counter).
  - The code key stores a sha256 hex digest of "{uid}:{code}", not the
    raw code. Verification uses hmac.compare_digest on the hashes.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Redis key prefixes — all own namespace; never shared with TOTP.
EMAIL_OTP_KEY_PREFIX = "auth:email_otp:"                    # stores hash, TTL 600s
EMAIL_OTP_COOLDOWN_PREFIX = "auth:email_otp_send_cooldown:" # SET NX EX 60
EMAIL_OTP_SEND_COUNT_PREFIX = "auth:email_otp_send_count:"  # SET NX + INCR, TTL 86400s
EMAIL_OTP_ATTEMPTS_PREFIX = "auth:email_otp_attempts:"      # SET NX + INCR, TTL 900s
EMAIL_OTP_USED_PREFIX = "auth:email_otp_used:"              # SET NX consume guard, TTL 600s

EMAIL_OTP_TTL = 600        # 10 minutes — code validity window
EMAIL_OTP_COOLDOWN_TTL = 60    # 1 minute between sends per account
EMAIL_OTP_DAILY_CAP = 10       # max sends per account per day
EMAIL_OTP_DAILY_TTL = 86400    # 24 hours for send count key
EMAIL_OTP_LOCK_LIMIT = 5       # wrong attempts before lock
EMAIL_OTP_LOCK_TTL = 900       # 15 minutes lock window


# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------

def generate_code() -> str:
    """
    Generate a cryptographically random 6-digit OTP, zero-padded.

    secrets.randbelow(1_000_000) gives a uniform integer in [0, 999_999].
    Zero-padding to 6 digits means e.g. 42 → "000042".
    """
    return str(secrets.randbelow(1_000_000)).zfill(6)


# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------

def _hash_code(uid: str, code: str) -> str:
    """Return sha256 hex of '{uid}:{code}'."""
    return hashlib.sha256(f"{uid}:{code}".encode()).hexdigest()


def _verify_code(uid: str, code: str, stored_hash: str) -> bool:
    """Timing-safe comparison against the stored hash."""
    candidate_hash = _hash_code(uid, code)
    return hmac.compare_digest(candidate_hash, stored_hash)


# ---------------------------------------------------------------------------
# Redis operations
# ---------------------------------------------------------------------------

async def store_code(uid: str, code: str) -> None:
    """
    Hash the code and store it in Redis under auth:email_otp:{uid}, TTL 600s.

    Overwrites any previously stored code (single active code per account).
    The raw code is NEVER stored or logged.
    """
    from dhanradar.redis_client import get_redis

    redis = get_redis()
    code_hash = _hash_code(uid, code)
    await redis.set(f"{EMAIL_OTP_KEY_PREFIX}{uid}", code_hash, ex=EMAIL_OTP_TTL)


async def check_and_set_cooldown(uid: str) -> bool:
    """
    Attempt to place a 60-second send cooldown for this uid.

    Returns True if cooldown was set (no prior send in last 60s → proceed).
    Returns False if cooldown already active (suppress this send attempt).

    Uses SET NX EX 60 — atomic, avoids a race where two concurrent requests
    both read "no cooldown" and both send.
    """
    from dhanradar.redis_client import get_redis

    redis = get_redis()
    result = await redis.set(
        f"{EMAIL_OTP_COOLDOWN_PREFIX}{uid}",
        "1",
        ex=EMAIL_OTP_COOLDOWN_TTL,
        nx=True,
    )
    return bool(result)


async def check_and_increment_daily_cap(uid: str) -> bool:
    """
    Increment the daily send counter for this uid.

    Returns True if the new count is within the cap (proceed with send).
    Returns False if the cap is already hit (suppress this send attempt).

    Atomicity: the first send of the day is SET NX with the 24-hour TTL in a
    single command — a crash can never leave the key without a TTL (an
    INCR-then-EXPIRE sequence could, permanently capping the account).
    """
    from dhanradar.redis_client import get_redis

    redis = get_redis()
    key = f"{EMAIL_OTP_SEND_COUNT_PREFIX}{uid}"
    placed = await redis.set(key, 1, ex=EMAIL_OTP_DAILY_TTL, nx=True)
    if placed:
        return True  # first send today — count == 1, within cap
    count = await redis.incr(key)
    return count <= EMAIL_OTP_DAILY_CAP


async def get_stored_hash(uid: str) -> str | None:
    """Fetch the stored sha256 hash for uid, or None if absent/expired."""
    from dhanradar.redis_client import get_redis

    redis = get_redis()
    return await redis.get(f"{EMAIL_OTP_KEY_PREFIX}{uid}")


async def increment_attempts(uid: str) -> int:
    """
    Increment the failed-attempt counter for uid (TTL 900s, fixed from the
    first failure — later attempts do not extend the window).

    Returns the new attempt count.
    Atomicity: the first failure is SET NX with the TTL in a single command —
    a crash can never leave the counter without a TTL (an INCR-then-EXPIRE
    sequence could, permanently locking the account).
    """
    from dhanradar.redis_client import get_redis

    redis = get_redis()
    key = f"{EMAIL_OTP_ATTEMPTS_PREFIX}{uid}"
    placed = await redis.set(key, 1, ex=EMAIL_OTP_LOCK_TTL, nx=True)
    if placed:
        return 1
    return await redis.incr(key)


async def get_attempt_count(uid: str) -> int:
    """Return the current failed-attempt count for uid (0 if absent)."""
    from dhanradar.redis_client import get_redis

    redis = get_redis()
    val = await redis.get(f"{EMAIL_OTP_ATTEMPTS_PREFIX}{uid}")
    return int(val) if val is not None else 0


async def consume_code(uid: str, code_hash: str) -> bool:
    """
    Atomically consume the verified code for uid (single-use guard).

    SET NX a PER-CODE used-marker (uid:code_hash — mirrors the TOTP replay
    guard's uid:code key shape) with the same TTL as the code's validity
    window. Exactly ONE concurrent caller receives True and may proceed to
    session issuance; every other concurrent request carrying the same
    (correct) code receives False and must be treated as a failed attempt.
    This closes the GET-hash → verify → DEL TOCTOU where two in-flight
    requests could each mint a session from one code.

    The marker is keyed per-code, NOT per-uid, and is deliberately never
    deleted: a freshly issued code has a different hash → a different marker
    key, so a successful login never blocks a later login with a new code.
    Deleting the marker on success would reopen the race (the concurrent
    loser's SET NX could land after the winner's cleanup). The marker only
    ever blocks re-spend of the one code it names, whose stored hash is
    deleted on success anyway.
    """
    from dhanradar.redis_client import get_redis

    redis = get_redis()
    placed = await redis.set(
        f"{EMAIL_OTP_USED_PREFIX}{uid}:{code_hash}",
        "1",
        ex=EMAIL_OTP_TTL,
        nx=True,
    )
    return bool(placed)


async def delete_code_and_attempts(uid: str) -> None:
    """
    Delete the code key and the attempts counter on successful verification.

    Single-use enforcement: after this call a replay of the same code will
    find no stored hash and will INCR a fresh attempts counter.
    """
    from dhanradar.redis_client import get_redis

    redis = get_redis()
    await redis.delete(
        f"{EMAIL_OTP_KEY_PREFIX}{uid}",
        f"{EMAIL_OTP_ATTEMPTS_PREFIX}{uid}",
    )


# ---------------------------------------------------------------------------
# Email delivery
# ---------------------------------------------------------------------------

async def send_otp_email(to: str, code: str) -> None:
    """
    Send the OTP code to the given email address via deliver_email.

    The raw code appears ONLY in the email body (which is never logged).
    If delivery fails, a warning is logged with the opaque result.code only —
    the code itself, the email address, and the body are never logged.

    This coroutine is designed to be safe for fire-and-forget via
    asyncio.create_task: deliver_email wraps all transport/timeout errors
    internally and returns DeliveryResult — it never raises.  The outer
    try/except is a defence-in-depth guard against unforeseen failure paths
    so the task can never die with an unobserved exception.
    """
    try:
        # Interface-only import — notifications owns all outbound delivery.
        from dhanradar.notifications.channels import deliver_email

        subject = "Your DhanRadar login code"
        html = (
            "<p>Your DhanRadar login code is: <strong>"
            f"{code}"
            "</strong></p>"
            "<p>This code is valid for <strong>10 minutes</strong>.</p>"
            "<p>If you didn't request this, you can ignore this email.</p>"
        )
        text = (
            f"Your DhanRadar login code is: {code}\n\n"
            "This code is valid for 10 minutes.\n\n"
            "If you didn't request this, you can ignore this email."
        )

        result = await deliver_email(to=to, subject=subject, html=html, text=text)
        if not result.ok:
            # Log opaque status code only — no code, no email, no body.
            logger.warning("email_otp delivery failed: %s", result.code)
    except Exception:
        logger.warning("email_otp send_otp_email unexpected error (suppressed)")
