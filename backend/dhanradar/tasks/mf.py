"""
DhanRadar — MF Celery tasks (Phase 5).

`parse_cas_job` is the CAS→report worker (architecture pipeline steps 3–8):
parse → upsert holdings → snapshot → score (via the engine interface) → cache the
report → done. The raw CAS file is deleted immediately after parse; a daily
`purge_cas_files` sweep is the 24h backstop (anti-pattern guard).

`nav_daily_fetch` pulls the current NAVAll.txt from AMFI, bulk-upserts
mf_nav_history and mf_funds metadata (amfi_code, scheme_name, category only —
other metadata columns such as expense_ratio/aum are not overwritten).

`nav_backfill` bootstraps multi-year historical NAV data by iterating over
<=90-day windows and upserting into mf_nav_history.  It is NOT in the beat
schedule — invoke manually.

All Celery tasks are sync; async DB/Redis/network pipelines run under asyncio.run.
Pure mapping helpers are factored out for unit testing without a worker.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

from structlog.contextvars import bind_contextvars

from dhanradar.celery_app import celery_app
from dhanradar.core.logging import get_logger, hash_user_ref
from dhanradar.mf import service
from dhanradar.mf.cas import CasParseError, ParsedHolding, parse_cas
from dhanradar.mf.scoring_bridge import score_fund, upsert_user_fund_score
from dhanradar.mf.signals import CategoryRelative, compute_fund_signals
from dhanradar.mf.snapshot import CashFlow, Holding, build_snapshot

logger = logging.getLogger(__name__)
_slog = get_logger(__name__)

_UPLOAD_TTL_SECONDS = 24 * 3600

# Batch size for bulk-upsert statements — bounds memory and statement size.
_UPSERT_CHUNK = 2000


def parsed_to_snapshot_holdings(
    parsed: list[ParsedHolding], nav_map: dict[str, float] | None = None
) -> list[Holding]:
    """Map parsed CAS holdings → snapshot.Holding, applying the latest NAV when
    available (else falling back to the CAS-reported valuation). Pure + testable."""
    nav_map = nav_map or {}
    out: list[Holding] = []
    for p in parsed:
        nav = nav_map.get(p.isin, p.nav)
        current_value = (p.units * nav) if (nav is not None) else (p.value or 0.0)
        invested = p.cost if p.cost is not None else 0.0
        cashflows = [CashFlow(when=t.when, amount=t.amount) for t in p.txns]
        if current_value:
            cashflows.append(CashFlow(when=p.as_of_date or date.today(), amount=current_value))
        out.append(
            Holding(
                isin=p.isin,
                units=p.units,
                invested_amount=invested,
                current_value=current_value,
                category="uncategorized",  # filled from mf_funds when metadata exists
                cashflows=cashflows,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Pure mapping helpers — unit-testable without DB
# ---------------------------------------------------------------------------

def _navrows_to_nav_upserts(rows: Any) -> list[dict]:
    """
    Map a list of NavRow → list of dicts ready for mf_nav_history upsert.

    Keying strategy: prefer isin_growth; fall back to isin_reinvest.
    Rows where BOTH ISINs are None are silently skipped (cannot key the row).
    Returns dicts with keys: isin, nav_date, nav, source.
    """
    out: list[dict] = []
    for row in rows:
        isin = row.isin_growth or row.isin_reinvest
        if isin is None:
            continue
        out.append(
            {
                "isin": isin,
                "nav_date": row.nav_date,
                "nav": row.nav,
                "source": "amfi",
            }
        )
    return out


def _navrows_to_fund_upserts(rows: Any) -> list[dict]:
    """
    Map a list of NavRow → list of dicts ready for mf_funds upsert.

    Only the three columns this feed owns are included: amfi_code, scheme_name,
    category.  isin is the PK (isin_growth preferred, else isin_reinvest).
    Rows without a keyable ISIN are skipped.
    """
    out: list[dict] = []
    for row in rows:
        isin = row.isin_growth or row.isin_reinvest
        if isin is None:
            continue
        out.append(
            {
                "isin": isin,
                "amfi_code": row.amfi_code,
                "scheme_name": row.scheme_name,
                "category": row.category,
            }
        )
    return out


# ---------------------------------------------------------------------------
# CAS pipeline helpers (unchanged)
# ---------------------------------------------------------------------------

@celery_app.task(name="dhanradar.tasks.mf.parse_cas_job", bind=True, max_retries=2)
def parse_cas_job(
    self, job_id: str, path: str, user_id: str, portfolio_id: str,
    request_id: str | None = None,
) -> str:
    """CAS→report worker. Always purges the raw file; marks the job failed with an
    OPAQUE code (never the raw exception, which could carry a path/PII)."""
    try:
        return asyncio.run(_run_pipeline(job_id, path, user_id, portfolio_id, request_id))
    except CasParseError as exc:
        # Log the underlying reason SERVER-SIDE for diagnosis — it is never sent
        # to the client. casparser raises short reason strings (incorrect
        # password / unsupported format / header parse error), not PII, and the
        # CAS password is never part of these messages. Without this, every CAS
        # failure is an undiagnosable opaque "parse_failed".
        logger.warning("CAS parse failed job=%s reason=%s", job_id, exc)
        # error_message is served to the client (CasJobStatus) — keep it OPAQUE:
        # only the fixed code, NEVER exc / str(exc).
        asyncio.run(_mark_failed(job_id, "parse_failed"))
        return "failed: parse_failed"
    except Exception:  # noqa: BLE001 — record opaque code + purge, never leak detail
        logger.exception("CAS pipeline error job=%s", job_id)
        asyncio.run(_mark_failed(job_id, "internal_error"))
        return "failed: internal_error"
    finally:
        _purge(path)


async def _run_pipeline(
    job_id: str, path: str, user_id: str, portfolio_id: str,
    request_id: str | None = None,
) -> str:
    from sqlalchemy import update

    from dhanradar.db import TaskSessionLocal
    from dhanradar.models.mf import MfCasJob
    from dhanradar.redis_client import get_redis
    from dhanradar.scoring.engine import RatingEngine
    from dhanradar.scoring.engine.schemas import DISCLAIMER_VERSION

    # Bind correlation context for all structured log lines in this pipeline run.
    bind_contextvars(job_id=job_id, request_id=request_id, user_ref=hash_user_ref(user_id))
    _slog.info("cas_pipeline_start", job_id=job_id)

    redis = get_redis()

    # Consume-and-delete the CAS password from its short-lived Redis key (it was
    # never put on the broker). Missing → None (an unprotected CAS still parses).
    pw_key = f"mf:cas:pw:{job_id}"
    password = await redis.get(pw_key)
    if password is not None:
        await redis.delete(pw_key)

    parsed = parse_cas(path, password)  # raises CasParseError on bad password/format
    rengine = RatingEngine()

    async with TaskSessionLocal() as db:
        await db.execute(
            update(MfCasJob).where(MfCasJob.job_id == job_id).values(status="parsing", progress_pct=40)
        )
        await db.commit()

        await _upsert_holdings(db, user_id, parsed, portfolio_id)
        await db.execute(
            update(MfCasJob).where(MfCasJob.job_id == job_id).values(status="scoring", progress_pct=70)
        )
        await db.commit()

        # Resolve Plus status once — controls whether history rows are written.
        from dhanradar.deps import is_plus
        from dhanradar.mf import history as mf_history

        plus = await is_plus(user_id, db)

        # Load each holding's NAV history (mf schema, read-only) so the engine
        # scores on real momentum/risk signals derived from NAV, and the snapshot
        # values on the latest NAV (B29). A holding with no NAV history yields no
        # axes → the engine refuses with insufficient_data (honest fail-safe).
        nav_series, latest_nav = await _load_nav_series(db, [p.isin for p in parsed])
        # Peer-cohort benchmark (B58): category-relative label inputs so the rule
        # table can emit in_form/off_track, not only on_track/insufficient_data.
        cohort = await _compute_cohort(db, [p.isin for p in parsed])

        snap = build_snapshot(parsed_to_snapshot_holdings(parsed, nav_map=latest_nav))

        from dhanradar.compliance import service as compliance_service

        funds_payload: list[dict] = []
        for p in parsed:
            # Signals are computed from the fund's own NAV series (momentum/risk);
            # fundamentals-backed axes stay None → partial_coverage (≤ medium).
            # category_relative carries the peer-cohort comparison (B58).
            signals = compute_fund_signals(
                p.isin, nav_series.get(p.isin, []), category_relative=cohort.get(p.isin)
            )
            result = await score_fund(rengine, signals)
            await upsert_user_fund_score(db, user_id, result, portfolio_id)
            # Plus-only: retain label history per fund (no numeric persisted).
            if plus:
                await mf_history.append_score_history(
                    db,
                    user_id=user_id,
                    result=result,
                    snapshot_date=date.today(),
                    source="cas_upload",
                    portfolio_id=portfolio_id,
                )
            # B26 — persist (label, model_used, disclaimer_version) for this served
            # label at GENERATION (once, with full provenance). Fire-and-forget: a
            # failure is logged and never breaks the report pipeline.
            await compliance_service.record_served_label(
                surface="mf_report",
                label=result.verb_label.value,
                model=rengine.model_version,
                disclaimer_version=result.disclaimer_version,
                user_id=user_id,
                identifier=p.isin,
                confidence_band=result.confidence_band.value,
                request_id=request_id,
            )
            funds_payload.append({
                "isin": p.isin, "scheme_name": p.scheme_name, "folio_number": p.folio_number,
                "units": p.units, "invested_amount": p.cost, "current_value": p.value,
                "verb_label": result.verb_label.value, "confidence_band": result.confidence_band.value,
                "contributing_signals": result.contributing_signals,
                "contradicting_signals": result.contradicting_signals,
            })

        # Plus-only: persist the portfolio-level snapshot (numbers stay server-side).
        if plus:
            await mf_history.persist_portfolio_snapshot(
                db,
                user_id=user_id,
                snapshot_date=date.today(),
                snap=snap,
                portfolio_id=portfolio_id,
            )

        report_payload = {
            "job_id": job_id, "status": "done",
            "snapshot": {
                "total_invested": snap.total_invested, "current_value": snap.current_value,
                "xirr_pct": snap.xirr_pct, "category_allocation": snap.category_allocation,
                "overlap_matrix": snap.overlap_matrix,
            },
            "funds": funds_payload, "model_version": rengine.model_version,
            "generated_at": datetime.now(UTC).isoformat(),
            # Stamp the in-force disclaimer version on the served + cached report so
            # it matches the audit rows written above (B26 tie-to-version).
            "disclaimer_version": DISCLAIMER_VERSION,
        }
        # First AI consumer — governed portfolio commentary (B20/B21/B22 gated).
        # Best-effort: a commentary failure NEVER breaks the report (mirrors the
        # fire-and-forget audit pattern above).
        try:
            from dhanradar.ai_gateway.gateway import OpenRouterGateway
            from dhanradar.mf.commentary import generate_commentary, is_commentary_entitled

            if await is_commentary_entitled(user_id, db):
                report_payload["ai_commentary"] = await generate_commentary(
                    OpenRouterGateway(), user_id=user_id, db=db, snapshot=snap, funds=funds_payload,
                    request_id=request_id,
                )
            else:
                report_payload["ai_commentary"] = {"state": "upgrade_required", "reason": "plus_feature"}
        except Exception:  # noqa: BLE001 — commentary is best-effort; report still completes
            logger.exception("AI commentary failed job=%s", job_id)
            report_payload["ai_commentary"] = {"state": "unavailable", "reason": "internal_error"}

        await redis.set(
            f"{service._REPORT_PREFIX}{job_id}", json.dumps(report_payload), ex=service._REPORT_TTL
        )
        await db.execute(
            update(MfCasJob).where(MfCasJob.job_id == job_id).values(
                status="done", progress_pct=100, completed_at=datetime.now(UTC)
            )
        )
        await db.commit()
    return f"done: {len(parsed)} schemes"


async def _upsert_holdings(
    db: Any, user_id: str, parsed: list[ParsedHolding], portfolio_id: str
) -> None:
    from sqlalchemy import func
    from sqlalchemy.dialects.postgresql import insert

    from dhanradar.models.mf import MfUserHolding

    for p in parsed:
        stmt = insert(MfUserHolding).values(
            user_id=user_id, portfolio_id=portfolio_id, isin=p.isin,
            folio_number=p.folio_number, units=p.units,
            avg_cost_nav=p.nav, invested_amount=p.cost, source="cas", as_of_date=p.as_of_date,
        ).on_conflict_do_update(
            constraint="uq_mf_holding",
            set_={"units": p.units, "invested_amount": p.cost, "source": "cas",
                  "as_of_date": p.as_of_date, "updated_at": func.now()},
        )
        await db.execute(stmt)
    await db.commit()


async def _load_nav_series(
    db: Any, isins: list[str], lookback_days: int = 400
) -> tuple[dict[str, list[tuple[date, float]]], dict[str, float]]:
    """Load recent NAV history for the given ISINs from mf_nav_history.

    Returns (series, latest_nav) where series maps isin → [(nav_date, nav), …]
    ascending, and latest_nav maps isin → its most recent NAV.  Read-only on the
    MF module's own schema (no cross-module access).  Empty isins → ({}, {})."""
    if not isins:
        return {}, {}

    from sqlalchemy import select

    from dhanradar.models.mf import MfNavHistory

    cutoff = datetime.now(timezone.utc).date() - timedelta(days=lookback_days)  # noqa: UP017
    result = await db.execute(
        select(MfNavHistory.isin, MfNavHistory.nav_date, MfNavHistory.nav)
        .where(MfNavHistory.isin.in_(isins), MfNavHistory.nav_date >= cutoff)
        .order_by(MfNavHistory.isin, MfNavHistory.nav_date)
    )
    series: dict[str, list[tuple[date, float]]] = {}
    for isin, nav_date, nav in result.all():
        series.setdefault(isin, []).append((nav_date, float(nav)))
    latest_nav = {isin: pts[-1][1] for isin, pts in series.items()}
    return series, latest_nav


