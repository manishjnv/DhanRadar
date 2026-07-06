"""
Integration tests for the manual disclosure inbox admin router
(admin/manual_ingest_router.py — Channel A: admin multipart upload).

Covers:
  - 404 surface-hiding for anonymous callers (mirrors admin/ops_router.py's
    RequireAdmin exactly — anon AND authenticated non-admin both get 404, never
    401/403; see dhanradar.deps.RequireAdmin's docstring).
  - 404 surface-hiding for authenticated non-admins.
  - Happy path: admin upload → 200, per-file result with status='pending'.
  - Dedup: uploading the identical bytes twice → second result status='duplicate'.
  - Bad extension → 422 (whole request rejected pre-flight).
  - Size cap exceeded → 413 (whole request rejected pre-flight).
  - GET /admin/ingest/disclosure-files → recent rows, admin-only.

`parse_manual_disclosure_file.delay()` is monkeypatched to a no-op throughout —
these tests exercise the route + intake service only, not the Celery broker
(mirrors the documented convention in test_admin_ops.py: routes that enqueue a
real task are not driven through a live broker in this suite).
"""

from __future__ import annotations

import io

import pytest

pytestmark = pytest.mark.integration

_XLSX_BYTES = b"PK\x03\x04fake-xlsx-content-not-a-real-workbook"


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch: pytest.MonkeyPatch):
    """Never touch the Celery broker in route tests — intake_file() enqueues
    parse_manual_disclosure_file.delay() as its last step."""
    from dhanradar.tasks.manual_ingest import parse_manual_disclosure_file

    monkeypatch.setattr(parse_manual_disclosure_file, "delay", lambda *a, **kw: None)


async def _signup(client, email: str) -> tuple[str, str]:
    from tests.conftest import extract_cookie

    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "ManualIngest42!"},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["user"]["id"]), extract_cookie(r, "__Host-access")


def _one_file(name: str = "HDFC_disclosure.xlsx", data: bytes = _XLSX_BYTES):
    return [
        (
            "files",
            (name, io.BytesIO(data), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        )
    ]


# ---------------------------------------------------------------------------
# 1. 404 for anonymous callers
# ---------------------------------------------------------------------------


async def test_endpoints_404_for_anonymous(async_client):
    r = await async_client.get("/api/v1/admin/ingest/disclosure-files")
    assert r.status_code == 404, r.text

    r = await async_client.post("/api/v1/admin/ingest/disclosure-files", files=_one_file())
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 2. 404 for authenticated non-admins
# ---------------------------------------------------------------------------


async def test_endpoints_404_for_non_admin(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")

    _uid, access = await _signup(async_client, "nonadmin_ingest@example.com")
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/ingest/disclosure-files", headers=headers)
    assert r.status_code == 404, r.text

    r = await async_client.post(
        "/api/v1/admin/ingest/disclosure-files", files=_one_file(), headers=headers
    )
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 3. Happy path — admin upload
# ---------------------------------------------------------------------------


async def test_admin_upload_happy_path(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, access = await _signup(async_client, "admin_ingest_ok@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.post(
        "/api/v1/admin/ingest/disclosure-files",
        files=_one_file(name="HDFC_June2026.xlsx", data=_XLSX_BYTES),
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["results"]) == 1
    result = body["results"][0]
    assert result["filename"] == "HDFC_June2026.xlsx"
    assert result["status"] == "pending"
    assert result["file_id"] is not None


# ---------------------------------------------------------------------------
# 4. Dedup — same bytes uploaded twice
# ---------------------------------------------------------------------------


async def test_admin_upload_dedup_second_upload_is_duplicate(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, access = await _signup(async_client, "admin_ingest_dedup@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=access)

    data = _XLSX_BYTES + b"-unique-marker-for-this-test"

    r1 = await async_client.post(
        "/api/v1/admin/ingest/disclosure-files",
        files=_one_file(name="SBI_July2026.xlsx", data=data),
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["results"][0]["status"] == "pending"
    first_file_id = r1.json()["results"][0]["file_id"]

    # Re-upload the SAME bytes (even under a different filename) — dedup keys on sha256.
    r2 = await async_client.post(
        "/api/v1/admin/ingest/disclosure-files",
        files=_one_file(name="SBI_July2026_copy.xlsx", data=data),
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    result2 = r2.json()["results"][0]
    assert result2["status"] == "duplicate"
    assert result2["file_id"] == first_file_id


# ---------------------------------------------------------------------------
# 5. Bad extension → 422 (whole request rejected pre-flight)
# ---------------------------------------------------------------------------


async def test_admin_upload_bad_extension_returns_422(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, access = await _signup(async_client, "admin_ingest_badext@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.post(
        "/api/v1/admin/ingest/disclosure-files",
        files=[("files", ("disclosure.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf"))],
        headers=headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["detail"] == "unsupported_file_type"


# ---------------------------------------------------------------------------
# 6. Size cap exceeded → 413
# ---------------------------------------------------------------------------


async def test_admin_upload_size_cap_returns_413(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, access = await _signup(async_client, "admin_ingest_toobig@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=access)

    oversized = b"0" * (25 * 1024 * 1024 + 1)
    r = await async_client.post(
        "/api/v1/admin/ingest/disclosure-files",
        files=[
            (
                "files",
                (
                    "huge.xlsx",
                    io.BytesIO(oversized),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )
        ],
        headers=headers,
    )
    assert r.status_code == 413, r.text


# ---------------------------------------------------------------------------
# 7. GET recent files
# ---------------------------------------------------------------------------


async def test_get_recent_files_returns_uploaded_row(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    admin_id, access = await _signup(async_client, "admin_ingest_list@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    headers = make_auth_headers(access_token=access)

    await async_client.post(
        "/api/v1/admin/ingest/disclosure-files",
        files=_one_file(name="AXIS_Aug2026.xlsx", data=_XLSX_BYTES + b"-axis-marker"),
        headers=headers,
    )

    r = await async_client.get("/api/v1/admin/ingest/disclosure-files?limit=10", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert any(row["original_filename"] == "AXIS_Aug2026.xlsx" for row in rows)
    row = next(row for row in rows if row["original_filename"] == "AXIS_Aug2026.xlsx")
    assert row["channel"] == "upload"
    assert row["status"] == "pending"
