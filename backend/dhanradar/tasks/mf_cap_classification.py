"""
DhanRadar — AMFI half-yearly Large/Mid/Small Cap classification ingestion task.

Celery task name : dhanradar.tasks.mf.mf_cap_classification_fetch
Beat schedule    : DAILY 04:15 IST (celery_app.py) — freshness addendum: the
                   source only updates half-yearly, so the daily run checks
                   whether the current half's data is already stored and
                   exits immediately (status='skipped') without any network
                   call when it is. This means a real fetch only actually
                   happens on the ~1-2 days per half when AMFI first
                   publishes, while still catching publish-lag variance
                   without a fragile fixed-date cron.
Source key       : amfi_cap_classification (matches ops_router._SOURCE_CATALOG)

What this task does
--------------------
1. Computes the most-recent half-year period end (candidate_period_ends);
   if a row for that period already exists in mf.stock_cap_classification,
   exits immediately (no HTTP call) — freshness addendum.
2. Otherwise fetches + parses the AMFI xlsx via
   dhanradar.market_data.amfi_cap_classification.fetch_cap_classification
   (tries current half, falls back to the previous half on 404/parse error).
3. Deduplicates by (stock_isin, effective_period) in Python BEFORE the
   upsert (prevents CardinalityViolation on the unique constraint).
4. Upserts rows into mf.stock_cap_classification in chunks of 2 000, stamping
   run_id + source_url + fetched_at.

Compliance
----------
No advisory verbs; no numeric scores; cap_class/avg_market_cap values are
stored exactly as AMFI publishes them — never derived, interpolated, or
imputed (§8.4). This is a stock-level reference dataset (equity ISINs), not
a fund-level one — no FK to mf_funds.
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
from dhanradar.models.mf import MfStockCapClassification

logger = logging.getLogger(__name__)

_SOURCE = "amfi_cap_classification"
_TASK_NAME = "dhanradar.tasks.mf.mf_cap_classification_fetch"
_UPSERT_CHUNK = 2000


@celery_app.task(name=_TASK_NAME)
def mf_cap_classification_fetch() -> str:
    """Celery entry point — sync wrapper around the async pipeline."""
    try:
        return asyncio.run(_mf_cap_classification_pipeline())
    except Exception:
        logger.exception("mf_cap_classification_fetch pipeline error")
        return "mf_cap_classification_fetch: failed — see worker logs"


async def _already_have_period(period_label: str) -> bool:
    async with TaskSessionLocal() as db:
        row = await db.scalar(
            select(MfStockCapClassification.id)
            .where(MfStockCapClassification.effective_period == period_label)
            .limit(1)
        )
        return row is not None


async def _mf_cap_classification_pipeline(today: date | None = None) -> str:
    """Async pipeline: freshness-check → fetch → validate → dedup → upsert."""
    from dhanradar.market_data.amfi_cap_classification import (
        candidate_period_ends,
        fetch_cap_classification,
        period_label,
    )
    from dhanradar.tasks.ingestion_run import ingestion_run, is_source_paused

    if await is_source_paused(_SOURCE):
        return "mf_cap_classification_fetch: skipped (paused)"

    today = today or date.today()
    latest_candidate_label = period_label(candidate_period_ends(today)[0])
    if await _already_have_period(latest_candidate_label):
        # Freshness addendum: half-yearly data, daily beat — exit without a
        # network call once the current half is already stored.
        async with ingestion_run(_TASK_NAME, _SOURCE) as (_run_id, stats):
            stats.status_override = "skipped"
        return f"mf_cap_classification_fetch: skipped (already have {latest_candidate_label})"

    async with ingestion_run(_TASK_NAME, _SOURCE) as (run_id, stats):
        await _run(run_id, stats, fetch_cap_classification, today)

    return f"mf_cap_classification_fetch: {stats.written} written, {stats.failed} failed"


async def _run(run_id: int, stats, fetch_fn, today: date) -> None:
    """Core pipeline body — separated so integration tests can inject fetch_fn."""
    async with httpx.AsyncClient(
        headers={"User-Agent": "DhanRadar/1.0 data-pipeline"},
        follow_redirects=True,
    ) as client:
        try:
            rows, period_label, source_url = await fetch_fn(client, today)
        except Exception as exc:  # noqa: BLE001
            stats.reachable = False
            stats.last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            stats.status_override = "partial"
            logger.warning("mf_cap_classification: fetch failed: %s", exc)
            return

    stats.reachable = True
    stats.fetched = len(rows)

    # --- Dedup by (stock_isin, effective_period) in Python ---
    seen: set[tuple[str, str]] = set()
    deduped = []
    for row in rows:
        key = (row.stock_isin, row.effective_period)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    if not deduped:
        logger.info("mf_cap_classification: all fetched rows were duplicates")
        return

    now_utc = datetime.now(UTC)
    written = 0

    for chunk_start in range(0, len(deduped), _UPSERT_CHUNK):
        chunk = deduped[chunk_start : chunk_start + _UPSERT_CHUNK]
        upsert_vals = [
            {
                "stock_isin": r.stock_isin,
                "stock_name": r.stock_name,
                "cap_class": r.cap_class,
                "avg_market_cap_cr": r.avg_market_cap_cr,
                "effective_period": r.effective_period,
                "source_url": source_url,
                "run_id": run_id,
                "fetched_at": now_utc,
            }
            for r in chunk
        ]
        stmt = (
            pg_insert(MfStockCapClassification)
            .values(upsert_vals)
            .on_conflict_do_update(
                constraint="uq_stock_cap_classification_isin_period",
                set_={
                    "stock_name": pg_insert(MfStockCapClassification).excluded.stock_name,
                    "cap_class": pg_insert(MfStockCapClassification).excluded.cap_class,
                    "avg_market_cap_cr": pg_insert(
                        MfStockCapClassification
                    ).excluded.avg_market_cap_cr,
                    "source_url": pg_insert(MfStockCapClassification).excluded.source_url,
                    "run_id": pg_insert(MfStockCapClassification).excluded.run_id,
                    "fetched_at": pg_insert(MfStockCapClassification).excluded.fetched_at,
                },
            )
        )
        try:
            async with TaskSessionLocal() as db:
                await db.execute(stmt)
                await db.commit()
            written += len(chunk)
        except Exception as exc:
            logger.error("mf_cap_classification: upsert chunk failed: %s", exc, exc_info=True)
            stats.failed += len(chunk)

    stats.written = written
