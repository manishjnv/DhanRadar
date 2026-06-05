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

All tokens are issued as RS256 JWTs in HttpOnly __Host-* cookies.
The JS layer never reads the token value.

Security notes:
  - Login 401 is generic "invalid_credentials" regardless of failure reason.
  - Signup 409 on duplicate email (intentional tradeoff — see service.py).
  - /refresh implements rotation + reuse detection.
  - Logout clears both cookies AND revokes the refresh jti in Redis.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.auth import schemas
from dhanradar.auth import service as auth_svc
from dhanradar.auth.security import (
    clear_auth_cookies,
    create_access_token,
    create_refresh_token,
    decode_token,
    set_auth_cookies,
)
from dhanradar.db import get_db
from dhanradar.deps import UserContext, current_user_or_anonymous
from dhanradar.ratelimit import RateLimit

router = APIRouter(prefix="/auth", tags=["auth"])

# Per-IP (CF-Connecting-IP) brute-force / abuse guards. Login and TOTP-verify
# are the credential-guessing surfaces, so they are tighter than the
# architecture's generic anon 30 r/m. Realises the architecture's
# "anon:10m rate=30r/m" zone at the app layer (no nginx in this deployment).
_rl_login = RateLimit(max_requests=5, window_seconds=60)
_rl_signup = RateLimit(max_requests=5, window_seconds=60)
_rl_refresh = RateLimit(max_requests=30, window_seconds=60)
_rl_totp = RateLimit(max_requests=10, window_seconds=60)


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
        user=schemas.UserResponse.model_validate(user),
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
        user=schemas.UserResponse.model_validate(user),
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
    access_token, _, new_refresh_token, _ = await auth_svc.rotate_refresh_token(
        old_jti, user_id
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

    return schemas.MeResponse(user=schemas.UserResponse.model_validate(db_user))


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
