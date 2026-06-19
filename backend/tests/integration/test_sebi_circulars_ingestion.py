"""
Integration tests for the SEBI circulars ingestion pipeline.

CI-only: requires a live Postgres test database (no local Postgres on dev boxes).
Run via ``pytest tests/integration/test_sebi_circulars_ingestion.py`` inside the
container (pyproject.toml marks these as ``integration``).

Covers
------
1. Happy-path (2 valid circular rows):
   - Exactly one mf.ingestion_runs row with source='sebi_circulars',
     status='success', records_written==2.
   - Exactly 2 mf.sebi_circulars rows with the expected circular numbers.
   - The title stored verbatim — no summarisation.

2. Re-run idempotency (on_conflict_do_update):
   - A second call to _sebi_circulars_pipeline() must NOT duplicate rows.
   - Still exactly 2 mf.sebi_circulars rows; a second ingestion_runs row is
     written (one per run), but circular data stays deduplicated.

Fixtures used: db_tables (creates all ORM tables), patch_redis (fake Redis).
TaskSessionLocal is the DB access path (NullPool; same as production).
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select, func, text

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Fixture data — 2 valid CircularRow instances for monkeypatching
# ---------------------------------------------------------------------------

_CIRC_A_NUMBER = "SEBI/HO/IMD/IMD-I/DOF5/CIR/2026/52"
_CIRC_B_NUMBER = "SEBI/HO/IMD/PoD-1/CIR/2026/48"

_FIXTURE_HTML = """\
<html><body>
<table>
  <tr>
    <td>SEBI/HO/IMD/IMD-I/DOF5/CIR/2026/52</td>
    <td><a href="https://www.sebi.gov.in/cms/circ52.pdf">
        Circular on MF Categorisation Update</a></td>
    <td>Jun 19, 2026</td>
    <td>Mutual Funds</td>
  </tr>
  <tr>
    <td>SEBI/HO/IMD/PoD-1/CIR/2026/48</td>
    <td><a href="/cms/circ48.pdf">Circular on Scheme Mergers Reporting</a></td>
    <td>May 30, 2026</td>
    <td>Mutual Funds</td>
  </tr>
</table>
</body></html>
"""


def _async_client_cm_mock():
    """Return a mock that behaves as ``async with httpx.AsyncClient(...) as client:``."""
    fake_client = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=fake_client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


async def _cleanup(db_session) -> None:
    """Remove all test rows inserted by the pipeline."""
    await db_session.execute(
        text("DELETE FROM mf.sebi_circulars WHERE source = 'sebi_circulars'")
    )
    await db_session.execute(
        text("DELETE FROM mf.ingestion_runs WHERE source = 'sebi_circulars'")
    )
    await db_session.execute(
        text("DELETE FROM mf.source_health WHERE source = 'sebi_circulars'")
    )
    await db_session.commit()


# ===========================================================================
# Test 1 — Happy path: 2 valid rows written
# ===========================================================================


async def test_pipeline_writes_run_and_circulars(db_tables, patch_redis, db_session):
    """Two valid circular rows arrive → written to mf.sebi_circulars + ingestion_runs."""
    from dhanradar.models.mf import MfIngestionRun, MfSebiCircular
    from dhanradar.tasks.sebi_circulars import _sebi_circulars_pipeline

    import dhanradar.market_data.sebi as _sebi_mod

    async def _fake_fetch(client):  # noqa: ARG001
        return _FIXTURE_HTML

    with patch.object(_sebi_mod, "fetch_circulars", new=_fake_fetch):
        with patch(
            "dhanradar.tasks.sebi_circulars.httpx.AsyncClient",
            return_value=_async_client_cm_mock(),
        ):
            result = await _sebi_circulars_pipeline()

    # Return string must mention written counts.
    assert "written" in result

    # -----------------------------------------------------------------
    # ingestion_runs: exactly one row for this source
    # -----------------------------------------------------------------
    run_rows = (
        await db_session.scalars(
            select(MfIngestionRun)
            .where(MfIngestionRun.source == "sebi_circulars")
            .order_by(MfIngestionRun.run_id.desc())
        )
    ).all()
    assert len(run_rows) == 1, (
        f"Expected 1 ingestion_runs row, got {len(run_rows)}"
    )
    run = run_rows[0]
    assert run.status == "success", f"Expected status='success', got {run.status!r}"
    assert run.records_written == 2, (
        f"Expected records_written=2, got {run.records_written}"
    )

    # -----------------------------------------------------------------
    # sebi_circulars: exactly 2 rows with the expected numbers
    # -----------------------------------------------------------------
    circ_rows = (
        await db_session.scalars(
            select(MfSebiCircular).where(
                MfSebiCircular.circular_number.in_([_CIRC_A_NUMBER, _CIRC_B_NUMBER])
            )
        )
    ).all()
    assert len(circ_rows) == 2, (
        f"Expected 2 sebi_circulars rows, got {len(circ_rows)}"
    )

    found_numbers = {r.circular_number for r in circ_rows}
    assert found_numbers == {_CIRC_A_NUMBER, _CIRC_B_NUMBER}

    # Title stored verbatim — not empty, not summarised
    circ_a = next(r for r in circ_rows if r.circular_number == _CIRC_A_NUMBER)
    assert "Categorisation Update" in circ_a.title
    assert circ_a.source == "sebi_circulars"
    assert circ_a.run_id is not None
    assert circ_a.circular_date == datetime.date(2026, 6, 19)

    await _cleanup(db_session)


# ===========================================================================
# Test 2 — Idempotency: re-run must NOT duplicate sebi_circulars rows
# ===========================================================================


async def test_rerun_does_not_duplicate_circulars(db_tables, patch_redis, db_session):
    """A second pipeline run upserts without duplicating sebi_circulars rows."""
    from dhanradar.models.mf import MfIngestionRun, MfSebiCircular
    from dhanradar.tasks.sebi_circulars import _sebi_circulars_pipeline

    import dhanradar.market_data.sebi as _sebi_mod

    async def _fake_fetch(client):  # noqa: ARG001
        return _FIXTURE_HTML

    # Run the pipeline twice.
    for _ in range(2):
        with patch.object(_sebi_mod, "fetch_circulars", new=_fake_fetch):
            with patch(
                "dhanradar.tasks.sebi_circulars.httpx.AsyncClient",
                return_value=_async_client_cm_mock(),
            ):
                await _sebi_circulars_pipeline()

    # -----------------------------------------------------------------
    # sebi_circulars: still exactly 2 rows (no duplication)
    # -----------------------------------------------------------------
    total_circulars = await db_session.scalar(
        select(func.count()).select_from(MfSebiCircular).where(
            MfSebiCircular.source == "sebi_circulars"
        )
    )
    assert total_circulars == 2, (
        f"Expected 2 sebi_circulars rows after 2 runs, got {total_circulars}"
    )

    # -----------------------------------------------------------------
    # ingestion_runs: 2 rows (one per run — each run is audited)
    # -----------------------------------------------------------------
    total_runs = await db_session.scalar(
        select(func.count()).select_from(MfIngestionRun).where(
            MfIngestionRun.source == "sebi_circulars"
        )
    )
    assert total_runs == 2, (
        f"Expected 2 ingestion_runs rows (one per run), got {total_runs}"
    )

    await _cleanup(db_session)
