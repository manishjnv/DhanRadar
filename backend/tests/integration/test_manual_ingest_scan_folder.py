"""
Integration tests for the manual disclosure inbox watched-folder scan
(dhanradar/tasks/manual_ingest.py::scan_incoming_folder / _scan_incoming_pipeline)
— Channel B. Covers per-AMC subfolders (contract §3) and zip intake (contract §1)
at the folder-scan layer.

`detect_amc_and_parse`'s amc_hint FALLBACK-MATCHING logic (filename/content
first, hint last, unknown hint ignored) is unit-tested directly in
tests/unit/test_manual_ingest_service.py (pure, no DB needed) — these tests
instead prove the folder scanner correctly DERIVES the hint from a subfolder
name and THREADS it all the way to the parse-task enqueue call.
"""

from __future__ import annotations

import io
import uuid
import zipfile

import pytest

from dhanradar.tasks import manual_ingest as mi

pytestmark = pytest.mark.integration


@pytest.fixture()
def _captured_delay(monkeypatch: pytest.MonkeyPatch, tmp_path, db_session):
    """Never touch the Celery broker — capture (file_id, amc_hint) instead of
    enqueueing, and point MANUAL_INGEST_DIR at a per-test tmp dir so these
    tests never write into a real data/manual_ingest on disk."""
    from dhanradar.config import settings

    calls: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        mi.parse_manual_disclosure_file,
        "delay",
        lambda file_id, amc_hint=None: calls.append((file_id, amc_hint)),
    )
    monkeypatch.setattr(settings, "MANUAL_INGEST_DIR", str(tmp_path))
    return calls


def _incoming(tmp_path):
    d = tmp_path / "incoming"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Per-AMC subfolders (contract §3)
# ---------------------------------------------------------------------------


async def test_top_level_file_gets_no_amc_hint(tmp_path, _captured_delay):
    incoming = _incoming(tmp_path)
    (incoming / "generic_disclosure.xlsx").write_bytes(b"fake-xlsx-bytes-top-level")

    result = await mi._scan_incoming_pipeline()

    assert "ok=1" in result
    assert len(_captured_delay) == 1
    file_id, amc_hint = _captured_delay[0]
    uuid.UUID(file_id)  # a real uuid was enqueued
    assert amc_hint is None
    assert (tmp_path / "processed" / "generic_disclosure.xlsx").exists()


async def test_subfolder_file_gets_amc_hint_from_folder_name(tmp_path, _captured_delay):
    incoming = _incoming(tmp_path)
    sub = incoming / "HDFC"
    sub.mkdir()
    (sub / "generic_disclosure.xlsx").write_bytes(b"fake-xlsx-bytes-subfolder")

    result = await mi._scan_incoming_pipeline()

    assert "ok=1" in result
    assert len(_captured_delay) == 1
    _file_id, amc_hint = _captured_delay[0]
    assert amc_hint == "HDFC"
    # Flat processed/ dir — the HDFC/ subfolder structure is never mirrored.
    assert (tmp_path / "processed" / "generic_disclosure.xlsx").exists()
    assert not (tmp_path / "processed" / "HDFC").exists()


async def test_unknown_subfolder_name_still_processes_the_file(tmp_path, _captured_delay):
    """An unrecognized folder name is passed through as the hint verbatim —
    `detect_amc_and_parse` (unit-tested separately) is what ignores it with a
    log line; the scanner's job is only to still PROCESS the file, never skip
    it just because the folder name is unfamiliar."""
    incoming = _incoming(tmp_path)
    sub = incoming / "SomeUnknownFundHouse"
    sub.mkdir()
    (sub / "generic_disclosure.xlsx").write_bytes(b"fake-xlsx-bytes-unknown-folder")

    result = await mi._scan_incoming_pipeline()

    assert "ok=1" in result
    _file_id, amc_hint = _captured_delay[0]
    assert amc_hint == "SomeUnknownFundHouse"  # passed through, not swallowed


async def test_subfolder_scanning_is_only_one_level_deep(tmp_path, _captured_delay):
    """A nested sub-subfolder is never scanned (contract §3 — one level only)."""
    incoming = _incoming(tmp_path)
    nested = incoming / "HDFC" / "2026"
    nested.mkdir(parents=True)
    (nested / "buried.xlsx").write_bytes(b"never-seen")

    result = await mi._scan_incoming_pipeline()

    assert "ok=0" in result
    assert _captured_delay == []
    assert (nested / "buried.xlsx").exists()  # left untouched, never moved


# ---------------------------------------------------------------------------
# ZIP intake at the folder-scan layer (contract §1)
# ---------------------------------------------------------------------------


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


async def test_zip_expands_and_moves_to_processed(tmp_path, _captured_delay):
    incoming = _incoming(tmp_path)
    (incoming / "bundle.zip").write_bytes(
        _zip_bytes({"HDFC_June2026.xlsx": b"member-a-bytes", "notes.txt": b"not eligible"})
    )

    result = await mi._scan_incoming_pipeline()

    assert "ok=1" in result
    assert "zip_skipped=1" in result
    assert len(_captured_delay) == 1
    assert (tmp_path / "processed" / "bundle.zip").exists()


async def test_zip_with_zero_eligible_members_moves_to_failed_and_logs_unsupported(
    tmp_path, _captured_delay, caplog
):
    import logging

    incoming = _incoming(tmp_path)
    (incoming / "empty.zip").write_bytes(_zip_bytes({"notes.txt": b"not eligible"}))

    caplog.set_level(logging.INFO, logger="dhanradar.tasks.manual_ingest")
    result = await mi._scan_incoming_pipeline()

    assert "ok=0" in result
    assert _captured_delay == []
    assert (tmp_path / "failed" / "empty.zip").exists()
    assert any("unsupported" in rec.message for rec in caplog.records)


async def test_zip_in_amc_subfolder_gets_amc_hint(tmp_path, _captured_delay):
    incoming = _incoming(tmp_path)
    sub = incoming / "SBI"
    sub.mkdir()
    (sub / "bundle.zip").write_bytes(_zip_bytes({"generic.xlsx": b"member-bytes"}))

    result = await mi._scan_incoming_pipeline()

    assert "ok=1" in result
    _file_id, amc_hint = _captured_delay[0]
    assert amc_hint == "SBI"
