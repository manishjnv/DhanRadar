"""
DhanRadar — Admin manual disclosure inbox router (Channel A: admin upload).

Manual-ingest side-channel for the 5 AMCs `mf_constituents_fetch` cannot
scrape (HDFC/SBI/ICICI-Pru/Kotak/Axis bot-block — ADR-0033(a)). This router
owns Channel A only (multipart upload + the recent-files read); Channels B
(watched folder) and C (email poller) are Celery beat tasks
(tasks/manual_ingest.py) that call the SAME shared intake service
(mf/manual_ingest.py::intake_file) — one pipeline, three doors in.

Auth: RequireAdmin() — mirrors admin/ops_router.py exactly (404 surface-hiding
for anon AND authenticated non-admin; see deps.RequireAdmin's docstring).

Untrusted input: extension + size are validated HERE (pre-flight, whole-batch
reject: 422 for a disallowed extension, 413 for oversized) so a structurally
bad request never reaches the DB; intake_file() re-validates independently
(defense in depth, and the only validation Channels B/C ever get, since they
have no HTTP layer to 422/413 against).

A `.zip` gets the SAME whole-batch-reject treatment: it is opened + expanded
(`expand_zip()`) during the SAME pre-flight loop (before anything is
persisted) — an entirely-ineligible zip (0 eligible members) 422s the whole
request exactly like a disallowed-extension file, never partially uploading
some good files first.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.audit.service import record_admin_action
from dhanradar.db import get_admin_db
from dhanradar.deps import RequireAdmin, UserContext
from dhanradar.mf.manual_ingest import (
    ALLOWED_EXTENSIONS,
    MAX_BYTES,
    MAX_ZIP_TOTAL_BYTES,
    ZIP_EXTENSION,
    ZipExpansion,
    expand_zip,
    intake_file,
)
from dhanradar.models.mf import MfManualIngestFile

from .manual_ingest_schemas import (
    ManualIngestFileRow,
    SkippedFileResult,
    UploadBatchResponse,
    UploadFileResult,
)

router = APIRouter(prefix="/admin/ingest", tags=["admin-manual-ingest"])

_MAX_FILES_PER_REQUEST = 10


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


# ---------------------------------------------------------------------------
# POST /admin/ingest/disclosure-files — multipart upload, ≤10 files/request
# ---------------------------------------------------------------------------


@router.post("/disclosure-files", response_model=UploadBatchResponse)
async def upload_disclosure_files(
    request: Request,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    files: Annotated[list[UploadFile], File()],
) -> UploadBatchResponse:
    """Upload up to 10 disclosure files (or .zip bundles of them) at once.
    Pre-flight validates EVERY file's extension + size — and, for a .zip,
    expands it in memory and requires ≥1 eligible member — before anything is
    persisted: a single bad file (or an entirely-ineligible zip) 422/413s the
    whole request rather than silently dropping it inside a 200 batch response."""
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no_files")
    if len(files) > _MAX_FILES_PER_REQUEST:
        raise HTTPException(status_code=422, detail="too_many_files")

    read: list[tuple[str, bytes]] = []
    zip_expansions: list[ZipExpansion] = []
    for f in files:
        filename = f.filename or "unnamed"
        ext = Path(filename).suffix.lower()
        if ext == ZIP_EXTENSION:
            data = await f.read(MAX_ZIP_TOTAL_BYTES + 1)
            if len(data) > MAX_ZIP_TOTAL_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file_too_large"
                )
            expansion = expand_zip(data, filename)
            if not expansion.eligible:
                raise HTTPException(status_code=422, detail="zip_no_eligible_members")
            zip_expansions.append(expansion)
            continue
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=422, detail="unsupported_file_type")
        data = await f.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file_too_large"
            )
        read.append((filename, data))

    # Nothing above touched the DB or disk — only now do we persist.
    results: list[UploadFileResult] = []
    skipped: list[SkippedFileResult] = []
    for filename, data in read:
        r = await intake_file(data, filename, "upload", admin.user_id)
        results.append(UploadFileResult(filename=filename, file_id=r.file_id, status=r.status))
    for expansion in zip_expansions:
        for member_name, member_data in expansion.eligible:
            r = await intake_file(member_data, member_name, "upload", admin.user_id)
            results.append(
                UploadFileResult(filename=member_name, file_id=r.file_id, status=r.status)
            )
        for member_name, reason in expansion.skipped:
            skipped.append(SkippedFileResult(filename=member_name, reason=reason))

    await record_admin_action(
        admin_id=admin.user_id,
        action="upload_disclosure_files",
        target_type="manual_ingest",
        target_id=None,
        result=f"{len(results)}_files",
        request_id=getattr(request.state, "request_id", None),
    )
    return UploadBatchResponse(results=results, skipped=skipped)


# ---------------------------------------------------------------------------
# GET /admin/ingest/disclosure-files — recent rows for the admin UI table
# ---------------------------------------------------------------------------


@router.get("/disclosure-files", response_model=list[ManualIngestFileRow])
async def list_disclosure_files(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_admin_db)],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ManualIngestFileRow]:
    rows = (
        await db.scalars(
            select(MfManualIngestFile).order_by(MfManualIngestFile.received_at.desc()).limit(limit)
        )
    ).all()
    return [
        ManualIngestFileRow(
            id=str(r.id),
            original_filename=r.original_filename,
            channel=r.channel,
            status=r.status,
            amc_detected=r.amc_detected,
            period_detected=r.period_detected.isoformat() if r.period_detected else None,
            rows_ingested=r.rows_ingested,
            error=r.error,
            received_at=_iso(r.received_at) or "",
            parsed_at=_iso(r.parsed_at),
        )
        for r in rows
    ]
