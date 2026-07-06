"""
DhanRadar — AMC Fund Manager ingestion task (Phase 6).

Celery task name : dhanradar.tasks.mf.mf_fund_manager_fetch
Beat schedule    : monthly (configured in celery_app.py)
Source key       : amc_fund_managers  (matches ops_router._SOURCE_CATALOG)

What this task does
-------------------
1. Fetches fund-manager tenure rows from non-bot-blocked AMC factsheet pages
   via dhanradar.market_data.amc_managers.fetch_fund_managers.
2. Validates each row: non-empty manager_name + parseable start_date +
   valid ISIN (^INF[A-Z0-9]{9}$) — invalid rows → stats.failed (never written).
3. Deduplicates vs the DB with a SELECT-then-INSERT pattern:
   - SELECT existing (scheme_uid, manager_name, start_date) tuples for the
     scheme_uids in this batch.
   - INSERT only the rows whose (scheme_uid, manager_name, start_date) tuple
     is NOT already present.
   This is required because mf.fund_manager_history has NO unique constraint
   (PK=id Identity + non-unique index only), so ON CONFLICT cannot be used.
   The pattern makes re-runs safe without a DB constraint (idempotent).
4. Bulk-INSERTs new rows in chunks of 2 000, stamping run_id + source.
5. Records bot-blocked / unreachable / format_mismatch AMC metadata in the
   ingestion_run row so the Ops console can tell "site down" from "site up,
   parser wrong" instead of collapsing both into one opaque failure bucket.

Bot-block handling (§12 Q3)
---------------------------
All-blocked / all-unreachable path (zero AMCs reported format_mismatch
either): stats.reachable=False, stats.status_override="partial" so the
source flips Planned → Failed (not Healthy) and an operator can review. If
at least one AMC returned HTTP 200 with 0 parseable rows (format_mismatch),
stats.reachable=True even though zero rows were written — the site itself
is reachable, only the parser needs attention. If SOME rows arrived,
reachable=True and metadata still records the blocked/mismatched AMCs for
the run-detail view.

Compliance
----------
No advisory verbs; no numeric scores/weights; no aum imputation; invalid rows
are counted as stats.failed and silently discarded (never guessed or filled in).
"""

from __future__ import annotations

import asyncio
import logging
import re

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from dhanradar.celery_app import celery_app
from dhanradar.db import TaskSessionLocal
from dhanradar.models.mf import MfFundManagerHistory

logger = logging.getLogger(__name__)

_SOURCE = "amc_fund_managers"
_TASK_NAME = "dhanradar.tasks.mf.mf_fund_manager_fetch"
_INSERT_CHUNK = 2000
_ISIN_RE = re.compile(r"^INF[A-Z0-9]{9}$")


@celery_app.task(name=_TASK_NAME)
def mf_fund_manager_fetch() -> str:
    """Celery entry point — sync wrapper around the async pipeline."""
    try:
        return asyncio.run(_mf_fund_manager_pipeline())
    except Exception:
        logger.exception("mf_fund_manager_fetch pipeline error")
        return "mf_fund_manager_fetch: failed — see worker logs"


async def _mf_fund_manager_pipeline() -> str:
    """Async pipeline: fetch → validate → dedup vs DB → insert."""
    from dhanradar.market_data.amc_managers import fetch_fund_managers
    from dhanradar.market_data.amc_managers_nippon import fetch_nippon_fund_managers
    from dhanradar.market_data.amc_managers_uti import fetch_uti_fund_managers
    from dhanradar.tasks.ingestion_run import ingestion_run, is_source_paused

    if await is_source_paused(_SOURCE):
        return "mf_fund_manager_fetch: skipped (paused)"

    async with ingestion_run(_TASK_NAME, _SOURCE) as (run_id, stats):
        await _run(
            run_id,
            stats,
            fetch_fund_managers,
            uti_fetch_fn=fetch_uti_fund_managers,
            nippon_fetch_fn=fetch_nippon_fund_managers,
        )

    return f"mf_fund_manager_fetch: {stats.written} written, {stats.failed} failed"


