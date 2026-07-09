"""
DhanRadar — Manual disclosure inbox Celery tasks.

Three tasks, one shared pipeline (dhanradar/mf/manual_ingest.py::intake_file):

  * parse_manual_disclosure_file — enqueued (never scheduled) by intake_file()
    for every channel. Detects AMC + disclosure month, routes through the
    EXISTING SEBI disclosure parser (`_upsert_constituents` — the same one
    `mf_constituents_fetch` uses, incl. its AUM extraction + fail-closed >105%
    guard), and records the outcome on the mf.manual_ingest_files row.
  * scan_incoming_folder   — beat, every 15 min. Channel B (watched folder).
  * poll_email_inbox       — beat, every 30 min. Channel C (email poller);
    DORMANT-SAFE: no-ops (logs, never crashes/alerts) until all 3 of
    MANUAL_INGEST_IMAP_HOST/USER/PASSWORD are set.

Source key: "manual_disclosure_inbox" (registered in admin/ops_router.py
_SOURCE_CATALOG). Uses the SAME ingestion_run()/source_health provenance every
other Phase-6 source uses — a failed parse surfaces via the existing
"N ingestion failures in 24h" admin alert for free (tasks/ingestion_run.py).
"""

from __future__ import annotations

import asyncio
import email
import email.utils
import imaplib
import logging
import shutil
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from dhanradar.celery_app import celery_app
from dhanradar.mf.disclosure_parsers import classify_file_class
from dhanradar.mf.manual_ingest import (
    ALLOWED_EXTENSIONS,
    ZIP_EXTENSION,
    detect_amc,
    detect_amc_and_parse,
    detect_period_from_filename,
    intake_upload,
    looks_closed_ended,
)

# NoReferencedTableError guard — MfManualIngestFile.uploaded_by (models/mf.py) has a
# STRING ForeignKey("auth.users.id"); SQLAlchemy only resolves that reference once the
# User model's Table has been registered into the shared declarative metadata, which
# only happens after `dhanradar.models.auth` is imported somewhere in the process. The
# FastAPI app transitively imports it at startup (auth router/deps), so the admin
# upload channel — routed through this same intake_file() — never hits this. This
# Celery worker boots this module directly via celery_app.py's `include=[...]` with no
# such transitive import, so scan_incoming_folder / parse_manual_disclosure_file were
# the first code in the worker process to ever touch MfManualIngestFile and crashed
# with "could not find table 'auth.users'". Mirrors the same FK-registration
# convention tasks/mf.py already uses for MfPortfolio (see
# tasks/mf.py::_store_or_validate_identity) — imported here at MODULE level (not
# function-scoped) so it runs once, deterministically, at worker boot, before ANY
# task in this module can touch the FK'd table regardless of execution order.
from dhanradar.models import auth as _auth_models  # noqa: F401

logger = logging.getLogger(__name__)

TASK_PARSE = "dhanradar.tasks.manual_ingest.parse_manual_disclosure_file"
TASK_SCAN_FOLDER = "dhanradar.tasks.manual_ingest.scan_incoming_folder"
TASK_POLL_EMAIL = "dhanradar.tasks.manual_ingest.poll_email_inbox"
TASK_REAP_STUCK = "dhanradar.tasks.manual_ingest.reap_stuck_manual_ingest_files"
SOURCE = "manual_disclosure_inbox"


# ---------------------------------------------------------------------------
# Parse task — enqueued per file by intake_file(), never scheduled.
# ---------------------------------------------------------------------------


@celery_app.task(name=TASK_PARSE, bind=True, max_retries=2)
def parse_manual_disclosure_file(self, file_id: str, amc_hint: str | None = None) -> str:
    try:
        return asyncio.run(_parse_pipeline(file_id, amc_hint))
    except Exception:  # noqa: BLE001 — never leave the row at 'pending' silently
        logger.exception("manual_ingest parse failed file_id=%s", file_id)
        try:
            asyncio.run(_mark(file_id, "failed", error="internal_error"))
        except Exception:  # noqa: BLE001
            logger.exception("manual_ingest: failed to mark file_id=%s as failed", file_id)
        return "failed: internal_error"


