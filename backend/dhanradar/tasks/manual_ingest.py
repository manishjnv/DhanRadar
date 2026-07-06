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
from datetime import UTC, date, datetime
from pathlib import Path

from dhanradar.celery_app import celery_app
from dhanradar.mf.manual_ingest import detect_amc_and_parse, intake_file

logger = logging.getLogger(__name__)

TASK_PARSE = "dhanradar.tasks.manual_ingest.parse_manual_disclosure_file"
TASK_SCAN_FOLDER = "dhanradar.tasks.manual_ingest.scan_incoming_folder"
TASK_POLL_EMAIL = "dhanradar.tasks.manual_ingest.poll_email_inbox"
SOURCE = "manual_disclosure_inbox"


# ---------------------------------------------------------------------------
# Parse task — enqueued per file by intake_file(), never scheduled.
# ---------------------------------------------------------------------------


@celery_app.task(name=TASK_PARSE, bind=True, max_retries=2)
def parse_manual_disclosure_file(self, file_id: str) -> str:
    try:
        return asyncio.run(_parse_pipeline(file_id))
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


async def _parse_pipeline(file_id: str) -> str:
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

    data = path.read_bytes()

    async with ingestion_run(TASK_PARSE, SOURCE) as (run_id, stats):
        stats.fetched = 1
        stats.reachable = True  # a local file read is never a reachability issue

        try:
            amc_name, period, rows = detect_amc_and_parse(data, original_filename)
        except Exception as exc:  # noqa: BLE001 — fail-closed, never partial-silent
            stats.failed = 1
            stats.last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            await _mark(file_id, "failed", error=f"parse_error:{type(exc).__name__}")
            return "failed: parse_error"

        if amc_name is None or not rows:
            stats.status_override = "skipped"  # undetectable ≠ a pipeline failure
            await _mark(
                file_id, "unsupported", period=period, error="amc_or_period_undetectable"
            )
            return "unsupported: amc_or_period_undetectable"

        rows_upserted, _aum_updates = await _upsert_constituents(rows, amc_name, run_id=run_id)
        stats.written = rows_upserted
        if rows_upserted == 0:
            stats.failed = 1
            stats.last_error = "zero_rows_upserted"
            await _mark(
                file_id, "failed", amc=amc_name, period=period,
                error="zero_rows_upserted_scheme_unresolved",
            )
            return "failed: zero_rows_upserted"

        await _mark(file_id, "parsed", amc=amc_name, period=period, rows=rows_upserted)
        return f"parsed: {rows_upserted} rows amc={amc_name}"


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


async def _scan_incoming_pipeline() -> str:
    from dhanradar.config import settings

    root = Path(settings.MANUAL_INGEST_DIR)
    incoming = root / "incoming"
    processed_dir = root / "processed"
    failed_dir = root / "failed"
    incoming.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    n_ok = n_dup = n_bad = 0
    for path in sorted(incoming.iterdir()):
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            logger.warning("manual_ingest: could not read %s — leaving in place", path.name)
            continue

        result = await intake_file(data, path.name, "folder", None)
        dest_dir = failed_dir if result.status == "unsupported" else processed_dir
        try:
            shutil.move(str(path), str(_unique_dest(dest_dir, path.name)))
        except OSError:
            logger.warning("manual_ingest: could not move %s to %s", path.name, dest_dir)

        if result.status == "unsupported":
            n_bad += 1
        elif result.status == "duplicate":
            n_dup += 1
        else:
            n_ok += 1

    return f"scanned: ok={n_ok} dup={n_dup} unsupported={n_bad}"


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
                if ext not in (".xls", ".xlsx"):
                    continue
                payload = part.get_payload(decode=True)
                if not isinstance(payload, bytes) or not payload:
                    continue
                await intake_file(payload, filename, "email", None)
                n_ingested += 1

            conn.store(mid, "+FLAGS", "\\Seen")
    finally:
        try:
            conn.logout()
        except Exception:  # noqa: BLE001 — logout failure must never mask the real result
            pass

    return f"polled: ingested={n_ingested} rejected_sender={n_rejected}"
