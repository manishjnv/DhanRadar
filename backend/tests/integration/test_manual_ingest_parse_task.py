"""
Integration test for the manual disclosure inbox parse task
(dhanradar/tasks/manual_ingest.py::parse_manual_disclosure_file) on a real
trimmed SEBI-format disclosure fixture — exercises the ACTUAL byte-parsing
path (openpyxl.load_workbook via _parse_sebi_xlsx, the SAME parser
mf_constituents_fetch uses), not a synthetic dict.

`_upsert_constituents` (dhanradar/tasks/mf.py) is monkeypatched: it resolves
scheme names to ISINs via a live pg_trgm similarity query against mf.mf_funds,
which this suite has no existing fixture-builder for (no test anywhere
exercises `_upsert_constituents` end-to-end yet — a pre-existing gap, not
introduced here). This test instead proves the manual-ingest ORCHESTRATION —
detect AMC/period from real bytes, route through the shared upsert function
with the RIGHT arguments (rows, amc_name, run_id), and record the outcome on
the mf.manual_ingest_files row — end to end.
"""

from __future__ import annotations

import io
import uuid

import pytest
from openpyxl import Workbook

from dhanradar.mf.manual_ingest import stored_path_for
from dhanradar.models.mf import MfManualIngestFile
from dhanradar.tasks import manual_ingest as mi

pytestmark = pytest.mark.integration


def _build_hdfc_disclosure_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["Portfolio as on 30-June-2026"])
    ws.append(["HDFC Flexi Cap Fund"])
    ws.append(["Name of Instrument", "ISIN", "% to NAV", "Market Value"])
    ws.append(["HDFC Bank Ltd", "INE040A01034", "5.00", "1234.56"])
    ws.append(["Reliance Industries Ltd", "INE002A01018", "4.50", "1000.00"])
    ws.append(["Net Assets", "", "100.00", "24000.00"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def _insert_pending_row(
    db_session, *, filename: str, channel: str = "folder"
) -> tuple[str, bytes]:
    from dhanradar.mf.manual_ingest import sha256_bytes

    data = _build_hdfc_disclosure_xlsx()
    file_id = uuid.uuid4()
    db_session.add(
        MfManualIngestFile(
            id=file_id,
            sha256=sha256_bytes(data),
            original_filename=filename,
            channel=channel,
            status="pending",
        )
    )
    await db_session.commit()
    return str(file_id), data


@pytest.fixture(autouse=True)
def _tmp_store(monkeypatch: pytest.MonkeyPatch, tmp_path):
    from dhanradar.config import settings

    monkeypatch.setattr(settings, "MANUAL_INGEST_DIR", str(tmp_path))


async def test_parse_pipeline_parses_real_xlsx_and_marks_row_parsed(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    file_id, data = await _insert_pending_row(db_session, filename="HDFC_June2026.xlsx")
    stored_path_for(file_id, "HDFC_June2026.xlsx").write_bytes(data)

    captured: dict = {}

    async def _fake_upsert(rows, amc_name, run_id=None):
        captured["rows"] = rows
        captured["amc_name"] = amc_name
        captured["run_id"] = run_id
        return len(rows), 1  # (rows_upserted, aum_updates)

    monkeypatch.setattr("dhanradar.tasks.mf._upsert_constituents", _fake_upsert)

    result = await mi._parse_pipeline(file_id)

    assert result.startswith("parsed:")
    assert captured["amc_name"] == "HDFC"
    assert len(captured["rows"]) == 3  # 2 holdings + 1 total row — real parser output
    assert captured["run_id"] is not None  # ingestion_run() provenance threaded through

    # _parse_pipeline wrote via a DIFFERENT session (TaskSessionLocal) — this
    # session's identity map still holds the pre-parse object (expire_on_commit=
    # False), so it must be told to re-read from the DB rather than serve a cache hit.
    db_session.expire_all()
    row = await db_session.get(MfManualIngestFile, uuid.UUID(file_id))
    assert row.status == "parsed"
    assert row.amc_detected == "HDFC"
    assert row.rows_ingested == 3
    assert row.period_detected is not None
    assert row.parsed_at is not None


async def test_parse_pipeline_amc_undetectable_marks_unsupported(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    """A scheme name that names no known AMC → 'unsupported', never a guess, and
    _upsert_constituents is never called (nothing to route through)."""
    from dhanradar.mf.manual_ingest import sha256_bytes

    wb = Workbook()
    ws = wb.active
    ws.append(["Portfolio as on 30-June-2026"])
    ws.append(["XYZ Multi Cap Fund"])
    ws.append(["Name of Instrument", "ISIN", "% to NAV", "Market Value"])
    ws.append(["Some Stock Ltd", "INE999Z99999", "5.00", "100.00"])
    buf = io.BytesIO()
    wb.save(buf)
    data = buf.getvalue()

    file_id = uuid.uuid4()
    db_session.add(
        MfManualIngestFile(
            id=file_id,
            sha256=sha256_bytes(data),
            original_filename="unknown_amc.xlsx",
            channel="folder",
            status="pending",
        )
    )
    await db_session.commit()
    stored_path_for(str(file_id), "unknown_amc.xlsx").write_bytes(data)

    def _boom(*_a, **_kw):
        raise AssertionError("_upsert_constituents must never run for an undetectable AMC")

    monkeypatch.setattr("dhanradar.tasks.mf._upsert_constituents", _boom)

    result = await mi._parse_pipeline(str(file_id))

    assert result.startswith("unsupported:")
    db_session.expire_all()
    row = await db_session.get(MfManualIngestFile, file_id)
    assert row.status == "unsupported"
    assert row.error == "amc_or_period_undetectable"
    assert row.amc_detected is None


async def test_parse_pipeline_missing_stored_file_marks_failed(db_session):
    """The DB row exists but the on-disk file is gone (e.g. a manual delete) —
    fail closed, never crash silently."""
    file_id = uuid.uuid4()
    db_session.add(
        MfManualIngestFile(
            id=file_id,
            sha256="deadbeef" * 8,
            original_filename="missing.xlsx",
            channel="folder",
            status="pending",
        )
    )
    await db_session.commit()

    result = await mi._parse_pipeline(str(file_id))

    assert result == "failed: stored_file_missing"
    db_session.expire_all()
    row = await db_session.get(MfManualIngestFile, file_id)
    assert row.status == "failed"
    assert row.error == "stored_file_missing"


async def test_parse_pipeline_skips_already_terminal_row(db_session):
    """Idempotency guard: a re-enqueued/duplicate task run must never re-parse a
    row that already reached a terminal status."""
    file_id = uuid.uuid4()
    db_session.add(
        MfManualIngestFile(
            id=file_id,
            sha256="alreadydone" * 6,
            original_filename="already_parsed.xlsx",
            channel="folder",
            status="parsed",
            rows_ingested=5,
        )
    )
    await db_session.commit()

    result = await mi._parse_pipeline(str(file_id))
    assert result == "skip:parsed"
