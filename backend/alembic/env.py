"""
Alembic async migration environment for DhanRadar.

Key design points:
  - Uses asyncio + create_async_engine (asyncpg driver) to match the
    application's async SQLAlchemy engine.
  - Imports Base.metadata so Alembic auto-detects all models.
  - include_schemas=True so tables in non-public schemas (e.g. auth.*) are
    visible to autogenerate.
  - compare_type=True so column type changes are detected.
  - version_table_schema left as default (public) — the alembic_version
    table lives in the public schema.

To run migrations (inside the container):
    docker compose exec dhanradar-fastapi alembic upgrade head
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# ---------------------------------------------------------------------------
# Alembic Config object — provides access to alembic.ini values.
# ---------------------------------------------------------------------------
config = context.config

# Interpret the config file for Python logging (if present).
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Import ALL models so their tables are registered in Base.metadata.
# Add new model modules here as they are created in later phases.
# ---------------------------------------------------------------------------
from dhanradar.models.base import Base  # noqa: E402
import dhanradar.models.auth  # noqa: E402, F401  — registers auth.users + auth.subscriptions
import dhanradar.models.billing  # noqa: E402, F401  — registers billing.plans
import dhanradar.models.mf  # noqa: E402, F401  — registers the mf.* tables
import dhanradar.models.notifications  # noqa: E402, F401  — registers notify.* tables
import dhanradar.models.compliance  # noqa: E402, F401  — registers compliance.* tables
import dhanradar.models.mood  # noqa: E402, F401  — registers mood.* tables
import dhanradar.models.consent  # noqa: E402, F401  — registers consent.* tables (B44)

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# DSN — read from application settings (not from alembic.ini sqlalchemy.url)
# ---------------------------------------------------------------------------
from dhanradar.config import settings  # noqa: E402

_DB_URL: str = settings.database_url


# ---------------------------------------------------------------------------
# Offline migrations (emit SQL without a live DB connection)
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL script)."""
    context.configure(
        url=_DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migrations (run against a live async engine)
# ---------------------------------------------------------------------------

def do_run_migrations(connection) -> None:  # type: ignore[type-arg]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using the async engine."""
    connectable = create_async_engine(
        _DB_URL,
        poolclass=pool.NullPool,  # NullPool is correct for migration runs
        future=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