# Long-range lookback for the peer-cohort benchmark (B58): the 3Y comparison needs
# > 3 years of NAV, unlike the 400-day momentum/risk load.
_COHORT_LOOKBACK_DAYS = 1200


async def _compute_cohort(
    db: Any, target_isins: list[str], *, as_of: date | None = None
) -> dict[str, CategoryRelative]:
    """Build category peer-cohort benchmarks and return each target fund's
    category-relative LABEL inputs (B58).  Returns {isin: CategoryRelative}; a fund
    absent from the map (no category, thin cohort, or no NAV) is scored with no
    category red flag → on_track, the honest fail-safe.

    Read-only on the mf schema (MfFund + mf_nav_history) — no cross-module access.
    The peer set for a category is every fund AMFI tags in that category; the fund
    itself is included (negligible self-bias on a ≥5-peer median).
    """
    from sqlalchemy import select

    from dhanradar.mf.cohort import build_benchmark, compare_to_cohort
    from dhanradar.mf.signals import long_horizon_stats
    from dhanradar.models.mf import MfFund

    if not target_isins:
        return {}
    as_of = as_of or date.today()

    # 1. Resolve each target's category; keep only real categories.
    cat_rows = (
        await db.execute(
            select(MfFund.isin, MfFund.category).where(MfFund.isin.in_(target_isins))
        )
    ).all()
    target_category: dict[str, str] = {
        i: c for i, c in cat_rows if c and c != "uncategorized"
    }
    categories = set(target_category.values())
    if not categories:
        return {}

    # 2. All peers in those categories.
    peer_rows = (
        await db.execute(
            select(MfFund.isin, MfFund.category).where(MfFund.category.in_(categories))
        )
    ).all()
    peers_by_cat: dict[str, list[str]] = {}
    all_peer_isins: list[str] = []
    for i, c in peer_rows:
        peers_by_cat.setdefault(c, []).append(i)
        all_peer_isins.append(i)

    # 3. Long NAV series for every peer (≥3y); compute each peer's long-horizon
    #    stats ONCE (targets are peers too), then the per-category median benchmark.
    series, _ = await _load_nav_series(db, all_peer_isins, lookback_days=_COHORT_LOOKBACK_DAYS)
    stats_by_isin = {
        i: long_horizon_stats(series.get(i, []), as_of=as_of) for i in set(all_peer_isins)
    }
    benchmarks = {
        cat: build_benchmark(cat, [stats_by_isin[i] for i in cat_isins])
        for cat, cat_isins in peers_by_cat.items()
    }

    # 4. Each target's own stats (reused from the cache) vs its category benchmark.
    out: dict[str, CategoryRelative] = {}
    for i in target_isins:
        c = target_category.get(i)
        if c is None:
            continue
        out[i] = compare_to_cohort(stats_by_isin.get(i, (None, None, None)), benchmarks.get(c))
    return out


