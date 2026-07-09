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
(.xls/.xlsx/.pdf), a hard size cap, sha256-keyed dedup (DB unique constraint
is the real backstop — a pre-check SELECT is just the common-case fast
path), and a uuid-named on-disk filename (the original name is kept ONLY as
a DB string, never used to build a path or shell command). PDFs are stored
and dedup'd identically but never parsed — the parse task marks them
'archived' immediately (factsheet-PDF parsing is a future wave).

`intake_upload()` is the ZIP-aware entry point every channel should call
instead of `intake_file()` directly: a `.zip` is NEVER stored as a row
itself — it is expanded in memory (`expand_zip()`) and each eligible member
goes through `intake_file()` individually (member basename as
original_filename, same channel/uploader/amc_hint). Plain (non-zip) input is
an unchanged 1-element pass-through.
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
import uuid
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

# .xls/.xlsx/.pdf — PDFs are accepted + archived (never parsed, contract §2).
ALLOWED_EXTENSIONS: tuple[str, ...] = (".xls", ".xlsx", ".pdf")
MAX_BYTES = 25 * 1024 * 1024  # 25 MB cap — applies per file AND per zip member

ZIP_EXTENSION = ".zip"
# Raised 50 → 1000 (2026-07-07): SBI's real per-scheme portfolio zips carry 441/57/156
# members — the original cap whole-rejected all three. The bomb guard is the TOTAL
# uncompressed budget below (checked against central-directory sizes BEFORE any
# decompression), not the member count; 1000 is a runaway backstop, not the defense.
MAX_ZIP_MEMBERS = 1000  # counts every zip entry incl. directories — cheap, safe cap
# Raised 100 MB → 300 MB (2026-07-07): 441 per-scheme xlsx members at ~0.2–0.7 MB each
# brush the old budget; members are still read one at a time, each ≤ MAX_BYTES.
MAX_ZIP_TOTAL_BYTES = 300 * 1024 * 1024  # uncompressed total across all members


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
    amc_hint: str | None = None,
) -> IntakeResult:
    """Validate, dedup, persist, and enqueue one file. Called by all 3 channels
    (directly for a plain file, or via `intake_upload()` per zip member).

    `channel` is 'upload' | 'folder' | 'email'. `uploaded_by` is the admin's
    user_id for channel='upload', else None (folder/email have no authenticated
    actor). `amc_hint` is the per-AMC subfolder name for channel='folder' (None
    otherwise) — threaded through to the parse task as a detection fallback,
    never used for validation here. Every VALIDATION outcome (bad extension,
    oversized, empty, dedup) is a returned status, never an exception —
    callers don't need a try/except for those. A genuine infra failure (DB
    unreachable) still raises; each channel's caller already runs inside its
    own fail-closed wrapper (the route's global 500 handler; the Celery task's
    outer try/except), so this is never silent.
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

    parse_manual_disclosure_file.delay(str(file_id), amc_hint)
    return IntakeResult(str(file_id), "pending", None)


# ---------------------------------------------------------------------------
# ZIP intake — expand in memory, never store the zip itself as a row.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ZipExpansion:
    eligible: list[tuple[str, bytes]]  # (member_basename, bytes) — already decompressed
    skipped: list[tuple[str, str]]  # (member_name_or_original, reason)


def expand_zip(data: bytes, original_filename: str) -> ZipExpansion:
    """Expand a `.zip` in memory. Every guard checks `ZipInfo.file_size` (the
    UNCOMPRESSED size, known from the central directory) BEFORE any bytes are
    decompressed, so a crafted zip-bomb is rejected without ever inflating it.
    Member names are NEVER used to build a path — only `Path(name).name` (a
    basename string) reaches `intake_file()`, same rule as `stored_path_for`.

    Whole-zip rejections (encrypted / too many members / corrupt) return an
    empty `eligible` list with a single skip entry naming the reason — callers
    treat "0 eligible members" as one uniform outcome regardless of cause.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        infos = zf.infolist()
    except zipfile.BadZipFile:
        return ZipExpansion([], [(original_filename, "corrupt_zip")])

    if any(info.flag_bits & 0x1 for info in infos):
        # Traditional PKWARE encryption bit — reject the whole zip outright,
        # never attempt to read a member (fail-closed, contract §1).
        return ZipExpansion([], [(original_filename, "encrypted_zip")])
    if len(infos) > MAX_ZIP_MEMBERS:
        return ZipExpansion([], [(original_filename, "too_many_members")])

    eligible: list[tuple[str, bytes]] = []
    skipped: list[tuple[str, str]] = []
    budget = MAX_ZIP_TOTAL_BYTES

    for info in infos:
        if info.is_dir():
            continue  # directories are structure, not abuse — silently skipped
        name = Path(info.filename).name  # basename ONLY — never a path
        suffix = Path(name).suffix.lower()
        if suffix == ZIP_EXTENSION:
            skipped.append((name, "nested_zip"))  # never recursed
            continue
        if suffix not in ALLOWED_EXTENSIONS:
            skipped.append((name, f"unsupported_extension:{suffix or 'none'}"))
            continue
        if info.file_size > MAX_BYTES:
            skipped.append((name, "file_too_large"))
            continue
        if info.file_size > budget:
            skipped.append((name, "zip_total_size_exceeded"))
            continue
        try:
            member_bytes = zf.read(info.filename)
        except (zipfile.BadZipFile, RuntimeError, OSError):
            # Corrupt member / mid-archive read failure — skip, never crash.
            skipped.append((name, "member_read_error"))
            continue
        budget -= info.file_size
        eligible.append((name, member_bytes))

    return ZipExpansion(eligible, skipped)


