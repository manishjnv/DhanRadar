"""
DhanRadar — AMFI Scheme Master ingestion task (Admin Console Phase 6).

Refreshes mf.mf_funds with the AMFI scheme master metadata:
  amfi_code, scheme_name, amc_name, category (=scheme_category), launch_date.

NEVER overwrites: aum_crore, expense_ratio_pct, sebi_category (§8.4 / NEVER impute AUM).
Closed schemes (closure_date <= today) are counted but NOT deleted.

Source key: "amfi_scheme_master"
Task name:  "dhanradar.tasks.mf.mf_scheme_master_refresh"

DB rules (CI Guard #6 / RCA 2026-06-10):
  - TaskSessionLocal (NullPool); never the pooled request engine.
  - pg_insert ON CONFLICT DO UPDATE, deduplicated by ISIN in Python before upsert.
  - Chunk size: 2000 rows per statement.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date

import httpx

from dhanradar.celery_app import celery_app
from dhanradar.market_data.amfi_scheme_master import SchemeMasterRow

logger = logging.getLogger(__name__)

_UPSERT_CHUNK = 2000

SOURCE = "amfi_scheme_master"
TASK = "dhanradar.tasks.mf.mf_scheme_master_refresh"


def secondary_isin_for(row: SchemeMasterRow, canonical_isin: str) -> str | None:
    """The AMFI plan-variant ISIN NOT chosen as canonical (2026-07-04 double-count incident,
    defect 2 of 3): AMFI's Scheme Master concatenates a Growth ISIN + a Reinvest ISIN per
    scheme-plan line; `parse_scheme_master` already splits both, but only the canonical one
    (growth-preferred) was ever stored — the other was silently discarded, so a CAS printed
    under the discarded ISIN became a second, un-aliased holding for the same real position.
    Pure — no DB/network — so the isin2 extraction is unit-testable from a synthetic AMFI row.
    Returns None when the scheme has no second variant (most schemes)."""
    return row.isin_reinvest if canonical_isin == row.isin_growth else row.isin_growth


# ---------------------------------------------------------------------------
# Celery sync wrapper (mirrors nav_daily_fetch pattern from mf.py)
# ---------------------------------------------------------------------------


@celery_app.task(name=TASK)
def mf_scheme_master_refresh() -> str:
    """Refresh mf.mf_funds from the AMFI Scheme Master endpoint.

    Fetches DownloadSchemeData_Po.aspx?mf=0, validates + deduplicates by ISIN,
    upserts amfi_code / scheme_name / amc_name / category / launch_date into
    mf_funds (never touching aum_crore / expense_ratio_pct / sebi_category).
    Wired to the beat schedule (daily, after nav_daily_fetch).
    """
    try:
        return asyncio.run(_mf_scheme_master_pipeline())
    except Exception:  # noqa: BLE001
        logger.exception("mf_scheme_master_refresh pipeline error")
        return "mf_scheme_master_refresh: failed — see worker logs"


# ---------------------------------------------------------------------------
# Async pipeline
# ---------------------------------------------------------------------------


async def _mf_scheme_master_pipeline() -> str:
    from dhanradar.market_data.amfi_scheme_master import (
        fetch_scheme_master,
        parse_scheme_master,
    )
    from dhanradar.tasks.ingestion_run import ingestion_run, is_source_paused

    if await is_source_paused(SOURCE):
        return "mf_scheme_master_refresh: skipped (paused)"

    async with ingestion_run(TASK, SOURCE) as (run_id, stats):
        # -----------------------------------------------------------------
        # 1. Fetch
        # -----------------------------------------------------------------
        async with httpx.AsyncClient() as client:
            # ProviderError propagates out of the ctx — helper records
            # 'failed' + unreachable; the exception re-raises to Celery.
            text = await fetch_scheme_master(client)

        stats.reachable = True

        # -----------------------------------------------------------------
        # 2. Parse
        # -----------------------------------------------------------------
        parsed = parse_scheme_master(text)
        stats.fetched = len(parsed)

        # -----------------------------------------------------------------
        # 3. Validate + dedup by canonical ISIN
        # -----------------------------------------------------------------
        today = date.today()
        deduped: dict[str, dict] = {}
        n_invalid = 0
        n_closed = 0

        for row in parsed:
            canonical_isin = row.isin_growth or row.isin_reinvest
            if not canonical_isin or not row.scheme_name:
                # Missing ISIN or scheme_name — count as failed, never guess.
                n_invalid += 1
                continue

            if row.closure_date and row.closure_date <= today:
                n_closed += 1

            # 2026-07-04 plan-variant fix: store the NOT-chosen ISIN in isin2 so the CAS ingest
            # aliasing (alias_secondary_isins) can rewrite a holding parsed under it back to the
            # primary ISIN.
            secondary_isin = secondary_isin_for(row, canonical_isin)

            # Last-seen wins for duplicate ISINs within one batch
            # (prevents ON CONFLICT DO UPDATE cardinality errors, mirrors
            # _navrows_to_fund_upserts dedup pattern in mf.py).
            deduped[canonical_isin] = {
                "isin": canonical_isin,
                "amfi_code": row.amfi_code,
                "scheme_name": row.scheme_name,
                "amc_name": row.amc_name,
                # "category" column stores the raw scheme_category from master.
                "category": row.scheme_category,
                "launch_date": row.launch_date,
                "isin2": secondary_isin,
            }

        stats.failed = n_invalid
        stats.metadata = {"closed_schemes": n_closed}

        upsert_rows = list(deduped.values())

        # -----------------------------------------------------------------
        # 4. Upsert into mf.mf_funds in chunks of 2000
        # -----------------------------------------------------------------
        from sqlalchemy import func
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from dhanradar.db import TaskSessionLocal
        from dhanradar.models.mf import MfFund

        n_written = 0
        async with TaskSessionLocal() as db:
            for start in range(0, len(upsert_rows), _UPSERT_CHUNK):
                chunk = upsert_rows[start : start + _UPSERT_CHUNK]
                if not chunk:
                    continue
                insert_stmt = pg_insert(MfFund).values(chunk)
                stmt = insert_stmt.on_conflict_do_update(
                    index_elements=["isin"],
                    set_={
                        # Only the columns this source owns — never touch
                        # aum_crore, expense_ratio_pct, sebi_category (§8.4).
                        "amfi_code": insert_stmt.excluded.amfi_code,
                        "scheme_name": insert_stmt.excluded.scheme_name,
                        "amc_name": insert_stmt.excluded.amc_name,
                        "category": insert_stmt.excluded.category,
                        "launch_date": insert_stmt.excluded.launch_date,
                        # Never overwrite a non-null isin2 with null: a later refresh whose row
                        # happens to have no secondary ISIN this time (or a stale batch) must not
                        # erase a previously-discovered plan-variant mapping.
                        "isin2": func.coalesce(insert_stmt.excluded.isin2, MfFund.isin2),
                    },
                )
                await db.execute(stmt)
                n_written += len(chunk)
            await db.commit()

        stats.written = n_written
        logger.info(
            "mf_scheme_master_refresh: fetched=%d written=%d failed=%d closed=%d",
            stats.fetched,
            stats.written,
            stats.failed,
            n_closed,
        )

    return f"mf_scheme_master_refresh: {stats.written} written, {stats.failed} failed"