async def _mark(
    file_id: str,
    status: str,
    *,
    amc: str | None = None,
    period: date | None = None,
    rows: int | None = None,
    error: str | None = None,
) -> None:
    from dhanradar.db import TaskSessionLocal
    from dhanradar.models.mf import MfManualIngestFile

    async with TaskSessionLocal() as db:
        row = await db.get(MfManualIngestFile, uuid.UUID(file_id))
        if row is None:
            return
        row.status = status
        row.amc_detected = amc
        row.period_detected = period
        row.rows_ingested = rows
        row.error = error
        row.parsed_at = datetime.now(UTC)
        await db.commit()


async def _parse_pipeline(file_id: str, amc_hint: str | None = None) -> str:
    from dhanradar.db import TaskSessionLocal
    from dhanradar.mf.manual_ingest import stored_path_for
    from dhanradar.models.mf import MfManualIngestFile
    from dhanradar.tasks.ingestion_run import ingestion_run
    from dhanradar.tasks.mf import _upsert_constituents

    async with TaskSessionLocal() as db:
        row = await db.get(MfManualIngestFile, uuid.UUID(file_id))
        if row is None:
            logger.warning("manual_ingest: file_id=%s not found — skipping", file_id)
            return "file_not_found"
        if row.status != "pending":
            # Idempotency guard — a duplicate enqueue (e.g. a retried task) must
            # never re-parse an already-terminal row.
            return f"skip:{row.status}"
        original_filename = row.original_filename

    path = stored_path_for(file_id, original_filename)
    if not path.exists():
        await _mark(file_id, "failed", error="stored_file_missing")
        return "failed: stored_file_missing"

    if Path(original_filename).suffix.lower() == ".pdf":
        # SBI's per-scheme "Fund Details" page rendered to PDF (2026-07-10 —
        # 52 founder uploads sat 'archived' while carrying CURRENT riskometer/
        # TER/benchmark/manager/exit-load) parses via the scheme_master
        # writer; every OTHER PDF keeps the contract-§2 archive behavior
        # (no fake parsing, no OCR).
        from dhanradar.mf.disclosure_parsers import looks_like_scheme_master_pdf

        data = path.read_bytes()
        if looks_like_scheme_master_pdf(data):
            return await _parse_special_class(
                file_id, "scheme_master_pdf", data, original_filename, amc_hint
            )
        await _mark(file_id, "archived")
        return "archived: pdf_saved_for_later"

    data = path.read_bytes()

    # File-class dispatch (2026-07-07): AAUM annexures, annual riskometer
    # disclosures, and scheme-performance files are NOT portfolio disclosures —
    # routing them through the constituents parser is what left them
    # 'unsupported' in the founder's first batch. Each class has its own pure
    # parser (mf/disclosure_parsers.py) and a targeted mf_funds writer below.
    # `data` is passed (2026-07-08) so scheme_master can be CONTENT-sniffed —
    # SBI's "Fund Details" HTML page uses a normal per-scheme filename
    # indistinguishable from a real portfolio disclosure by name alone.
    file_class = classify_file_class(original_filename, data)
    if file_class != "portfolio":
        return await _parse_special_class(file_id, file_class, data, original_filename, amc_hint)

    async with ingestion_run(TASK_PARSE, SOURCE) as (run_id, stats):
        stats.fetched = 1
        stats.reachable = True  # a local file read is never a reachability issue

        try:
            amc_name, period, rows = detect_amc_and_parse(data, original_filename, amc_hint)
        except Exception as exc:  # noqa: BLE001 — fail-closed, never partial-silent
            stats.failed = 1
            stats.last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            await _mark(file_id, "failed", error=f"parse_error:{type(exc).__name__}")
            return "failed: parse_error"

        if amc_name is None or not rows:
            # A recognizably closed-ended file (FMP / Series / Dual Advantage —
            # see looks_closed_ended) that yields nothing is a matured scheme
            # absent from the AMFI master, not a parser defect: honest terminal
            # outcome, never re-queued by failed-row resets.
            if amc_name is not None and looks_closed_ended(original_filename):
                stats.status_override = "skipped"
                await _mark(
                    file_id,
                    "unsupported",
                    amc=amc_name,
                    period=period,
                    error="scheme_not_in_master",
                )
                return "unsupported: scheme_not_in_master"
            stats.status_override = "skipped"  # undetectable ≠ a pipeline failure
            await _mark(file_id, "unsupported", period=period, error="amc_or_period_undetectable")
            return "unsupported: amc_or_period_undetectable"

        rows_upserted, _aum_updates = await _upsert_constituents(rows, amc_name, run_id=run_id)
        stats.written = rows_upserted
        if rows_upserted == 0:
            # Distinguish the three honest causes of an empty upsert:
            #   1. Closed-ended scheme genuinely absent from the master
            #      (name lookup RE-CHECKED here, never assumed) → terminal
            #      'scheme_not_in_master', not an endlessly retryable failure.
            #   2. Names resolve but rows carried no usable as-of month →
            #      period problem, not a resolution problem — say so.
            #   3. Anything else → the pre-existing scheme-unresolved failure.
            from dhanradar.tasks.mf import _resolve_scheme_isins

            names = {r["scheme_name"] for r in rows if r.get("scheme_name")}
            resolved = await _resolve_scheme_isins(names, amc_name) if names else {}
            if not resolved and (
                looks_closed_ended(original_filename)
                or (names and all(looks_closed_ended(n) for n in names))
            ):
                stats.status_override = "skipped"
                await _mark(
                    file_id,
                    "unsupported",
                    amc=amc_name,
                    period=period,
                    error="scheme_not_in_master",
                )
                return "unsupported: scheme_not_in_master"
            stats.failed = 1
            stats.last_error = "zero_rows_upserted"
            error = (
                "zero_rows_upserted_period_missing"
                if resolved
                else "zero_rows_upserted_scheme_unresolved"
            )
            await _mark(file_id, "failed", amc=amc_name, period=period, error=error)
            return "failed: zero_rows_upserted"

        await _mark(file_id, "parsed", amc=amc_name, period=period, rows=rows_upserted)
        return f"parsed: {rows_upserted} rows amc={amc_name}"


