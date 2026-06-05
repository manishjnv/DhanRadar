"""
DhanRadar — FastAPI dependency classes.

Provides:
  - UserContext           dataclass returned by current_user_or_anonymous
  - current_user_or_anonymous  reads __Host-access JWT cookie; anonymous if absent/invalid
  - RequireTier           class-based dependency; raises HTTP 402 on insufficient tier
  - RequireConsent        STUB — Consent module is a later session (shape preserved)

Anti-pattern (FORBIDDEN):
    def require_tier(tier: str):
        async def _dep(): ...
        return _dep

Correct pattern (used here):
    class RequireTier:
        def __init__(self, tier: str): ...
        async def __call__(self, ...): ...

Security notes:
  - JWT is RS256 only; decode_token enforces alg whitelist and typ check.
  - Anonymous is VALID — missing / invalid cookie yields UserContext(is_anonymous=True);
    routes that need authentication must check is_anonymous themselves OR
    use Depends(RequireTier("free")).
  - Tier hierarchy: anonymous < free < pro < pro_plus; founder_lifetime >= pro_plus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Optional

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.db import get_db


# ---------------------------------------------------------------------------
# UserContext — returned by current_user_or_anonymous
# ---------------------------------------------------------------------------

@dataclass
class UserContext:
    user_id: str = "anonymous"
    tier: str = "free"
    is_anonymous: bool = True
    consented_purposes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# current_user_or_anonymous
# ---------------------------------------------------------------------------

async def current_user_or_anonymous(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    access_token: Annotated[Optional[str], Cookie(alias="__Host-access")] = None,
) -> UserContext:
    """
    FastAPI dependency — returns the authenticated user or a default
    anonymous UserContext.

    Anonymous is VALID — callers must not raise 401 solely because this
    returns is_anonymous=True unless the route requires authentication.

    Flow:
      1. Read __Host-access cookie.
      2. Decode RS256 JWT (enforces alg whitelist, typ="access", exp).
      3. On any JWT error → return anonymous (do NOT 401 here).
      4. Resolve current tier via Redis cache + DB fallback.
    """
    if not access_token:
        return UserContext()

    try:
        from dhanradar.auth.security import decode_token
        payload = decode_token(access_token, expected_typ="access")
    except jwt.PyJWTError:
        # Invalid / expired token — treat as anonymous (not 401).
        # The client should call /auth/refresh to get a new access token.
        return UserContext()

    # Reject access tokens explicitly revoked by logout (stateless JWTs
    # otherwise stay valid until exp). Denylist self-expires with the token.
    from dhanradar.auth.service import is_access_revoked
    if await is_access_revoked(payload["jti"]):
        return UserContext()

    user_id: str = payload["sub"]

    # Resolve tier with Redis cache + DB fallback
    from dhanradar.auth.service import resolve_tier_with_db
    tier = await resolve_tier_with_db(user_id, db)

    return UserContext(
        user_id=user_id,
        tier=tier,
        is_anonymous=False,
    )


# ---------------------------------------------------------------------------
# Tier hierarchy
# ---------------------------------------------------------------------------

_TIER_ORDER: dict[str, int] = {
    "anonymous": 0,
    "free": 1,
    "pro": 2,
    "pro_plus": 3,
    "founder_lifetime": 4,  # treated as >= pro_plus
}


def _tier_rank(tier: str) -> int:
    return _TIER_ORDER.get(tier, 0)


# ---------------------------------------------------------------------------
# RequireTier
# ---------------------------------------------------------------------------

class RequireTier:
    """
    Dependency class that enforces a minimum subscription tier.

    Raises HTTP 402 with {"error": "upgrade_required", "upgrade_url": "/pricing"}
    when the user's tier is below the required minimum.

    Usage::

        @router.get("/premium-endpoint")
        async def premium(
            _: None = Depends(RequireTier("pro")),
            user: UserContext = Depends(current_user_or_anonymous),
        ): ...
    """

    def __init__(self, tier: str) -> None:
        if tier not in _TIER_ORDER:
            raise ValueError(
                f"Unknown tier '{tier}'. Valid values: {list(_TIER_ORDER.keys())}"
            )
        self.tier = tier

    async def __call__(
        self,
        user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    ) -> None:
        required_rank = _tier_rank(self.tier)
        user_rank = _tier_rank(user.tier)

        if user_rank < required_rank:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "upgrade_required",
                    "upgrade_url": "/pricing",
                },
            )


# Convenience alias matching the contract name in the spec
require_tier = RequireTier


# ---------------------------------------------------------------------------
# RequireConsent  — STUB (Consent module is a later session)
# ---------------------------------------------------------------------------

class RequireConsent:
    """
    Dependency class that enforces the user has given consent for a purpose.

    STUB — the Consent module is implemented in a later phase.
    When implemented, this will check user.consented_purposes against
    self.purpose and raise HTTP 403 with code CONSENT_REQUIRED if consent
    has not been recorded.

    Usage::

        @router.post("/ai-analysis")
        async def analyse(
            _: None = Depends(RequireConsent("ai_processing")),
        ): ...
    """

    def __init__(self, purpose: str) -> None:
        self.purpose = purpose

    async def __call__(
        self,
        user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    ) -> None:
        """
        Phase stub: always passes through.
        Future implementation: check consent schema and raise HTTP 403
        with code CONSENT_REQUIRED if consent has not been recorded for
        self.purpose (architecture §3 — consent failure is 403 CONSENT_REQUIRED).
        """
        # TODO Phase: implement consent check → HTTP 403 CONSENT_REQUIRED.
        return None


# Convenience alias matching the contract name in the spec
require_consent = RequireConsent
