"""
DhanRadar — Application settings.

Reads all configuration from environment variables (or .env file).
Pydantic-settings v2 automatically validates types and raises on missing required fields.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field, computed_field
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
    # Owner / superuser role: used by Alembic migrations + owns every table & trigger.
    POSTGRES_USER: str = "dhanradar"
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str = "dhanradar"

    # Least-privilege RUNTIME role (B80). The FastAPI app + Celery connect as this so the
    # append-only trigger (I12) and RLS (I5) actually bind them. When the password is unset,
    # database_url falls back to the owner role with a loud warning — a half-configured env runs
    # (no outage) at the old privilege until the password is set on the box. Field names ARE the
    # env-var names (this file's convention: POSTGRES_PASSWORD, RAZORPAY_KEY_ID, …).
    DHANRADAR_APP_DB_USER: str = "dhanradar_app"
    DHANRADAR_APP_DB_PASSWORD: str | None = None

    # BYPASSRLS role for legitimate CROSS-USER readers (admin console + Celery aggregate jobs +
    # webhooks) — B81. Required in prod once RLS is enforced (same fail-closed gate as the app pw).
    DHANRADAR_ADMIN_DB_USER: str = "dhanradar_admin"
    DHANRADAR_ADMIN_DB_PASSWORD: str | None = None

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
    # Cheap NON-premium paid-model fallback (operator-set, verified ids), tried when
    # the free pool yields nothing usable for AI_PAID_FALLBACK_TASKS. Keeps low-volume
    # signals (mood news-sentiment / commentary) alive through free-tier 429 weather
    # WITHOUT premium-Sonnet spend. Policy: non-Claude/OpenAI/Google ids only. For the
    # listed tasks this fallback OWNS the retry (those tasks skip the Sonnet spillover).
    AI_PAID_FALLBACK_MODELS: str = ""
    AI_PAID_FALLBACK_TASKS: str = ""
    # Rough blended $/1M tokens for the cheap fallback — debits the premium budget
    # counter only (not a billing source of truth); conservative over-estimate.
    AI_PAID_FALLBACK_USD_PER_1M: float = 0.5
    # Groundedness eval (PR-4): fraction [0..1] of served AI outputs to score with a
    # sampled LLM-judge. Default 0 = OFF (opt-in): the judge runs on the FREE pool,
    # uninstrumented, and only the 0..1 score is stored (never the context/output);
    # a sampled call pays one extra free-pool call of latency (lands on background
    # commentary/mood jobs). Enable in prod via env (set the value to e.g. 0.2).
    AI_GROUNDEDNESS_SAMPLE_RATE: float = 0.0
    # A sample scoring below this is counted as a low-groundedness flag (health surface).
    AI_GROUNDEDNESS_LOW_THRESHOLD: float = 0.6
    # Cheap paid model for the groundedness judge when the free pool is 429-throttled (PR-4b).
    # Empty = disabled (judge returns None when free pool is exhausted).
    # Example: "deepseek/deepseek-chat-v3-0324" ($0.28/M out, reliable paid tier).
    AI_GROUNDEDNESS_JUDGE_PAID_MODEL: str = ""

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
    JWT_ALGORITHM: str = "RS256"  # Hard-coded to RS256; env override is informational only
    ACCESS_TTL_MIN: int = 15  # Access token TTL in minutes
    REFRESH_TTL_DAYS: int = 7  # Refresh token TTL in days

    # ------------------------------------------------------------------
    # Cookie
    # ------------------------------------------------------------------
    COOKIE_SECURE: bool = True  # Set False only in dev without HTTPS

    # ------------------------------------------------------------------
    # Kite Connect (MF instrument enrichment — ADR-0033 extension)
    # access_token expires daily at 06:00 IST; mf_kite_enrich refreshes it
    # automatically via TOTP (pyotp).  All five fields empty ⇒ task is a
    # no-op.  KITE_API_KEY / KITE_API_SECRET may already be in .env from
    # the equity stub; KITE_USER_ID / KITE_USER_PASSWORD / KITE_TOTP_SECRET
    # are the three NEW vars required for unattended token refresh.
    # ------------------------------------------------------------------
    KITE_API_KEY: str = ""
    KITE_API_SECRET: str = ""
    KITE_USER_ID: str = ""
    KITE_USER_PASSWORD: str = ""
    KITE_TOTP_SECRET: str = ""

    # ------------------------------------------------------------------
    # Manual disclosure ingestion inbox (ADR-0033(a) human side-channel).
    # HDFC/SBI/ICICI-Pru/Kotak/Axis block mf_constituents_fetch (Akamai/Radware);
    # a human downloads the monthly SEBI disclosure and drops it via one of 3
    # channels (admin upload / watched folder / email poller — all 3 funnel
    # through dhanradar/mf/manual_ingest.py's one intake service).
    # ------------------------------------------------------------------
    # Filesystem root the intake service writes into (mirrors the CAS upload dir
    # convention — a docker-volume-backed path in prod; default is repo-root-
    # relative for local dev, matching the top-level .gitignore `data/` entry).
    MANUAL_INGEST_DIR: str = "data/manual_ingest"
    # Email poller (Channel C) — DORMANT unless all three of host/user/password
    # are set (fail-closed no-op, never a crash or alert spam when unconfigured).
    MANUAL_INGEST_IMAP_HOST: str = ""
    MANUAL_INGEST_IMAP_USER: str = ""
    MANUAL_INGEST_IMAP_PASSWORD: str = ""
    # Comma-separated sender email allowlist. EMPTY ⇒ accept none (fail-closed —
    # mirrors ADMIN_USER_IDS/BSE_WEBHOOK_SOURCE_IPS: no allowlist means no access,
    # never "no filter"). Resolve via manual_ingest_sender_allowlist, never raw.
    MANUAL_INGEST_SENDER_ALLOWLIST: str = ""

    # ------------------------------------------------------------------
    # Upstox Analytics (Mood Compass FII / DII / PCR — Phase 2)
    # ------------------------------------------------------------------
    # Read-only 1-year Upstox Analytics Token for the market-data API
    # (/v2/market/fii, /dii, /pcr). EMPTY ⇒ UpstoxAnalyticsProvider returns no
    # signals (fail-soft): the Mood engine runs without FII/DII/PCR rather than
    # crashing or imputing a missing factor. Operator-set; NEVER commit a real
    # token (kept out of the repo like every other secret).
    UPSTOX_ANALYTICS_TOKEN: str = ""

    # ------------------------------------------------------------------
    # Razorpay
    # ------------------------------------------------------------------
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # ------------------------------------------------------------------
    # BSE Star MF 2.0 (mutual-fund execution integration)
    # ------------------------------------------------------------------
    # Webhook transport is JOSE (API doc §6.1.7): BSE sends a JWS (signed with
    # BSE's private key) wrapping a JWE (encrypted to OUR public key). The receiver
    # VERIFIES the JWS with BSE's public key, then DECRYPTS the JWE with our private
    # key — fail-closed: if either key is unset the webhook is refused (503), never
    # parsed unverified.
    #   * BSE_WEBHOOK_PUBLIC_KEY(_FILE)  — BSE's public key (verify their signature).
    #   * BSE_PRIVATE_KEY(_FILE)         — OUR private key (decrypt the JWE; also signs
    #                                      our outbound API requests). Mounted file is
    #                                      the production form (key never transits env).
    # Resolve via the bse_webhook_public_key / bse_private_key computed properties.
    BSE_WEBHOOK_PUBLIC_KEY: str = ""
    BSE_WEBHOOK_PUBLIC_KEY_FILE: str = ""
    BSE_PRIVATE_KEY: str = ""
    BSE_PRIVATE_KEY_FILE: str = ""
    # uat | production — selects which BSE base URL the outbound client targets.
    BSE_ENV: str = "uat"
    BSE_API_BASE_URL_UAT: str = "https://starmfv2demo.bseindia.com/api/"
    BSE_API_BASE_URL_PROD: str = "https://v2.bsestarmf.in/api/"
    # Scheme-master enrichment (tasks/bse_enrich.py) — dedicated arm flag, NOT
    # inferred from BSE_ENV (mirrors BSE_WEBHOOK_ALLOW_PLAINTEXT: an unrelated
    # ops change must never arm it). Even when True, writes require
    # BSE_ENV=prod + credentials; anything else is a dry run.
    BSE_ENRICH_ENABLED: bool = False
    # Founder decision 2026-07-10 (ADR-0042 addendum): the DEMO master is
    # verified CURRENT (2024-25 NFOs present; demo NAV cross-checked equal to
    # AMFI), so slow-changing fields (exit load / min amounts / benchmark
    # fill) may be written from it behind this SECOND explicit flag. Off by
    # default; irrelevant once BSE_ENV=prod.
    BSE_ENRICH_ALLOW_DEMO: bool = False
    # Our BSE member code + the X-API-Org-ID header value BSE assigns at onboarding
    # (member/<org-code>:<fingerprint>). Empty until BSE provisions us.
    BSE_MEMBER_CODE: str = ""
    BSE_API_ORG_ID: str = ""
    BSE_LOGIN_USERNAME: str = ""
    BSE_LOGIN_PASSWORD: str = ""
    # Optional comma-separated allowlist of BSE webhook SOURCE IPs (defence in depth
    # on top of the JOSE signature). EMPTY ⇒ IP check skipped (signature is the gate).
    BSE_WEBHOOK_SOURCE_IPS: str = ""
    # Explicit opt-in to accept BSE's UNSIGNED plain-JSON webhooks (their UAT pushes
    # plaintext; their doc defines no webhook signing). SECURITY: a dedicated flag —
    # NOT overloaded onto BSE_ENV — so an unrelated ops change never re-arms it.
    # Even when True, plaintext is accepted ONLY from a non-empty BSE_WEBHOOK_SOURCE_IPS
    # allowlist (the source IP is the authentication in place of a signature). Keep
    # False in any environment where BSE signs its webhooks.
    BSE_WEBHOOK_ALLOW_PLAINTEXT: bool = False

    # ------------------------------------------------------------------
    # Google SSO (OAuth 2.0 authorization-code + PKCE)
    # All three must be set for SSO to be active; any absent → 503.
    # ------------------------------------------------------------------
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URI: str | None = None

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
    FOUNDING_ACCESS_UNTIL: datetime | None = datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC)

    # ------------------------------------------------------------------
    # Risk-free rate proxy (Sharpe / Sortino denominators)
    # ------------------------------------------------------------------
    # Annual risk-free rate as a FRACTION (e.g. 0.065 = 6.5 %).
    # Proxy for the RBI 91-day T-bill / 10Y G-sec rate (~6.5% as of 2026).
    # FALLBACK value: mf_metrics_refresh resolves the real rate nightly via
    # mf.risk.resolve_risk_free_rate(), preferring a fresh+sane ingested
    # 'tbill_91d_yield_pct' row from mf.macro_indicators over this constant.
    # As of 2026-07-04 the rbi_dbie fetch URL (market_data/rbi.py) 404s, so
    # no row is ever ingested and this placeholder is what's actually used —
    # ingestion is a separate follow-up once a working RBI money-market
    # source is identified (do not swap the placeholder default without one).
    RISK_FREE_RATE_ANNUAL: float = Field(
        default=0.065,
        description="Annual risk-free proxy for Sharpe/Sortino (~6.5%). "
        "Fallback used by mf_metrics_refresh when no fresh/sane "
        "ingested 'tbill_91d_yield_pct' row exists.",
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
    def bse_webhook_public_key(self) -> str:
        """BSE's public key (PEM) used to VERIFY the JWS on inbound webhooks.
        Empty ⇒ webhook verification fails closed (receiver returns 503)."""
        return self._resolve_pem(self.BSE_WEBHOOK_PUBLIC_KEY_FILE, self.BSE_WEBHOOK_PUBLIC_KEY)

    @computed_field  # type: ignore[misc]
    @property
    def bse_private_key(self) -> str:
        """OUR private key (PEM) used to DECRYPT the JWE on inbound webhooks (and
        to sign outbound API requests). Empty ⇒ fails closed (receiver 503)."""
        return self._resolve_pem(self.BSE_PRIVATE_KEY_FILE, self.BSE_PRIVATE_KEY)

    @computed_field  # type: ignore[misc]
    @property
    def bse_api_base_url(self) -> str:
        """Active BSE base URL, selected by BSE_ENV (uat | production)."""
        return (
            self.BSE_API_BASE_URL_PROD
            if self.BSE_ENV.strip().lower() == "production"
            else self.BSE_API_BASE_URL_UAT
        )

    @computed_field  # type: ignore[misc]
    @property
    def bse_webhook_source_ips(self) -> frozenset[str]:
        """Optional allowlist of BSE webhook source IPs (defence in depth). Empty
        set ⇒ no IP gate (the JOSE signature is the real authentication)."""
        return frozenset(ip.strip() for ip in self.BSE_WEBHOOK_SOURCE_IPS.split(",") if ip.strip())

    @computed_field  # type: ignore[misc]
    @property
    def manual_ingest_sender_allowlist(self) -> frozenset[str]:
        """Normalized (lowercased) set of allowed sender email addresses for the manual
        disclosure email poller (Channel C). Empty ⇒ no sender can pass (fail-closed —
        mirrors bse_webhook_source_ips: an unset allowlist widens nothing)."""
        return frozenset(
            e.strip().lower() for e in self.MANUAL_INGEST_SENDER_ALLOWLIST.split(",") if e.strip()
        )

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

        # B80 fail-closed boot guard: outside dev/test/ci the runtime MUST connect as the
        # least-privilege dhanradar_app role — never silently fall back to the DB superuser (which
        # would leave I12 append-only + I5 RLS unenforced with only a WARN). Mirror the consent
        # kill-switch above. Safe: the deploy order is migrate → set DHANRADAR_APP_DB_PASSWORD →
        # compose up, so prod always boots with it set (deploy.sh syncs it onto the role).
        if self.ENV.strip().lower() not in _CONSENT_BYPASS_ALLOWED_ENVS:
            missing = [
                name
                for name, val in (
                    ("DHANRADAR_APP_DB_PASSWORD", self.DHANRADAR_APP_DB_PASSWORD),  # B80
                    ("DHANRADAR_ADMIN_DB_PASSWORD", self.DHANRADAR_ADMIN_DB_PASSWORD),  # B81
                )
                if not val
            ]
            if missing:
                raise ValueError(
                    f"{', '.join(missing)} required in ENV={self.ENV!r} (B80/B81): the runtime must "
                    "connect as the least-privilege dhanradar_app role (never the DB superuser), and "
                    "cross-user readers (admin/Celery/webhooks) as the BYPASSRLS dhanradar_admin role "
                    "— else RLS silently empties their queries. Set both in .env before starting "
                    "(deploy.sh applies them to the roles)."
                )

    def _dsn(self, user: str, password: str) -> str:
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def database_url(self) -> str:
        """RUNTIME DSN (app + Celery) — the least-privilege dhanradar_app role (B80), so the
        append-only trigger (I12) and RLS (I5) bind the app. In dev/test/ci ONLY, falls back to the
        owner role with a startup warning when the app password is unset (local convenience). In any
        other ENV, model_post_init has already FAILED the boot (fail-closed) before this is reached,
        so prod can never silently run as superuser."""
        import logging

        if self.DHANRADAR_APP_DB_PASSWORD:
            return self._dsn(self.DHANRADAR_APP_DB_USER, self.DHANRADAR_APP_DB_PASSWORD)
        logging.getLogger("dhanradar.config").warning(
            "DHANRADAR_APP_DB_PASSWORD unset — DB connection uses the OWNER/superuser role (%s). "
            "I12 append-only + I5 RLS are NOT hard-enforced until the app role is configured (B80).",
            self.POSTGRES_USER,
        )
        return self._dsn(self.POSTGRES_USER, self.POSTGRES_PASSWORD)

    @computed_field  # type: ignore[misc]
    @property
    def migration_database_url(self) -> str:
        """OWNER DSN — used ONLY by Alembic env.py. DDL + table/trigger ownership stay with the
        owner so the app role (dhanradar_app) cannot DISABLE TRIGGER or otherwise bypass I12/I5."""
        return self._dsn(self.POSTGRES_USER, self.POSTGRES_PASSWORD)

    @computed_field  # type: ignore[misc]
    @property
    def admin_database_url(self) -> str:
        """BYPASSRLS DSN (admin console + Celery aggregate jobs + webhooks) — B81. These read across
        users and would silently get 0 rows under RLS as dhanradar_app. Falls back to the runtime
        DSN when the admin password is unset (dev: usually the owner, which bypasses RLS anyway);
        prod requires it via model_post_init (fail-closed)."""
        if self.DHANRADAR_ADMIN_DB_PASSWORD:
            return self._dsn(self.DHANRADAR_ADMIN_DB_USER, self.DHANRADAR_ADMIN_DB_PASSWORD)
        # Fall back to the OWNER (superuser → bypasses RLS) — NOT the app role (NOBYPASSRLS), which
        # would silently 0-row every cross-user job. Prod requires the password (model_post_init).
        import logging

        logging.getLogger("dhanradar.config").warning(
            "DHANRADAR_ADMIN_DB_PASSWORD unset — cross-user readers (admin/Celery/webhooks) fall back "
            "to the OWNER role. Set it to use the dedicated BYPASSRLS dhanradar_admin role (B81)."
        )
        return self.migration_database_url


settings = Settings()  # type: ignore[call-arg]
