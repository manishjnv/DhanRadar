"""
DhanRadar — MF Celery tasks (Phase 5).

`parse_cas_job` is the CAS→report worker (architecture pipeline steps 3–8):
parse → upsert holdings → snapshot → score (via the engine interface) → cache the
report → done. The raw CAS file is deleted immediately after parse; a daily
`purge_cas_files` sweep is the 24h backstop (anti-pattern guard).

The Celery task is sync; the async DB/Redis/engine pipeline runs under
`asyncio.run`. The pure mapping (`parsed_to_snapshot_holdings`) is factored out so
it is unit-testable without a worker.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import date, datetime, timezone
from typing import Any, Optional

from dhanradar.celery_app import celery_app
from dhanradar.mf import service
from dhanradar.mf.cas import CasParseError, ParsedHolding, parse_cas

logger = logging.getLogger(__name__)
from dhanradar.mf.scoring_bridge import FundSignals, score_fund, upsert_user_fund_score
from dhanradar.mf.snapshot import CashFlow, Holding, build_snapshot

_UPLOAD_TTL_SECONDS = 24 * 3600


def parsed_to_snapshot_holdings(
    parsed: list[ParsedHolding], nav_map: Optional[dict[str, float]] = None
) -> list[Holding]:
    """Map parsed CAS holdings → snapshot.Holding, applying the latest NAV when
    available (else falling back to the CAS-reported valuation). Pure + testable."""
    nav_map = nav_map or {}
    out: list[Holding] = []
    for p in parsed:
        nav = nav_map.get(p.isin, p.nav)
        current_value = (p.units * nav) if (nav is not None) else (p.value or 0.0)
        invested = p.cost if p.cost is not None else 0.0
        cashflows = [CashFlow(when=t.when, amount=t.amount) for t in p.txns]
        if current_value:
            cashflows.append(CashFlow(when=p.as_of_date or date.today(), amount=current_value))
        out.append(
            Holding(
                isin=p.isin,
                units=p.units,
                invested_amount=invested,
                current_value=current_value,
                category="uncategorized",  # filled from mf_funds when metadata exists
                cashflows=cashflows,
            )
        )
    return out


@celery_app.task(name="dhanradar.tasks.mf.parse_cas_job", bind=True, max_retries=2)
def parse_cas_job(self, job_id: str, path: str, user_id: str) -> str:
    """CAS→report worker. Always purges the raw file; marks the job failed with an
    OPAQUE code (never the raw exception, which could carry a path/PII)."""
    try:
        return asyncio.run(_run_pipeline(job_id, path, user_id))
    except CasParseError:
        logger.warning("CAS parse failed job=%s", job_id)  # full detail not echoed to client
        asyncio.run(_mark_failed(job_id, "parse_failed"))
        return "failed: parse_failed"
    except Exception:  # noqa: BLE001 — record opaque code + purge, never leak detail
        logger.exception("CAS pipeline error job=%s", job_id)
        asyncio.run(_mark_failed(job_id, "internal_error"))
        return "failed: internal_error"
    finally:
        _purge(path)


async def _run_pipeline(job_id: str, path: str, user_id: str) -> str:
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from dhanradar.db import engine
    from dhanradar.models.mf import MfCasJob
    from dhanradar.redis_client import get_redis
    from dhanradar.scoring.engine import RatingEngine

    redis = get_redis()
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Consume-and-delete the CAS password from its short-lived Redis key (it was
    # never put on the broker). Missing → None (an unprotected CAS still parses).
    pw_key = f"mf:cas:pw:{job_id}"
    password = await redis.get(pw_key)
    if password is not None:
        await redis.delete(pw_key)

    parsed = parse_cas(path, password)  # raises CasParseError on bad password/format
    rengine = RatingEngine()

    async with SessionLocal() as db:
        await db.execute(
            update(MfCasJob).where(MfCasJob.job_id == job_id).values(status="parsing", progress_pct=40)
        )
        await db.commit()

        await _upsert_holdings(db, user_id, parsed)
        await db.execute(
            update(MfCasJob).where(MfCasJob.job_id == job_id).values(status="scoring", progress_pct=70)
        )
        await db.commit()

        snap = build_snapshot(parsed_to_snapshot_holdings(parsed))

        funds_payload: list[dict] = []
        for p in parsed:
            # v1 signals are thin (NAV/fundamentals pipeline lands later); the
            # engine refuses (insufficient_data) where coverage is too low.
            result = await score_fund(rengine, FundSignals(isin=p.isin))
            await upsert_user_fund_score(db, user_id, result)
            funds_payload.append({
                "isin": p.isin, "scheme_name": p.scheme_name, "folio_number": p.folio_number,
                "units": p.units, "invested_amount": p.cost, "current_value": p.value,
                "verb_label": result.verb_label.value, "confidence_band": result.confidence_band.value,
                "contributing_signals": result.contributing_signals,
                "contradicting_signals": result.contradicting_signals,
            })

        report_payload = {
            "job_id": job_id, "status": "done",
            "snapshot": {
                "total_invested": snap.total_invested, "current_value": snap.current_value,
                "xirr_pct": snap.xirr_pct, "category_allocation": snap.category_allocation,
                "overlap_matrix": snap.overlap_matrix,
            },
            "funds": funds_payload, "model_version": rengine.model_version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        await redis.set(
            f"{service._REPORT_PREFIX}{job_id}", json.dumps(report_payload), ex=service._REPORT_TTL
        )
        await db.execute(
            update(MfCasJob).where(MfCasJob.job_id == job_id).values(
                status="done", progress_pct=100, completed_at=datetime.now(timezone.utc)
            )
        )
        await db.commit()
    return f"done: {len(parsed)} schemes"


async def _upsert_holdings(db: Any, user_id: str, parsed: list[ParsedHolding]) -> None:
    from sqlalchemy import func
    from sqlalchemy.dialects.postgresql import insert

    from dhanradar.models.mf import MfUserHolding

    for p in parsed:
        stmt = insert(MfUserHolding).values(
            user_id=user_id, isin=p.isin, folio_number=p.folio_number, units=p.units,
            avg_cost_nav=p.nav, invested_amount=p.cost, source="cas", as_of_date=p.as_of_date,
        ).on_conflict_do_update(
            constraint="uq_mf_holding",
            set_={"units": p.units, "invested_amount": p.cost, "source": "cas",
                  "as_of_date": p.as_of_date, "updated_at": func.now()},
        )
        await db.execute(stmt)
    await db.commit()


async def _mark_failed(job_id: str, message: str) -> None:
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from dhanradar.db import engine
    from dhanradar.models.mf import MfCasJob

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with SessionLocal() as db:
        await db.execute(
            update(MfCasJob).where(MfCasJob.job_id == job_id).values(
                status="failed", error_message=message[:500]
            )
        )
        await db.commit()


def _purge(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


@celery_app.task(name="dhanradar.tasks.mf.nav_daily_fetch")
def nav_daily_fetch() -> str:
    """AMFI NAV daily refresh (Implementation Plan Phase 5 §2): fetch
    portal.amfiindia.com/spages/NAVAll.txt → bulk-upsert mf_nav_history →
    refresh Redis → emit mf.nav.refreshed → targeted invalidation via
    mf:isin_users. STUB — the AMFI fetch + hypertable bulk-upsert is the data
    pipeline, deferred (no scheme metadata/NAV feed wired yet). Tracked B-mf-nav."""
    return "nav_daily_fetch: stub — AMFI fetch pipeline deferred"


@celery_app.task(name="dhanradar.tasks.mf.purge_cas_files")
def purge_cas_files() -> str:
    """24h backstop: delete any raw CAS file older than the TTL (anti-pattern guard)."""
    import tempfile

    d = os.path.join(tempfile.gettempdir(), "dhanradar_cas")
    if not os.path.isdir(d):
        return "purge: no dir"
    now = time.time()
    removed = 0
    for name in os.listdir(d):
        fp = os.path.join(d, name)
        try:
            if os.path.isfile(fp) and (now - os.path.getmtime(fp)) > _UPLOAD_TTL_SECONDS:
                os.remove(fp)
                removed += 1
        except OSError:
            pass
    return f"purge: removed {removed}"