async def _parse_special_class(
    file_id: str, file_class: str, data: bytes, original_filename: str, amc_hint: str | None
) -> str:
    """Parse + apply a non-portfolio disclosure class (aaum / riskometer /
    performance). Same fail-closed contract as the portfolio path: layout not
    recognized → 'unsupported'; parsed but zero schemes resolved to ISINs →
    'failed' (the file is kept for a resolution-tuning re-run); parser
    exception → 'failed: parse_error'.
    """
    from dhanradar.tasks.ingestion_run import ingestion_run

    ext = Path(original_filename).suffix.lower()
    amc_name = detect_amc(original_filename) or (detect_amc(amc_hint) if amc_hint else None)

    async with ingestion_run(TASK_PARSE, SOURCE) as (run_id, stats):
        stats.fetched = 1
        stats.reachable = True

        if amc_name is None:
            stats.status_override = "skipped"
            await _mark(file_id, "unsupported", error="amc_undetectable")
            return "unsupported: amc_undetectable"

        try:
            period, updates, resolved = await _apply_file_class(
                file_class, data, ext, original_filename, amc_name, run_id
            )
        except Exception as exc:  # noqa: BLE001 — fail-closed, never partial-silent
            stats.failed = 1
            stats.last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            await _mark(file_id, "failed", amc=amc_name, error=f"parse_error:{type(exc).__name__}")
            return "failed: parse_error"

        if updates is None:
            stats.status_override = "skipped"
            await _mark(
                file_id, "unsupported", amc=amc_name, error=f"{file_class}_layout_unrecognized"
            )
            return f"unsupported: {file_class}_layout_unrecognized"
        if resolved == 0:
            stats.failed = 1
            stats.last_error = "zero_schemes_resolved"
            await _mark(
                file_id,
                "failed",
                amc=amc_name,
                period=period,
                error="zero_rows_upserted_scheme_unresolved",
            )
            return f"failed: {file_class} zero_schemes_resolved"

        stats.written = updates
        await _mark(file_id, "parsed", amc=amc_name, period=period, rows=updates)
        return f"parsed: {file_class} updates={updates} amc={amc_name}"


