"""
DhanRadar test suite — shared fixtures.

Fixture layers
--------------
rsa_keypair          : session-scoped ephemeral RSA-2048 keypair (PEM strings).
patch_settings_keys  : function-scoped — monkeypatches settings.jwt_private_key and
                       settings.jwt_public_key to use the ephemeral keypair. Also
                       disables COOKIE_SECURE so __Host- cookies survive http:// in tests.
fake_redis           : function-scoped fakeredis.aioredis.FakeRedis instance; resets
                       (flushall) between every test.
patch_redis          : function-scoped — monkeypatches dhanradar.redis_client._client
                       to the fake_redis instance so every path that calls get_redis()
                       returns the fake. Also patches the module-level _client so that
                       any import-time singleton in auth.service / subscriptions / budget
                       also points at the fake.

Integration-only fixtures (defined here, used by tests/integration/*)
----------------------------------------------------------------------
db_engine            : session-scoped async SQLAlchemy engine against
                       settings.database_url with the test database.
db_tables            : session-scoped — creates auth schema, pgcrypto extension, and all
                       ORM tables; drops nothing (tables are truncated between tests).
db_session           : function-scoped async session; truncates auth.users and
                       auth.subscriptions after each test.
override_get_db      : function-scoped — installs app.dependency_overrides[get_db] to
                       route requests through the test session.
async_client         : function-scoped — httpx.AsyncClient(transport=ASGITransport(app)).

IMPORTANT — lifespan / ASGITransport note
-----------------------------------------
httpx.ASGITransport does NOT trigger the FastAPI lifespan (startup/shutdown handlers).
This is intentional: the lifespan would attempt a real DB connect + Redis connect before
the test overrides are in place, causing a connection failure or bypassing fakes.
Without lifespan, the dependency_overrides for get_db and the monkeypatched redis client
are the only wiring, which is exactly what we want for hermetic tests.

__Host- cookie note
-------------------
RFC 6265bis requires __Host- cookies to be set only over HTTPS. httpx.AsyncClient with
base_url="http://test" (non-TLS) will receive Set-Cookie headers containing __Host-access
and __Host-refresh, but httpx's cookie jar silently drops cookies whose name starts with
"__Host-" when the connection is not secure (same behaviour as browsers per the spec).

Workaround applied throughout integration tests: after each endpoint call that should set
auth cookies, the test reads the raw "set-cookie" response header and extracts the token
value manually, then injects it as an explicit header (Cookie: __Host-access=<value>) on
subsequent requests. Helper functions `extract_cookie` and `make_cookie_header` below
encapsulate this pattern. This is a test-harness limitation, not an app bug.
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# PRE-IMPORT ENVIRONMENT SETUP
#
# dhanradar.config.Settings is a pydantic-settings singleton constructed at
# module import time (the `settings = Settings()` line at the bottom of
# config.py). Any env var that must be visible to Settings must be set BEFORE
# the first `import dhanradar.*` anywhere in the test process.
#
# conftest.py is loaded before test modules, so module-level code here runs
# first. We set:
#   - POSTGRES_DB → appends "_test" so we never touch the production database.
#   - POSTGRES_PASSWORD → required field with no default; set a placeholder
#     (the test DB engine uses the compose-service credentials from the real
#     env when running inside the container; this only covers the case where
#     the real env is absent, e.g. a dry import check).
#   - RAZORPAY_KEY_ID / KEY_SECRET / WEBHOOK_SECRET → deterministic test values
#     so signature tests produce reproducible HMACs.
#   - JWT_PRIVATE_KEY / JWT_PUBLIC_KEY → a real RSA-2048 keypair generated
#     inline so Settings.jwt_private_key / jwt_public_key are non-empty PEMs.
#     We generate it here (once, at conftest load) and also expose it via the
#     session-scoped `rsa_keypair` fixture for use in unit tests.
#   - JWT_PRIVATE_KEY_FILE / JWT_PUBLIC_KEY_FILE → cleared so _resolve_pem
#     uses the inline fields.
#   - COOKIE_SECURE → False so __Host- cookie set_cookie does not enforce HTTPS
#     at the FastAPI layer (httpx ASGITransport is http://).
# ---------------------------------------------------------------------------

# Generate the keypair early (before Settings() is called by any import).
# This module-level variable is also returned by the `rsa_keypair` fixture.
def _gen_rsa_keypair() -> tuple[str, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


_SESSION_PRIVATE_PEM, _SESSION_PUBLIC_PEM = _gen_rsa_keypair()

# Set all required env vars BEFORE any dhanradar module is imported.
_base_db = os.environ.get("POSTGRES_DB", "dhanradar")
if not _base_db.endswith("_test"):
    os.environ["POSTGRES_DB"] = _base_db + "_test"

os.environ.setdefault("POSTGRES_PASSWORD", "dhanradar")   # compose default
os.environ["RAZORPAY_KEY_ID"] = "rzp_test_TESTKEY123456"
os.environ["RAZORPAY_KEY_SECRET"] = "test_secret_ABCDEFGH"
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "test_webhook_secret_XYZ"
os.environ["JWT_PRIVATE_KEY"] = _SESSION_PRIVATE_PEM
os.environ["JWT_PUBLIC_KEY"] = _SESSION_PUBLIC_PEM
os.environ["JWT_PRIVATE_KEY_FILE"] = ""
os.environ["JWT_PUBLIC_KEY_FILE"] = ""
os.environ["COOKIE_SECURE"] = "false"

# ---------------------------------------------------------------------------
# RSA keypair fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def rsa_keypair() -> tuple[str, str]:
    """
    Generate an ephemeral RSA-2048 keypair for the test session.

    Returns (private_key_pem, public_key_pem) as UTF-8 strings.
    Uses the `cryptography` library (already a transitive dep via pyjwt[crypto]).
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


