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


def assemble_report(
    *,
    job_id: str,
    status: str,
    snapshot: Optional[dict],
    funds: list[dict],
    model_version: Optional[str] = None,
    generated_at: Optional[str] = None,
    disclaimer_version: Optional[str] = None,
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
        model_version=model_version,
        generated_at=generated_at,
        disclosure=DISCLOSURE_BUNDLE,
        not_advice=NOT_ADVICE,
        disclaimer_version=disclaimer_version or DISCLAIMER_VERSION,
    )
