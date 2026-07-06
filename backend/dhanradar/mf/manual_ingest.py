"""
DhanRadar — Manual disclosure ingestion inbox: shared intake service.

The 5 top-10-AUM AMCs `mf_constituents_fetch` cannot scrape (HDFC/SBI/ICICI-Pru/
Kotak/Axis — Akamai/Radware bot-block, see `_AMC_DISCLOSURE_ROOTS` in
dhanradar/tasks/mf.py) still publish the SAME SEBI-mandated monthly portfolio
disclosure file; a human downloads it and drops it via one of 3 channels:

  A) admin/manual_ingest_router.py  — POST /admin/ingest/disclosure-files (multipart)
  B) tasks/manual_ingest.py::scan_incoming_folder — watched MANUAL_INGEST_DIR/incoming/
  C) tasks/manual_ingest.py::poll_email_inbox     — IMAP UNSEEN attachments (dormant
     unless MANUAL_INGEST_IMAP_* env is set)

All 3 channels call `intake_file()` below — the ONE place that validates,
dedups, persists, and enqueues. Untrusted input handling: extension allowlist
(.xls/.xlsx only this wave), a hard size cap, sha256-keyed dedup (DB unique
constraint is the real backstop — a pre-check SELECT is just the common-case
fast path), and a uuid-named on-disk filename (the original name is kept ONLY
as a DB string, never used to build a path or shell command).
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

# .xls/.xlsx ONLY this wave — factsheet PDFs are a later parser (contract §2).
ALLOWED_EXTENSIONS: tuple[str, ...] = (".xls", ".xlsx")
MAX_BYTES = 25 * 1024 * 1024  # 25 MB cap


@dataclass(frozen=True)
class IntakeResult:
    file_id: str | None
    status: str  # 'pending' | 'duplicate' | 'unsupported'
    error: str | None = None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _store_dir() -> Path:
    """Canonical on-disk storage for every intake channel's file — decoupled from
    MANUAL_INGEST_DIR/incoming (the folder-watch drop zone only; see
    tasks/manual_ingest.py::scan_incoming_folder), so the parse task always reads
    from one predictable place regardless of which channel delivered the file."""
    from dhanradar.config import settings

    d = Path(settings.MANUAL_INGEST_DIR) / "store"
    d.mkdir(parents=True, exist_ok=True)
    return d


def stored_path_for(file_id: str, original_filename: str) -> Path:
    """Reconstruct the on-disk path for a row — uuid-named, never the original
    filename (never used to build a path or shell command)."""
    ext = Path(original_filename).suffix.lower()
    return _store_dir() / f"{file_id}{ext}"


async def intake_file(
    data: bytes,
    original_filename: str,
    channel: str,
    uploaded_by: str | None,
) -> IntakeResult:
    """Validate, dedup, persist, and enqueue one file. Called by all 3 channels.

    `channel` is 'upload' | 'folder' | 'email'. `uploaded_by` is the admin's
    user_id for channel='upload', else None (folder/email have no authenticated
    actor). Every VALIDATION outcome (bad extension, oversized, empty, dedup) is
    a returned status, never an exception — callers don't need a try/except for
    those. A genuine infra failure (DB unreachable) still raises; each channel's
    caller already runs inside its own fail-closed wrapper (the route's global
    500 handler; the Celery task's outer try/except), so this is never silent.
    """
    from dhanradar.db import TaskSessionLocal
    from dhanradar.models.mf import MfManualIngestFile

    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return IntakeResult(None, "unsupported", f"unsupported_extension:{ext or 'none'}")
    if not data:
        return IntakeResult(None, "unsupported", "empty_file")
    if len(data) > MAX_BYTES:
        return IntakeResult(None, "unsupported", "file_too_large")

    digest = sha256_bytes(data)

    try:
        uploader_uuid = uuid.UUID(uploaded_by) if uploaded_by else None
    except ValueError:
        uploader_uuid = None  # malformed id — store as anonymous rather than fail the intake

    async with TaskSessionLocal() as db:
        existing_id = await db.scalar(
            select(MfManualIngestFile.id).where(MfManualIngestFile.sha256 == digest)
        )
        if existing_id is not None:
            return IntakeResult(str(existing_id), "duplicate", None)

        file_id = uuid.uuid4()
        stored_path = stored_path_for(str(file_id), original_filename)
        stored_path.write_bytes(data)

        db.add(
            MfManualIngestFile(
                id=file_id,
                sha256=digest,
                original_filename=original_filename[:512],
                channel=channel,
                uploaded_by=uploader_uuid,
                status="pending",
            )
        )
        try:
            await db.commit()
        except IntegrityError:
            # Race: another channel/request inserted the same sha256 first (unique
            # constraint is the real backstop — the SELECT above is only the
            # common-case fast path). Drop our copy; the winner's row already has
            # its own parse enqueued.
            await db.rollback()
            stored_path.unlink(missing_ok=True)
            return IntakeResult(None, "duplicate", None)

    from dhanradar.tasks.manual_ingest import parse_manual_disclosure_file

    parse_manual_disclosure_file.delay(str(file_id))
    return IntakeResult(str(file_id), "pending", None)


# ---------------------------------------------------------------------------
# AMC detection — filename first, then a scheme-name keyword fallback.
# Reuses dhanradar.tasks.mf._parse_sebi_xlsx (the SAME parser the automated
# scraper uses) — never a second parser.
# ---------------------------------------------------------------------------

# Keyword → canonical AMC name (matches the `name` values in
# dhanradar.tasks.mf._AMC_DISCLOSURE_ROOTS, so a detected name routes straight
# into the existing _upsert_constituents / _resolve_scheme_isins AMC-prefix
# matching without translation). The 5 bot-blocked AMCs this wave targets are
# first; the rest are free coverage since the parser is AMC-agnostic anyway.
_AMC_KEYWORDS: dict[str, str] = {
    "hdfc": "HDFC",
    "sbi": "SBI",
    "icici": "ICICI_PRU",
    "kotak": "KOTAK",
    "axis": "AXIS",
    "uti": "UTI",
    "nippon": "NIPPON",
    "mirae": "MIRAE",
    "franklin": "FRANKLIN",
    "dsp": "DSP",
}


def detect_amc(text: str) -> str | None:
    """Keyword match against a filename or scheme name. Pure — unit-testable."""
    low = text.lower()
    for kw, amc in _AMC_KEYWORDS.items():
        if kw in low:
            return amc
    return None


def detect_amc_and_parse(
    data: bytes, original_filename: str
) -> tuple[str | None, date | None, list[dict]]:
    """Detect the AMC + disclosure month and parse constituent rows in one pass.

    Filename first (cheap, no parse needed); if that fails, parse once with a
    placeholder AMC name and fall back to matching the first parsed scheme name.
    Returns (amc_name, period, rows). `amc_name` is None when undetectable — the
    caller (tasks/manual_ingest.py::parse_manual_disclosure_file) treats that as
    `status='unsupported'`. May raise on a genuinely corrupt/legacy-binary .xls
    openpyxl cannot open — the caller catches that and marks the file 'failed'
    (fail-closed, never partial-silent, per contract §3).
    """
    from dhanradar.tasks.mf import _parse_sebi_xlsx  # reuse — never a second parser

    amc_guess = detect_amc(original_filename)
    rows = _parse_sebi_xlsx(data, amc_guess or "UNKNOWN")

    amc_name = amc_guess
    if amc_name is None:
        for row in rows:
            scheme_name = row.get("scheme_name") or ""
            amc_name = detect_amc(scheme_name)
            if amc_name:
                break

    period = next((r["as_of_month"] for r in rows if r.get("as_of_month")), None)
    return amc_name, period, rows
