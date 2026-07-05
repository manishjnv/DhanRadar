"""
DhanRadar — AMFI monthly category-wise fund flows ingestion task.

Celery task name : dhanradar.tasks.mf.mf_category_flows_fetch
Beat schedule    : DAILY 04:45 IST (celery_app.py) — freshness addendum: the
                   source only updates monthly, so the daily run checks
                   whether the latest candidate month is already stored and
                   exits immediately (status='skipped') without any network
                   call when it is. This means a real fetch only actually
                   happens on the handful of days per month around AMFI's
                   publish date, without a fragile fixed-date cron guessing
                   the exact publish day.
Source key       : amfi_category_flows (matches ops_router._SOURCE_CATALOG)

What this task does
--------------------
1. Computes the most-recent candidate report month (candidate_months); if a
   row for that month already exists in mf.mf_category_flows, exits
   immediately (no HTTP call) — freshness addendum.
2. Otherwise fetches + parses the AMFI legacy .xls via
   dhanradar.market_data.amfi_category_flows.fetch_category_flows (tries
   last full month, falls back to the month before on 404/parse error).
3. Deduplicates by (period_month, scheme_category) in Python BEFORE the
   upsert (prevents CardinalityViolation on the unique constraint).
4. Upserts rows into mf.mf_category_flows in chunks of 2 000, stamping
   run_id + source_url + fetched_at.

Compliance
----------
No advisory verbs; no numeric scores. Category-level ONLY — never back out
or estimate per-scheme flows from this data (§8.4). scheme_category is
AMFI's raw SEBI category label stored verbatim.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from dhanradar.celery_app import celery_app
from dhanradar.db import TaskSessionLocal
from dhanradar.models.mf import MfCategoryFlows

logger = logging.getLogger(__name__)

_SOURCE = "amfi_category_flows"
_TASK_NAME = "dhanradar.tasks.mf.mf_category_flows_fetch"
_UPSERT_CHUNK = 2000


@celery_app.task(name=_TASK_NAME)
def mf_category_flows_fetch() -> str:
    """Celery entry point — sync wrapper around the async pipeline."""
    try:
        return asyncio.run(_mf_category_flows_pipeline())
    except Exception:
        logger.exception("mf_category_flows_fetch pipeline error")
        return "mf_category_flows_fetch: failed — see worker logs"


async def _already_have_month(period_month: date) -> bool:
    async with TaskSessionLocal() as db:
        row = await db.scalar(
            select(MfCategoryFlows.id).where(MfCategoryFlows.period_month == period_month).limit(1)
        )
        return row is not None


async def _mf_category_flows_pipeline(today: date | None = None) -> str:
    """Async pipeline: freshness-check → fetch → validate → dedup → upsert."""
    from dhanradar.market_data.amfi_category_flows import (
        candidate_months,
        fetch_category_flows,
    )
    from dhanradar.tasks.ingestion_run import ingestion_run, is_source_paused

    if await is_source_paused(_SOURCE):
        return "mf_category_flows_fetch: skipped (paused)"

    today = today or date.today()
    latest_candidate_month = candidate_months(today)[0]
    if await _already_have_month(latest_candidate_month):
        # Freshness addendum: monthly data, daily beat — exit without a
        # network call once the latest candidate month is already stored.
        async with ingestion_run(_TASK_NAME, _SOURCE) as (_run_id, stats):
            stats.status_override = "skipped"
        return (
            f"mf_category_flows_fetch: skipped (already have {latest_candidate_month.isoformat()})"
        )

    async with ingestion_run(_TASK_NAME, _SOURCE) as (run_id, stats):
        await _run(run_id, stats, fetch_category_flows, today)

    return f"mf_category_flows_fetch: {stats.written} written, {stats.failed} failed"


async def _run(run_id: int, stats, fetch_fn, today: date) -> None:
    """Core pipeline body — separated so integration tests can inject fetch_fn."""
    async with httpx.AsyncClient(
        headers={"User-Agent": "DhanRadar/1.0 data-pipeline"},
        follow_redirects=True,
    ) as client:
        try:
            rows, period_month, source_url = await fetch_fn(client, today)
        except Exception as exc:  # noqa: BLE001
            stats.reachable = False
            stats.last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            stats.status_override = "partial"
            logger.warning("mf_category_flows: fetch failed: %s", exc)
            return

    stats.reachable = True
    stats.fetched = len(rows)

    # --- Dedup by (period_month, scheme_type, scheme_category) in Python ---
    seen: set[tuple[date, str, str]] = set()
    deduped = []
    for row in rows:
        key = (row.period_month, row.scheme_type, row.scheme_category)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    if not deduped:
        logger.info("mf_category_flows: all fetched rows were duplicates")
        return

    now_utc = datetime.now(UTC)
    written = 0

    for chunk_start in range(0, len(deduped), _UPSERT_CHUNK):
        chunk = deduped[chunk_start : chunk_start + _UPSERT_CHUNK]
        upsert_vals = [
            {
                "period_month": r.period_month,
                "scheme_type": r.scheme_type,
                "scheme_category": r.scheme_category,
                "num_schemes": r.num_schemes,
                "num_folios": r.num_folios,
                "funds_mobilized_cr": r.funds_mobilized_cr,
                "redemption_cr": r.redemption_cr,
                "net_flow_cr": r.net_flow_cr,
                "net_aum_cr": r.net_aum_cr,
                "avg_aum_cr": r.avg_aum_cr,
                "source_url": source_url,
                "run_id": run_id,
                "fetched_at": now_utc,
            }
            for r in chunk
        ]
        stmt = (
            pg_insert(MfCategoryFlows)
            .values(upsert_vals)
            .on_conflict_do_update(
                constraint="uq_mf_category_flows_month_type_category",
                set_={
                    "num_schemes": pg_insert(MfCategoryFlows).excluded.num_schemes,
                    "num_folios": pg_insert(MfCategoryFlows).excluded.num_folios,
                    "funds_mobilized_cr": pg_insert(MfCategoryFlows).excluded.funds_mobilized_cr,
                    "redemption_cr": pg_insert(MfCategoryFlows).excluded.redemption_cr,
                    "net_flow_cr": pg_insert(MfCategoryFlows).excluded.net_flow_cr,
                    "net_aum_cr": pg_insert(MfCategoryFlows).excluded.net_aum_cr,
                    "avg_aum_cr": pg_insert(MfCategoryFlows).excluded.avg_aum_cr,
                    "source_url": pg_insert(MfCategoryFlows).excluded.source_url,
                    "run_id": pg_insert(MfCategoryFlows).excluded.run_id,
                    "fetched_at": pg_insert(MfCategoryFlows).excluded.fetched_at,
                },
            )
        )
        try:
            async with TaskSessionLocal() as db:
                await db.execute(stmt)
                await db.commit()
            written += len(chunk)
        except Exception as exc:
            logger.error("mf_category_flows: upsert chunk failed: %s", exc, exc_info=True)
            stats.failed += len(chunk)

    stats.written = written
