"""Single source of truth for the Postgres schemas the runtime role (`dhanradar_app`) needs
grants on (B80).

The grant migration, `infra/postgres/init/01_init.sql`, and the test fixtures all derive the set
from here so they cannot silently drift — the original B80 defect was a grant list copied from the
*aspirational* 17-schema list in `01_init.sql` instead of the schemas migrations actually create,
leaving 7 real schemas (audit, billing, bse, concepts, education, notify, signal) with ZERO grants
(a prod outage the moment the app de-superusers). The per-schema regression test reads this constant
and asserts it equals the schemas that actually have tables, so adding a schema without granting it
fails CI.

Every schema where the app or Celery reads/writes a table MUST be listed. Verified against
`CREATE SCHEMA` across `backend/alembic/versions/` + every model's `__table_args__` (2026-06-27).
"""

from __future__ import annotations

APP_SCHEMAS: tuple[str, ...] = (
    "auth",
    "billing",
    "mf",
    "notify",  # NOT "notif" — the real notifications schema (migration 0005); init had the typo.
    "compliance",
    "mood",
    "consent",
    "audit",
    "education",
    "news",
    "concepts",
    "signal",
    "bse",
)
