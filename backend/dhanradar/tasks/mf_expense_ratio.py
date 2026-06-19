"""
DhanRadar — AMC Expense Ratio (TER) ingestion task (Phase 6).

Celery task name : dhanradar.tasks.mf.mf_expense_ratio_fetch
Beat schedule    : 15th of each month, 04:00 IST (celery_app.py)
Source key       : amc_expense_ratios  (matches ops_router._SOURCE_CATALOG)

What this task does
-------------------
1. Fetches TER rows from non-bot-blocked AMC factsheet pages via
   dhanradar.market_data.amc_expense.fetch_expense_ratios.
2. Validates ter_pct in (0, 10] — invalid rows → stats.failed (never written).
3. Deduplicates the fetched batch by (isin, effective_date) in Python BEFORE
   the upsert (prevents CardinalityViolation on the unique constraint).
4. Upserts valid rows into mf.expense_ratio_history (constraint
   uq_expense_ratio_isin_date) in chunks of 2 000, stamping run_id.
5. Updates mf_funds.expense_ratio_pct to the latest ter_pct per isin (plain
   UPDATE; never touches aum_crore — §8.4 no-imputation rule).
6. Records bot-blocked / unreachable AMC metadata in the ingestion_run row so
   the Ops console surfaces the partial-data reality.

Bot-block handling (§12 Q3)
---------------------------
All-blocked / all-unreachable path: stats.reachable=False,
stats.status_override="partial" so the source flips Planned → Failed (not
Healthy) and an operator can review. If SOME rows arrived, reachable=True and
metadata still records the blocked AMCs for the run-detail view.

Compliance
----------
No advisory verbs; no numeric scores; no aum imputation; invalid rows are
counted as stats.failed and silently discarded (never guessed or filled in).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from dhanradar.celery_app import celery_app
from dhanradar.db import TaskSessionLocal
from dhanradar.models.mf import MfExpenseRatioHistory, MfFund

logger = logging.getLogger(__name__)

_SOURCE = "amc_expense_ratios"
_TASK_NAME = "dhanradar.tasks.mf.mf_expense_ratio_fetch"
_UPSERT_CHUNK = 2000


@celery_app.task(name=_TASK_NAME)
def mf_expense_ratio_fetch() -> str:
    """Celery entry point — sync wrapper around the async pipeline."""
    try:
        return asyncio.run(_mf_expense_ratio_pipeline())
    except Exception:
        logger.exception("mf_expense_ratio_fetch pipeline error")
        return "mf_expense_ratio_fetch: failed — see worker logs"


async def _mf_expense_ratio_pipeline() -> str:
    """Async pipeline: fetch → validate → dedup → upsert → update mf_funds."""
    from dhanradar.market_data.amc_expense import fetch_expense_ratios
    from dhanradar.tasks.ingestion_run import ingestion_run, is_source_paused

    if await is_source_paused(_SOURCE):
        return "mf_expense_ratio_fetch: skipped (paused)"

    async with ingestion_run(_TASK_NAME, _SOURCE) as (run_id, stats):
        await _run(run_id, stats, fetch_expense_ratios)

    return f"mf_expense_ratio_fetch: {stats.written} written, {stats.failed} failed"


async def _run(run_id: int, stats, fetch_fn) -> None:
    """Core pipeline body — separated so integration tests can inject fetch_fn."""
    async with httpx.AsyncClient(
        headers={"User-Agent": "DhanRadar/1.0 data-pipeline"},
        follow_redirects=True,
    ) as client:
        rows, status = await fetch_fn(client)

    bot_blocked: list[str] = status.get("bot_blocked", [])
    unreachable: list[str] = status.get("unreachable", [])
    ok_amcs: list[str] = status.get("ok", [])

    stats.metadata = {
        "bot_blocked": bot_blocked,
        "unreachable": unreachable,
        "ok": ok_amcs,
    }

    if not rows:
        # No rows fetched — all AMCs were bot-blocked or unreachable.
        blocked_names = ", ".join(bot_blocked + unreachable) or "all"
        stats.reachable = False
        stats.last_error = f"bot_blocked: {blocked_names}"
        stats.status_override = "partial"
        logger.warning(
            "mf_expense_ratio: zero rows fetched (bot_blocked=%s unreachable=%s)",
            bot_blocked,
            unreachable,
        )
        return

    stats.reachable = True  # at least some AMCs returned data

    # --- Validate ter_pct range before dedup ---
    valid_rows = []
    for row in rows:
        stats.fetched += 1
        if row.ter_pct <= 0 or row.ter_pct > 10:
            logger.debug(
                "mf_expense_ratio: rejecting out-of-range ter_pct=%.4f isin=%s",
                row.ter_pct,
                row.isin,
            )
            stats.failed += 1
            continue
        valid_rows.append(row)

    # --- Dedup by (isin, effective_date) in Python (CardinalityViolation guard) ---
    seen: set[tuple[str, object]] = set()
    deduped = []
    for row in valid_rows:
        key = (row.isin, row.effective_date)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    if not deduped:
        logger.info("mf_expense_ratio: all fetched rows were invalid or deduped away")
        return

    # --- Upsert mf.expense_ratio_history in chunks ---
    now_utc = datetime.now(UTC)
    written = 0

    for chunk_start in range(0, len(deduped), _UPSERT_CHUNK):
        chunk = deduped[chunk_start : chunk_start + _UPSERT_CHUNK]
        upsert_vals = [
            {
                "isin": r.isin,
                "ter_pct": r.ter_pct,
                "effective_date": r.effective_date,
                "source": _SOURCE,
                "run_id": run_id,
                "ingested_at": now_utc,
            }
            for r in chunk
        ]
        stmt = (
            pg_insert(MfExpenseRatioHistory)
            .values(upsert_vals)
            .on_conflict_do_update(
                constraint="uq_expense_ratio_isin_date",
                set_={
                    "ter_pct": pg_insert(MfExpenseRatioHistory).excluded.ter_pct,
                    "source": pg_insert(MfExpenseRatioHistory).excluded.source,
                    "run_id": pg_insert(MfExpenseRatioHistory).excluded.run_id,
                    "ingested_at": pg_insert(MfExpenseRatioHistory).excluded.ingested_at,
                },
            )
        )
        try:
            async with TaskSessionLocal() as db:
                await db.execute(stmt)
                await db.commit()
            written += len(chunk)
        except Exception as exc:
            logger.error(
                "mf_expense_ratio: upsert chunk failed: %s", exc, exc_info=True
            )
            stats.failed += len(chunk)

    stats.written = written

    # --- Update mf_funds.expense_ratio_pct to the latest ter_pct per isin ---
    # For each isin, pick the row with the latest effective_date.
    latest_per_isin: dict[str, tuple] = {}  # isin -> (effective_date, ter_pct)
    for row in deduped:
        prev = latest_per_isin.get(row.isin)
        if prev is None or row.effective_date > prev[0]:
            latest_per_isin[row.isin] = (row.effective_date, row.ter_pct)

    if latest_per_isin:
        try:
            async with TaskSessionLocal() as db:
                for isin, (_, ter_pct) in latest_per_isin.items():
                    await db.execute(
                        update(MfFund)
                        .where(MfFund.isin == isin)
                        .values(expense_ratio_pct=ter_pct)
                    )
                await db.commit()
            logger.info(
                "mf_expense_ratio: updated expense_ratio_pct on %d mf_funds rows",
                len(latest_per_isin),
            )
        except Exception as exc:
            logger.error(
                "mf_expense_ratio: mf_funds update failed: %s", exc, exc_info=True
            )
            # Do not increment stats.failed — mf_funds update is a denorm mirror;
            # the history rows were already written. Log only.
