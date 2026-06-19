"""
DhanRadar — RBI DBIE macro data ingestion task (Phase 6).

Celery task name : dhanradar.tasks.mf.macro_data_refresh
Beat schedule    : daily, 06:00 IST (add to celery_app.py beat schedule)
Source key       : rbi_dbie  (matches ops_router._SOURCE_CATALOG)

What this task does
-------------------
1. Fetches the raw CSV payload from RBI DBIE via
   dhanradar.market_data.rbi.fetch_macro_indicators.
2. Parses into MacroRow objects via parse_macro (pure function).
3. Validates each row against sane indicator-specific ranges
   (out-of-range → stats.failed, never written).
4. Deduplicates the parsed batch by (indicator_key, as_of_date) in Python
   BEFORE upsert (prevents CardinalityViolation on uq_macro_indicator_key_date).
5. Upserts valid rows into mf.macro_indicators (constraint
   uq_macro_indicator_key_date) in chunks of 2 000, stamping run_id + ingested_at.

Sane-range validation
---------------------
  repo_rate         :  0 .. 20  (%)
  cpi_inflation     : -10 .. 50 (%)
  wpi_inflation     : -10 .. 50 (%)
  gdp_growth        : -25 .. 25 (%)
  m3_money_supply   : > 0       (₹ crore; open-ended upper bound)

Source-blocked note
-------------------
RBI DBIE is an undocumented SPA. The fetch URL may return an HTML shell, a
CloudFlare block, or HTTP 4xx/5xx without notice. On a structural failure
(ProviderError), ingestion_run records the source as unreachable with
status='failed'. The Ops console surfaces this under Sources → rbi_dbie.
No fallback or imputation is performed — the run is simply failed and the
operator must investigate.

Compliance
----------
  - No advisory verbs (enum or copy).
  - No numeric scores / weights — indicator_value is a published fact (rate /
    percentage / monetary aggregate), not a DhanRadar score.
  - No forecast or interpolation — only published values are stored.
  - Invalid / out-of-range rows → stats.failed; they are NEVER guessed.
  - Source key 'rbi_dbie' must match admin/ops_router._SOURCE_CATALOG exactly.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert

from dhanradar.celery_app import celery_app
from dhanradar.db import TaskSessionLocal
from dhanradar.models.mf import MfMacroIndicator

logger = logging.getLogger(__name__)

_SOURCE = "rbi_dbie"
_TASK_NAME = "dhanradar.tasks.mf.macro_data_refresh"
_UPSERT_CHUNK = 2000

# ---------------------------------------------------------------------------
# Sane-range validation table
# Each entry: indicator_key -> (min_inclusive, max_inclusive)
# For m3_money_supply the upper bound is None (open-ended — it is a monetary
# aggregate in ₹ crore and grows over time without a natural ceiling).
# ---------------------------------------------------------------------------
_VALID_RANGES: dict[str, tuple[float, float | None]] = {
    "repo_rate": (0.0, 20.0),
    "cpi_inflation": (-10.0, 50.0),
    "wpi_inflation": (-10.0, 50.0),
    "gdp_growth": (-25.0, 25.0),
    "m3_money_supply": (0.0, None),  # strictly positive; no upper bound
}


def _is_in_range(key: str, value: float) -> bool:
    """Return True if value is within the sane range for the given indicator key."""
    bounds = _VALID_RANGES.get(key)
    if bounds is None:
        # Unknown key — should have been filtered by parse_macro already; reject here too.
        return False
    lo, hi = bounds
    if value <= lo and key == "m3_money_supply":
        # m3_money_supply must be strictly > 0
        return False
    if key != "m3_money_supply" and value < lo:
        return False
    if hi is not None and value > hi:
        return False
    return True


# ---------------------------------------------------------------------------
# Celery entry point
# ---------------------------------------------------------------------------


@celery_app.task(name=_TASK_NAME)
def macro_data_refresh() -> str:
    """Celery entry point — sync wrapper around the async pipeline."""
    try:
        return asyncio.run(_macro_data_pipeline())
    except Exception:
        logger.exception("macro_data_refresh pipeline error")
        return "macro_data_refresh: failed — see worker logs"


# ---------------------------------------------------------------------------
# Async pipeline
# ---------------------------------------------------------------------------


async def _macro_data_pipeline() -> str:
    """Full async ingestion pipeline: fetch → parse → validate → dedup → upsert."""
    from dhanradar.market_data.rbi import fetch_macro_indicators
    from dhanradar.tasks.ingestion_run import ingestion_run, is_source_paused

    if await is_source_paused(_SOURCE):
        return "macro_data_refresh: skipped (paused)"

    async with ingestion_run(_TASK_NAME, _SOURCE) as (run_id, stats):
        await _run(run_id, stats, fetch_macro_indicators)

    return f"macro_data_refresh: {stats.written} written, {stats.failed} failed"


async def _run(run_id: int, stats, fetch_fn) -> None:
    """Core pipeline body — separated so integration tests can inject fetch_fn."""
    from dhanradar.market_data.rbi import parse_macro

    # --- Fetch raw payload ---
    async with httpx.AsyncClient(
        headers={"User-Agent": "DhanRadar/1.0 data-pipeline"},
        follow_redirects=True,
    ) as client:
        # ProviderError propagates out of _run → out of `async with ingestion_run`
        # → helper records the source unreachable and re-raises. No swallowing.
        raw_payload = await fetch_fn(client)

    # --- Parse ---
    parsed_rows = parse_macro(raw_payload)
    stats.fetched = len(parsed_rows)

    if not parsed_rows:
        logger.info(
            "macro_data: parse_macro returned 0 rows (payload may be SPA HTML / empty)"
        )
        # Not a reachability failure — source was reachable (HTTP 200), just no rows.
        # The run will be recorded as status='success' with 0 written rows.
        return

    # --- Validate sane ranges ---
    valid_rows = []
    for row in parsed_rows:
        if not _is_in_range(row.indicator_key, row.indicator_value):
            logger.debug(
                "macro_data: rejecting out-of-range key=%s value=%s",
                row.indicator_key,
                row.indicator_value,
            )
            stats.failed += 1
            continue
        valid_rows.append(row)

    if not valid_rows:
        logger.info("macro_data: all parsed rows failed range validation")
        return

    # --- Dedup by (indicator_key, as_of_date) — CardinalityViolation guard ---
    seen: set[tuple[str, object]] = set()
    deduped = []
    for row in valid_rows:
        key = (row.indicator_key, row.as_of_date)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    # --- Upsert in chunks ---
    now_utc = datetime.now(UTC)
    written = 0

    for chunk_start in range(0, len(deduped), _UPSERT_CHUNK):
        chunk = deduped[chunk_start : chunk_start + _UPSERT_CHUNK]
        upsert_vals = [
            {
                "indicator_key": r.indicator_key,
                "indicator_value": r.indicator_value,
                "unit": r.unit,
                "as_of_date": r.as_of_date,
                "source": _SOURCE,
                "run_id": run_id,
                "ingested_at": now_utc,
            }
            for r in chunk
        ]
        stmt = (
            pg_insert(MfMacroIndicator)
            .values(upsert_vals)
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
        try:
            async with TaskSessionLocal() as db:
                await db.execute(stmt)
                await db.commit()
            written += len(chunk)
        except Exception as exc:
            logger.error(
                "macro_data: upsert chunk failed: %s", exc, exc_info=True
            )
            stats.failed += len(chunk)

    stats.written = written
    logger.info(
        "macro_data: upsert complete — written=%d failed=%d",
        stats.written,
        stats.failed,
    )
