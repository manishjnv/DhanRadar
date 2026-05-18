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
    # Observability
    # ------------------------------------------------------------------
    SENTRY_DSN: Optional[str] = None

    # ------------------------------------------------------------------
    # JWT (RS256 asymmetric)
    # Generate dev keys with: python backend/scripts/gen_jwt_keys.py
    # ------------------------------------------------------------------
    JWT_PRIVATE_KEY: str = ""      # PEM-encoded RSA private key (from env)
    JWT_PUBLIC_KEY: str = ""       # PEM-encoded RSA public key (from env)
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
    # Runtime
    # ------------------------------------------------------------------
    ENV: str = "development"

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------
    @computed_field  # type: ignore[misc]
    @property
    def database_url(self) -> str:
        """Async-compatible DSN for SQLAlchemy + asyncpg."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()  # type: ignore[call-arg]
