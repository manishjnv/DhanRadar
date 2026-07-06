"""
Integration tests for the shared manual-ingest intake service
(dhanradar/mf/manual_ingest.py::intake_file) — the ONE function all 3 channels
(upload/folder/email) call. Needs a real DB (TaskSessionLocal writes
mf.manual_ingest_files) — covers what the route tests can't reach directly:
channel='folder'/'email' behavior (no HTTP layer), and the on-disk file write.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from dhanradar.mf.manual_ingest import intake_file, stored_path_for
from dhanradar.models.mf import MfManualIngestFile

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch: pytest.MonkeyPatch, tmp_path, db_session):
    """Never touch the Celery broker; point MANUAL_INGEST_DIR at a per-test tmp dir
    so these tests never write into a real data/manual_ingest on disk."""
    from dhanradar.config import settings
    from dhanradar.tasks.manual_ingest import parse_manual_disclosure_file

    monkeypatch.setattr(parse_manual_disclosure_file, "delay", lambda *a, **kw: None)
    monkeypatch.setattr(settings, "MANUAL_INGEST_DIR", str(tmp_path))


async def test_intake_file_folder_channel_persists_row_and_bytes(db_session):
    result = await intake_file(b"fake-xlsx-bytes", "HDFC_disclosure.xlsx", "folder", None)
    assert result.status == "pending"
    assert result.file_id is not None

    row = await db_session.get(MfManualIngestFile, uuid.UUID(result.file_id))
    assert row is not None
    assert row.channel == "folder"
    assert row.original_filename == "HDFC_disclosure.xlsx"
    assert row.status == "pending"
    assert row.uploaded_by is None

    path = stored_path_for(result.file_id, "HDFC_disclosure.xlsx")
    assert path.exists()
    assert path.read_bytes() == b"fake-xlsx-bytes"


async def test_intake_file_email_channel_no_uploader(db_session):
    result = await intake_file(b"email-bytes", "SBI_disclosure.xls", "email", None)
    row = await db_session.get(MfManualIngestFile, uuid.UUID(result.file_id))
    assert row.channel == "email"
    assert row.uploaded_by is None


async def test_intake_file_dedup_returns_existing_id_and_writes_nothing_new(db_session):
    first = await intake_file(b"same-bytes-twice", "AXIS_disclosure.xlsx", "folder", None)
    assert first.status == "pending"

    count_before = await db_session.scalar(
        select(MfManualIngestFile.id).where(MfManualIngestFile.sha256.isnot(None))
    )
    assert count_before is not None

    second = await intake_file(b"same-bytes-twice", "AXIS_disclosure_reupload.xlsx", "email", None)
    assert second.status == "duplicate"
    assert second.file_id == first.file_id


async def test_intake_file_rejects_bad_extension(db_session):
    result = await intake_file(b"not-really-a-doc", "notes.txt", "folder", None)
    assert result.status == "unsupported"
    assert result.error is not None
    assert "unsupported_extension" in result.error
    assert result.file_id is None


async def test_intake_file_rejects_oversized(db_session):
    from dhanradar.mf.manual_ingest import MAX_BYTES

    result = await intake_file(b"0" * (MAX_BYTES + 1), "huge.xlsx", "folder", None)
    assert result.status == "unsupported"
    assert result.error == "file_too_large"


async def test_intake_file_rejects_empty_bytes(db_session):
    result = await intake_file(b"", "empty.xlsx", "folder", None)
    assert result.status == "unsupported"
    assert result.error == "empty_file"


async def test_intake_file_upload_channel_stores_uploader(db_session, async_client):
    # uploaded_by FKs to auth.users.id — needs a REAL row, not an arbitrary UUID.
    from tests.conftest import extract_cookie

    r = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": "manual_ingest_uploader@example.com", "password": "ManualIngest42!"},
    )
    assert r.status_code in (200, 201), r.text
    user_id = str(r.json()["user"]["id"])
    extract_cookie(r, "__Host-access")  # not needed further; signup itself is enough

    result = await intake_file(b"admin-upload-bytes", "KOTAK_disclosure.xlsx", "upload", user_id)
    row = await db_session.get(MfManualIngestFile, uuid.UUID(result.file_id))
    assert row.channel == "upload"
    assert str(row.uploaded_by) == user_id
