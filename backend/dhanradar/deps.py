"""
DhanRadar — FastAPI dependency classes.

PLACEHOLDER — these are wired in Phase 2 (auth / consent implementation).
For Phase 0/1 the __call__ methods are no-ops that pass through, but the
CLASS SHAPE (constructor + async __call__) is intentional and must not be
replaced with closure-style helpers.

Anti-pattern (FORBIDDEN):
    def require_tier(tier: str):
        async def _dep(): ...
        return _dep

Correct pattern (used here):
    class RequireTier:
        def __init__(self, tier: str): ...
        async def __call__(self, ...): ...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends, Request


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
async def current_user_or_anonymous(request: Request) -> UserContext:
    """
    FastAPI dependency — returns the authenticated user or a default
    anonymous UserContext.

    Phase 2 will replace this with JWT/session extraction.
    """
    # TODO Phase 2: extract and verify JWT from Authorization header.
    return UserContext()


# ---------------------------------------------------------------------------
# require_tier
# ---------------------------------------------------------------------------
class RequireTier:
    """
    Dependency class that enforces a minimum subscription tier.

    Usage::

        @router.get("/premium-endpoint")
        async def premium(
            _: None = Depends(RequireTier("premium")),
            user: UserContext = Depends(current_user_or_anonymous),
        ): ...
    """

    def __init__(self, tier: str) -> None:
        self.tier = tier

    async def __call__(
        self,
        user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    ) -> None:
        """
        Phase 1 stub: always passes.
        Phase 2: raise HTTP 402 with {"upgrade_url": ...} if user.tier does
        not meet self.tier (architecture §B2 — the tier gate is 402, NOT 403).
        """
        # TODO Phase 2: implement tier hierarchy check → HTTP 402 + upgrade_url.
        return None


# Convenience alias matching the contract name in the spec
require_tier = RequireTier


# ---------------------------------------------------------------------------
# require_consent
# ---------------------------------------------------------------------------
class RequireConsent:
    """
    Dependency class that enforces the user has given consent for a purpose.

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
        Phase 1 stub: always passes.
        Phase 2: check the consent schema and raise HTTP 403 with code
        CONSENT_REQUIRED if consent has not been recorded for self.purpose
        (architecture §3 — consent failure is 403 CONSENT_REQUIRED).
        """
        # TODO Phase 2: implement consent check → HTTP 403 CONSENT_REQUIRED.
        return None


# Convenience alias matching the contract name in the spec
require_consent = RequireConsent
