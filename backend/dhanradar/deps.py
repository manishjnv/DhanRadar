"""
DhanRadar — FastAPI dependency classes.

Provides:
  - UserContext           dataclass returned by current_user_or_anonymous
  - current_user_or_anonymous  reads __Host-access JWT cookie; anonymous if absent/invalid
  - RequireTier           class-based dependency; raises HTTP 402 on insufficient tier
  - RequireConsent        fail-closed per-purpose DPDP gate (B3); anonymous → 401,
                          missing/false grant → 403. The full Consent module
                          (audit log, grant/revoke endpoints, CMP) is a later slice.

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
    # Intentionally NOT populated by current_user_or_anonymous — the ONLY valid
    # consent check is `Depends(RequireConsent(purpose))`, which reads the grant
    # FRESH from the DB. Do not gate on this list (it stays empty, so a check
    # against it would fail OPEN); kept for the future Consent module.
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
# RequireConsent  — fail-closed per-purpose DPDP consent gate (B3)
# ---------------------------------------------------------------------------

# Canonical DPDP purpose taxonomy (DhanRadar_Architecture_Final.md §Compliance).
# A purpose outside this set is a programming error, caught at construction time.
_CONSENT_PURPOSES: frozenset[str] = frozenset(
    {"mf_analytics", "ai_insights", "marketing", "portfolio_sync", "behavioral_nudges"}
)


def _consent_granted(consents: object, purpose: str) -> bool:
    """Fail-closed read of the user's `dpdp_consents` JSONB for one purpose.

    Granted ONLY if the stored value is exactly ``True`` or a mapping with
    ``granted is True``. Anything else (missing, false, malformed, null) →
    NOT granted. The Consent module owns the write format; this reader stays
    forward-compatible with both `{purpose: true}` and
    `{purpose: {"granted": true, ...}}` while never failing open.
    """
    if not isinstance(consents, dict):
        return False
    value = consents.get(purpose)
    if value is True:
        return True
    return isinstance(value, dict) and value.get("granted") is True


class RequireConsent:
    """
    Dependency class enforcing the user has granted consent for a purpose.

    Fail-closed (B3): no recorded grant → HTTP 403 ``consent_required``. The
    grant state is read FRESH from ``auth.users.dpdp_consents`` on every call
    (no cache) so a revoke is honoured immediately — a cache may be added later
    only together with its flush-on-revoke writer in the Consent module, never
    before (a stale cache here would fail OPEN).

    The full Consent module (append-only ``consent_audit_log``, grant/revoke
    endpoints, CMP banner, erasure) is a later slice; THIS is only the gate
    primitive, hardened so the first route that adopts it cannot fail open.

    Usage::

        @router.post("/ai-analysis")
        async def analyse(
            _: None = Depends(RequireConsent("ai_insights")),
        ): ...
    """

    def __init__(self, purpose: str) -> None:
        if purpose not in _CONSENT_PURPOSES:
            raise ValueError(
                f"Unknown consent purpose '{purpose}'. "
                f"Valid values: {sorted(_CONSENT_PURPOSES)}"
            )
        self.purpose = purpose

    async def __call__(
        self,
        user: Annotated[UserContext, Depends(current_user_or_anonymous)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> None:
        # Anonymous principals cannot hold consent. Raise 401 (not 403) so the
        # gate is safe-by-default: a future route that adopts RequireConsent
        # WITHOUT a preceding auth check still returns "authenticate first" to an
        # anonymous caller, and the 401-before-403 ordering holds without relying
        # on each caller to add its own is_anonymous guard (Phase-7 §5 hardening).
        if user.is_anonymous:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="not_authenticated",
            )

        from uuid import UUID as _UUID

        from sqlalchemy import select as _select

        from dhanradar.models.auth import User

        # Parse the subject defensively: a malformed user_id must fail CLOSED
        # (403), never propagate a ValueError as an unhandled 500. The anonymous
        # guard above already covers the `"anonymous"` default, but we do not rely
        # on guard ordering for a load-bearing DPDP gate.
        try:
            uid = _UUID(user.user_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "consent_required", "purpose": self.purpose},
            )

        consents = await db.scalar(
            _select(User.dpdp_consents).where(User.id == uid)
        )
        if not _consent_granted(consents, self.purpose):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "consent_required", "purpose": self.purpose},
            )


# Convenience alias matching the contract name in the spec
require_consent = RequireConsent