# ---------------------------------------------------------------------------
# Settings monkeypatch: JWT keys + COOKIE_SECURE
# ---------------------------------------------------------------------------


@pytest.fixture()
def patch_settings_keys(monkeypatch: pytest.MonkeyPatch, rsa_keypair: tuple[str, str]) -> None:
    """
    Monkeypatch settings to use the ephemeral RSA keypair and disable
    COOKIE_SECURE (so __Host- cookies can be set in http:// tests).

    The computed properties jwt_private_key and jwt_public_key are defined with
    @computed_field on the Settings instance. Pydantic-settings computed_field
    properties do NOT cache; they call _resolve_pem() every invocation.  The
    cleanest override is to patch the underlying raw fields (JWT_PRIVATE_KEY /
    JWT_PUBLIC_KEY) on the singleton Settings instance via object.__setattr__
    (bypasses pydantic's __setattr__ validation) and clear the FILE fields so
    _resolve_pem falls through to the inline path.
    """
    from dhanradar.config import settings

    private_pem, public_pem = rsa_keypair

    # Use object.__setattr__ to bypass Pydantic's immutability guard.
    object.__setattr__(settings, "JWT_PRIVATE_KEY", private_pem)
    object.__setattr__(settings, "JWT_PUBLIC_KEY", public_pem)
    object.__setattr__(settings, "JWT_PRIVATE_KEY_FILE", "")
    object.__setattr__(settings, "JWT_PUBLIC_KEY_FILE", "")
    object.__setattr__(settings, "COOKIE_SECURE", False)

    # Verify the patch actually works (fail fast if _resolve_pem caches somehow)
    assert settings.jwt_private_key == private_pem
    assert settings.jwt_public_key == public_pem


# ---------------------------------------------------------------------------
# fakeredis
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def fake_redis():
    """Return a fresh fakeredis.aioredis.FakeRedis instance, flushed after use."""
    try:
        from fakeredis.aioredis import FakeRedis
    except ImportError:
        from fakeredis import aioredis as _fa
        FakeRedis = _fa.FakeRedis

    client = FakeRedis(decode_responses=True)
    yield client
    await client.flushall()
    await client.aclose()


@pytest.fixture()
def patch_redis(fake_redis, monkeypatch: pytest.MonkeyPatch):
    """
    Monkeypatch the global redis singleton so all get_redis() calls return
    the fakeredis instance. Patches both the module-level _client variable
    and the function so any code that caches the result also uses the fake.
    """
    import dhanradar.redis_client as _rc

    monkeypatch.setattr(_rc, "_client", fake_redis)

    # Also override get_redis() itself so callers always get the fake even
    # if they don't use the module-level _client.
    monkeypatch.setattr(_rc, "get_redis", lambda: fake_redis)

    return fake_redis