async def _apply_file_class(
    file_class: str,
    data: bytes,
    ext: str,
    original_filename: str,
    amc_name: str,
    run_id: int | None,
) -> tuple[date | None, int | None, int]:
    """Parse one special file class and write its mf_funds fields.

    Returns (period, updates, resolved). updates=None means the layout was not
    recognized (caller marks 'unsupported'). resolved counts scheme names that
    matched an ISIN — resolved=0 is the honest failure ('nothing matched our
    master'), while resolved>0 with updates=0 is a legitimate no-op (e.g. every
    fund already carries a fresher net-assets AUM; the fill-only rule skipped
    all writes).

    Write rules (all values VERBATIM from the file, never derived):
      - aaum → `aum_crore`/`aum_as_of`, but only where NULL or OLDER — the
        monthly portfolio disclosure's stated net-assets figure (same field,
        written by `_upsert_constituents`) always wins over an average-AUM
        figure for the same or newer month. History rows use
        on_conflict_do_nothing for the same reason (ADR-0035: stated only).
      - riskometer → `risk_o_meter` (regulatory band word, pre-validated
        against the 6 official values by the parser).
      - performance → `benchmark_index` (the scheme's PRIMARY benchmark name —
        the plan §11 unblock for per-fund benchmark mapping).
      - scheme_master (SBI's per-scheme "Fund Details" HTML page, 2026-07-08)
        → `risk_o_meter` + `benchmark_index` (same fields as above, same
        rules) + `expense_ratio_pct` (a single current snapshot, no history
        row — the file states no "effective from" date we could honestly
        attribute to `expense_ratio_history`, so writing that table here
        would fabricate a date §8.4 forbids) + `fund_manager_history` (one
        row per manager, deduped against already-stored (scheme_uid,
        manager_name, start_date) tuples — the exact pattern
        `tasks/mf_fund_manager.py` already uses, never a second one).
      - ter (2026-07-09 — Total Expense Ratio disclosures: SBI/ABSL/
        Edelweiss/HDFC all publish a Regular-Plan-vs-Direct-Plan TER table)
        → `expense_ratio_pct`, written to EVERY option-variant ISIN
        (Growth/IDCW/Bonus/etc.) under each resolved plan — TER is a
        plan-level fee, identical across every option of the same plan, so
        a single top-1 fuzzy match (like other classes use) would silently
        leave sibling option ISINs stale. A simple overwrite (not fill-only)
        mirrors the scheme_master rule above: no `expense_ratio_history` row
        (no honest "effective from" date to attribute one to, §8.4).
    """
    from sqlalchemy import text as sa_text
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from dhanradar.db import TaskSessionLocal
    from dhanradar.mf.disclosure_parsers import (
        parse_aaum_annexure,
        parse_riskometer_annual,
        parse_scheme_master_details,
        parse_scheme_performance,
        parse_ter_disclosure,
    )
    from dhanradar.models.mf import MfAumHistory, MfFundManagerHistory
    from dhanradar.tasks.mf import _resolve_scheme_isins, _resolve_scheme_isins_by_plan

    if file_class == "aaum":
        period, pairs = parse_aaum_annexure(data, ext)
        period = period or detect_period_from_filename(original_filename)
        if not pairs:
            return period, None, 0
        isin_map = await _resolve_scheme_isins({name for name, _v in pairs}, amc_name)
        resolved = sum(1 for name, _v in pairs if name in isin_map)
        updates = 0
        async with TaskSessionLocal() as db:
            for name, aaum_cr in pairs:
                isin = isin_map.get(name)
                if not isin:
                    continue
                result = await db.execute(
                    sa_text(
                        "UPDATE mf.mf_funds SET aum_crore = :v, aum_as_of = :p "
                        "WHERE isin = :i AND (aum_as_of IS NULL OR aum_as_of < :p)"
                    ),
                    {"v": aaum_cr, "p": period, "i": isin},
                )
                updates += int(getattr(result, "rowcount", 0) or 0)
                if period is not None:
                    await db.execute(
                        pg_insert(MfAumHistory)
                        .values(
                            isin=isin,
                            aum_crore=aaum_cr,
                            as_of_month=period,
                            source=amc_name,
                            run_id=run_id,
                        )
                        .on_conflict_do_nothing(index_elements=["isin", "as_of_month"])
                    )
            await db.commit()
        return period, updates, resolved

    if file_class == "riskometer":
        band_pairs = parse_riskometer_annual(data, ext)
        # A file NAMED/classified "riskometer" can still carry a usable
        # benchmark table even when its own risk-o-meter LEVEL column is
        # blank (confirmed 2026-07-08: Kotak's annual riskometer file is a
        # change-COUNT disclosure, not a current-level one, but the same
        # workbook has a plain scheme->benchmark table) — try both parsers
        # on the same bytes rather than leaving that data stranded behind
        # the wrong file-class label.
        bench_pairs = parse_scheme_performance(data, ext)
        if not band_pairs and not bench_pairs:
            return None, None, 0

        all_names = {name for name, _b in band_pairs} | {name for name, _b in bench_pairs}
        isin_map = await _resolve_scheme_isins(all_names, amc_name)
        resolved = sum(1 for name in all_names if name in isin_map)
        updates = 0
        async with TaskSessionLocal() as db:
            for name, band in band_pairs:
                isin = isin_map.get(name)
                if not isin:
                    continue
                result = await db.execute(
                    sa_text("UPDATE mf.mf_funds SET risk_o_meter = :b WHERE isin = :i"),
                    {"b": band, "i": isin},
                )
                updates += int(getattr(result, "rowcount", 0) or 0)
            for name, bench in bench_pairs:
                isin = isin_map.get(name)
                if not isin:
                    continue
                result = await db.execute(
                    sa_text("UPDATE mf.mf_funds SET benchmark_index = :b WHERE isin = :i"),
                    {"b": bench, "i": isin},
                )
                updates += int(getattr(result, "rowcount", 0) or 0)
            await db.commit()
        return None, updates, resolved

    if file_class == "performance":
        bench_pairs = parse_scheme_performance(data, ext)
        if not bench_pairs:
            return None, None, 0
        isin_map = await _resolve_scheme_isins({name for name, _b in bench_pairs}, amc_name)
        resolved = sum(1 for name, _b in bench_pairs if name in isin_map)
        updates = 0
        async with TaskSessionLocal() as db:
            for name, bench in bench_pairs:
                isin = isin_map.get(name)
                if not isin:
                    continue
                result = await db.execute(
                    sa_text("UPDATE mf.mf_funds SET benchmark_index = :b WHERE isin = :i"),
                    {"b": bench, "i": isin},
                )
                updates += int(getattr(result, "rowcount", 0) or 0)
            await db.commit()
        return None, updates, resolved

    if file_class in ("scheme_master", "scheme_master_pdf"):
        if file_class == "scheme_master_pdf":
            from dhanradar.mf.disclosure_parsers import parse_scheme_master_pdf

            parsed = parse_scheme_master_pdf(data)
        else:
            parsed = parse_scheme_master_details(data)
        scheme_name = parsed.get("scheme_name")
        if not scheme_name:
            return None, None, 0
        isin_map = await _resolve_scheme_isins({scheme_name}, amc_name)
        isin = isin_map.get(scheme_name)
        resolved = 1 if isin else 0
        if not isin:
            return None, 0, 0

        updates = 0
        async with TaskSessionLocal() as db:
            if parsed.get("risk_band"):
                result = await db.execute(
                    sa_text("UPDATE mf.mf_funds SET risk_o_meter = :b WHERE isin = :i"),
                    {"b": parsed["risk_band"], "i": isin},
                )
                updates += int(getattr(result, "rowcount", 0) or 0)
            if parsed.get("benchmark_tier1"):
                result = await db.execute(
                    sa_text("UPDATE mf.mf_funds SET benchmark_index = :b WHERE isin = :i"),
                    {"b": parsed["benchmark_tier1"], "i": isin},
                )
                updates += int(getattr(result, "rowcount", 0) or 0)
            if parsed.get("exit_load_pct") is not None:
                result = await db.execute(
                    sa_text(
                        "UPDATE mf.mf_funds SET exit_load_pct = :p, "
                        "exit_load_days = COALESCE(:d, exit_load_days) WHERE isin = :i"
                    ),
                    {
                        "p": parsed["exit_load_pct"],
                        "d": parsed.get("exit_load_days"),
                        "i": isin,
                    },
                )
                updates += int(getattr(result, "rowcount", 0) or 0)
            if parsed.get("ter_pct") is not None:
                # Single current-snapshot mirror onto mf_funds — same field
                # `mf_expense_ratio_fetch` maintains from factsheets, so a
                # simple overwrite (not fill-only) keeps whichever source ran
                # most recently as the current value. No `expense_ratio_history`
                # row: this file states no "effective from" date to honestly
                # attribute one to (§8.4 — never fabricate a date).
                result = await db.execute(
                    sa_text("UPDATE mf.mf_funds SET expense_ratio_pct = :v WHERE isin = :i"),
                    {"v": parsed["ter_pct"], "i": isin},
                )
                updates += int(getattr(result, "rowcount", 0) or 0)
            manager_pairs = parsed.get("manager_pairs") or []
            if manager_pairs:
                existing = await db.execute(
                    sa_text(
                        "SELECT manager_name, start_date FROM mf.fund_manager_history "
                        "WHERE scheme_uid = :i"
                    ),
                    {"i": isin},
                )
                existing_tuples = {(row[0], row[1]) for row in existing}
                new_rows = [
                    {
                        "scheme_uid": isin,
                        "manager_name": name,
                        "start_date": start,
                        "end_date": None,
                        "source": amc_name,
                        "run_id": run_id,
                    }
                    for name, start in manager_pairs
                    if (name, start) not in existing_tuples
                ]
                if new_rows:
                    await db.execute(pg_insert(MfFundManagerHistory).values(new_rows))
                    updates += len(new_rows)
            await db.commit()
        return None, updates, resolved

    if file_class == "ter":
        ter_rows = parse_ter_disclosure(data, ext)
        if not ter_rows:
            return None, None, 0

        resolved = 0
        updates = 0
        latest_period: date | None = None
        async with TaskSessionLocal() as db:
            for scheme_name, ter_date, regular_pct, direct_pct in ter_rows:
                if latest_period is None or ter_date > latest_period:
                    latest_period = ter_date
                regular_isins, direct_isins = await _resolve_scheme_isins_by_plan(
                    scheme_name, amc_name
                )
                if not regular_isins and not direct_isins:
                    continue
                resolved += 1
                for isin in regular_isins:
                    result = await db.execute(
                        sa_text("UPDATE mf.mf_funds SET expense_ratio_pct = :v WHERE isin = :i"),
                        {"v": regular_pct, "i": isin},
                    )
                    updates += int(getattr(result, "rowcount", 0) or 0)
                for isin in direct_isins:
                    result = await db.execute(
                        sa_text("UPDATE mf.mf_funds SET expense_ratio_pct = :v WHERE isin = :i"),
                        {"v": direct_pct, "i": isin},
                    )
                    updates += int(getattr(result, "rowcount", 0) or 0)
            await db.commit()
        return latest_period, updates, resolved

    raise ValueError(f"unknown file_class: {file_class}")  # unreachable by construction


