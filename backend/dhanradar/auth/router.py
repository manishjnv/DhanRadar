"""
DhanRadar — Auth API router.

Endpoints:
  POST /api/v1/auth/signup
  POST /api/v1/auth/login
  POST /api/v1/auth/logout
  POST /api/v1/auth/refresh
  GET  /api/v1/auth/me
  POST /api/v1/auth/totp/setup
  POST /api/v1/auth/totp/verify
  POST /api/v1/auth/totp/login         (Feature 2: standalone TOTP login)
  GET  /api/v1/auth/google/start       (Feature 1: Google SSO — begin flow)
  GET  /api/v1/auth/google/callback    (Feature 1: Google SSO — code exchange)
  POST /api/v1/auth/email-otp/request  (Feature 3: email OTP — request code)
  POST /api/v1/auth/email-otp/login    (Feature 3: email OTP — verify & login)

All tokens are issued as RS256 JWTs in HttpOnly __Host-* cookies.
The JS layer never reads the token value.

Security notes:
  - Login 401 is generic "invalid_credentials" regardless of failure reason.
  - Signup 409 on duplicate email (intentional tradeoff — see service.py).
  - /refresh implements rotation + reuse detection.
  - Logout clears both cookies AND revokes the refresh jti in Redis.
  - Google callback failures redirect to /login?error= (browser navigation path).
  - Tokens are NEVER put in URLs, response bodies, or non-HttpOnly cookies.
  - email-otp/request always returns 202 regardless of whether the account exists.
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.auth import google as google_svc
from dhanradar.auth import schemas
from dhanradar.auth import service as auth_svc
from dhanradar.auth.security import (
    clear_auth_cookies,
    create_access_token,
    create_refresh_token,
    decode_token,
    set_auth_cookies,
)
from dhanradar.config import settings
from dhanradar.db import get_db
from dhanradar.deps import UserContext, current_user_or_anonymous
from dhanradar.ratelimit import RateLimit
from dhanradar.redis_client import get_redis

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_response(user: object) -> schemas.UserResponse:
    """Build a UserResponse with is_admin computed from settings.admin_user_ids.

    is_admin MUST be set on EVERY auth response that emits a user (login, signup,
    TOTP login, email-OTP login, /me) — not just /me. The frontend admin guard reads
    the login-seeded `me` cache; if login omits is_admin (schema default False), an
    admin who just logged in is wrongly 404'd at /admin until the cache goes stale.
    Mirrors RequireAdmin()'s canonical-UUID normalisation.
    """
    from uuid import UUID

    data = schemas.UserResponse.model_validate(user)
    try:
        data.is_admin = str(UUID(str(user.id))) in settings.admin_user_ids  # type: ignore[attr-defined]
    except (ValueError, TypeError):
        data.is_admin = False
    return data

# Per-IP (CF-Connecting-IP) brute-force / abuse guards. Login and TOTP-verify
# are the credential-guessing surfaces, so they are tighter than the
# architecture's generic anon 30 r/m. Realises the architecture's
# "anon:10m rate=30r/m" zone at the app layer (no nginx in this deployment).
_rl_login = RateLimit(max_requests=5, window_seconds=60)
_rl_signup = RateLimit(max_requests=5, window_seconds=60)
_rl_refresh = RateLimit(max_requests=30, window_seconds=60)
_rl_totp = RateLimit(max_requests=10, window_seconds=60)
# Google SSO: 10 starts per minute per IP (prevents state-spray).
_rl_google = RateLimit(max_requests=10, window_seconds=60)
# Standalone TOTP login: tighter than setup/verify.
_rl_totp_login = RateLimit(max_requests=5, window_seconds=60)
# Email OTP: request is looser (3/min per IP); login is the credential-guessing
# surface so matches the password-login limit (5/min per IP).
_rl_email_otp_request = RateLimit(max_requests=3, window_seconds=60)
_rl_email_otp_login = RateLimit(max_requests=5, window_seconds=60)

_OAUTH_STATE_TTL = 600  # seconds — matches the Google flow time-to-live
_OAUTH_STATE_PREFIX = "auth:oauth_state:"


# ---------------------------------------------------------------------------
# POST /auth/signup
# ---------------------------------------------------------------------------

@router.post(
    "/signup",
    response_model=schemas.SignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new free-tier account",
)
async def signup(
    body: schemas.SignupRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    _rl: Annotated[None, Depends(_rl_signup)] = None,
) -> schemas.SignupResponse:
    user = await auth_svc.signup_user(body.email, body.password, db)

    access_token, _ = create_access_token(str(user.id))
    refresh_token, refresh_jti = create_refresh_token(str(user.id))
    await auth_svc.store_refresh_jti(refresh_jti, str(user.id))

    set_auth_cookies(response, access_token, refresh_token)

    return schemas.SignupResponse(
        message="account_created",
        user=_user_response(user),
    )


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    response_model=schemas.LoginResponse,
    summary="Authenticate and receive session cookies",
)
async def login(
    body: schemas.LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    _rl: Annotated[None, Depends(_rl_login)] = None,
) -> schemas.LoginResponse:
    # authenticate_user raises 401 for any failure (no enumeration).
    user = await auth_svc.authenticate_user(body.email, body.password, db)

    access_token, _ = create_access_token(str(user.id))
    refresh_token, refresh_jti = create_refresh_token(str(user.id))
    await auth_svc.store_refresh_jti(refresh_jti, str(user.id))

    set_auth_cookies(response, access_token, refresh_token)

    return schemas.LoginResponse(
        message="login_successful",
        user=_user_response(user),
    )


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

@router.post(
    "/logout",
    response_model=schemas.LogoutResponse,
    summary="Invalidate session — clears cookies and revokes refresh token",
)
async def logout(
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias="__Host-refresh")] = None,
    access_token: Annotated[str | None, Cookie(alias="__Host-access")] = None,
) -> schemas.LogoutResponse:
    if refresh_token:
        try:
            payload = decode_token(refresh_token, expected_typ="refresh")
            await auth_svc.logout_user(payload["jti"])
        except jwt.PyJWTError:
            # Token invalid/expired — still clear cookies.
            pass

    # Revoke the still-valid stateless access token so logout is real, not
    # just a cookie-clear. TTL = the token's own remaining lifetime.
    if access_token:
        try:
            ap = decode_token(access_token, expected_typ="access")
            now_ts = int(datetime.now(UTC).timestamp())
            await auth_svc.revoke_access_jti(ap["jti"], int(ap["exp"]) - now_ts)
        except jwt.PyJWTError:
            # Already expired/invalid → nothing to revoke.
            pass

    clear_auth_cookies(response)
    return schemas.LogoutResponse(message="logged_out")


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------

@router.post(
    "/refresh",
    response_model=schemas.RefreshResponse,
    summary="Silent refresh — rotate refresh token and issue new access token",
)
async def refresh(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie(alias="__Host-refresh")] = None,
    _rl: Annotated[None, Depends(_rl_refresh)] = None,
) -> schemas.RefreshResponse:
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_refresh_token",
        )

    try:
        payload = decode_token(refresh_token, expected_typ="refresh")
    except jwt.PyJWTError:
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_refresh_token",
        )

    user_id: str = payload["sub"]
    old_jti: str = payload["jti"]

    # rotate_refresh_token handles reuse detection and Redis rotation.
    access_token, _, new_refresh_token, new_refresh_jti = await auth_svc.rotate_refresh_token(
        old_jti, user_id
    )

    # Suspended-account check: load user and refuse if suspended.
    # Checked after rotation so the old jti is already consumed (reuse detection
    # still fires) and the new jti is stored (but we revoke it below on refusal).
    from sqlalchemy import select as _select

    from dhanradar.models.auth import User as _User

    db_user = await db.scalar(_select(_User).where(_User.id == user_id))
    if db_user is not None and db_user.suspended_at is not None:
        # Revoke the newly-issued refresh jti so the suspended user cannot
        # silently keep sessions alive after suspension.
        await auth_svc.revoke_refresh_jti(new_refresh_jti)
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account_suspended",
        )

    set_auth_cookies(response, access_token, new_refresh_token)
    return schemas.RefreshResponse(message="tokens_rotated")


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=schemas.MeResponse,
    summary="Return current authenticated user profile",
)
async def me(
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> schemas.MeResponse:
    if user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not_authenticated",
        )

    from sqlalchemy import select

    from dhanradar.models.auth import User as UserModel

    db_user = await db.scalar(
        select(UserModel).where(UserModel.id == user.user_id)
    )
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user_not_found",
        )

    return schemas.MeResponse(user=_user_response(db_user))


# ---------------------------------------------------------------------------
# POST /auth/totp/setup
# ---------------------------------------------------------------------------

@router.post(
    "/totp/setup",
    response_model=schemas.TOTPSetupResponse,
    summary="Generate TOTP secret and provisioning URI (pre-verify)",
)
async def totp_setup(
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _rl: Annotated[None, Depends(_rl_totp)] = None,
) -> schemas.TOTPSetupResponse:
    if user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not_authenticated",
        )

    from sqlalchemy import select

    from dhanradar.models.auth import User as UserModel

    db_user = await db.scalar(
        select(UserModel).where(UserModel.id == user.user_id)
    )
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user_not_found",
        )

    uri, secret = await auth_svc.totp_setup(db_user, db)
    return schemas.TOTPSetupResponse(provisioning_uri=uri, secret=secret)


# ---------------------------------------------------------------------------
# POST /auth/totp/verify
# ---------------------------------------------------------------------------

@router.post(
    "/totp/verify",
    response_model=schemas.TOTPVerifyResponse,
    summary="Verify TOTP code and activate 2FA on the account",
)
async def totp_verify(
    body: schemas.TOTPVerifyRequest,
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _rl: Annotated[None, Depends(_rl_totp)] = None,
) -> schemas.TOTPVerifyResponse:
    if user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not_authenticated",
        )

    import uuid as _uuid
    await auth_svc.totp_verify(_uuid.UUID(user.user_id), body.code, db)
    return schemas.TOTPVerifyResponse(message="totp_verified")


# ---------------------------------------------------------------------------
# POST /auth/totp/login  — Feature 2: standalone TOTP login
# ---------------------------------------------------------------------------

@router.post(
    "/totp/login",
    response_model=schemas.LoginResponse,
    summary="Authenticate with TOTP code (standalone — not a second factor)",
)
async def totp_login(
    body: schemas.TOTPLoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    _rl: Annotated[None, Depends(_rl_totp_login)] = None,
) -> schemas.LoginResponse:
    """
    Issue a session using a valid TOTP code in place of a password.

    Security properties mirror /auth/login exactly:
      - Generic 401 on any failure (no enumeration).
      - Brute-force + replay guards in service.authenticate_totp.
      - Same cookie issuance as every other login path.
    """
    user = await auth_svc.authenticate_totp(body.email, body.code, db)

    access_token, _ = create_access_token(str(user.id))
    refresh_token, refresh_jti = create_refresh_token(str(user.id))
    await auth_svc.store_refresh_jti(refresh_jti, str(user.id))

    set_auth_cookies(response, access_token, refresh_token)

    return schemas.LoginResponse(
        message="login_successful",
        user=_user_response(user),
    )


# ---------------------------------------------------------------------------
# POST /auth/email-otp/request  — Feature 3: request an email OTP
# ---------------------------------------------------------------------------

@router.post(
    "/email-otp/request",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a 6-digit login code sent to the given email address",
)
async def email_otp_request(
    body: schemas.EmailOTPRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _rl: Annotated[None, Depends(_rl_email_otp_request)] = None,
) -> dict:
    """
    Trigger delivery of a one-time login code to the supplied email address.

    Fail-closed: returns 503 if RESEND_API_KEY is not configured (mirrors
    google_start's 503 pattern for unconfigured providers).

    Security: ALWAYS returns {"message": "otp_sent_if_account_exists"} with
    HTTP 202 — identical response regardless of whether the account exists,
    whether the cooldown is active, or whether the daily cap is hit.  This
    prevents using the endpoint as a user-existence oracle.
    """
    if not settings.RESEND_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="email_otp_not_configured",
        )

    await auth_svc.request_email_otp(body.email, db)
    return {"message": "otp_sent_if_account_exists"}


# ---------------------------------------------------------------------------
# POST /auth/email-otp/login  — Feature 3: verify OTP and issue session
# ---------------------------------------------------------------------------

@router.post(
    "/email-otp/login",
    response_model=schemas.LoginResponse,
    summary="Authenticate with a one-time email code (standalone — not a second factor)",
)
async def email_otp_login(
    body: schemas.EmailOTPLoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    _rl: Annotated[None, Depends(_rl_email_otp_login)] = None,
) -> schemas.LoginResponse:
    """
    Issue a session using a valid email OTP in place of a password.

    Security properties mirror /auth/totp/login exactly:
      - Generic 401 on any failure (no enumeration).
      - Brute-force + expiry guards in service.authenticate_email_otp.
      - Same cookie issuance as every other login path.
    """
    user = await auth_svc.authenticate_email_otp(body.email, body.code, db)

    access_token, _ = create_access_token(str(user.id))
    refresh_token, refresh_jti = create_refresh_token(str(user.id))
    await auth_svc.store_refresh_jti(refresh_jti, str(user.id))

    set_auth_cookies(response, access_token, refresh_token)

    return schemas.LoginResponse(
        message="login_successful",
        user=_user_response(user),
    )


# ---------------------------------------------------------------------------
# GET /auth/google/start  — Feature 1: initiate Google SSO
# ---------------------------------------------------------------------------

@router.get(
    "/google/start",
    summary="Begin Google SSO — redirects to Google with PKCE + nonce",
    status_code=status.HTTP_302_FOUND,
)
async def google_start(
    next: Annotated[str | None, Query(alias="next")] = None,
    _rl: Annotated[None, Depends(_rl_google)] = None,
) -> RedirectResponse:
    """
    Generate PKCE state, nonce, and code_verifier; store them in Redis; then
    redirect the browser to Google's authorisation endpoint.

    Fail-closed: returns 503 if any Google credential is absent from settings.
    """
    if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET and settings.GOOGLE_REDIRECT_URI):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="google_sso_not_configured",
        )

    safe_next = google_svc.validate_next(next)
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = google_svc.pkce_challenge(code_verifier)

    redis = get_redis()
    state_payload = json.dumps(
        {"nonce": nonce, "code_verifier": code_verifier, "next": safe_next}
    )
    await redis.set(f"{_OAUTH_STATE_PREFIX}{state}", state_payload, ex=_OAUTH_STATE_TTL)

    auth_url = google_svc.build_auth_url(
        state=state,
        nonce=nonce,
        code_challenge=code_challenge,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )
    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


# ---------------------------------------------------------------------------
# GET /auth/google/callback  — Feature 1: handle Google's redirect
# ---------------------------------------------------------------------------

_ERROR_REDIRECT = "/login?error=google_auth_failed"
_DELETION_REDIRECT = "/login?error=account_deletion_pending"
_SUSPENDED_REDIRECT = "/login?error=account_suspended"
# A password account already exists for this email — auto-link is forbidden
# (local emails are never verified; see _resolve_existing_email_user).
_ACCOUNT_EXISTS_REDIRECT = "/login?error=account_exists_use_password"


@router.get(
    "/google/callback",
    summary="Google SSO callback — exchanges code and issues session cookies",
    status_code=status.HTTP_303_SEE_OTHER,
)
async def google_callback(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    state: Annotated[str | None, Query()] = None,
    code: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
    _rl: Annotated[None, Depends(_rl_google)] = None,
) -> RedirectResponse:
    """
    Browser-navigation endpoint — ALL failures redirect to /login?error=...
    so the user never sees a raw JSON error page.

    Security properties:
      - state is single-use (GETDEL); stale/missing → error redirect.
      - nonce verified against stored value (replay protection).
      - id_token verified locally with JWKS (not trusted blindly).
      - email_verified must be True.
      - Tokens are NEVER placed in URLs, response bodies, or non-HttpOnly cookies.
    """
    # --- Validate state and consume it atomically ---
    if not state:
        return RedirectResponse(url=_ERROR_REDIRECT, status_code=status.HTTP_302_FOUND)

    redis = get_redis()
    raw_state = await redis.getdel(f"{_OAUTH_STATE_PREFIX}{state}")
    if raw_state is None:
        return RedirectResponse(url=_ERROR_REDIRECT, status_code=status.HTTP_302_FOUND)

    try:
        state_data = json.loads(raw_state)
        stored_nonce: str = state_data["nonce"]
        code_verifier: str = state_data["code_verifier"]
        stored_next: str = state_data.get("next", "/dashboard")
    except (KeyError, ValueError):
        return RedirectResponse(url=_ERROR_REDIRECT, status_code=status.HTTP_302_FOUND)

    # --- Check for provider error ---
    if error:
        return RedirectResponse(url=_ERROR_REDIRECT, status_code=status.HTTP_302_FOUND)

    if not code:
        return RedirectResponse(url=_ERROR_REDIRECT, status_code=status.HTTP_302_FOUND)

    # --- Exchange code for tokens ---
    try:
        token_response = await google_svc.exchange_code_with_verifier(code, code_verifier)
    except Exception:
        return RedirectResponse(url=_ERROR_REDIRECT, status_code=status.HTTP_302_FOUND)

    id_token = token_response.get("id_token")
    if not id_token:
        return RedirectResponse(url=_ERROR_REDIRECT, status_code=status.HTTP_302_FOUND)

    # --- Verify id_token locally ---
    try:
        claims = await google_svc.verify_id_token(id_token, stored_nonce)
    except Exception:
        return RedirectResponse(url=_ERROR_REDIRECT, status_code=status.HTTP_302_FOUND)

    # email_verified must be explicitly True.
    if not claims.get("email_verified"):
        return RedirectResponse(url=_ERROR_REDIRECT, status_code=status.HTTP_302_FOUND)

    google_sub: str = claims["sub"]
    email: str = claims["email"].lower()

    # --- Resolve or create user ---
    try:
        user = await auth_svc.get_or_create_google_user(google_sub, email, db)
    except auth_svc._DeletionPendingError:
        return RedirectResponse(url=_DELETION_REDIRECT, status_code=status.HTTP_302_FOUND)
    except auth_svc._SuspendedError:
        return RedirectResponse(url=_SUSPENDED_REDIRECT, status_code=status.HTTP_302_FOUND)
    except auth_svc._SubConflictError:
        return RedirectResponse(url=_ERROR_REDIRECT, status_code=status.HTTP_302_FOUND)
    except auth_svc._AccountExistsError:
        return RedirectResponse(url=_ACCOUNT_EXISTS_REDIRECT, status_code=status.HTTP_302_FOUND)
    except Exception:
        return RedirectResponse(url=_ERROR_REDIRECT, status_code=status.HTTP_302_FOUND)

    # --- Stamp last_login_at for the resolved/created SSO user ---
    await auth_svc._record_login(user, db)
    await db.commit()

    # --- Issue session cookies (same path as login) ---
    # Re-validate `next` defensively before using it.
    safe_next = google_svc.validate_next(stored_next)

    redirect = RedirectResponse(url=safe_next, status_code=status.HTTP_303_SEE_OTHER)

    access_token, _ = create_access_token(str(user.id))
    refresh_token, refresh_jti = create_refresh_token(str(user.id))
    await auth_svc.store_refresh_jti(refresh_jti, str(user.id))

    set_auth_cookies(redirect, access_token, refresh_token)
    return redirect
