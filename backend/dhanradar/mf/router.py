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
from dhanradar.deps import RequireConsent, UserContext, current_user_or_anonymous, is_plus
from dhanradar.mf import history as mf_history
from dhanradar.mf import service
from dhanradar.mf.schemas import (
    CasJobStatus,
    CasUploadResponse,
    PortfolioHistoryResponse,
    PortfolioReport,
    SnapshotHistoryItem,
)
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
    # 1. Auth (401) BEFORE consent (403). The consent gate is invoked explicitly
    #    (keyword args) to preserve the 401-then-403 ordering; it is the same
    #    fail-closed RequireConsent used as a Depends elsewhere.
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    # 2. DPDP consent gate (B20) — fail-closed.
    await _require_mf_consent(user=user, db=db)

    # 3. Bounded read (cap memory at ~15MB+1 — never buffer an unbounded body).
    data = await file.read(_MAX_CAS_BYTES + 1)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty_file")
    if len(data) > _MAX_CAS_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file_too_large")
    if not data.startswith(b"%PDF-"):  # magic-byte check before touching disk
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_pdf")

    redis = get_redis()
    source_hash = service.cas_sha256(data)

    # 4. Per-USER SHA-256 dedup — re-upload of the same statement returns the
    #    existing job; another user's identical bytes get an independent job.
    existing = await service.dedup_lookup(redis, user.user_id, source_hash)
    if existing:
        return CasUploadResponse(job_id=existing, deduped=True)

    # 5. Persist the raw file for the worker (purged after parse + 24h backstop),
    #    create the job row queued, enqueue, return < 200ms.
    job_id = str(uuid.uuid4())
    path = os.path.join(_upload_dir(), f"{job_id}.pdf")
    with open(path, "wb") as fh:
        fh.write(data)

    db.add(MfCasJob(job_id=uuid.UUID(job_id), user_id=uuid.UUID(user.user_id),
                    status="queued", progress_pct=0, source_hash=source_hash))
    await db.commit()
    await service.dedup_record(redis, user.user_id, source_hash, job_id)

    # 6. Keep the CAS password OFF the Celery broker — stash it in a short-lived
    #    Redis key the worker consumes-and-deletes (never serialized into a task arg).
    if password:
        await redis.set(f"mf:cas:pw:{job_id}", password, ex=600)

    from dhanradar.tasks.mf import parse_cas_job

    parse_cas_job.delay(job_id, path, user.user_id)
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


@router.get("/history", response_model=PortfolioHistoryResponse)
async def portfolio_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
) -> PortfolioHistoryResponse:
    """Return Plus users' label history grouped by snapshot date.

    Gating order: 401 (anonymous) → 402 (not Plus) → 403 (no consent).
    No numeric fields in the response (non-neg #2).
    """
    from dhanradar.scoring.engine.schemas import (
        DISCLAIMER_VERSION,
        DISCLOSURE_BUNDLE,
        NOT_ADVICE,
    )

    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    if not await is_plus(user.user_id, db):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"error": "upgrade_required", "upgrade_url": "/pricing"},
        )
    await _require_mf_consent(user=user, db=db)

    raw = await mf_history.get_snapshot_history(db, user.user_id)
    snapshots = [
        SnapshotHistoryItem(snapshot_date=item["snapshot_date"], funds=item["funds"])
        for item in raw
    ]
    return PortfolioHistoryResponse(
        snapshots=snapshots,
        disclosure=DISCLOSURE_BUNDLE,
        not_advice=NOT_ADVICE,
        disclaimer_version=DISCLAIMER_VERSION,
    )


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
