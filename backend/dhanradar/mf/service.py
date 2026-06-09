"""
DhanRadar — MF service: CAS dedup, job lifecycle, report assembly (Phase 5).

Owns the non-pipeline glue:
  * `cas_sha256` + Redis dedup (`mf:cas:dedup:{hash}` → job_id) so re-uploading the
    same statement returns the existing job rather than reprocessing.
  * report assembly that injects the SEBI disclosure bundle at serialization
    (anti-pattern guard) and NEVER emits the unified_score numeric (non-neg #2).
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional

from dhanradar.mf.schemas import FundReportItem, PortfolioReport
from dhanradar.scoring.engine.schemas import (
    DISCLAIMER_VERSION,
    DISCLOSURE_BUNDLE,
    NOT_ADVICE,
)

_DEDUP_PREFIX = "mf:cas:dedup:"
_DEDUP_TTL = 24 * 3600  # match the 24h raw-file purge window
_REPORT_PREFIX = "mf:report:"
_REPORT_TTL = 2 * 3600  # cache the assembled report 2h (architecture)


def cas_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dedup_key(user_id: str, portfolio_id: str, source_hash: str) -> str:
    """Dedup is scoped per (user, portfolio) — two users uploading the same CAS bytes
    get INDEPENDENT jobs, so one user can never receive another's job_id (a financial
    co-relationship leak). Re-upload of one's own statement still dedups."""
    return f"{_DEDUP_PREFIX}{user_id}:{portfolio_id}:{source_hash}"


async def dedup_lookup(redis: Any, user_id: str, portfolio_id: str, source_hash: str) -> Optional[str]:
    """Return an existing job_id for this (user, portfolio, CAS hash), or None."""
    return await redis.get(dedup_key(user_id, portfolio_id, source_hash))


async def dedup_record(redis: Any, user_id: str, portfolio_id: str, source_hash: str, job_id: str) -> None:
    await redis.set(dedup_key(user_id, portfolio_id, source_hash), job_id, ex=_DEDUP_TTL)


async def dedup_clear(redis: Any, user_id: str, portfolio_id: str, source_hash: str) -> None:
    """Drop a stale dedup record so a re-upload reprocesses. Used when the prior
    job for this statement did NOT complete successfully (failed / stuck), OR when
    it succeeded but its assembled report has since expired from the cache."""
    await redis.delete(dedup_key(user_id, portfolio_id, source_hash))


async def can_return_existing(redis: Any, prior_status: Optional[str], job_id: str) -> bool:
    """Whether a re-upload may short-circuit (dedup) to an existing job.

    Returns True ONLY when the prior job COMPLETED *and* its assembled report is
    still in the cache. The dedup key lives `_DEDUP_TTL` (24h) but the report cache
    only `_REPORT_TTL` (2h); in that 22h gap a done job's report has expired, so
    short-circuiting to it bounces the user to a GET /report 404 ('report_expired')
    — the very 'dead job' failure the dedup self-heal exists to prevent. A non-done
    status (failed/stuck/None) or a missing report both fall through to reprocess
    the freshly-uploaded bytes."""
    if prior_status != "done":
        return False
    return bool(await redis.exists(f"{_REPORT_PREFIX}{job_id}"))


def assemble_report(
    *,
    job_id: str,
    status: str,
    snapshot: Optional[dict],
    funds: list[dict],
    model_version: Optional[str] = None,
    generated_at: Optional[str] = None,
    disclaimer_version: Optional[str] = None,
    commentary: Optional[str] = None,
) -> PortfolioReport:
    """Build the client report. The disclosure bundle + NOT_ADVICE are ALWAYS
    injected here; `unified_score` is never included (each fund carries only
    verb_label + confidence_band)."""
    snap = snapshot or {}
    items = [
        FundReportItem(
            isin=f["isin"],
            scheme_name=f.get("scheme_name", ""),
            folio_number=f.get("folio_number", ""),
            units=f.get("units", 0.0),
            invested_amount=f.get("invested_amount"),
            current_value=f.get("current_value"),
            verb_label=f.get("verb_label"),
            confidence_band=f.get("confidence_band"),
            contributing_signals=f.get("contributing_signals", []),
            contradicting_signals=f.get("contradicting_signals", []),
        )
        for f in funds
    ]
    return PortfolioReport(
        job_id=job_id,
        status=status,
        total_invested=snap.get("total_invested"),
        current_value=snap.get("current_value"),
        xirr_pct=snap.get("xirr_pct"),
        category_allocation=snap.get("category_allocation", {}),
        overlap_matrix=snap.get("overlap_matrix", {}),
        funds=items,
        commentary=commentary,
        model_version=model_version,
        generated_at=generated_at,
        disclosure=DISCLOSURE_BUNDLE,
        not_advice=NOT_ADVICE,
        disclaimer_version=disclaimer_version or DISCLAIMER_VERSION,
    )