# ---------------------------------------------------------------------------
# Integration-only fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def db_engine():
    """
    Async SQLAlchemy engine pointed at settings.database_url.

    Function-scoped on purpose: pytest-asyncio's default loop scope is the
    function, so a session-scoped async engine would bind asyncpg
    connections to a setup loop and then be used from per-test loops
    ("got Future attached to a different loop"). Per-test engine + the
    idempotent (checkfirst) schema setup keeps every connection on the
    test's own loop. Reachable as `dhanradar-postgres` inside the container.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from dhanradar.config import settings

    engine = create_async_engine(
        settings.database_url,
        pool_size=2,
        max_overflow=2,
        echo=False,
        future=True,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_tables(db_engine):
    """
    Create auth schema, pgcrypto extension, the user_tier enum, and all ORM
    tables. Function-scoped to match db_engine's loop scope; every statement
    is idempotent (IF NOT EXISTS / checkfirst), so re-running per test is a
    handful of cheap catalog lookups. Rows are truncated between tests by
    db_session. The auth schema + pgcrypto are normally created by
    infra/postgres/init/01_init.sql; recreated here so the test DB is
    self-contained.
    """
    from sqlalchemy import text

    from dhanradar.models.auth import Base  # noqa: F401 — registers all models
    import dhanradar.models.billing  # noqa: F401 — registers billing.plans
    from dhanradar.models.base import Base as MetaBase

    async with db_engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS billing"))
        await conn.execute(
            text("CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public")
        )
        # Create the user_tier enum if it doesn't exist
        await conn.execute(
            text(
                "DO $$ BEGIN "
                "  CREATE TYPE auth.user_tier AS ENUM "
                "    ('anonymous','free','pro','pro_plus','founder_lifetime'); "
                "EXCEPTION WHEN duplicate_object THEN NULL; "
                "END $$;"
            )
        )
    async with db_engine.begin() as conn:
        await conn.run_sync(MetaBase.metadata.create_all)

    yield


@pytest_asyncio.fixture()
async def db_session(db_engine, db_tables):
    """
    Function-scoped async session. Truncates auth.users and
    auth.subscriptions after each test (CASCADE handles FK children).
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    SessionLocal = async_sessionmaker(
        db_engine, expire_on_commit=False, class_=AsyncSession
    )
    async with SessionLocal() as session:
        yield session

    # Teardown: truncate tables so each test starts clean
    async with db_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE auth.subscriptions, auth.users, billing.plans "
                "RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture()
def override_get_db(db_session):
    """
    Install app.dependency_overrides[get_db] to route DB calls through the
    test session. Returns the override dict so the test can verify or extend.
    """
    from dhanradar.db import get_db
    from dhanradar.main import app

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture()
async def async_client(override_get_db, patch_redis, patch_settings_keys):
    """
    httpx.AsyncClient backed by ASGITransport(app=app).

    ASGITransport does NOT run the FastAPI lifespan — this is intentional
    so the app never attempts a real DB/Redis connection during tests.
    The test session provides DB via override_get_db and Redis via patch_redis.

    __Host- cookie limitation: httpx drops __Host- prefixed cookies when the
    base_url is http:// (non-TLS). Tests must use `extract_cookie()` /
    `inject_cookies()` helpers to pass auth cookies manually.
    """
    import httpx
    from httpx import ASGITransport

    from dhanradar.main import app

    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=True,
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Cookie helpers for integration tests
# ---------------------------------------------------------------------------


def extract_cookie(response, name: str) -> str | None:
    """
    Extract a cookie value from a raw Set-Cookie response header.

    httpx drops __Host- cookies on non-TLS connections (browser spec compliance),
    so we parse the Set-Cookie header ourselves. Returns None if not found.
    """
    for header_value in response.headers.get_list("set-cookie"):
        # Each Set-Cookie value is "name=value; attr; attr"
        parts = header_value.split(";")
        cookie_pair = parts[0].strip()
        if "=" in cookie_pair:
            k, v = cookie_pair.split("=", 1)
            if k.strip() == name:
                return v.strip()
    return None


def make_auth_headers(access_token: str | None = None, refresh_token: str | None = None) -> dict:
    """Build a Cookie header dict containing the provided auth tokens."""
    parts = []
    if access_token:
        parts.append(f"__Host-access={access_token}")
    if refresh_token:
        parts.append(f"__Host-refresh={refresh_token}")
    if not parts:
        return {}
    return {"Cookie": "; ".join(parts)}
