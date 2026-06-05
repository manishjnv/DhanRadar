"""
DhanRadar — Application settings.

Reads all configuration from environment variables (or .env file).
Pydantic-settings v2 automatically validates types and raises on missing required fields.
"""

from __future__ import annotations

from typing import Optional

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # ------------------------------------------------------------------
    # External APIs
    # ------------------------------------------------------------------
    OPENROUTER_API_KEY: str = ""
    RESEND_API_KEY: str = ""

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
    SENTRY_DSN: Optional[str] = None

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
    def database_url(self) -> str:
        """Async-compatible DSN for SQLAlchemy + asyncpg."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()  # type: ignore[call-arg]
