"""
DhanRadar — Mutual Fund API router (Phase 5, architecture Tier-C MF Module).

Endpoints (all under /api/v1):
  POST /mf/upload/cas       (authed + mf_analytics consent) — enqueue CAS parse
  GET  /mf/cas/{job}/status (authed, own job) — poll progress
  GET  /mf/report/{job}     (authed, own job) — labelled report (disclaimer-injected)

DPDP (B20): the CAS upload is a data-processing route handling financial PII, so
it is gated by RequireConsent("mf_analytics") — fail-closed 403 without consent.
Auth is checked first (401), then consent (403). IDOR: status/report are scoped to
the caller's own job. The raw CAS file is purged after parse (+ a 24h backstop).
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.db import get_db
from dhanradar.deps import RequireConsent, UserContext, current_user_or_anonymous
from dhanradar.mf import service
from dhanradar.mf.schemas import CasJobStatus, CasUploadResponse, PortfolioReport
from dhanradar.models.mf import MfCasJob
from dhanradar.ratelimit import RateLimit
from dhanradar.redis_client import get_redis

router = APIRouter(prefix="/mf", tags=["mutual-fund"])

_MAX_CAS_BYTES = 15 * 1024 * 1024  # 15 MB cap on the upload
_rl_upload = RateLimit(max_requests=10, window_seconds=60)
_require_mf_consent = RequireConsent("mf_analytics")  # B20 — DPDP data-processing gate


def _upload_dir() -> str:
    d = os.path.join(tempfile.gettempdir(), "dhanradar_cas")
    os.makedirs(d, exist_ok=True)
    return d


@router.post("/upload/cas", response_model=CasUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_cas(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    file: Annotated[UploadFile, File()],
    password: Annotated[Optional[str], Form()] = None,
    _rl: Annotated[None, Depends(_rl_upload)] = None,
) -> CasUploadResponse:
    # 1. Auth (401) BEFORE consent (403).
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    # 2. DPDP consent gate (B20) — fail-closed.
    await _require_mf_consent(user, db)

    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty_file")
    if len(data) > _MAX_CAS_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file_too_large")

    redis = get_redis()
    source_hash = service.cas_sha256(data)

    # 3. SHA-256 dedup — re-upload of the same statement returns the existing job.
    existing = await service.dedup_lookup(redis, source_hash)
    if existing:
        return CasUploadResponse(job_id=existing, deduped=True)

    # 4. Persist the raw file for the worker (purged after parse + 24h backstop),
    #    create the job row queued, enqueue, return < 200ms.
    job_id = str(uuid.uuid4())
    path = os.path.join(_upload_dir(), f"{job_id}.pdf")
    with open(path, "wb") as fh:
        fh.write(data)

    db.add(MfCasJob(job_id=uuid.UUID(job_id), user_id=uuid.UUID(user.user_id),
                    status="queued", progress_pct=0, source_hash=source_hash))
    await db.commit()
    await service.dedup_record(redis, source_hash, job_id)

    from dhanradar.tasks.mf import parse_cas_job

    parse_cas_job.delay(job_id, path, password, user.user_id)
    return CasUploadResponse(job_id=job_id, estimated_seconds=60)


@router.get("/cas/{job_id}/status", response_model=CasJobStatus)
async def cas_status(
    job_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
) -> CasJobStatus:
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    job = await _own_job(db, job_id, user.user_id)
    return CasJobStatus(
        job_id=str(job.job_id),
        status=job.status,
        progress_pct=job.progress_pct,
        error_message=job.error_message,
    )


@router.get("/report/{job_id}", response_model=PortfolioReport)
async def cas_report(
    job_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
) -> PortfolioReport:
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    job = await _own_job(db, job_id, user.user_id)  # IDOR guard
    redis = get_redis()
    cached = await redis.get(f"{service._REPORT_PREFIX}{job_id}")
    if cached:
        payload = json.loads(cached)
        return service.assemble_report(**payload)
    if job.status != "done":
        # Not ready yet — return the current status with the disclosure injected.
        return service.assemble_report(job_id=job_id, status=job.status, snapshot=None, funds=[])
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report_expired")


async def _own_job(db: AsyncSession, job_id: str, user_id: str) -> MfCasJob:
    try:
        jid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
    job = await db.scalar(
        select(MfCasJob).where(MfCasJob.job_id == jid, MfCasJob.user_id == uuid.UUID(user_id))
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
    return job
