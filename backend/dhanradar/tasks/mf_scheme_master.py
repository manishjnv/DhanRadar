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
import re
from datetime import date

import httpx

from dhanradar.celery_app import celery_app
from dhanradar.market_data.amfi_scheme_master import SchemeMasterRow

logger = logging.getLogger(__name__)

_UPSERT_CHUNK = 2000

SOURCE = "amfi_scheme_master"
TASK = "dhanradar.tasks.mf.mf_scheme_master_refresh"

# Scheme-lineage noise guard (enrichment item 6): AMFI's feed occasionally drops chunks
# transiently, which looks exactly like a wave of scheme closures. Above this fraction of
# tracked funds, treat it as a bad fetch, not real mergers/closures — fail closed.
_DISAPPEARED_NOISE_THRESHOLD = 0.02


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
# Scheme lineage diff (enrichment item 6 — renames / disappearances).
#
# mf_funds is upserted IN PLACE, so a rename or disappearance is only ever
# observable at the moment of this refresh, diffed against the pre-upsert DB
# state — there are no historical snapshots. All functions below are pure
# (no DB/network) so they are unit-testable from synthetic fund dicts; the one
# DB-touching helper (_write_scheme_lineage) is a thin wrapper around them.
#
# Fund dict shape used throughout: {"isin": str, "amfi_code": str | None,
# "scheme_name": str}.
# ---------------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[^a-z0-9]+")


def _normalize_scheme_name(name: str) -> str:
    """Lowercase + collapse whitespace/punctuation runs to a single space.

    Two names that normalize equal differ only in case/spacing/punctuation —
    not a real rename (e.g. "ABC Fund - Direct" == "abc  fund  direct").
    """
    return _PUNCT_RE.sub(" ", name.lower()).strip()


def _match_fresh(fund: dict, by_isin: dict[str, dict], by_amfi: dict[str, dict]) -> dict | None:
    """Find the fresh-AMFI-batch record for a tracked DB fund: same isin, falling
    back to same amfi_code (a scheme can carry its AMFI code across an ISIN change)."""
    match = by_isin.get(fund["isin"])
    if match is not None:
        return match
    amfi_code = fund.get("amfi_code")
    return by_amfi.get(amfi_code) if amfi_code else None


def detect_renames(
    db_funds: list[dict], fresh_funds: list[dict], *, effective_date: date
) -> list[dict]:
    """Compare scheme_name for every DB fund matched in the fresh AMFI batch (by isin,
    or by amfi_code) and emit a scheme_lineage row dict for each material rename.
    Pure — no DB. Returns rows shaped for MfSchemeLineage(**row)."""
    by_isin = {f["isin"]: f for f in fresh_funds}
    by_amfi = {f["amfi_code"]: f for f in fresh_funds if f.get("amfi_code")}
    rows = []
    for old in db_funds:
        match = _match_fresh(old, by_isin, by_amfi)
        if match is None:
            continue
        if _normalize_scheme_name(old["scheme_name"]) == _normalize_scheme_name(
            match["scheme_name"]
        ):
            continue
        rows.append(
            {
                "old_scheme_uid": old["isin"],
                "new_scheme_uid": match["isin"],
                "event_type": "rename",
                "effective_date": effective_date,
                "sebi_circular": None,
                "notes": f"{old['scheme_name']} -> {match['scheme_name']}",
            }
        )
    return rows


def detect_disappeared(
    db_funds: list[dict], fresh_funds: list[dict], *, effective_date: date
) -> tuple[list[dict], bool, int, int]:
    """Diff DB-tracked (AMFI-sourced) funds against the fresh AMFI batch for isins
    present in the DB but unmatched in the fresh file (by isin or amfi_code) — a
    candidate merger/closure, never confirmed without a SEBI circular.

    NB: the scheme_lineage.event_type check constraint (migration 0035) has no
    'disappeared' member; 'closure' is the closest existing value for an
    unconfirmed candidate — the caveat lives in `notes`.

    Applies the _DISAPPEARED_NOISE_THRESHOLD noise guard: when tripped, returns no
    rows (fail closed) — the caller decides whether/how to log the warning.
    Returns (lineage_rows, noise_guard_tripped, missing_count, tracked_count).
    """
    by_isin = {f["isin"]: f for f in fresh_funds}
    by_amfi = {f["amfi_code"]: f for f in fresh_funds if f.get("amfi_code")}
    missing = [old for old in db_funds if _match_fresh(old, by_isin, by_amfi) is None]
    tracked_count = len(db_funds)
    missing_count = len(missing)
    tripped = tracked_count > 0 and missing_count > _DISAPPEARED_NOISE_THRESHOLD * tracked_count
    if tripped:
        return [], True, missing_count, tracked_count
    rows = [
        {
            "old_scheme_uid": f["isin"],
            "new_scheme_uid": f["isin"],
            "event_type": "closure",
            "effective_date": effective_date,
            "sebi_circular": None,
            "notes": "candidate merger or closure; unconfirmed without SEBI circular",
        }
        for f in sorted(missing, key=lambda x: x["isin"])
    ]
    return rows, False, missing_count, tracked_count


