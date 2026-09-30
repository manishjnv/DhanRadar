"""
DhanRadar — Auth Security primitives.

Responsibilities:
  - Argon2id password hashing / constant-time verification
  - RS256 JWT encode / decode (access + refresh)
  - Cookie set / clear helpers (HttpOnly __Host- prefix cookies)

Security invariants enforced here:
  • Argon2id via argon2-cffi — never store/log plaintext.
  • RS256 only — alg:none and HS256 are rejected explicitly.
  • Every token carries jti (uuid4), iat, exp, sub, typ.
  • Cookie names use __Host- prefix → browser enforces Secure+Path=/ and
    no Domain attribute.  HttpOnly and SameSite=lax are set explicitly.
  • Refresh cookie Path=/ (not scoped to /api/v1/auth/refresh) so the
    browser sends it on the refresh endpoint; scoping is enforced server-side
    by the refresh route only consuming the __Host-refresh cookie.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Response

from dhanradar.config import settings

# ---------------------------------------------------------------------------
# Argon2id hasher — library defaults are OWASP-compliant
# ---------------------------------------------------------------------------
_ph = PasswordHasher()


def hash_password(plaintext: str) -> str:
    """Return an Argon2id hash.  Never call with an empty string."""
    return _ph.hash(plaintext)


def verify_password(hashed: str, plaintext: str) -> bool:
    """
    Constant-time Argon2id verification.

    Returns True on match.  On any mismatch/invalid-hash/error returns False
    WITHOUT leaking whether the email exists — callers must return the same
    generic error response for unknown-email and wrong-password paths.
    """
    try:
        return _ph.verify(hashed, plaintext)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# ---------------------------------------------------------------------------
# JWT — RS256 encode / decode
# ---------------------------------------------------------------------------

_ALGORITHM = "RS256"
_ALLOWED_ALGORITHMS = ["RS256"]  # explicitly deny HS256 and alg:none


def _now_utc() -> datetime:
    return datetime.now(UTC)


def create_access_token(user_id: str) -> tuple[str, str]:
    """
    Issue an RS256 access token.

    Returns (encoded_jwt, jti).
    TTL: settings.ACCESS_TTL_MIN minutes.
    """
    jti = str(uuid.uuid4())
    now = _now_utc()
    payload = {
        "sub": user_id,
        "jti": jti,
        "typ": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TTL_MIN),
    }
    token = jwt.encode(payload, settings.jwt_private_key, algorithm=_ALGORITHM)
    return token, jti


def create_refresh_token(user_id: str, session_start: int | None = None) -> tuple[str, str]:
    """
    Issue an RS256 refresh token.

    Returns (encoded_jwt, jti).
    `sst` = session start (epoch s, the original sign-in), carried through every
    rotation so `exp` is an ABSOLUTE cap of REFRESH_TTL_DAYS from sign-in — a
    rotation never restarts the clock. Omit `session_start` at sign-in.
    """
    jti = str(uuid.uuid4())
    now = _now_utc()
    sst = session_start if session_start is not None else int(now.timestamp())
    payload = {
        "sub": user_id,
        "jti": jti,
        "typ": "refresh",
        "iat": now,
        "sst": sst,
        "exp": datetime.fromtimestamp(sst, UTC) + timedelta(days=settings.REFRESH_TTL_DAYS),
    }
    token = jwt.encode(payload, settings.jwt_private_key, algorithm=_ALGORITHM)
    return token, jti


def create_deletion_cancel_token(user_id: str, deletion_requested_at: datetime) -> str:
    """
    Issue an RS256 "deletion cancel" token — the link emailed on a deletion
    request so the user can undo it within the wait window.

    ``drq`` (deletion-requested epoch seconds) is carried so the cancel route
    can refuse a token from a STALE request (the account was cancelled and
    re-requested since the email was sent) without a DB round trip up front.
    ``exp`` = drq + ERASURE_DUE — the token outlives the cancel window itself
    (ERASURE_WAIT) so a slow-reading user can still cancel up to the erasure
    deadline; the route's own drq-equality check is the real gate.
    """
    from dhanradar.compliance.data_policy import ERASURE_DUE

    jti = str(uuid.uuid4())
    now = _now_utc()
    drq = int(deletion_requested_at.timestamp())
    payload = {
        "sub": user_id,
        "jti": jti,
        "typ": "deletion_cancel",
        "iat": now,
        "drq": drq,
        "exp": datetime.fromtimestamp(drq, UTC) + ERASURE_DUE,
    }
    return jwt.encode(payload, settings.jwt_private_key, algorithm=_ALGORITHM)


def decode_token(
    token: str, expected_typ: Literal["access", "refresh", "deletion_cancel"]
) -> dict:
    """
    Decode and validate an RS256 JWT.

    Raises jwt.PyJWTError subclasses on any failure (expired, bad sig,
    wrong alg, missing/wrong typ, alg:none).  Callers must catch and
    convert to HTTP 401/400.

    Invariants enforced:
      - algorithms= whitelist rejects alg:none and HS256 at the PyJWT level.
      - `typ` claim is verified against expected_typ after decode — an access
        or refresh token is never accepted where a deletion_cancel token is
        expected, and vice versa.
    """
    payload = jwt.decode(
        token,
        settings.jwt_public_key,
        algorithms=_ALLOWED_ALGORITHMS,
        options={"require": ["sub", "jti", "typ", "iat", "exp"]},
    )
    if payload.get("typ") != expected_typ:
        raise jwt.InvalidTokenError(
            f"Token type mismatch: expected '{expected_typ}', got '{payload.get('typ')}'"
        )
    return payload


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------

_ACCESS_COOKIE = "__Host-access"
_REFRESH_COOKIE = "__Host-refresh"

# __Host- prefix rules (RFC 6265bis §4.1.3):
#   MUST be Secure, MUST have Path=/, MUST NOT have Domain attribute.
# We set SameSite=lax and HttpOnly on both.
_COOKIE_KWARGS = dict(
    httponly=True,
    secure=settings.COOKIE_SECURE,
    samesite="lax",
    path="/",
    # No `domain` kwarg — required for __Host- prefix compliance.
)


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Write __Host-access and __Host-refresh cookies onto *response*."""
    access_max_age = settings.ACCESS_TTL_MIN * 60
    refresh_max_age = settings.REFRESH_TTL_DAYS * 86400

    response.set_cookie(
        key=_ACCESS_COOKIE,
        value=access_token,
        max_age=access_max_age,
        **_COOKIE_KWARGS,
    )
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=refresh_token,
        max_age=refresh_max_age,
        **_COOKIE_KWARGS,
    )


def clear_auth_cookies(response: Response) -> None:
    """Expire both auth cookies (used on logout)."""
    response.delete_cookie(key=_ACCESS_COOKIE, path="/", secure=settings.COOKIE_SECURE, httponly=True, samesite="lax")
    response.delete_cookie(key=_REFRESH_COOKIE, path="/", secure=settings.COOKIE_SECURE, httponly=True, samesite="lax")


def get_access_cookie_name() -> str:
    return _ACCESS_COOKIE


def get_refresh_cookie_name() -> str:
    return _REFRESH_COOKIE
