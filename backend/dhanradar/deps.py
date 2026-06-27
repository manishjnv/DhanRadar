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
from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.contextvars import bind_contextvars

from dhanradar.core.logging import hash_user_ref
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
    access_token: Annotated[str | None, Cookie(alias="__Host-access")] = None,
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

    # Bind hashed user ref into the structlog context (raw user_id never logged).
    bind_contextvars(user_ref=hash_user_ref(user_id))

    # B81: scope this request's transaction to the authenticated owner so RLS on personal tables
    # returns only their rows. SET LOCAL (set_config ..., is_local=true) — resets at commit/rollback,
    # never leaks across the pooled connection. FastAPI caches Depends(get_db), so this same session
    # is the one the route uses → the GUC is set before the route's personal-table queries.
    from dhanradar.db_security import set_rls_user

    await set_rls_user(db, user_id)

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

_PRO_RANK = _TIER_ORDER["pro"]
_ACTIVE_SUB_STATUSES = frozenset({"active", "authenticated"})  # mirror subscriptions/service._ACTIVE_STATUSES


def _tier_rank(tier: str) -> int:
    return _TIER_ORDER.get(tier, 0)


async def is_plus(user_id: str, db: AsyncSession) -> bool:
    """True iff the user currently has DhanRadar Plus — a LIVE time-window grant
    (now < users.pro_access_until) OR an active subscription. Computed live (no
    cache) so an expired window auto-downgrades by timestamp (no revoke job).
    Fail-closed: malformed/anonymous subject → False."""
    from uuid import UUID as _UUID

    from sqlalchemy import select as _select

    from dhanradar.models.auth import Subscription, User

    if not isinstance(user_id, str) or user_id == "anonymous":
        return False
    try:
        uid = _UUID(user_id)
    except (ValueError, TypeError):
        return False
    pro_until = await db.scalar(_select(User.pro_access_until).where(User.id == uid))
    if pro_until is not None and datetime.now(UTC) < pro_until:
        return True
    sub = await db.scalar(
        _select(Subscription.id)
        .where(Subscription.user_id == uid, Subscription.status.in_(_ACTIVE_SUB_STATUSES))
        .limit(1)
    )
    return sub is not None


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
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> None:
        required_rank = _tier_rank(self.tier)
        user_rank = _tier_rank(user.tier)

        # PHASE 5M: a time-window grant or active subscription bumps an otherwise
        # sub-pro user up to pro rank (live check; auto-downgrades by timestamp).
        if user_rank < _PRO_RANK and required_rank <= _PRO_RANK and not user.is_anonymous:
            if await is_plus(user.user_id, db):
                user_rank = _PRO_RANK

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
#
# Cross-border purposes grant transfer of the user's personal data OUTSIDE India
# (a DPDP concern distinct from the per-feature *processing* purposes). They are
# kept PER-PROCESSOR — not one bundled grant — per DPDP's specific-consent /
# no-bundling principle (ADR-0024): `cross_border_ai` gates the AI gateway →
# OpenRouter (B20); `cross_border_notify` gates the notification deliver seam →
# Telegram / Resend-Tokyo (B31). Enforced at the CALL SITE via
# consent_granted / assert_consent.
_CONSENT_PURPOSES: frozenset[str] = frozenset(
    {
        "mf_analytics",
        "ai_insights",
        "marketing",
        "portfolio_sync",
        "behavioral_nudges",
        "cross_border_ai",
        "cross_border_notify",
    }
)

# Public alias — used by the Consent module (B44) for purpose validation.
# The underscore-prefixed frozenset is the canonical internal name; this alias
# lets other modules import without touching private symbols.
CONSENT_PURPOSES = _CONSENT_PURPOSES


def _consent_granted(consents: object, purpose: str) -> bool:
    """Fail-closed read of the user's `dpdp_consents` JSONB for one purpose.

    Granted ONLY if the stored value is exactly ``True`` or a mapping with
    ``granted is True``. Anything else (missing, false, malformed, null) →
    NOT granted. The Consent module owns the write format; this reader stays
    forward-compatible with both `{purpose: true}` and
    `{purpose: {"granted": true, ...}}` while never failing open.

    REVOKE CONTRACT (the future Consent-module writer MUST honour): a revoke is
    written as ``granted: false`` or by removing the key — NEVER by adding a
    separate ``revoked`` key, which this reader would ignore and thus fail OPEN.
    """
    # TEMPORARY pre-launch kill-switch (B48): when consent enforcement is disabled
    # via config — dev/pre-launch only, no real user data — every purpose reads as
    # granted so gated routes/call sites work without a consent-capture UI (B44).
    # Single chokepoint: RequireConsent, consent_granted, and assert_consent all
    # route through here, so this disables all three. Fail-safe by design:
    #   - default config is ENFORCED=True, so the gate is on unless explicitly off;
    #   - `consent_bypassed` is True ONLY in an allowlisted dev/test/ci env, and a
    #     disabled flag in any other env is a hard boot failure (config.model_post_init),
    #     so the bypass can never reach production/staging.
    # The one-time "disabled" warning is emitted at startup, not here. Remove this
    # block when B48 is closed at launch.
    from dhanradar.config import settings

    if settings.consent_bypassed:
        return True

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