def _dedupe_new_lineage_rows(
    candidate_rows: list[dict], existing_keys: set[tuple[str, str, date]]
) -> list[dict]:
    """Filter out rows whose (old_scheme_uid, event_type, effective_date) already
    exists — scheme_lineage has no unique constraint on this triple (predates this
    writer), so idempotency across repeated runs is enforced here in Python."""
    return [
        r
        for r in candidate_rows
        if (r["old_scheme_uid"], r["event_type"], r["effective_date"]) not in existing_keys
    ]


async def _write_scheme_lineage(db, rows: list[dict]) -> int:
    """Insert lineage rows idempotently (see _dedupe_new_lineage_rows). Append-only —
    never updates/deletes an existing row. Returns the count actually written."""
    if not rows:
        return 0

    from sqlalchemy import select

    from dhanradar.models.mf import MfSchemeLineage

    old_uids = {r["old_scheme_uid"] for r in rows}
    dates = {r["effective_date"] for r in rows}
    existing = (
        await db.execute(
            select(
                MfSchemeLineage.old_scheme_uid,
                MfSchemeLineage.event_type,
                MfSchemeLineage.effective_date,
            ).where(
                MfSchemeLineage.old_scheme_uid.in_(old_uids),
                MfSchemeLineage.effective_date.in_(dates),
            )
        )
    ).all()
    existing_keys = {(r[0], r[1], r[2]) for r in existing}
    new_rows = _dedupe_new_lineage_rows(rows, existing_keys)
    if new_rows:
        db.add_all(MfSchemeLineage(**r) for r in new_rows)
    return len(new_rows)


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

        # Batch-level isin2 dedupe (adversarial-review condition, 2026-07-04): AMFI ships
        # duplicate primaries (hence the last-seen-wins dict above), so duplicate SECONDARIES
        # are equally plausible — and uq_mf_funds_isin2 would fail the whole upsert chunk on
        # one. Also null out an isin2 that collides with any batch PRIMARY (primary wins,
        # mirroring alias_secondary_isins' precedence). First-seen keeps the secondary.
        seen_secondary: set[str] = set()
        n_isin2_dropped = 0
        for rec in deduped.values():
            sec = rec["isin2"]
            if sec is None:
                continue
            if sec in deduped or sec in seen_secondary:
                rec["isin2"] = None
                n_isin2_dropped += 1
            else:
                seen_secondary.add(sec)
        if n_isin2_dropped:
            logger.warning(
                "mf_scheme_master_refresh: %d duplicate/primary-colliding isin2 values dropped"
                " from this batch (first-seen kept; uq_mf_funds_isin2 protected)",
                n_isin2_dropped,
            )

        upsert_rows = list(deduped.values())
        fresh_funds = [
            {"isin": r["isin"], "amfi_code": r["amfi_code"], "scheme_name": r["scheme_name"]}
            for r in upsert_rows
        ]

        # -----------------------------------------------------------------
        # 4. Upsert into mf.mf_funds in chunks of 2000
        # -----------------------------------------------------------------
        from sqlalchemy import func, select
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from dhanradar.db import TaskSessionLocal
        from dhanradar.models.mf import MfFund

        n_written = 0
        n_renamed = 0
        n_disappeared = 0
        async with TaskSessionLocal() as db:
            # -------------------------------------------------------------
            # 3.5 Scheme lineage diff — MUST run before the upsert below
            # overwrites mf_funds; it is the only point a rename/disappearance
            # is ever observable (no historical snapshots exist). "AMFI-sourced"
            # = amfi_code IS NOT NULL: the only two writers of mf_funds (this
            # task + nav_daily_fetch) both stamp amfi_code from an AMFI feed, so
            # it is a reliable "previously seen from AMFI" signal.
            # -------------------------------------------------------------
            db_rows = (
                await db.execute(
                    select(MfFund.isin, MfFund.amfi_code, MfFund.scheme_name).where(
                        MfFund.amfi_code.isnot(None)
                    )
                )
            ).all()
            db_funds = [
                {"isin": r.isin, "amfi_code": r.amfi_code, "scheme_name": r.scheme_name}
                for r in db_rows
            ]

            rename_rows = detect_renames(db_funds, fresh_funds, effective_date=today)
            disappeared_rows, noise_tripped, n_missing, n_tracked = detect_disappeared(
                db_funds, fresh_funds, effective_date=today
            )
            if noise_tripped:
                logger.warning(
                    "mf_scheme_master_refresh: disappeared-count noise guard tripped — "
                    "%d/%d (%.1f%%) exceeds the %.0f%% threshold; writing NO disappeared "
                    "lineage rows this run (treated as a transient AMFI drop, not real "
                    "closures/mergers)",
                    n_missing,
                    n_tracked,
                    (100 * n_missing / n_tracked) if n_tracked else 0.0,
                    _DISAPPEARED_NOISE_THRESHOLD * 100,
                )

            n_renamed = await _write_scheme_lineage(db, rename_rows)
            n_disappeared = await _write_scheme_lineage(db, disappeared_rows)

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
        stats.metadata = {
            **(stats.metadata or {}),
            "lineage_renamed": n_renamed,
            "lineage_disappeared": n_disappeared,
        }
        logger.info(
            "mf_scheme_master_refresh: fetched=%d written=%d failed=%d closed=%d "
            "lineage_renamed=%d lineage_disappeared=%d",
            stats.fetched,
            stats.written,
            stats.failed,
            n_closed,
            n_renamed,
            n_disappeared,
        )

    return f"mf_scheme_master_refresh: {stats.written} written, {stats.failed} failed"