async def _mark_failed(job_id: str, message: str) -> None:
    from sqlalchemy import update

    from dhanradar.db import TaskSessionLocal
    from dhanradar.models.mf import MfCasJob

    async with TaskSessionLocal() as db:
        await db.execute(
            update(MfCasJob).where(MfCasJob.job_id == job_id).values(
                status="failed", error_message=message[:500]
            )
        )
        await db.commit()


def _purge(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# NAV ingestion tasks
# ---------------------------------------------------------------------------

@celery_app.task(name="dhanradar.tasks.mf.nav_daily_fetch")
def nav_daily_fetch() -> str:
    """AMFI NAV daily refresh: fetch NAVAll.txt → bulk-upsert mf_nav_history +
    mf_funds metadata (amfi_code, scheme_name, category only).  Real network call
    via fetch_navall_rows_with_category.  Wired to the beat schedule."""
    try:
        return asyncio.run(_nav_daily_pipeline())
    except Exception:  # noqa: BLE001
        logger.exception("nav_daily_fetch pipeline error")
        return "nav_daily_fetch: failed — see worker logs"


async def _nav_daily_pipeline() -> str:
    from sqlalchemy.dialects.postgresql import insert

    from dhanradar.db import TaskSessionLocal
    from dhanradar.market_data import amfi
    from dhanradar.models.mf import MfFund, MfNavHistory

    logger.info("nav_daily_fetch: fetching NAVAll.txt from AMFI")
    rows = await amfi.fetch_navall_rows_with_category()
    logger.info("nav_daily_fetch: fetched %d rows", len(rows))

    nav_dicts = _navrows_to_nav_upserts(rows)
    fund_dicts = _navrows_to_fund_upserts(rows)

    async with TaskSessionLocal() as db:
        # -- mf_nav_history bulk upsert in chunks ---------------------------------
        n_nav = 0
        for i in range(0, len(nav_dicts), _UPSERT_CHUNK):
            chunk = nav_dicts[i : i + _UPSERT_CHUNK]
            if not chunk:
                continue
            stmt = insert(MfNavHistory).values(chunk).on_conflict_do_update(
                constraint="uq_mf_nav_isin_date",
                set_={"nav": insert(MfNavHistory).excluded.nav, "source": "amfi"},
            )
            await db.execute(stmt)
            n_nav += len(chunk)

        # -- mf_funds upsert (only the 3 AMFI-owned columns) ---------------------
        n_funds = 0
        for i in range(0, len(fund_dicts), _UPSERT_CHUNK):
            chunk = fund_dicts[i : i + _UPSERT_CHUNK]
            if not chunk:
                continue
            stmt = insert(MfFund).values(chunk).on_conflict_do_update(
                index_elements=["isin"],
                set_={
                    "amfi_code": insert(MfFund).excluded.amfi_code,
                    "scheme_name": insert(MfFund).excluded.scheme_name,
                    "category": insert(MfFund).excluded.category,
                },
            )
            await db.execute(stmt)
            n_funds += len(chunk)

        await db.commit()

    summary = f"nav_daily_fetch: {n_nav} navs, {n_funds} funds"
    logger.info(summary)
    return summary


@celery_app.task(name="dhanradar.tasks.mf.nav_backfill")
def nav_backfill(years: int = 3) -> str:
    """Bootstrap multi-year historical NAV from AMFI history endpoint.

    Iterates backwards in <=90-day windows from (today - years*365) to today.
    Upserts nav rows only (no mf_funds update — history feed carries no category).
    NOT in the beat schedule — invoke manually.
    """
    try:
        return asyncio.run(_nav_backfill_pipeline(years))
    except Exception:  # noqa: BLE001
        logger.exception("nav_backfill pipeline error years=%d", years)
        return f"nav_backfill: failed after error — see worker logs (years={years})"


async def _nav_backfill_pipeline(years: int) -> str:
    import asyncio as _asyncio

    from sqlalchemy.dialects.postgresql import insert

    from dhanradar.db import TaskSessionLocal
    from dhanradar.market_data import amfi
    from dhanradar.market_data.exceptions import ProviderError
    from dhanradar.models.mf import MfNavHistory

    today = datetime.now(timezone.utc).date()  # noqa: UP017 — matches pre-existing style in this file
    start = today - timedelta(days=years * 365)

    # Build list of (frmdt, todt) windows of at most 90 days each, from
    # start → today, non-overlapping.
    _WINDOW_DAYS = 90
    windows: list[tuple[date, date]] = []
    cursor = start
    while cursor < today:
        end = min(cursor + timedelta(days=_WINDOW_DAYS - 1), today)
        windows.append((cursor, end))
        cursor = end + timedelta(days=1)

    logger.info(
        "nav_backfill: years=%d, windows=%d, start=%s, end=%s",
        years, len(windows), start, today,
    )

    total_rows = 0
    windows_fetched = 0

    for idx, (frmdt, todt) in enumerate(windows, start=1):
        try:
            rows = await amfi.fetch_nav_history(frmdt, todt)
        except ProviderError as exc:
            logger.warning(
                "nav_backfill: window %d/%d (%s–%s) fetch failed: %s",
                idx, len(windows), frmdt, todt, exc,
            )
            await _asyncio.sleep(1)
            continue

        nav_dicts = _navrows_to_nav_upserts(rows)
        if nav_dicts:
            async with TaskSessionLocal() as db:
                for i in range(0, len(nav_dicts), _UPSERT_CHUNK):
                    chunk = nav_dicts[i : i + _UPSERT_CHUNK]
                    if not chunk:
                        continue
                    stmt = insert(MfNavHistory).values(chunk).on_conflict_do_update(
                        constraint="uq_mf_nav_isin_date",
                        set_={"nav": insert(MfNavHistory).excluded.nav, "source": "amfi"},
                    )
                    await db.execute(stmt)
                await db.commit()
            total_rows += len(nav_dicts)

        windows_fetched += 1
        logger.info(
            "nav_backfill: window %d/%d (%s–%s) → %d rows (total so far: %d)",
            idx, len(windows), frmdt, todt, len(nav_dicts), total_rows,
        )
        await _asyncio.sleep(1)

    summary = (
        f"nav_backfill: {total_rows} rows upserted across {windows_fetched}/{len(windows)} windows"
        f" (years={years})"
    )
    logger.info(summary)
    return summary


@celery_app.task(name="dhanradar.tasks.mf.monthly_rescore_plus_users")
def monthly_rescore_plus_users() -> str:
    """Re-score every Plus user's current holdings from the latest NAV without
    requiring a re-upload.  Writes label history + portfolio snapshot (Plus only).
    Free users are skipped — no history rows, no snapshot.  Wired to the beat
    schedule (1st of month, 03:00 IST).
    """
    try:
        return asyncio.run(_monthly_rescore())
    except Exception:  # noqa: BLE001
        logger.exception("monthly_rescore_plus_users pipeline error")
        return "monthly_rescore: failed — see worker logs"


async def _monthly_rescore() -> str:
    from sqlalchemy import select

    from dhanradar.db import TaskSessionLocal
    from dhanradar.deps import is_plus
    from dhanradar.mf import history as mf_history
    from dhanradar.mf.snapshot import CashFlow as _CashFlow
    from dhanradar.mf.snapshot import Holding as _Holding
    from dhanradar.models.mf import MfFund, MfPortfolio, MfUserHolding
    from dhanradar.notifications import service as notif_service
    from dhanradar.redis_client import get_redis
    from dhanradar.scoring.engine import RatingEngine
    from dhanradar.scoring.engine.schemas import DISCLAIMER_VERSION

    rengine = RatingEngine()
    today = date.today()
    redis = get_redis()

    async with TaskSessionLocal() as db:
        # All distinct portfolios that currently have holdings.
        pid_rows = (
            await db.execute(
                select(MfUserHolding.portfolio_id).distinct()
            )
        ).all()
        portfolio_ids = [str(row[0]) for row in pid_rows]

    rescored = 0

    for pid in portfolio_ids:
        try:
            async with TaskSessionLocal() as db:
                # Resolve the owning user_id + portfolio name for this portfolio.
                port_row = (
                    await db.execute(
                        select(MfPortfolio.user_id, MfPortfolio.name).where(
                            MfPortfolio.id == pid  # type: ignore[arg-type]
                        )
                    )
                ).first()
                if port_row is None:
                    continue
                uid = str(port_row[0])
                portfolio_name: str = port_row[1] or ""

                if not await is_plus(uid, db):
                    continue  # Free users — no history/snapshot written.

                # Load holding rows for this portfolio.
                holding_rows = (
                    await db.execute(
                        select(MfUserHolding).where(
                            MfUserHolding.portfolio_id == pid  # type: ignore[arg-type]
                        )
                    )
                ).scalars().all()

                if not holding_rows:
                    continue

                isins = [h.isin for h in holding_rows]
                nav_series, latest_nav = await _load_nav_series(db, isins)
                # Peer-cohort benchmark for category-relative labels (B58).
                cohort = await _compute_cohort(db, isins)

                # Batch-fetch scheme names for alert copy (never scores or numerics).
                scheme_rows = await db.execute(
                    select(MfFund.isin, MfFund.scheme_name).where(
                        MfFund.isin.in_(isins)
                    )
                )
                scheme_by_isin: dict[str, str] = {
                    i: n for i, n in scheme_rows.all()
                }

                # Score each fund via the bridge (never recompute the engine directly).
                for h_row in holding_rows:
                    isin = h_row.isin
                    signals = compute_fund_signals(
                        isin, nav_series.get(isin, []), category_relative=cohort.get(isin)
                    )
                    result = await score_fund(rengine, signals)
                    await upsert_user_fund_score(db, uid, result, pid)

                    new_label = result.verb_label.value
                    prior_label = await mf_history.get_prior_label(db, pid, isin, today)

                    inserted = await mf_history.append_score_history(
                        db,
                        user_id=uid,
                        result=result,
                        snapshot_date=today,
                        source="monthly_rescore",
                        portfolio_id=pid,
                    )

                    # Enqueue educational label-change alert (best-effort).
                    # Guard: inserted=True (real new row) + prior exists + label changed.
                    # The inserted guard makes alerts idempotent: a beat re-run on the
                    # same day returns inserted=False and skips the enqueue entirely.
                    if inserted and prior_label is not None and prior_label != new_label:
                        payload = {
                            "scheme_name": scheme_by_isin.get(isin, "A fund in your portfolio"),
                            "portfolio_name": portfolio_name,
                            "prior_label": prior_label,
                            "new_label": new_label,
                            "isin": isin,
                            "confidence_band": result.confidence_band.value,
                            # Stamp the in-force disclaimer version at GENERATION so the
                            # B26 deliver-seam audit ties to what was served, not the live
                            # constant at drain time (Tier-B audit-integrity fix).
                            "disclaimer_version": DISCLAIMER_VERSION,
                        }
                        for ch in ("telegram", "email"):
                            try:
                                await notif_service.publish_notification(
                                    redis, uid, ch, "mf_label_change", payload
                                )
                            except Exception:  # noqa: BLE001 — alert is best-effort; never abort rescore
                                # user_ref is hashed (never the raw uid in logs).
                                _slog.warning(
                                    "label_change_alert_enqueue_failed",
                                    user_ref=hash_user_ref(str(uid)),
                                    isin=isin,
                                    ch=ch,
                                )

                # Build snapshot from current holdings + latest NAV.
                holdings: list[_Holding] = []
                for h_row in holding_rows:
                    nav = latest_nav.get(h_row.isin)
                    current_value = (
                        float(h_row.units) * nav if nav is not None else 0.0
                    )
                    invested = float(h_row.invested_amount) if h_row.invested_amount is not None else 0.0
                    holdings.append(
                        _Holding(
                            isin=h_row.isin,
                            units=float(h_row.units),
                            invested_amount=invested,
                            current_value=current_value,
                            category="uncategorized",
                            cashflows=[_CashFlow(when=today, amount=current_value)],
                        )
                    )

                snap = build_snapshot(holdings)
                await mf_history.persist_portfolio_snapshot(
                    db,
                    user_id=uid,
                    snapshot_date=today,
                    snap=snap,
                    portfolio_id=pid,
                )
                rescored += 1

        except Exception:  # noqa: BLE001 — one bad portfolio never aborts the beat
            logger.exception("monthly_rescore: failed for portfolio_id=%s", pid)
            continue

    summary = f"monthly_rescore: rescored {rescored} Plus users"
    logger.info(summary)
    return summary


@celery_app.task(name="dhanradar.tasks.mf.purge_cas_files")
def purge_cas_files() -> str:
    """24h backstop: delete any raw CAS file older than the TTL (anti-pattern guard)."""
    import tempfile

    d = os.path.join(tempfile.gettempdir(), "dhanradar_cas")
    if not os.path.isdir(d):
        return "purge: no dir"
    now = time.time()
    removed = 0
    for name in os.listdir(d):
        fp = os.path.join(d, name)
        try:
            if os.path.isfile(fp) and (now - os.path.getmtime(fp)) > _UPLOAD_TTL_SECONDS:
                os.remove(fp)
                removed += 1
        except OSError:
            pass
    return f"purge: removed {removed}"
