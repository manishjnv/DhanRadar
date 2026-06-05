"""
DhanRadar — Auth Pydantic v2 request / response schemas.

Rules:
  - EmailStr for all email fields (requires email-validator).
  - password min_length=10.
  - Use `pattern=` NOT `regex=` (Pydantic v2 deprecates regex=).
  - No sensitive data in response schemas (no hashed_password, no totp_secret).
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    email: EmailStr
    # max_length bounds Argon2 input — an unbounded multi-MB password is a
    # cheap CPU-DoS vector even with per-IP rate limiting.
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)  # bound at the edge


class TOTPVerifyRequest(BaseModel):
    code: str = Field(
        min_length=6,
        max_length=8,
        pattern=r"^\d{6,8}$",
        description="6-8 digit TOTP code",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    email: str
    tier: str
    totp_verified: bool
    risk_profile: Optional[str]
    dpdp_consent_version: Optional[str]


class SignupResponse(BaseModel):
    message: str
    user: UserResponse


class LoginResponse(BaseModel):
    message: str
    user: UserResponse


class MeResponse(BaseModel):
    user: UserResponse


class TOTPSetupResponse(BaseModel):
    provisioning_uri: str
    secret: str


class TOTPVerifyResponse(BaseModel):
    message: str


class LogoutResponse(BaseModel):
    message: str


class RefreshResponse(BaseModel):
    message: str
