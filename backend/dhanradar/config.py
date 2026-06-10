"""
DhanRadar — Application settings.

Reads all configuration from environment variables (or .env file).
Pydantic-settings v2 automatically validates types and raises on missing required fields.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Envs in which the B48 pre-launch consent kill-switch may take effect. This is an
# ALLOWLIST, not a denylist: any other ENV — "production", "staging", "preview",
# unset/unknown, mis-cased — keeps the DPDP gate ENFORCED (fail-closed). Inverting
# the check this way means a leaked `DPDP_CONSENT_ENFORCED=false` cannot disable
# consent anywhere except an explicit dev/test/ci box. (B48 Security condition.)
_CONSENT_BYPASS_ALLOWED_ENVS: frozenset[str] = frozenset({"development", "test", "ci"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ------------------------------------------------------------------
    # Postgres
    # ------------------------------------------------------------------
    POSTGRES_HOST: str = "dhanradar-postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "dhanradar"
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str = "dhanradar"

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    REDIS_URL: str = "redis://dhanradar-redis:6379/0"

    # ------------------------------------------------------------------
    # Cloudflare R2
    # ------------------------------------------------------------------
    R2_ACCOUNT_ID: str = ""
    R2_ENDPOINT: str = ""
    R2_BUCKET: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    # DPDP / ADR-0022: the audit archive carries user_id and MUST be India-resident.
    # OFF by default — the daily audit→R2 export is gated on this so PII is never
    # sent cross-border until an India-resident archive target is explicitly enabled.
    # The primary 7-yr audit record lives in the India-resident Postgres regardless.
    AUDIT_ARCHIVE_ENABLED: bool = False

    # ------------------------------------------------------------------
    # External APIs
    # ------------------------------------------------------------------
    OPENROUTER_API_KEY: str = ""
    RESEND_API_KEY: str = ""

    # ------------------------------------------------------------------
    # Notification module (Phase 6, architecture Global §5)
    # ------------------------------------------------------------------
    # Telegram Bot API. Token EMPTY ⇒ Telegram delivery is DISABLED (fail-closed):
    # the drain logs the job failed rather than calling a tokenless endpoint.
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_API_BASE: str = "https://api.telegram.org"
    # Optional public-channel chat id for the daily Mood card (deferred until Mood
    # Compass ships); empty ⇒ that path is skipped.
    TELEGRAM_PUBLIC_CHANNEL_ID: str = ""
    # Resend email. Verified-working sender domain is any @dhanradar.com.
    # api.resend.com is behind Cloudflare and 403s the default urllib UA (error
    # 1010) — httpx sends a real UA; we also set one explicitly.
    RESEND_API_BASE: str = "https://api.resend.com"
    EMAIL_FROM: str = "noreply@dhanradar.com"
    NOTIFY_USER_AGENT: str = "DhanRadar/1.0 (+https://dhanradar.com)"
    # Optional public base URL for R2 share-cards served without a signature
    # (public mood/badge cards). Empty ⇒ a presigned S3 URL is returned instead.
    R2_PUBLIC_BASE_URL: str = ""

    # ------------------------------------------------------------------
    # AI / LLM Gateway (Phase 3, architecture §B3)
    # ------------------------------------------------------------------
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    # Free-model pool, comma-separated, OPERATOR-SET and verified live at
    # openrouter.ai/models before use (startup verify_models()). Kept out of code
    # so no unverified ':free' id is hardcoded. Empty = no free pool configured.
    AI_FREE_MODELS: str = ""
    # High-stakes schema-failure spillover (premium budget). A real, paid id.
    AI_SONNET_MODEL: str = "anthropic/claude-sonnet-4.6"

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------
    SENTRY_DSN: str | None = None

    # ------------------------------------------------------------------
    # JWT (RS256 asymmetric)
    # Generate dev keys with: python backend/scripts/gen_jwt_keys.py
    # ------------------------------------------------------------------
    # Provide the PEM either inline (JWT_*_KEY, with literal "\n" allowed for
    # single-line .env values) OR as a path to a mounted PEM file (JWT_*_FILE,
    # the production-preferred form — keys never transit the env). The *_FILE
    # path is operator-set via env, not request-derived. Resolve via the
    # jwt_private_key / jwt_public_key computed properties — never read the
    # raw fields directly.
    JWT_PRIVATE_KEY: str = ""
    JWT_PUBLIC_KEY: str = ""
    JWT_PRIVATE_KEY_FILE: str = ""
    JWT_PUBLIC_KEY_FILE: str = ""
    JWT_ALGORITHM: str = "RS256"   # Hard-coded to RS256; env override is informational only
    ACCESS_TTL_MIN: int = 15       # Access token TTL in minutes
    REFRESH_TTL_DAYS: int = 7      # Refresh token TTL in days

    # ------------------------------------------------------------------
    # Cookie
    # ------------------------------------------------------------------
    COOKIE_SECURE: bool = True     # Set False only in dev without HTTPS

    # ------------------------------------------------------------------
    # Razorpay
    # ------------------------------------------------------------------
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # ------------------------------------------------------------------
    # Internal service auth (server-to-server)
    # ------------------------------------------------------------------
    # Shared secret for the internal numeric endpoints (e.g. /internal/v1/score).
    # Defense-in-depth on top of network topology (those paths are not on the
    # public ^/api/.* ingress). EMPTY ⇒ the internal endpoints are DISABLED
    # (fail-closed) — set this in any environment that needs them.
    INTERNAL_API_TOKEN: str = ""

    # ------------------------------------------------------------------
    # Admin authorization (B26 Admin module)
    # ------------------------------------------------------------------
    # Comma-separated allowlist of admin user-id UUIDs. There is NO admin tier/role
    # in the DB — admins are an operator-set allowlist (set via env/secret). EMPTY ⇒
    # no admins ⇒ every admin endpoint is effectively disabled (fail-closed, like
    # INTERNAL_API_TOKEN). Resolve via the `admin_user_ids` computed set, never the
    # raw string. NOTE: read once at process start (pydantic-settings) — adding or
    # removing an admin requires a process restart to take effect.
    ADMIN_USER_IDS: str = ""

    # ------------------------------------------------------------------
    # DPDP consent gate — TEMPORARY pre-launch kill-switch (B48)
    # ------------------------------------------------------------------
    # The fail-closed RequireConsent / assert_consent / consent_granted gates
    # (deps.py, B3) refuse any data-processing route/call site without a recorded
    # DPDP grant. There is NO consent-capture UI yet (B44), and there is NO real
    # user data pre-launch (dev runs on mocks/synthetic fixtures), so during
    # development this gate blocks gated routes with no way to grant.
    #
    # Setting this False makes every purpose read as granted, so gated routes work
    # in dev. It is DEFAULT TRUE (gate ENFORCED) and only takes effect in an
    # allowlisted dev env (_CONSENT_BYPASS_ALLOWED_ENVS, via `consent_bypassed`).
    # Setting it False in any other env is a hard BOOT FAILURE (model_post_init) —
    # so a leaked override on a prod/staging box refuses to start rather than
    # silently serving real users without consent. MUST be removed / verified True
    # before the July-15 launch. Tracked: BLOCKERS B48.
    DPDP_CONSENT_ENFORCED: bool = True

    # ------------------------------------------------------------------
    # DPDP consent version (B44 — consent grant/revoke writer)
    # Bumped when the consent text/purposes change; stored on every
    # grant/revoke row so the version in force at consent time is auditable.
    # ------------------------------------------------------------------
    DPDP_CONSENT_VERSION: str = "2026-06-01"

    # ------------------------------------------------------------------
    # PHASE 5M Founding Access window end (placeholder — reset to
    # (billing_go_live + 30d) at go-live). Signup stamps pro_access_until
    # to this while now < it.
    # ------------------------------------------------------------------
    FOUNDING_ACCESS_UNTIL: datetime | None = datetime(
        2026, 12, 31, 23, 59, 59, tzinfo=UTC
    )

    # ------------------------------------------------------------------
    # News RSS ingestion (B56)
    # ------------------------------------------------------------------
    # Drop items older than this from list_news results (recency guard).
    NEWS_MAX_AGE_DAYS: int = 30
    # Emit a staleness warning log when the newest served item is older than
    # this many hours (observability — lets us catch feed outages early).
    NEWS_STALENESS_WARN_HOURS: int = 24
    # Per-URL HEAD liveness check timeout in seconds.
    NEWS_URL_HEAD_TIMEOUT_S: int = 8
    # Overall per-feed fetch timeout in seconds.
    NEWS_FEED_FETCH_TIMEOUT_S: int = 15

    # ------------------------------------------------------------------
    # Runtime
    # ------------------------------------------------------------------
    ENV: str = "development"

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_pem(file_path: str, inline: str) -> str:
        """
        Resolve a PEM key: a mounted file path wins; otherwise the inline
        value with literal '\\n' un-escaped (single-line .env compatibility).
        Returns "" if neither is configured (callers fail closed — an empty
        key makes JWT encode/decode raise, never silently weaken).
        """
        if file_path:
            from pathlib import Path

            return Path(file_path).read_text(encoding="utf-8")
        if inline:
            return inline.replace("\\n", "\n")
        return ""

    @computed_field  # type: ignore[misc]
    @property
    def jwt_private_key(self) -> str:
        return self._resolve_pem(self.JWT_PRIVATE_KEY_FILE, self.JWT_PRIVATE_KEY)

    @computed_field  # type: ignore[misc]
    @property
    def jwt_public_key(self) -> str:
        return self._resolve_pem(self.JWT_PUBLIC_KEY_FILE, self.JWT_PUBLIC_KEY)

    @computed_field  # type: ignore[misc]
    @property
    def admin_user_ids(self) -> frozenset[str]:
        """Normalized (canonical UUID string) set of admin user-ids. Malformed or
        blank entries are dropped — fail-closed: a garbage id simply is not an
        admin, it never widens access."""
        from uuid import UUID

        out: set[str] = set()
        for raw in self.ADMIN_USER_IDS.split(","):
            s = raw.strip()
            if not s:
                continue
            try:
                out.add(str(UUID(s)))
            except ValueError:
                continue
        return frozenset(out)

    @computed_field  # type: ignore[misc]
    @property
    def consent_bypassed(self) -> bool:
        """True only when the B48 pre-launch consent kill-switch is ACTIVE:
        enforcement explicitly disabled AND running in an allowlisted dev/test/ci
        env. Any other env (production / staging / preview / unknown / mis-cased)
        → False, i.e. the DPDP gate stays enforced. Single source of truth read by
        ``deps._consent_granted``."""
        return (
            not self.DPDP_CONSENT_ENFORCED
            and self.ENV.strip().lower() in _CONSENT_BYPASS_ALLOWED_ENVS
        )

    def model_post_init(self, __context: object) -> None:
        """Fail-closed boot guard for the B48 consent kill-switch.

        If consent enforcement is disabled but the env is NOT in the dev allowlist
        (e.g. a dev `DPDP_CONSENT_ENFORCED=false` leaked onto a prod/staging box),
        refuse to start — convert a silent consent bypass into a hard crash. When
        the bypass is legitimately active, emit ONE startup warning (not per-call).
        """
        if not self.DPDP_CONSENT_ENFORCED and not self.consent_bypassed:
            raise ValueError(
                f"DPDP_CONSENT_ENFORCED=false is not permitted in ENV={self.ENV!r}. "
                "Only development/test/ci may disable DPDP consent enforcement (B48)."
            )
        if self.consent_bypassed:
            import logging

            logging.getLogger("dhanradar.consent").warning(
                "DPDP consent enforcement is DISABLED (B48 pre-launch bypass, "
                "ENV=%r). Gated routes treat all purposes as granted. This MUST be "
                "re-enabled before the launch deploy.",
                self.ENV,
            )

    @computed_field  # type: ignore[misc]
    @property
    def database_url(self) -> str:
        """Async-compatible DSN for SQLAlchemy + asyncpg."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()  # type: ignore[call-arg]
