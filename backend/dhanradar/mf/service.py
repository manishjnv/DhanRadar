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
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

from dhanradar.mf.schemas import FundReportItem, PortfolioReport
from dhanradar.scoring.engine.schemas import (
    DISCLAIMER_VERSION,
    DISCLOSURE_BUNDLE,
    NOT_ADVICE,
)

_DEDUP_PREFIX = "mf:cas:dedup:"
_DEDUP_TTL = 24 * 3600  # match the 24h raw-file purge window
_REPORT_PREFIX = "mf:report:"
_REPORT_TTL = 2 * 3600  # cache the assembled report 2h (fresh CAS upload)
_REBUILD_TTL = 25 * 3600  # rebuilt-from-DB report lives until next daily refresh
_LATEST_JOB_PREFIX = "mf:portfolio:latest_job:"  # portfolio_id → job_id


def cas_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dedup_key(user_id: str, portfolio_id: str, source_hash: str) -> str:
    """Dedup is scoped per (user, portfolio) — two users uploading the same CAS bytes
    get INDEPENDENT jobs, so one user can never receive another's job_id (a financial
    co-relationship leak). Re-upload of one's own statement still dedups."""
    return f"{_DEDUP_PREFIX}{user_id}:{portfolio_id}:{source_hash}"


async def dedup_lookup(redis: Any, user_id: str, portfolio_id: str, source_hash: str) -> str | None:
    """Return an existing job_id for this (user, portfolio, CAS hash), or None."""
    return await redis.get(dedup_key(user_id, portfolio_id, source_hash))


async def dedup_record(redis: Any, user_id: str, portfolio_id: str, source_hash: str, job_id: str) -> None:
    await redis.set(dedup_key(user_id, portfolio_id, source_hash), job_id, ex=_DEDUP_TTL)


async def dedup_clear(redis: Any, user_id: str, portfolio_id: str, source_hash: str) -> None:
    """Drop a stale dedup record so a re-upload reprocesses. Used when the prior
    job for this statement did NOT complete successfully (failed / stuck), OR when
    it succeeded but its assembled report has since expired from the cache."""
    await redis.delete(dedup_key(user_id, portfolio_id, source_hash))


async def can_return_existing(redis: Any, prior_status: str | None, job_id: str) -> bool:
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
    snapshot: dict | None,
    funds: list[dict],
    model_version: str | None = None,
    generated_at: str | None = None,
    disclaimer_version: str | None = None,
    commentary: dict | None = None,
    portfolio_id: str | None = None,
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
            previous_label=f.get("previous_label"),
            confidence_factors=f.get("confidence_factors"),
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
        portfolio_id=portfolio_id,
        disclosure=DISCLOSURE_BUNDLE,
        not_advice=NOT_ADVICE,
        disclaimer_version=disclaimer_version or DISCLAIMER_VERSION,
    )


async def rebuild_report_from_db(
    *,
    job_id: str,
    portfolio_id: str,
    redis: Any,
    db: Any,
) -> PortfolioReport | None:
    """Rebuild an expired report from stored holdings + today's NAV + stored scores.

    Called when GET /report/{job_id} misses the Redis cache.  The rebuilt report
    reflects current NAV so the user sees live portfolio value without re-uploading.

    Note: contributing/contradicting signals and confidence_factors are NOT stored in
    user_fund_scores — those fields will be empty in the rebuilt report.  Labels and
    confidence_band ARE stored and will appear correctly.
    """
    from sqlalchemy import select, text
    from uuid import UUID as _UUID

    from dhanradar.models.mf import (
        MfFund,
        MfPortfolioSnapshot,
        MfUserHolding,
        UserFundScore,
    )

    pid = _UUID(portfolio_id)

    # 1. Current holdings for this portfolio.
    holdings = (
        await db.execute(select(MfUserHolding).where(MfUserHolding.portfolio_id == pid))
    ).scalars().all()

    if not holdings:
        logger.warning("rebuild_report: no holdings for portfolio_id=%s", portfolio_id)
        return None

    isins = [h.isin for h in holdings]

    # 2. Latest NAV per ISIN — single query using DISTINCT ON.
    nav_rows = await db.execute(
        text(
            "SELECT DISTINCT ON (isin) isin, nav FROM mf.mf_nav_history"
            " WHERE isin = ANY(:isins) ORDER BY isin, nav_date DESC"
        ),
        {"isins": isins},
    )
    nav_map: dict[str, float] = {r.isin: float(r.nav) for r in nav_rows}

    # 3. Fund metadata (scheme_name, sebi_category/category).
    fund_rows = (
        await db.execute(select(MfFund).where(MfFund.isin.in_(isins)))
    ).scalars().all()
    fund_meta: dict[str, MfFund] = {f.isin: f for f in fund_rows}

    # 4. Stored labels from the last score run.
    score_rows = (
        await db.execute(select(UserFundScore).where(UserFundScore.portfolio_id == pid))
    ).scalars().all()
    score_map: dict[str, Any] = {s.isin: s for s in score_rows}

    # 5. Build per-fund payload with today's NAV.
    total_invested = 0.0
    total_current = 0.0
    cat_totals: dict[str, float] = {}
    funds_payload: list[dict] = []

    for h in holdings:
        nav = nav_map.get(h.isin, float(h.avg_cost_nav or 0))
        current_value = float(h.units or 0) * nav
        invested = float(h.invested_amount or 0)
        total_invested += invested
        total_current += current_value

        fund = fund_meta.get(h.isin)
        score = score_map.get(h.isin)
        category = (
            (fund.sebi_category or fund.category) if fund else None
        ) or "Unknown"
        cat_totals[category] = cat_totals.get(category, 0.0) + current_value

        funds_payload.append({
            "isin": h.isin,
            "scheme_name": fund.scheme_name if fund else h.isin,
            "folio_number": h.folio_number or "",
            "units": float(h.units or 0),
            "invested_amount": invested,
            "current_value": current_value,
            "verb_label": score.verb_label if score else None,
            "confidence_band": score.confidence_band if score else None,
            "contributing_signals": [],
            "contradicting_signals": [],
            "previous_label": None,
            "confidence_factors": None,
        })

    # 6. Category allocation as % of current value.
    category_allocation = (
        {cat: round(v / total_current * 100, 2) for cat, v in cat_totals.items()}
        if total_current else {}
    )

    # 7. XIRR from the most recent portfolio snapshot (Plus users; None otherwise).
    snap_row = (
        await db.execute(
            select(MfPortfolioSnapshot)
            .where(MfPortfolioSnapshot.portfolio_id == pid)
            .order_by(MfPortfolioSnapshot.snapshot_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    xirr_pct = float(snap_row.xirr_pct) if snap_row and snap_row.xirr_pct is not None else None

    snapshot = {
        "total_invested": total_invested,
        "current_value": total_current,
        "xirr_pct": xirr_pct,
        "category_allocation": category_allocation,
        "overlap_matrix": {},
    }

    # 8. Cache the rebuilt report with a longer TTL — the daily refresh task
    #    will invalidate and refresh it with the next day's NAV.
    payload = {
        "job_id": job_id,
        "status": "done",
        "snapshot": snapshot,
        "funds": funds_payload,
        "portfolio_id": portfolio_id,
    }
    await redis.set(f"{_REPORT_PREFIX}{job_id}", json.dumps(payload), ex=_REBUILD_TTL)
    logger.info("rebuild_report: rebuilt job=%s portfolio=%s funds=%d", job_id, portfolio_id, len(funds_payload))

    return assemble_report(**payload)
