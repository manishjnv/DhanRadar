"""
Regression test (fix/manual-ingest-worker-auth-import) — proves the Celery
worker's manual-ingest task module can perform a real DB insert against
`MfManualIngestFile` WITHOUT ever having imported `dhanradar.models.auth` via
any other path (e.g. the FastAPI app's auth router at startup).

Prod incident: `sqlalchemy.exc.NoReferencedTableError` was raised the first
time `scan_incoming_folder` ran in the Celery worker process (which boots
ONLY the task modules listed in `celery_app.py`'s `include=[...]`) and
touched `MfManualIngestFile` — its `uploaded_by` column has a string
`ForeignKey("auth.users.id")`, and that table was never registered in the
shared declarative metadata because `dhanradar.models.auth` had never been
imported anywhere in that process. The admin upload route never hit this
because the FastAPI app transitively imports `dhanradar.models.auth` (auth
router/deps) at startup, long before any request touches the manual-ingest
table.

Every OTHER integration test in this suite uses the `db_tables` fixture,
which explicitly imports `dhanradar.models.auth` (see tests/conftest.py's
`db_tables`) before creating tables — so this exact gap was invisible to the
whole existing test suite and passed CI. This test runs the insert in a
SEPARATE, freshly-started Python process that imports ONLY
`dhanradar.tasks.manual_ingest` (mirroring the real worker's import surface,
never `dhanradar.main`/the app, never any conftest fixture) to prove the fix
— a module-level `from dhanradar.models import auth` in
tasks/manual_ingest.py — actually closes the gap, rather than merely "working
because some other test already warmed the shared metadata in this pytest
session".
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Runs in a BRAND NEW interpreter (subprocess), so this is the ONLY dhanradar
# import in that process's history — exactly what the real Celery worker does
# per celery_app.py's `include=[...]` list.
_SUBPROCESS_SCRIPT = """
import asyncio
import sys

from dhanradar.tasks import manual_ingest as mi

# Never touch the real Celery broker — CI has no Redis service ("Redis is
# faked in tests (fakeredis)", ci.yml). This subprocess has no monkeypatch
# fixture, so patch .delay directly on the shared task object; the local
# `from dhanradar.tasks.manual_ingest import parse_manual_disclosure_file`
# inside intake_file() resolves to this SAME object (module already imported
# once in this process).
mi.parse_manual_disclosure_file.delay = lambda *a, **k: None


async def main() -> None:
    data = ("regression-test-file-" + sys.argv[1]).encode("utf-8")
    extracted, skipped = await mi.intake_upload(
        data=data,
        original_filename="regression_test.xlsx",
        channel="folder",
        uploaded_by=None,
        amc_hint=None,
    )
    assert not skipped, skipped
    assert len(extracted) == 1, extracted
    _name, result = extracted[0]
    assert result.status == "pending", result
    assert result.file_id is not None
    print("REGRESSION_TEST_OK")


asyncio.run(main())
"""


async def test_manual_ingest_worker_insert_with_only_task_module_imported(db_tables) -> None:
    """Spawn a fresh interpreter that imports ONLY `dhanradar.tasks.manual_ingest`
    and exercise the exact insert path the Celery worker runs. Without the
    module-level auth-models import in tasks/manual_ingest.py, this reproduces
    the prod `NoReferencedTableError` verbatim. `db_tables` (this pytest
    process) only ensures the schema/tables exist on the shared test database
    beforehand — the actual assertion runs in the CHILD process, which starts
    with a clean import cache, never touching this process's already-warmed
    SQLAlchemy metadata.
    """
    token = uuid.uuid4().hex
    result = subprocess.run(
        [sys.executable, "-c", _SUBPROCESS_SCRIPT, token],
        cwd=str(BACKEND_DIR),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"worker-only import crashed (stdout={result.stdout!r}):\n{result.stderr}"
    )
    assert "REGRESSION_TEST_OK" in result.stdout, result.stdout
    assert "NoReferencedTableError" not in result.stderr