async def intake_upload(
    data: bytes,
    original_filename: str,
    channel: str,
    uploaded_by: str | None,
    amc_hint: str | None = None,
) -> tuple[list[tuple[str, IntakeResult]], list[tuple[str, str]]]:
    """ZIP-aware entry point — every channel calls this instead of
    `intake_file()` directly. A plain (non-zip) file is an unchanged
    1-element pass-through; a `.zip` is expanded (`expand_zip()`) and each
    eligible member is intake_file()'d individually. Returns
    (extracted [(member_name, IntakeResult), ...], skipped [(name, reason), ...]).
    """
    if Path(original_filename).suffix.lower() != ZIP_EXTENSION:
        result = await intake_file(data, original_filename, channel, uploaded_by, amc_hint)
        return [(original_filename, result)], []

    expansion = expand_zip(data, original_filename)
    extracted: list[tuple[str, IntakeResult]] = []
    for member_name, member_data in expansion.eligible:
        result = await intake_file(member_data, member_name, channel, uploaded_by, amc_hint)
        extracted.append((member_name, result))
    return extracted, expansion.skipped


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
    # Edelweiss's own filename convention abbreviates to "EDEL_" (not the full
    # "EDELWEISS_"), while its watched-subfolder hint is the full "Edelweiss" name —
    # "edel" is the one substring present (lowercased) in BOTH, so a single keyword
    # covers filename detection, scheme-name fallback, AND the folder hint. Not added
    # to tasks.mf._AMC_DISCLOSURE_ROOTS — that list is the automated-scraper source
    # registry, a separate (unverified, out-of-scope) concern from manual-ingest AMC
    # recognition.
    "edel": "EDELWEISS",
    # PPFAS files/folders say "PPFAS" or "Parag Parikh" — scheme names only the latter.
    "ppfas": "PPFAS",
    "parag": "PPFAS",
    # ABSL files say "ABSLMF"; scheme names say "Aditya Birla Sun Life ..." —
    # two keywords cover filenames, folder hints, AND the scheme-name fallback.
    "absl": "ABSL",
    "birla": "ABSL",
    # HSBC (KVM4-unreachable site -> manual-only AMC; founder's 49 per-scheme
    # May-2026 files, 2026-07-07). Master scheme names start "HSBC ..." so the
    # resolver's default prefix works without an override.
    "hsbc": "HSBC",
    # TATA (B87, added 2026-07-08): genuinely new AMC — no prior recognition at
    # all. Master scheme names start "Tata ..." so the resolver's default
    # AMC-name-as-prefix matching works without an override, same as HSBC.
    "tata": "TATA",
    # B90 (added 2026-07-08/09): 4 new AMCs, all with a plain single-keyword
    # match against BOTH their real filename convention and their scheme-name
    # prefix — no abbreviation split needed (unlike ABSL/Edelweiss above).
    "motilal": "MOTILAL_OSWAL",
    "canara": "CANARA_ROBECO",
    "navi": "NAVI",
    "zerodha": "ZERODHA",
    # BHARAT 22 ETF is an ICICI Prudential-managed CPSE scheme whose file AND
    # master name (`mf_funds` "BHARAT 22 ETF", INF109KB15Y7) carry no "ICICI"
    # anywhere (confirmed 2026-07-10 — 2 real inbox files failed
    # amc_undetectable). Resolver-side, `_amc_scheme_prefixes` in tasks/mf.py
    # pairs this with a "BHARAT 22%" prefix for ICICI_PRU.
    "bharat 22": "ICICI_PRU",
    # QUANTUM (2026-07-10, joins the automated scraper): filenames and scheme
    # names both say "Quantum". NOTE: deliberately the full word — "quant"
    # would collide with Quant MF (a different AMC, manual-download list).
    "quantum": "QUANTUM",
}


def detect_amc(text: str) -> str | None:
    """Keyword match against a filename or scheme name. Pure — unit-testable."""
    low = text.lower()
    for kw, amc in _AMC_KEYWORDS.items():
        if kw in low:
            return amc
    return None


_MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
# Filename period patterns, tried in order (most specific first). Real evidence
# (2026-07-07): several AMCs put the disclosure month ONLY in the filename —
# KOTAK "…PortfolioMay2026.xlsx", "…PortfolioJune302026.xlsx",
# EDEL "…Notes 31-May-2026_….xlsx" — while their sheets carry no as-on line the
# sheet-level detection can find. Fail-closed: an unparseable match yields None.
_FILENAME_PERIOD_RES = (
    # 31-May-2026 · 30Jun2026 · 15_06 handled by sheet parse; this is DD-Mon-YYYY
    re.compile(rf"(\d{{1,2}})[-_ ]?({_MONTHS})[a-z]*[-_ ]?(\d{{4}})", re.IGNORECASE),
    # June302026 (month name directly followed by day+year)
    re.compile(rf"({_MONTHS})[a-z]*[-_ ]?(\d{{1,2}})[-_ ]?(\d{{4}})", re.IGNORECASE),
    # May2026 · May_2026 · May 2026 (month name + year, no day)
    re.compile(rf"({_MONTHS})[a-z]*[-_ ]?(\d{{4}})", re.IGNORECASE),
)


def detect_period_from_filename(filename: str) -> date | None:
    """Extract the disclosure month from a filename — pure, fail-closed.

    Used ONLY as a fallback when the sheet parse found rows but no as-on date
    (`detect_amc_and_parse` below). Returns the first day of the month.

    A disclosure always describes a PAST (or at most the current) month, so a
    match beyond next month is rejected and scanning continues — target-maturity
    scheme names ("ICICI Prudential Nifty SDL Sep 2027 Index Fund.xlsx") embed
    their MATURITY month, which this fallback used to stamp onto every holding
    as the as-of month (244 future-dated constituent rows in prod, 2026-07-10).
    """
    today = datetime.now().date()
    max_month = date(today.year + (today.month // 12), (today.month % 12) + 1, 1)
    for pattern in _FILENAME_PERIOD_RES:
        for m in pattern.finditer(filename):
            groups = m.groups()
            month_str = next(g for g in groups if g and g[0].isalpha())
            year_str = groups[-1]
            try:
                parsed = datetime.strptime(f"01-{month_str[:3]}-{year_str}", "%d-%b-%Y")
            except ValueError:
                continue
            candidate = parsed.date().replace(day=1)
            if 2000 <= candidate.year and candidate <= max_month:
                return candidate
    return None


# Closed-ended / matured scheme markers — FMPs, fixed-term series, dual-advantage
# and capital-protection series wind up and leave the AMFI master; their
# disclosure files can NEVER resolve to an ISIN. Word-boundary matched so
# open-ended names are untouched (real evidence 2026-07-10: "SBI Debt Fund
# Series C - 1", "SBI Dual Advantage Fund Series – XIII", "SBI Tax Advantage
# Fund - Series I", "HDFC FMP 1269D March 2023", folder prefix
# "close_ended_schemes\\...").
_CLOSED_ENDED_RE = re.compile(
    r"\b(fmp|fixed\s+maturity|fixed\s+term|series|dual\s+advantage"
    r"|capital\s+protection|interval\s+fund|segregated)\b|close[_\s-]*ended",
    re.IGNORECASE,
)


def looks_closed_ended(text: str) -> bool:
    """True when a filename or scheme banner names a closed-ended/matured
    scheme class (FMP / Series / Dual Advantage / ...). Pure — combined by the
    parse task with a FAILED ISIN lookup to mark files 'scheme_not_in_master'
    (honest terminal outcome) instead of an endlessly retryable failure."""
    return bool(_CLOSED_ENDED_RE.search(text))


def detect_amc_and_parse(
    data: bytes, original_filename: str, amc_hint: str | None = None
) -> tuple[str | None, date | None, list[dict]]:
    """Detect the AMC + disclosure month and parse constituent rows in one pass.

    Filename first (cheap, no parse needed); if that fails, parse once with a
    placeholder AMC name and fall back to matching the first parsed scheme
    name; if THAT still fails, `amc_hint` (the per-AMC watched-subfolder name,
    e.g. incoming/HDFC/) is the last-resort fallback — matched against the
    SAME keyword set as filename/scheme-name detection (`detect_amc`), so an
    unrecognized folder name is simply ignored (logged), never guessed.
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

    if amc_name is None and amc_hint:
        hinted = detect_amc(amc_hint)
        if hinted:
            amc_name = hinted
        else:
            logger.info("manual_ingest: unknown AMC subfolder hint=%r — ignoring", amc_hint)

    period = next((r["as_of_month"] for r in rows if r.get("as_of_month")), None)
    if period is None:
        # Filename fallback (KOTAK/EDEL evidence 2026-07-07): sheets carry no
        # as-on line but the filename names the month. Stamp it onto the rows
        # too — _upsert_constituents keys history on as_of_month.
        period = detect_period_from_filename(original_filename)
        if period is not None:
            for row in rows:
                if not row.get("as_of_month"):
                    row["as_of_month"] = period
    return amc_name, period, rows
