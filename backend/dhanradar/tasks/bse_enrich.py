"""
DhanRadar — BSE StAR MF scheme-master enrichment (exit load, min amounts).

Fills the two enrichment fields no disclosure file carries (verified dead ends —
see AMC_DATA_COMPLETENESS.md): per-scheme EXIT LOAD and MINIMUM lumpsum/SIP
amounts, from BSE StAR MF v2's `master_scheme_list` read API (plaintext +
Bearer; ~28k scheme records, one per plan×option ISIN — so every write is an
EXACT `mf_funds.isin` match, no fuzzy resolution anywhere in this pipeline).
Bonus cross-fill: `scheme_benchmark`, written only where `benchmark_index` is
NULL (the disclosure-file parsers stay the primary source).

DORMANT-SAFE by design (mirrors the email-poller pattern) — three independent
gates, all fail-closed:

  1. ``BSE_ENRICH_ENABLED`` (default False) — a dedicated flag, never inferred
     from BSE_ENV, so an unrelated ops change can't arm it.
  2. ``BSE_LOGIN_USERNAME`` + ``BSE_LOGIN_PASSWORD`` present.
  3. Writes happen ONLY when ``BSE_ENV == "prod"``. Any other env runs the full
     fetch+map as a DRY RUN (counts logged, zero writes) — enforcing the
     documented policy that UAT/demo data must NEVER enrich the production
     master (demo `scheme_bse_code`s may differ in prod; see the BSE guide,
     "Enrichment policy — DEV-ONLY").

Operational discipline (all from the verified BSE guide):
  * browser User-Agent always — the Radware WAF blocks python UAs, and a WAF
    block arrives as an HTML body with HTTP 200, so responses are content-
    sniffed, never trusted by status code alone;
  * login = ONE attempt, never retried (lockout risk on a valid username);
  * data requests retry ≤3 times on gateway-level failures only
    (timeout/502/503/504) — never on a definitive API error;
  * gentle paging (2k/page, small pause) — no tight loops; each raw page is
    mapped and DISCARDED before the next fetch (a full-master accumulation
    OOM-killed the 640 MB worker on the first live dry run).

Provenance: the whole run rides ``ingestion_run()`` (source key
"bse_scheme_master"), so failures surface through the existing admin
ingestion-failure alert and the Data Operations source-health panel for free.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

from dhanradar.celery_app import celery_app

logger = logging.getLogger(__name__)

TASK_ENRICH = "dhanradar.tasks.bse_enrich.bse_scheme_master_enrich"
SOURCE = "bse_scheme_master"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_PAGE_SIZE = 2_000  # deliberately far below the 10k API max: one page of
# records (with the nested lumpsum/systematic blocks) must fit the 640 MB
# celery-batch cgroup alongside its baseline — 10k pages OOM-killed the live
# dry run (exit 137, 2026-07-10). ~15 gentle pages for the 28k master.
_PAGE_PAUSE_S = 2.0  # gentle — the WAF does bot/rate-based blocking
_GATEWAY_RETRY = 3  # timeout/502/503/504 only, never definitive API errors
_WRITE_CHUNK = 500

_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


# ---------------------------------------------------------------------------
# Pure mapping helpers — unit-tested against a REAL UAT record (2026-07-10).
# ---------------------------------------------------------------------------


def _parse_exit_load_pct(raw: Any) -> float | None:
    """`scheme_exit_load` is a numeric STRING ("0", "1", "1.5"). "0" is a real
    fact (no exit load) and is kept as 0.0 — only unparseable input is None."""
    s = str(raw).strip().replace("%", "") if raw is not None else ""
    if not s:
        return None
    try:
        val = float(s)
    except ValueError:
        return None
    return val if 0 <= val <= 20 else None  # >20% is never a real exit load


_DAYS_RES = (
    (re.compile(r"(\d+)\s*day", re.IGNORECASE), 1),
    (re.compile(r"(\d+)\s*month", re.IGNORECASE), 30),
    (re.compile(r"(\d+)\s*year", re.IGNORECASE), 365),
)


def _parse_exit_load_days(remarks: Any) -> int | None:
    """Longest holding period mentioned in the exit-load remarks prose
    ("1% if redeemed within 365 days" → 365; "within 12 months" → 360;
    tiered loads take the max). Fail-closed None when no period is stated."""
    text = str(remarks) if remarks is not None else ""
    candidates = [
        int(m.group(1)) * mult for pattern, mult in _DAYS_RES for m in pattern.finditer(text)
    ]
    plausible = [c for c in candidates if 0 < c <= 3650]
    return max(plausible) if plausible else None


def _min_amt_of(block: dict) -> float | None:
    amt = (
        (block.get("scheme_transaction_single_details") or {}).get("scheme_transaction_amt") or {}
    ).get("scheme_transaction_min_amt")
    if amt is None:
        return None
    try:
        val = float(amt)
    except (TypeError, ValueError):
        return None
    return val if val > 0 else None


def _extract_min_amounts(record: dict) -> tuple[float | None, float | None]:
    """(min_lumpsum, min_sip) from the transactability blocks.

    `lumpsum` / `systematic` are LISTS of per-transaction-type blocks
    (Purchase, Additional Purchase, Redemption, SIP-per-frequency, ...) —
    only fresh-Purchase (never "Additional") counts for lumpsum; the SIP
    minimum is the smallest across SIP frequency blocks."""
    min_lumpsum: float | None = None
    for block in record.get("lumpsum") or []:
        ttype = str(block.get("scheme_transaction_type") or "").lower()
        if "purchase" in ttype and "additional" not in ttype:
            amt = _min_amt_of(block)
            if amt is not None and (min_lumpsum is None or amt < min_lumpsum):
                min_lumpsum = amt

    min_sip: float | None = None
    for block in record.get("systematic") or []:
        ttype = str(block.get("scheme_transaction_type") or "").lower()
        if "systematic investment" in ttype or ttype == "sip":
            amt = _min_amt_of(block)
            if amt is not None and (min_sip is None or amt < min_sip):
                min_sip = amt
    return min_lumpsum, min_sip


def map_scheme_record(record: dict) -> dict | None:
    """One BSE scheme record → the mf_funds field dict, or None when the
    record carries no usable ISIN. Pure; every value taken verbatim from the
    record (never derived across records)."""
    isin = str(record.get("scheme_isin") or "").strip().upper()
    if not _ISIN_RE.fullmatch(isin):
        return None
    min_lumpsum, min_sip = _extract_min_amounts(record)
    benchmark = str(record.get("scheme_benchmark") or "").strip() or None
    return {
        "isin": isin,
        "exit_load_pct": _parse_exit_load_pct(record.get("scheme_exit_load")),
        "exit_load_days": _parse_exit_load_days(record.get("scheme_exit_load_remarks")),
        "min_lumpsum_amount": min_lumpsum,
        "min_sip_amount": min_sip,
        "benchmark_index": benchmark,
    }


# ---------------------------------------------------------------------------
# HTTP client — plaintext read path, per the verified guide.
# ---------------------------------------------------------------------------


class BseApiError(RuntimeError):
    """Definitive API-level failure — never retried."""


def _looks_like_waf_block(body: str) -> bool:
    # The Radware WAF returns its block page as HTTP 200 HTML — sniff content.
    return body.lstrip()[:1] == "<"


async def _post(client: Any, path: str, payload: dict, token: str | None = None) -> dict:
    """POST with gateway-level retry only. Raises BseApiError on definitive
    API errors (wrong creds, WAF block, error envelope) — callers never retry
    those."""
    import json as _json

    import httpx

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": _UA,
    }
    if token:
        # Non-neg #4 (cookie-only) governs OUR inbound API auth; this is the
        # scheme BSE's API requires of clients.
        headers["Authorization"] = f"Bearer {token}"  # outbound to BSE — not our auth surface

    last_exc: Exception | None = None
    for attempt in range(1, _GATEWAY_RETRY + 1):
        try:
            resp = await client.post(path, json=payload, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            await asyncio.sleep(2 * attempt)
            continue
        if resp.status_code in (502, 503, 504):
            last_exc = BseApiError(f"gateway {resp.status_code}")
            await asyncio.sleep(2 * attempt)
            continue
        body = resp.text
        if _looks_like_waf_block(body):
            raise BseApiError("WAF block page returned (HTML body)")
        try:
            parsed = _json.loads(body)
        except ValueError as exc:
            raise BseApiError(f"non-JSON response (HTTP {resp.status_code})") from exc
        if resp.status_code != 200 or parsed.get("status") == "error":
            raise BseApiError(f"HTTP {resp.status_code} / {str(parsed.get('messages'))[:200]}")
        return parsed
    raise BseApiError(f"gateway retries exhausted: {last_exc}")


async def _login(client: Any, username: str, password: str) -> str:
    """ONE attempt, never retried at the credential level (lockout discipline).
    Gateway-level retries inside _post are safe — they never reach auth."""
    parsed = await _post(client, "/login", {"data": {"username": username, "password": password}})
    data = parsed.get("data") or {}
    token = data.get("access_token") or (data.get("data") or {}).get("access_token")
    if not token:
        raise BseApiError("login succeeded without an access_token")
    return str(token)


# Only the fields the mapper consumes — the API honors field selection
# (verified 2026-07-10: unrequested fields come back empty), and requesting
# ALL made 28k deeply-nested records big enough to OOM-kill the worker
# (exit 137 on the live dry run; celery-batch has a 640 MB cgroup cap).
_FIELDS = [
    "scheme_isin",
    "scheme_exit_load",
    "scheme_exit_load_remarks",
    "scheme_benchmark",
    "lumpsum",
    "systematic",
]


async def _fetch_page(client: Any, token: str, start: int) -> list[dict]:
    """One page of scheme records. Callers map+discard each page before
    fetching the next — the FULL raw set must never be held in memory."""
    parsed = await _post(
        client,
        "/master_scheme_list",
        {
            "data": {
                "fields": _FIELDS,
                "count_only": False,
                "start": start,
                "length": _PAGE_SIZE,
            }
        },
        token,
    )
    return (parsed.get("data") or {}).get("lists") or []


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


@celery_app.task(name=TASK_ENRICH)
def bse_scheme_master_enrich() -> str:
    try:
        return asyncio.run(_enrich_pipeline())
    except Exception:  # noqa: BLE001 — beat task must never crash the worker
        logger.exception("bse_scheme_master_enrich failed")
        return "failed — see worker logs"


async def _enrich_pipeline() -> str:
    import httpx
    from sqlalchemy import text as sa_text

    from dhanradar.config import settings
    from dhanradar.db import TaskSessionLocal
    from dhanradar.tasks.ingestion_run import ingestion_run

    # Gate 1+2 — dormant until explicitly armed AND credentialed. A no-op is
    # logged, never alerted (dormant ≠ failing).
    if not settings.BSE_ENRICH_ENABLED:
        logger.info("bse_enrich: BSE_ENRICH_ENABLED is off — dormant, skipping")
        return "skipped: disabled"
    if not (settings.BSE_LOGIN_USERNAME and settings.BSE_LOGIN_PASSWORD):
        logger.info("bse_enrich: no BSE credentials configured — dormant, skipping")
        return "skipped: no_credentials"

    # Gate 3 — writes are structurally impossible off prod (demo data must
    # never enrich the real master; demo values are UAT-specific).
    dry_run = settings.BSE_ENV.strip().lower() != "prod"
    base_url = (
        settings.BSE_API_BASE_URL_PROD if not dry_run else settings.BSE_API_BASE_URL_UAT
    ).rstrip("/")

    async with ingestion_run(TASK_ENRICH, SOURCE) as (_run_id, stats):
        started = time.monotonic()
        fetched = 0
        mapped: list[dict] = []
        try:
            async with httpx.AsyncClient(base_url=base_url, timeout=90.0) as client:
                token = await _login(
                    client, settings.BSE_LOGIN_USERNAME, settings.BSE_LOGIN_PASSWORD
                )
                stats.reachable = True
                start = 0
                while True:
                    # Map + discard each raw page immediately — only the tiny
                    # mapped dicts (~200 B each) are accumulated (OOM guard).
                    page = await _fetch_page(client, token, start)
                    fetched += len(page)
                    mapped.extend(m for m in (map_scheme_record(r) for r in page) if m is not None)
                    if len(page) < _PAGE_SIZE:
                        break
                    start += _PAGE_SIZE
                    await asyncio.sleep(_PAGE_PAUSE_S)
        except BseApiError as exc:
            stats.failed = 1
            stats.last_error = str(exc)[:200]
            logger.warning("bse_enrich: fetch failed: %s", exc)
            return f"failed: {exc}"

        stats.fetched = fetched
        with_data = [
            m
            for m in mapped
            if any(
                m[k] is not None
                for k in (
                    "exit_load_pct",
                    "exit_load_days",
                    "min_lumpsum_amount",
                    "min_sip_amount",
                    "benchmark_index",
                )
            )
        ]

        # Match against OUR master by exact ISIN (read-only — also runs in
        # dry-run so the summary reports the true would-update count).
        matched = 0
        updates = 0
        async with TaskSessionLocal() as db:
            for i in range(0, len(with_data), _WRITE_CHUNK):
                chunk = with_data[i : i + _WRITE_CHUNK]
                result = await db.execute(
                    sa_text("SELECT isin FROM mf.mf_funds WHERE isin = ANY(:isins)"),
                    {"isins": [m["isin"] for m in chunk]},
                )
                known = {row[0] for row in result}
                matched += len(known)
                if dry_run:
                    continue
                for m in chunk:
                    if m["isin"] not in known:
                        continue
                    result = await db.execute(
                        sa_text(
                            "UPDATE mf.mf_funds SET "
                            "exit_load_pct = COALESCE(:elp, exit_load_pct), "
                            "exit_load_days = COALESCE(:eld, exit_load_days), "
                            "min_lumpsum_amount = COALESCE(:mla, min_lumpsum_amount), "
                            "min_sip_amount = COALESCE(:msa, min_sip_amount), "
                            "benchmark_index = COALESCE(benchmark_index, :bmk) "
                            "WHERE isin = :isin"
                        ),
                        {
                            "elp": m["exit_load_pct"],
                            "eld": m["exit_load_days"],
                            "mla": m["min_lumpsum_amount"],
                            "msa": m["min_sip_amount"],
                            "bmk": m["benchmark_index"],
                            "isin": m["isin"],
                        },
                    )
                    updates += int(getattr(result, "rowcount", 0) or 0)
                await db.commit()

        stats.written = updates
        elapsed = time.monotonic() - started
        summary = (
            f"{'DRY-RUN (env != prod, zero writes)' if dry_run else 'enriched'}: "
            f"fetched={fetched} mapped={len(mapped)} with_data={len(with_data)} "
            f"matched_in_master={matched} updated={updates} in {elapsed:.0f}s"
        )
        logger.info("bse_enrich: %s", summary)
        return summary