def _merge_status(*status_dicts: dict) -> dict:
    """Merge several {"bot_blocked": [...], "unreachable": [...],
    "format_mismatch": [...], "ok": [...]} status dicts (one per source) into
    one, concatenating each bucket. Shared by the generic factsheet fetch +
    the UTI JSON-API fetch + the NIPPON PDF fetch."""
    merged: dict[str, list[str]] = {"bot_blocked": [], "unreachable": [], "format_mismatch": [], "ok": []}
    for d in status_dicts:
        for key in merged:
            merged[key].extend(d.get(key, []))
    return merged


async def _resolve_raw_manager_rows(amc_name: str, raw_rows: list) -> list:
    """Resolve scheme-NAME-keyed rows (UTI JSON, NIPPON PDF) to `FundManagerRow`
    (scheme_uid=ISIN) via the SAME pg_trgm fuzzy matcher the constituents
    pipeline uses — never a second matcher. A scheme name that doesn't resolve
    to an ISIN with sufficient similarity is dropped (fail-closed, never
    guessed); see `dhanradar.tasks.mf._resolve_scheme_isins`."""
    from dhanradar.market_data.amc_managers import FundManagerRow
    from dhanradar.tasks.mf import _resolve_scheme_isins

    if not raw_rows:
        return []

    scheme_names = {r.scheme_name for r in raw_rows}
    scheme_isin_map = await _resolve_scheme_isins(scheme_names, amc_name)

    resolved: list[FundManagerRow] = []
    for r in raw_rows:
        isin = scheme_isin_map.get(r.scheme_name)
        if isin is None:
            logger.debug(
                "mf_fund_manager: %s scheme %r did not resolve to an ISIN — dropping row",
                amc_name,
                r.scheme_name,
            )
            continue
        resolved.append(
            FundManagerRow(
                scheme_uid=isin,
                manager_name=r.manager_name,
                start_date=r.start_date,
                end_date=None,
            )
        )
    return resolved


