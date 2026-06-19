"""
DhanRadar — shared ingestion-run lifecycle helper (Admin Console Phase 6).

Every scheduled ingestion task opens an `mf.ingestion_runs` row at the start and
closes it at the end, and appends an `mf.source_health` row recording reachability.
The admin Ops console (`admin/ops_router.py`) reads exactly these two tables to render
the Sources/Tasks/Runs surfaces and to derive a source's status:

    no ingestion_runs row for source  → "Planned"
    latest run status failed/partial   → "Failed"
    otherwise                          → "Healthy"
    (Redis `paused_sources` membership  → "Paused", checked independently)

So a source flips Planned → Healthy automatically the moment a task writes its first
successful run with `source` == the catalog `source_key` in ops_router._SOURCE_CATALOG.
The `source` string MUST match that key exactly — that is the integration contract.

Six-question provenance (Data-Ingestion-Normalization §8.3): the run_id this helper
returns is stamped onto every canonical row a task writes, linking each value back to
the exact fetch event. Resilience (§20): a task that raises is recorded as 'failed'
(never a silent drop) and the source is marked unreachable; the exception is re-raised
so the Celery sync wrapper logs it.

DB access uses TaskSessionLocal (NullPool) per the mandatory Celery async-DB rule
(RCA 2026-06-10 / CI Guard #6) — never the pooled request engine.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from sqlalchemy import select

from dhanradar.db import TaskSessionLocal
from dhanradar.models.mf import MfIngestionRun, MfSourceHealth
from dhanradar.redis_client import get_redis

logger = logging.getLogger(__name__)

# Mirror of admin/ops_router._PAUSED_SOURCES_KEY. Re-declared (not imported) to keep
# module isolation: the tasks layer must not import the admin router. If the literal
# changes in one place it must change in both (covered by test_admin_ops).
_PAUSED_SOURCES_KEY = "paused_sources"


@dataclass
class RunStats:
    """Mutable counters a task fills in while it runs; read by the helper on close.

    fetched  — rows received from the source (pre-validation)
    written  — rows successfully upserted into canonical tables
    failed   — rows that failed validation / could not be written (never silently dropped)
    reachable — False when the source could not be reached at all (bot-block / 404 / timeout);
                drives the source_health row (and the Overview "sources healthy" count)
    last_error — short human reason recorded on source_health when not reachable
    raw_file_path — R2/object-store path if the raw payload was archived (Q4 / rebuild-from-raw)
    metadata — small JSON blob surfaced in the run-detail view (e.g. per-AMC bot-block map)
    status_override — force a terminal status (e.g. 'skipped'); otherwise derived from counts
    """

    fetched: int = 0
    written: int = 0
    failed: int = 0
    reachable: bool = True
    last_error: str | None = None
    raw_file_path: str | None = None
    metadata: dict | None = field(default=None)
    status_override: str | None = None


def _derive_status(stats: RunStats) -> str:
    if stats.status_override:
        return stats.status_override
    if stats.failed and not stats.written:
        return "failed"
    if stats.failed:
        return "partial"
    return "success"


async def is_source_paused(source: str) -> bool:
    """True if an admin paused this source via the Ops console (Redis set)."""
    redis = get_redis()
    members = await redis.smembers(_PAUSED_SOURCES_KEY)
    # decode_responses may yield str or bytes depending on client config — handle both.
    return source in members or source.encode() in members


async def _append_source_health(source: str, *, reachable: bool, last_error: str | None) -> None:
    """Append a source_health row, carrying consecutive_failures / last_success_at forward."""
    from sqlalchemy import func as _func

    async with TaskSessionLocal() as db:
        prev = await db.scalar(
            select(MfSourceHealth)
            .where(MfSourceHealth.source == source)
            .order_by(MfSourceHealth.check_time.desc())
            .limit(1)
        )
        prev_failures = (prev.consecutive_failures if prev else 0) or 0
        prev_success_at = prev.last_success_at if prev else None
        row = MfSourceHealth(
            source=source,
            reachable=reachable,
            last_success_at=(_func.now() if reachable else prev_success_at),
            consecutive_failures=(0 if reachable else prev_failures + 1),
            last_error=(None if reachable else last_error),
        )
        db.add(row)
        await db.commit()


async def _finish_run(run_id: int, *, status: str, stats: RunStats, error: BaseException | None) -> None:
    from sqlalchemy import func as _func
    from sqlalchemy import update

    async with TaskSessionLocal() as db:
        await db.execute(
            update(MfIngestionRun)
            .where(MfIngestionRun.run_id == run_id)
            .values(
                status=status,
                finished_at=_func.now(),
                records_fetched=stats.fetched,
                records_written=stats.written,
                records_failed=stats.failed,
                error_class=(type(error).__name__ if error else None),
                error_detail=((str(error)[:1000]) if error else stats.last_error),
                raw_file_path=stats.raw_file_path,
                run_metadata=stats.metadata,
            )
        )
        await db.commit()


@asynccontextmanager
async def ingestion_run(task_name: str, source: str) -> AsyncIterator[tuple[int, RunStats]]:
    """Open an ingestion_runs START row, yield (run_id, stats), close it on exit.

    Usage::

        async with ingestion_run("dhanradar.tasks.mf.macro_data_refresh", "rbi_dbie") as (run_id, stats):
            rows = await fetch(...)
            stats.fetched = len(rows)
            ...write canonical rows, stamping run_id...
            stats.written = n_written
            stats.failed = n_failed

    On a clean exit the terminal status is derived from the counts (success / partial /
    failed); on an exception the row is marked 'failed', source_health records the source
    unreachable, and the exception is re-raised. Either way exactly one START and one END
    write occur — no silent drops (§8.8, §20).
    """
    async with TaskSessionLocal() as db:
        run = MfIngestionRun(task_name=task_name, source=source, status="running")
        db.add(run)
        await db.flush()
        run_id = int(run.run_id)
        await db.commit()

    stats = RunStats()
    try:
        yield run_id, stats
    except BaseException as exc:  # noqa: BLE001 — record then re-raise; never swallow
        await _finish_run(run_id, status="failed", stats=stats, error=exc)
        await _append_source_health(
            source, reachable=False, last_error=f"{type(exc).__name__}: {str(exc)[:200]}"
        )
        raise
    else:
        status = _derive_status(stats)
        await _finish_run(run_id, status=status, stats=stats, error=None)
        # A 'skipped' run is not a reachability signal — leave source_health untouched.
        if status != "skipped":
            await _append_source_health(
                source, reachable=stats.reachable, last_error=stats.last_error
            )
