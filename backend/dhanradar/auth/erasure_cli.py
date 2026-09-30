"""
DhanRadar — erasure re-apply CLI (B79 follow-up, backup-restore cleanup).

A restored backup can resurrect rows for a user who was hard-erased AFTER the
backup snapshot was taken (``scripts/restore-db.sh``). This CLI re-runs
``auth.erasure.reapply_erasure`` for a list of user ids against the RESTORED
database so those users end up erased again post-restore. Builder D's restore
scripts call this exact interface.

Usage::

    python -m dhanradar.auth.erasure_cli --database <name> --ids-file <path|->

``--ids-file -`` reads the id list from stdin. One UUID per line; blank lines
and ``#``-prefixed comment lines are ignored. Any other malformed line is a
hard stop — this prints every bad line and exits 1 BEFORE touching the
database (a typo must never silently skip a user that needed re-erasing).

Sends NO email (this is cleanup after a restore, not a user-facing deletion —
the affected users already got their erasure-done email the first time).

Connection: the OWNER DSN (``settings.migration_database_url`` — the same one
Alembic uses), with the database name swapped to ``--database``, NullPool.
NOT the dhanradar_admin (BYPASSRLS) DSN: ``scripts/restore-db.sh`` restores
with ``pg_restore --no-owner --no-acl``, so a freshly restored database has NO
grants for dhanradar_admin yet — only the owner role can act on it. The owner
also bypasses RLS, so cross-user erasure works the same as the admin DSN
would have. A dedicated engine/sessionmaker is used here (never db.py's
pooled `engine`) — the local names are NOT literally `engine` so
``scripts/ci_guards.py`` guard #6 does not need an exemption; NullPool anyway
makes this safe across repeated ``asyncio.run()`` calls the same way
``task_engine`` is (see db.py's module docstring).
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import uuid
from typing import TextIO

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from dhanradar.auth.erasure import reapply_erasure
from dhanradar.config import settings

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _parse_ids(lines: list[str]) -> tuple[list[uuid.UUID], list[tuple[int, str]]]:
    """Return (valid ids, [(line_no, raw_line)] for every malformed line)."""
    ids: list[uuid.UUID] = []
    bad: list[tuple[int, str]] = []
    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not _UUID_RE.match(line):
            bad.append((lineno, raw.rstrip("\n")))
            continue
        ids.append(uuid.UUID(line))
    return ids, bad


def _cli_dsn(database: str) -> str:
    """Owner DSN with the database name swapped to *database*.

    ``migration_database_url`` is ``postgresql+asyncpg://user:pass@host:port/<db>``
    — a Postgres database name can never contain a ``/``, so replacing
    everything after the last ``/`` is exact.
    """
    base = settings.migration_database_url
    return base.rsplit("/", 1)[0] + f"/{database}"


async def _run(database: str, ids: list[uuid.UUID]) -> tuple[int, int]:
    """Re-apply erasure for every id against *database*. Returns (reerased, absent)."""
    cli_engine = create_async_engine(_cli_dsn(database), poolclass=NullPool, future=True)
    session_factory = async_sessionmaker(cli_engine, expire_on_commit=False)

    reerased = 0
    absent = 0
    try:
        async with session_factory() as db:
            for user_id in ids:
                counts = await reapply_erasure(db, user_id)
                if counts is None:
                    absent += 1
                else:
                    reerased += 1
    finally:
        await cli_engine.dispose()

    return reerased, absent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Re-apply DPDP erasure for a list of user ids after a backup restore."
    )
    parser.add_argument("--database", required=True, help="Target Postgres database name.")
    parser.add_argument(
        "--ids-file",
        required=True,
        help="Path to a file of one UUID per line, or '-' for stdin.",
    )
    args = parser.parse_args(argv)

    stream: TextIO
    if args.ids_file == "-":
        lines = sys.stdin.readlines()
    else:
        with open(args.ids_file, encoding="utf-8") as stream:
            lines = stream.readlines()

    ids, bad = _parse_ids(lines)
    if bad:
        print("Malformed id lines (fix these and re-run — nothing was touched):", file=sys.stderr)
        for lineno, raw in bad:
            print(f"  line {lineno}: {raw!r}", file=sys.stderr)
        return 1

    reerased, absent = asyncio.run(_run(args.database, ids))
    print(f"reerased={reerased} absent={absent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
