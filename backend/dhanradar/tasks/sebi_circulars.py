"""
DhanRadar — SEBI Circulars ingestion task (Admin Console Phase 6).

Fetches the SEBI MF circulars listing page and upserts circular metadata
into mf.sebi_circulars.

STORES RAW METADATA ONLY (circular_number, circular_date, title, url,
coarse category).  Does NOT:
  - Summarise circular body text (no advisory language — non-neg #1).
  - Derive merger/category-change semantics into scheme_lineage (no
    fabrication — §8.4).  That requires structured human review.
  - Store numeric scores, weights, or factor values (non-neg #2).

Source key: "sebi_circulars"
Task name:  "dhanradar.tasks.mf.sebi_circulars_fetch"

DB rules (CI Guard #6 / RCA 2026-06-10):
  - TaskSessionLocal (NullPool); never the pooled request engine.
  - pg_insert ON CONFLICT DO UPDATE on constraint ``uq_sebi_circular_number``.
  - Deduplicate by circular_number in Python BEFORE upsert (avoids
    CardinalityViolation when the listing page has duplicate entries).
  - Chunk size: 2000 rows per statement.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from dhanradar.celery_app import celery_app

logger = logging.getLogger(__name__)

_UPSERT_CHUNK = 2000

SOURCE = "sebi_circulars"
TASK = "dhanradar.tasks.mf.sebi_circulars_fetch"


# ---------------------------------------------------------------------------
# Celery sync wrapper (mirrors mf_scheme_master_refresh pattern)
# ---------------------------------------------------------------------------


@celery_app.task(name=TASK)
def sebi_circulars_fetch() -> str:
    """Fetch and upsert SEBI MF circular metadata into mf.sebi_circulars.

    Fetches the SEBI circulars listing page, validates and deduplicates by
    circular_number, then upserts circular_number/circular_date/title/url/
    category into mf.sebi_circulars (never derives advisory content from
    circular titles).
    """
    try:
        return asyncio.run(_sebi_circulars_pipeline())
    except Exception:  # noqa: BLE001
        logger.exception("sebi_circulars_fetch pipeline error")
        return "sebi_circulars_fetch: failed — see worker logs"


# ---------------------------------------------------------------------------
# Async pipeline
# ---------------------------------------------------------------------------


async def _sebi_circulars_pipeline() -> str:
    from dhanradar.market_data.sebi import fetch_circulars, parse_circulars
    from dhanradar.tasks.ingestion_run import ingestion_run, is_source_paused

    if await is_source_paused(SOURCE):
        return "sebi_circulars_fetch: skipped (paused)"

    async with ingestion_run(TASK, SOURCE) as (run_id, stats):
        # -----------------------------------------------------------------
        # 1. Fetch HTML
        # -----------------------------------------------------------------
        async with httpx.AsyncClient() as client:
            # ProviderError propagates out of the ctx — helper records
            # 'failed' + unreachable; exception re-raises to Celery.
            html = await fetch_circulars(client)

        stats.reachable = True

        # -----------------------------------------------------------------
        # 2. Parse
        # -----------------------------------------------------------------
        parsed = parse_circulars(html)
        stats.fetched = len(parsed)

        # -----------------------------------------------------------------
        # 3. Validate + dedup by circular_number
        # -----------------------------------------------------------------
        deduped: dict[str, dict] = {}
        n_invalid = 0

        for row in parsed:
            # All three fields are mandatory — skip and count any gap.
            if not row.circular_number or not row.circular_date or not row.title:
                n_invalid += 1
                continue

            # Last-seen wins for duplicate circular_numbers within one batch
            # (prevents ON CONFLICT DO UPDATE cardinality errors).
            deduped[row.circular_number] = {
                "circular_number": row.circular_number,
                "circular_date": row.circular_date,
                "title": row.title,         # stored verbatim — no summarisation
                "url": row.url,
                "category": row.category,
                "source": SOURCE,
                "run_id": run_id,
            }

        stats.failed = n_invalid
        upsert_rows = list(deduped.values())

        # -----------------------------------------------------------------
        # 4. Upsert into mf.sebi_circulars in chunks of 2000
        # -----------------------------------------------------------------
        from sqlalchemy import func as _func
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from dhanradar.db import TaskSessionLocal
        from dhanradar.models.mf import MfSebiCircular

        n_written = 0
        async with TaskSessionLocal() as db:
            for start in range(0, len(upsert_rows), _UPSERT_CHUNK):
                chunk = upsert_rows[start : start + _UPSERT_CHUNK]
                if not chunk:
                    continue
                stmt = (
                    pg_insert(MfSebiCircular)
                    .values(chunk)
                    .on_conflict_do_update(
                        constraint="uq_sebi_circular_number",
                        set_={
                            "circular_date": pg_insert(MfSebiCircular).excluded.circular_date,
                            "title": pg_insert(MfSebiCircular).excluded.title,
                            "url": pg_insert(MfSebiCircular).excluded.url,
                            "category": pg_insert(MfSebiCircular).excluded.category,
                            "source": pg_insert(MfSebiCircular).excluded.source,
                            "run_id": pg_insert(MfSebiCircular).excluded.run_id,
                            "ingested_at": _func.now(),
                        },
                    )
                )
                await db.execute(stmt)
                n_written += len(chunk)
            await db.commit()

        stats.written = n_written
        logger.info(
            "sebi_circulars_fetch: fetched=%d written=%d failed=%d",
            stats.fetched,
            stats.written,
            stats.failed,
        )

    return f"sebi_circulars_fetch: {stats.written} written, {stats.failed} failed"