# ---------------------------------------------------------------------------
# Channel B — watched folder. Beat, every 15 min.
# ---------------------------------------------------------------------------


@celery_app.task(name=TASK_SCAN_FOLDER)
def scan_incoming_folder() -> str:
    try:
        return asyncio.run(_scan_incoming_pipeline())
    except Exception:  # noqa: BLE001
        logger.exception("manual_ingest scan_incoming_folder failed")
        return "failed"


def _unique_dest(dest_dir: Path, name: str) -> Path:
    """Avoid clobbering a same-named file already moved into processed/failed."""
    dest = dest_dir / name
    if not dest.exists():
        return dest
    stem, suffix = Path(name).stem, Path(name).suffix
    return dest_dir / f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"


def _list_incoming(incoming: Path) -> list[tuple[Path, str | None]]:
    """Flat files at the top level (amc_hint=None) + one level of per-AMC
    subfolders (e.g. incoming/HDFC/file.xlsx -> amc_hint='HDFC'). Never
    recurses past that one level — a subfolder's own subfolders are ignored."""
    entries: list[tuple[Path, str | None]] = []
    for path in sorted(incoming.iterdir()):
        if path.is_file():
            entries.append((path, None))
        elif path.is_dir():
            for sub in sorted(path.iterdir()):
                if sub.is_file():
                    entries.append((sub, path.name))
    return entries