# ---------------------------------------------------------------------------
# RequireAdmin — fail-closed admin gate (B26 Admin module)
# ---------------------------------------------------------------------------

class RequireAdmin:
    """Dependency that restricts an endpoint to operator-configured admins.

    There is NO admin tier/role in the DB — admins are an allowlist of user-id
    UUIDs in ``settings.ADMIN_USER_IDS`` (operator-set via env/secret). The gate is
    fail-closed and surface-hiding:

      - EVERY non-admin — anonymous OR an authenticated non-admin — receives **404
        not_found**, not 401/403. This hides the admin surface entirely (no oracle
        that the endpoint exists or that it is admin-gated), and avoids a
        401-vs-404 distinction that would confirm the route to an authenticated
        non-admin.
      - An EMPTY allowlist ⇒ no admins ⇒ every admin endpoint is disabled
        (fail-closed default, mirroring INTERNAL_API_TOKEN).

    Returns the admin's ``UserContext`` so the endpoint can attribute actions
    (e.g. activated_by / created_by) to the admin.

    Usage::

        @router.post("/admin/disclaimers/{version}/activate")
        async def activate(
            admin: UserContext = Depends(RequireAdmin()),
        ): ...
    """

    async def __call__(
        self,
        user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    ) -> UserContext:
        from uuid import UUID as _UUID

        from dhanradar.config import settings

        # Normalize the subject to a canonical UUID; anonymous ("anonymous") and any
        # malformed id raise → treated as non-admin → 404 (never an unhandled 500).
        try:
            uid = str(_UUID(user.user_id))
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="not_found"
            )
        if user.is_anonymous or uid not in settings.admin_user_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="not_found"
            )
        return user


# Convenience alias
require_admin = RequireAdmin


# ---------------------------------------------------------------------------
# Reusable, NON-route consent checks (B20/B31 foundation)
# ---------------------------------------------------------------------------
#
# RequireConsent is a FastAPI route dependency. Internal call sites — Celery
# workers, the notification deliver seam, AI consumers — have no Request/route,
# so they use these instead. Both read `auth.users.dpdp_consents` FRESH (no
# cache) via the same fail-closed reader as RequireConsent, so a revoke is
# honoured immediately and identically.


class ConsentRequiredError(Exception):
    """Raised by ``assert_consent`` when a required DPDP purpose is not granted.

    Deliberately NOT an HTTPException — it is raised at non-route call sites; the
    caller decides how to surface it (skip a channel, refuse a job, log + drop).
    """

    def __init__(self, purpose: str) -> None:
        super().__init__(f"consent_required:{purpose}")
        self.purpose = purpose


async def consent_granted(user_id: str, purpose: str, db: AsyncSession) -> bool:
    """Fail-closed bool check of a user's DPDP consent for ``purpose``.

    The non-raising counterpart of ``RequireConsent`` for internal call sites
    (e.g. a deliver seam that should SKIP a channel rather than error). Fail
    CLOSED everywhere: an unknown ``purpose`` is a programming error
    (``ValueError``); a malformed/absent user, or a missing/false/malformed
    grant → ``False``. Never raises on bad data, never fails open.
    """
    if purpose not in _CONSENT_PURPOSES:
        raise ValueError(
            f"Unknown consent purpose '{purpose}'. "
            f"Valid values: {sorted(_CONSENT_PURPOSES)}"
        )

    from uuid import UUID as _UUID

    from sqlalchemy import select as _select

    from dhanradar.models.auth import User

    # Fail closed on any non-string / malformed subject (mirrors RequireConsent's
    # direct parse; a `None`/`True`/object id must never reach the DB or pass).
    if not isinstance(user_id, str):
        return False
    try:
        uid = _UUID(user_id)
    except (ValueError, TypeError):
        return False

    consents = await db.scalar(_select(User.dpdp_consents).where(User.id == uid))
    return _consent_granted(consents, purpose)


async def assert_consent(user_id: str, purpose: str, db: AsyncSession) -> None:
    """Hard-stop variant: raise ``ConsentRequiredError`` if consent is not
    granted. For call sites that must REFUSE (not skip)."""
    if not await consent_granted(user_id, purpose, db):
        raise ConsentRequiredError(purpose)