async def _run(
    run_id: int,
    stats,
    fetch_fn,
    *,
    uti_fetch_fn=None,
    nippon_fetch_fn=None,
) -> None:
    """Core pipeline body — separated so integration tests can inject fetch_fn
    (+ optional uti_fetch_fn / nippon_fetch_fn; both default to no-op sources
    that return zero rows so existing tests that don't pass them keep working
    unchanged)."""
    async def _noop_fetch(client):
        return [], {"bot_blocked": [], "unreachable": [], "format_mismatch": [], "ok": []}

    uti_fetch_fn = uti_fetch_fn or _noop_fetch
    nippon_fetch_fn = nippon_fetch_fn or _noop_fetch

    async with httpx.AsyncClient(
        headers={"User-Agent": "DhanRadar/1.0 data-pipeline"},
        follow_redirects=True,
    ) as client:
        rows, status = await fetch_fn(client)
        uti_raw_rows, uti_status = await uti_fetch_fn(client)
        nippon_raw_rows, nippon_status = await nippon_fetch_fn(client)

    uti_rows = await _resolve_raw_manager_rows("UTI", uti_raw_rows)
    nippon_rows = await _resolve_raw_manager_rows("NIPPON", nippon_raw_rows)
    rows = list(rows) + uti_rows + nippon_rows
    status = _merge_status(status, uti_status, nippon_status)

    bot_blocked: list[str] = status.get("bot_blocked", [])
    unreachable: list[str] = status.get("unreachable", [])
    format_mismatch: list[str] = status.get("format_mismatch", [])
    ok_amcs: list[str] = status.get("ok", [])

    stats.metadata = {
        "bot_blocked": bot_blocked,
        "unreachable": unreachable,
        "format_mismatch": format_mismatch,
        "ok": ok_amcs,
    }

    if not rows:
        # No rows fetched this run — reachable depends on WHY, so Ops can tell
        # "site down" (unreachable/bot_blocked) from "site up, parser wrong"
        # (format_mismatch — HTTP 200, 0 rows matched). An AMC that only ever
        # produces format_mismatch is still reachable; the fix is a parser
        # rewrite, not a network/access escalation.
        stats.reachable = bool(format_mismatch)
        parts = []
        if unreachable:
            parts.append(f"unreachable: {', '.join(unreachable)}")
        if bot_blocked:
            parts.append(f"bot_blocked: {', '.join(bot_blocked)}")
        if format_mismatch:
            parts.append(f"format_mismatch: {', '.join(format_mismatch)}")
        stats.last_error = "; ".join(parts) or "no AMC sources configured"
        stats.status_override = "partial"
        logger.warning(
            "mf_fund_manager: zero rows fetched (bot_blocked=%s unreachable=%s "
            "format_mismatch=%s)",
            bot_blocked,
            unreachable,
            format_mismatch,
        )
        return

    stats.reachable = True  # at least some AMCs returned data

    # --- Validate each row ---
    valid_rows = []
    for row in rows:
        stats.fetched += 1
        if not _ISIN_RE.match(row.scheme_uid):
            logger.debug(
                "mf_fund_manager: rejecting invalid ISIN %r", row.scheme_uid
            )
            stats.failed += 1
            continue
        if not row.manager_name or not row.manager_name.strip():
            logger.debug(
                "mf_fund_manager: empty manager_name for %s", row.scheme_uid
            )
            stats.failed += 1
            continue
        if row.start_date is None:
            logger.debug(
                "mf_fund_manager: missing start_date for %s", row.scheme_uid
            )
            stats.failed += 1
            continue
        valid_rows.append(row)

    if not valid_rows:
        logger.info("mf_fund_manager: all fetched rows were invalid")
        return

    # --- Dedup vs DB: SELECT existing tuples, then INSERT only new ones ---
    # The table has no unique constraint (PK=id autoincrement + non-unique index).
    # We cannot use ON CONFLICT; instead we select existing rows for the scheme_uids
    # in this batch and filter them out in Python before inserting.
    scheme_uids_in_batch = list({r.scheme_uid for r in valid_rows})

    try:
        async with TaskSessionLocal() as db:
            existing_result = await db.execute(
                select(
                    MfFundManagerHistory.scheme_uid,
                    MfFundManagerHistory.manager_name,
                    MfFundManagerHistory.start_date,
                ).where(
                    MfFundManagerHistory.scheme_uid.in_(scheme_uids_in_batch)
                )
            )
            existing_tuples: set[tuple[str, str, object]] = {
                (row.scheme_uid, row.manager_name, row.start_date)
                for row in existing_result
            }
    except Exception as exc:
        logger.error(
            "mf_fund_manager: failed to fetch existing rows for dedup: %s",
            exc,
            exc_info=True,
        )
        stats.failed += len(valid_rows)
        return

    new_rows = [
        r for r in valid_rows
        if (r.scheme_uid, r.manager_name, r.start_date) not in existing_tuples
    ]

    if not new_rows:
        logger.info(
            "mf_fund_manager: all %d valid rows already exist in DB — nothing to insert",
            len(valid_rows),
        )
        return

    # --- Bulk INSERT new rows in chunks ---
    written = 0
    for chunk_start in range(0, len(new_rows), _INSERT_CHUNK):
        chunk = new_rows[chunk_start : chunk_start + _INSERT_CHUNK]
        insert_vals = [
            {
                "scheme_uid": r.scheme_uid,
                "manager_name": r.manager_name,
                "start_date": r.start_date,
                "end_date": r.end_date,
                "source": _SOURCE,
                "run_id": run_id,
            }
            for r in chunk
        ]
        try:
            async with TaskSessionLocal() as db:
                await db.execute(
                    pg_insert(MfFundManagerHistory).values(insert_vals)
                )
                await db.commit()
            written += len(chunk)
        except Exception as exc:
            logger.error(
                "mf_fund_manager: insert chunk failed: %s", exc, exc_info=True
            )
            stats.failed += len(chunk)

    stats.written = written
    logger.info(
        "mf_fund_manager: inserted %d new rows (%d already existed)",
        written,
        len(valid_rows) - len(new_rows),
    )