async def _scan_incoming_pipeline() -> str:
    from dhanradar.config import settings

    root = Path(settings.MANUAL_INGEST_DIR)
    incoming = root / "incoming"
    processed_dir = root / "processed"
    failed_dir = root / "failed"
    incoming.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    n_ok = n_dup = n_bad = n_skipped = 0
    for path, amc_hint in _list_incoming(incoming):
        try:
            data = path.read_bytes()
        except OSError:
            logger.warning("manual_ingest: could not read %s — leaving in place", path.name)
            continue

        extracted, skipped = await intake_upload(data, path.name, "folder", None, amc_hint)
        n_skipped += len(skipped)
        if not extracted:
            # 0 eligible members — a bad extension, or a zip that yielded
            # nothing usable (encrypted/corrupt/too-many-members/all-skipped).
            logger.info(
                "manual_ingest: unsupported — %s (0 eligible members, skipped=%s)",
                path.name,
                skipped,
            )
        elif skipped:
            logger.info(
                "manual_ingest: %s partially skipped %d member(s): %s",
                path.name,
                len(skipped),
                skipped,
            )

        for _name, result in extracted:
            if result.status == "unsupported":
                n_bad += 1
            elif result.status == "duplicate":
                n_dup += 1
            else:
                n_ok += 1

        all_unsupported = (not extracted) or all(r.status == "unsupported" for _n, r in extracted)
        dest_dir = failed_dir if all_unsupported else processed_dir
        try:
            # Flat processed/failed dirs — subfolders are never mirrored.
            shutil.move(str(path), str(_unique_dest(dest_dir, path.name)))
        except OSError:
            logger.warning("manual_ingest: could not move %s to %s", path.name, dest_dir)

    return f"scanned: ok={n_ok} dup={n_dup} unsupported={n_bad} zip_skipped={n_skipped}"


