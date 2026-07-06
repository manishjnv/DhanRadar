"""
DhanRadar — RBI 91-day T-bill yield ingestion task (Phase 6, Block 0.8).

Celery task name : dhanradar.tasks.mf.rbi_tbill_refresh
Beat schedule    : weekly, Wednesday 17:00 IST (add to celery_app.py beat schedule)
Source key       : rbi_tbill  (matches ops_router._SOURCE_CATALOG)

What this task does
-------------------
1. Fetches the latest 91-day T-bill cut-off yield from RBI press releases
   via dhanradar.market_data.rbi_tbill.fetch_tbill_yield.
2. Validates the extracted yield against sane bounds (3.0–10.0%, matching
   mf/risk.py _TBILL_MIN_SANE_PCT/_TBILL_MAX_SANE_PCT) — out-of-range values
   are rejected (stats.failed) and never written.
3. Upserts the valid yield into mf.macro_indicators (constraint
   uq_macro_indicator_key_date, indicator_key='tbill_91d_yield_pct') with
   run_id + ingested_at provenance stamping.

Sane-range validation
---------------------
  tbill_91d_yield_pct : 3.0 .. 10.0 (%)
  Matches mf/risk.py _TBILL_MIN_SANE_PCT/_TBILL_MAX_SANE_PCT (imported here
  rather than redefined to avoid drift).

Source-blocked note
-------------------
RBI press releases are authoritative, official, and free — the ONLY working
source for India's sovereign risk-free rate found for this block. On a
structural failure (ProviderError — listing/detail page unreachable, no
matching title found, unexpected table shape/column order, no parseable
yield), ingestion_run records the source as unreachable with
status='failed'. The Ops console surfaces this under Sources → rbi_tbill.
No fallback or imputation is performed — the run is simply failed and the
operator must investigate.

Compliance
----------
  - No advisory verbs (enum or copy).
  - No numeric scores / weights — the T-bill yield is a published fact (rate),
    not a DhanRadar score. It feeds resolve_risk_free_rate's internal
    Sharpe/Sortino denominator, never shown raw on a public surface.
  - No forecast or interpolation — only the published cut-off yield is stored.
  - Invalid / out-of-range rows → stats.failed; they are NEVER guessed.
  - Source key 'rbi_tbill' must match admin/ops_router._SOURCE_CATALOG exactly.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert

from dhanradar.celery_app import celery_app
from dhanradar.db import TaskSessionLocal

# Import the sane-range constants from mf/risk.py to avoid drift (the consume
# side and the ingest side must agree on what is "sane").
from dhanradar.mf.risk import _TBILL_MAX_SANE_PCT, _TBILL_MIN_SANE_PCT
from dhanradar.models.mf import MfMacroIndicator

logger = logging.getLogger(__name__)

_SOURCE = "rbi_tbill"
_TASK_NAME = "dhanradar.tasks.mf.rbi_tbill_refresh"

# ---------------------------------------------------------------------------
# Celery entry point
# ---------------------------------------------------------------------------


@celery_app.task(name=_TASK_NAME)
def rbi_tbill_refresh() -> str:
    """Celery entry point — sync wrapper around the async pipeline."""
    try:
        return asyncio.run(_rbi_tbill_pipeline())
    except Exception:
        logger.exception("rbi_tbill_refresh pipeline error")
        return "rbi_tbill_refresh: failed — see worker logs"


# ---------------------------------------------------------------------------
# Async pipeline
# ---------------------------------------------------------------------------


async def _rbi_tbill_pipeline() -> str:
    """Full async ingestion pipeline: fetch → validate → upsert."""
    from dhanradar.market_data.rbi_tbill import fetch_tbill_yield
    from dhanradar.tasks.ingestion_run import ingestion_run, is_source_paused

    if await is_source_paused(_SOURCE):
        return "rbi_tbill_refresh: skipped (paused)"

    async with ingestion_run(_TASK_NAME, _SOURCE) as (run_id, stats):
        await _run(run_id, stats, fetch_tbill_yield)

    return f"rbi_tbill_refresh: {stats.written} written, {stats.failed} failed"


async def _run(run_id: int, stats, fetch_fn) -> None:
    """Core pipeline body — separated so integration tests can inject fetch_fn."""

    # --- Fetch the latest T-bill yield ---
    async with httpx.AsyncClient(
        headers={"User-Agent": "DhanRadar/1.0 data-pipeline"},
        follow_redirects=True,
    ) as client:
        # ProviderError propagates out of _run → out of `async with ingestion_run`
        # → helper records the source unreachable and re-raises. No swallowing.
        macro_row = await fetch_fn(client)

    stats.fetched = 1

    # --- Validate sane range ---
    # The extracted value must fall within [_TBILL_MIN_SANE_PCT, _TBILL_MAX_SANE_PCT].
    # Out-of-range values are rejected — never written.
    if not (_TBILL_MIN_SANE_PCT <= macro_row.indicator_value <= _TBILL_MAX_SANE_PCT):
        logger.warning(
            "rbi_tbill: rejecting out-of-range value=%.4f (sane range: %.1f–%.1f)",
            macro_row.indicator_value,
            _TBILL_MIN_SANE_PCT,
            _TBILL_MAX_SANE_PCT,
        )
        stats.failed += 1
        return

    # --- Upsert into mf.macro_indicators ---
    now_utc = datetime.now(UTC)
    upsert_val = {
        "indicator_key": macro_row.indicator_key,
        "indicator_value": macro_row.indicator_value,
        "unit": macro_row.unit,
        "as_of_date": macro_row.as_of_date,
        "source": _SOURCE,
        "run_id": run_id,
        "ingested_at": now_utc,
    }

    async with TaskSessionLocal() as db:
        stmt = (
            pg_insert(MfMacroIndicator)
            .values([upsert_val])
            .on_conflict_do_update(
                constraint="uq_macro_indicator_key_date",
                set_={
                    "indicator_value": pg_insert(MfMacroIndicator).excluded.indicator_value,
                    "unit": pg_insert(MfMacroIndicator).excluded.unit,
                    "source": pg_insert(MfMacroIndicator).excluded.source,
                    "run_id": pg_insert(MfMacroIndicator).excluded.run_id,
                    "ingested_at": pg_insert(MfMacroIndicator).excluded.ingested_at,
                },
            )
        )
        await db.execute(stmt)
        await db.commit()

    stats.written += 1
    logger.info(
        "rbi_tbill: upserted indicator_key=%s value=%.4f as_of_date=%s",
        macro_row.indicator_key,
        macro_row.indicator_value,
        macro_row.as_of_date,
    )
