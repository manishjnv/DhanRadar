"""
DhanRadar — Compliance Audit Celery tasks (architecture Global §4).

`archive_audit_daily` (beat 02:00 IST, batch queue): export the prior IST day's
`ai_recommendation_audit` rows to R2 for the 7-yr lifecycle. Best-effort — a
failure is logged and retried by the next run; it never blocks (the rows stay in
Postgres). Export format is gzipped JSONL (no heavy parquet/pyarrow dependency at
launch; the architecture's parquet target is a follow-on optimization). The 7-yr
R2 lifecycle itself is a bucket policy (infra), not code.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from dhanradar.celery_app import celery_app

logger = logging.getLogger(__name__)

_IST = ZoneInfo("Asia/Kolkata")
_ARCHIVE_PREFIX = "audit/"


@celery_app.task(name="dhanradar.tasks.compliance.archive_audit_daily")
def archive_audit_daily() -> str:
    """Export the prior IST day's audit rows to R2. Returns a short status string."""
    return asyncio.run(_archive())


async def _archive() -> str:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from dhanradar import storage
    from dhanradar.config import settings
    from dhanradar.db import engine
    from dhanradar.models.compliance import AiRecommendationAudit

    # DPDP / ADR-0022 fail-safe: do NOT export user_id-bearing audit rows to the
    # (currently cross-border) R2 bucket unless an India-resident archive is
    # explicitly enabled. The audit data remains in the India-resident Postgres.
    if not settings.AUDIT_ARCHIVE_ENABLED:
        return "audit archival disabled (AUDIT_ARCHIVE_ENABLED=false) — rows retained in Postgres only"

    # Prior IST calendar day → UTC bounds.
    now_ist = datetime.now(_IST)
    day_start_ist = (now_ist - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    day_end_ist = day_start_ist + timedelta(days=1)
    start_utc = day_start_ist.astimezone(timezone.utc)
    end_utc = day_end_ist.astimezone(timezone.utc)
    key = f"{_ARCHIVE_PREFIX}{day_start_ist:%Y/%m/%d}.jsonl.gz"

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with SessionLocal() as db:
        rows = (
            await db.scalars(
                select(AiRecommendationAudit)
                .where(
                    AiRecommendationAudit.served_at >= start_utc,
                    AiRecommendationAudit.served_at < end_utc,
                )
                .order_by(AiRecommendationAudit.served_at)
            )
        ).all()

    if not rows:
        return f"archive: 0 rows for {day_start_ist:%Y-%m-%d} (nothing to do)"

    lines = []
    for r in rows:
        lines.append(json.dumps({
            "id": str(r.id), "served_at": r.served_at.isoformat(),
            "user_id": str(r.user_id) if r.user_id else None,
            "recommendation_type": r.recommendation_type, "label": r.label,
            "content_hash": r.content_hash, "model": r.model,
            "prompt_version": r.prompt_version,
            "confidence_score": float(r.confidence_score) if r.confidence_score is not None else None,
            "confidence_band": r.confidence_band, "disclaimer_version": r.disclaimer_version,
            "surface": r.surface, "session_id": r.session_id, "request_id": r.request_id,
        }, separators=(",", ":")))
    blob = gzip.compress(("\n".join(lines) + "\n").encode("utf-8"))

    try:
        await asyncio.to_thread(storage.put_object, key, blob, "application/gzip")
    except storage.StorageNotConfigured:
        logger.warning("archive_audit_daily: R2 not configured; %d rows kept in PG only", len(rows))
        return f"archive: R2 unconfigured ({len(rows)} rows kept in PG)"
    except Exception:  # noqa: BLE001 — best-effort; rows remain in PG, next run retries
        logger.exception("archive_audit_daily: R2 upload failed for %s", key)
        return "archive: upload failed (rows kept in PG)"
    return f"archive: {len(rows)} rows → r2://{key}"


@celery_app.task(name="dhanradar.tasks.compliance.reconcile_audit_disclaimers")
def reconcile_audit_disclaimers() -> str:
    """Flag any audited disclaimer_version not present in the disclaimers registry.
    A served label tied to an unregistered disclaimer version is a compliance gap
    (the in-force-version tie is broken). Logs + emits a metric; returns status."""
    return asyncio.run(_reconcile_disclaimers())


async def _reconcile_disclaimers() -> str:
    from sqlalchemy import distinct, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from dhanradar.compliance.service import bump_audit_metric
    from dhanradar.db import engine
    from dhanradar.models.compliance import AiRecommendationAudit, Disclaimer

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with SessionLocal() as db:
        audited = set(
            (
                await db.scalars(
                    select(distinct(AiRecommendationAudit.disclaimer_version)).where(
                        AiRecommendationAudit.disclaimer_version.is_not(None)
                    )
                )
            ).all()
        )
        known = set((await db.scalars(select(distinct(Disclaimer.version)))).all())

    orphans = sorted(audited - known)
    if not orphans:
        return f"reconcile: OK — all {len(audited)} audited disclaimer_version(s) registered"
    logger.error(
        "compliance reconcile: %d audited disclaimer_version(s) NOT in the disclaimers "
        "registry (served labels tie to an unregistered disclaimer — compliance gap): %s",
        len(orphans),
        ", ".join(orphans),
    )
    await bump_audit_metric("audit_orphan_disclaimer_versions", len(orphans))
    return f"reconcile: {len(orphans)} ORPHAN disclaimer_version(s): {', '.join(orphans)}"