# ---------------------------------------------------------------------------
# Stuck-file reaper (2026-07-08, celery-resilience hardening) — beat, every 5 min.
# ---------------------------------------------------------------------------


@celery_app.task(name=TASK_REAP_STUCK)
def reap_stuck_manual_ingest_files() -> str:
    """Beat task: mark manual_ingest_files rows stuck in 'pending' for more than
    30 minutes as failed='stuck_timeout'.

    Complements the celery-wide task_time_limit safety net (celery_app.py): if
    parse_manual_disclosure_file is ever hard-killed mid-flight (task_time_limit
    SIGKILL, worker OOM, host restart), the row is left at 'pending' forever
    with no automatic self-heal — unlike CAS jobs, which already have
    reap_stuck_cas_jobs (tasks/mf.py). 30 min is generous: real prod parses
    complete in sub-second-to-low-seconds per file; a reaped row is a plain
    'status=pending, error=NULL' reset away from being re-processed (see the
    runbook footgun note in MANUAL_DATA_DOWNLOAD_RUNBOOK.md for the correct
    re-enqueue pattern).

    Safe to run every few minutes — idempotent (WHERE status='pending' guards
    against re-touching an already-terminal row).
    """
    try:
        return asyncio.run(_reap_stuck_manual_ingest_files())
    except Exception:  # noqa: BLE001
        logger.exception("reap_stuck_manual_ingest_files pipeline error")
        return "reap_stuck_manual_ingest_files: failed — see worker logs"


