"""
DhanRadar — Google SSO helpers (server-side OAuth 2.0 + PKCE + nonce).

Public API consumed by auth.router:
  build_auth_url(state, nonce, code_challenge, redirect_uri) -> str
  validate_next(next_param) -> str
  async exchange_code(code) -> dict          # network — monkeypatch in tests
  async verify_id_token(id_token, expected_nonce) -> dict  # network — monkeypatch in tests

Security invariants:
  - PKCE code_verifier is 64 url-safe random bytes; challenge = BASE64URL-no-pad(SHA256(verifier)).
  - state is single-use (GETDEL in Redis at callback).
  - nonce claim is compared against the stored value so a replayed token cannot be reused.
  - id_token is verified locally with PyJWT + JWKS (no blind trust of Google's token endpoint).
  - JWKS keys are cached module-level for 3600s to avoid hammering Google on every login.
  - id_token, code, and code_verifier are NEVER logged.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

from dhanradar.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------

_GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"

# Accepted issuers per Google's token documentation.
_GOOGLE_ISSUERS = frozenset({"https://accounts.google.com", "accounts.google.com"})


def pkce_challenge(verifier: str) -> str:
    """Return BASE64URL-no-padding SHA256 of the verifier (code_challenge, S256)."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def validate_next(next_param: str | None) -> str:
    """
    Validate the `next` redirect path.

    Must start with "/", NOT start with "//", and contain no backslash or
    control characters (open-redirect guard).  Browsers fold "\\" into "/"
    when following a Location header, so "/\\evil.com" would leave the origin.
    Returns "/dashboard" as the safe fallback on any invalid input.
    """
    if (
        next_param
        and next_param.startswith("/")
        and not next_param.startswith("//")
        and "\\" not in next_param
        and not any(ord(c) < 0x20 for c in next_param)
    ):
        return next_param
    return "/dashboard"


def build_auth_url(
    state: str,
    nonce: str,
    code_challenge: str,
    redirect_uri: str,
) -> str:
    """Construct the Google authorisation URL with all required parameters."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email",
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return f"{_GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"


# ---------------------------------------------------------------------------
# JWKS cache — module-level, re-fetched after 3600s
# ---------------------------------------------------------------------------

_jwks_cache: dict[str, Any] = {}
_jwks_fetched_at: float = 0.0
_JWKS_TTL = 3600.0


async def _get_jwks() -> dict[str, Any]:
    """Return the cached JWKS dict, refreshing if older than _JWKS_TTL seconds."""
    global _jwks_cache, _jwks_fetched_at
    now = time.monotonic()
    if not _jwks_cache or (now - _jwks_fetched_at) > _JWKS_TTL:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_GOOGLE_JWKS_URI)
            resp.raise_for_status()
            _jwks_cache = resp.json()
            _jwks_fetched_at = now
    return _jwks_cache


# ---------------------------------------------------------------------------
# Network steps — separated so tests can monkeypatch them
# ---------------------------------------------------------------------------


async def exchange_code_with_verifier(code: str, code_verifier: str) -> dict:
    """
    Exchange an authorisation code + PKCE verifier for tokens.

    Returns the raw JSON response dict.  Raises httpx.HTTPStatusError on non-200.
    NOTE: never log `code`, `code_verifier`, or `client_secret`.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            _GOOGLE_TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def verify_id_token(id_token: str, expected_nonce: str) -> dict:
    """
    Locally verify a Google id_token with JWKS and return validated claims.

    Invariants enforced:
      - RS256 only (no alg:none).
      - iss in {"https://accounts.google.com", "accounts.google.com"}.
      - aud == settings.GOOGLE_CLIENT_ID.
      - nonce claim == expected_nonce (replay protection).
      - email_verified == True (checked by caller after returning claims).

    Raises jwt.PyJWTError on any failure (expired, bad sig, missing claim, etc.).
    NOTE: never log the id_token value.
    """
    jwks_data = await _get_jwks()
    jwks = jwt.PyJWKSet.from_dict(jwks_data)

    # Decode header to find the correct key.
    unverified_header = jwt.get_unverified_header(id_token)
    kid = unverified_header.get("kid")

    signing_key = None
    for key in jwks.keys:
        if key.key_id == kid:
            signing_key = key
            break

    if signing_key is None:
        raise jwt.InvalidTokenError(f"No JWKS key found for kid={kid!r}")

    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.GOOGLE_CLIENT_ID,
        options={"require": ["sub", "email", "iss", "aud", "exp", "iat", "nonce"]},
    )

    if claims.get("iss") not in _GOOGLE_ISSUERS:
        raise jwt.InvalidIssuerError(f"Unexpected iss: {claims.get('iss')!r}")

    if claims.get("nonce") != expected_nonce:
        raise jwt.InvalidTokenError("nonce mismatch")

    return claims