async def _reap_stuck_manual_ingest_files() -> str:
    from sqlalchemy import or_, select, update

    from dhanradar.db import admin_task_session
    from dhanradar.models.mf import MfManualIngestFile

    cutoff = datetime.now(UTC) - timedelta(minutes=30)

    async with admin_task_session() as db:
        # A pending row is stuck only when it shows NO recent activity on
        # EITHER timestamp. Keying on received_at alone killed every bulk
        # RE-PARSE (2026-07-10: 454 of 477 reset rows reaped mid-drain —
        # reset rows are days old by received_at, and this beat fires every
        # 5 min). The runbook's re-parse reset stamps parsed_at=now() so each
        # reset row gets a fresh 30-min window; genuinely fresh files have
        # parsed_at NULL and keep the original received_at behavior.
        result = await db.execute(
            select(MfManualIngestFile.id).where(
                MfManualIngestFile.status == "pending",
                MfManualIngestFile.received_at < cutoff,
                or_(
                    MfManualIngestFile.parsed_at.is_(None),
                    MfManualIngestFile.parsed_at < cutoff,
                ),
            )
        )
        ids = [r[0] for r in result.all()]

        if not ids:
            logger.debug("reap_stuck_manual_ingest_files: nothing to reap")
            return "reaped 0 stuck manual-ingest files"

        await db.execute(
            update(MfManualIngestFile)
            .where(MfManualIngestFile.id.in_(ids))  # type: ignore[arg-type]
            .values(status="failed", error="stuck_timeout")
        )
        await db.commit()

    return f"reaped {len(ids)} stuck manual-ingest file(s)"


# ---------------------------------------------------------------------------
# Channel C — email poller. Beat, every 30 min. DORMANT-SAFE.
# ---------------------------------------------------------------------------


@celery_app.task(name=TASK_POLL_EMAIL)
def poll_email_inbox() -> str:
    try:
        return asyncio.run(_poll_email_pipeline())
    except Exception:  # noqa: BLE001
        logger.exception("manual_ingest poll_email_inbox failed")
        return "failed"


async def _poll_email_pipeline() -> str:
    from dhanradar.config import settings

    if not (
        settings.MANUAL_INGEST_IMAP_HOST
        and settings.MANUAL_INGEST_IMAP_USER
        and settings.MANUAL_INGEST_IMAP_PASSWORD
    ):
        logger.info("manual_ingest: IMAP not configured — dormant, skipping")
        return "skipped: not_configured"

    allowlist = settings.manual_ingest_sender_allowlist
    if not allowlist:
        logger.warning(
            "manual_ingest: MANUAL_INGEST_SENDER_ALLOWLIST is empty — no sender can pass"
        )
        return "skipped: empty_allowlist"

    n_ingested = 0
    n_rejected = 0

    conn = imaplib.IMAP4_SSL(settings.MANUAL_INGEST_IMAP_HOST)
    try:
        conn.login(settings.MANUAL_INGEST_IMAP_USER, settings.MANUAL_INGEST_IMAP_PASSWORD)
        conn.select("INBOX")
        status, data = conn.search(None, "UNSEEN")
        if status != "OK":
            logger.warning("manual_ingest: IMAP search failed status=%s", status)
            return "failed: search"

        for mid in data[0].split():
            fstatus, msg_data = conn.fetch(mid, "(RFC822)")
            if fstatus != "OK" or not msg_data or msg_data[0] is None:
                continue
            item = msg_data[0]
            if not isinstance(item, tuple) or not isinstance(item[1], bytes):
                continue  # unexpected IMAP response shape — skip rather than crash
            msg = email.message_from_bytes(item[1])
            sender = email.utils.parseaddr(msg.get("From", ""))[1].lower()

            if sender not in allowlist:
                n_rejected += 1
                conn.store(mid, "+FLAGS", "\\Seen")  # mark seen — never reprocess forever
                continue

            for part in msg.walk():
                filename = part.get_filename()
                if not filename:
                    continue
                ext = Path(filename).suffix.lower()
                if ext not in ALLOWED_EXTENSIONS and ext != ZIP_EXTENSION:
                    continue
                payload = part.get_payload(decode=True)
                if not isinstance(payload, bytes) or not payload:
                    continue
                extracted, _skipped = await intake_upload(payload, filename, "email", None)
                n_ingested += len(extracted)

            conn.store(mid, "+FLAGS", "\\Seen")
    finally:
        try:
            conn.logout()
        except Exception:  # noqa: BLE001 — logout failure must never mask the real result
            pass

    return f"polled: ingested={n_ingested} rejected_sender={n_rejected}"
