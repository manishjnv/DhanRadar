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
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

from structlog.contextvars import bind_contextvars

from dhanradar.celery_app import celery_app
from dhanradar.core.logging import get_logger, hash_user_ref
from dhanradar.mf import service
from dhanradar.mf.cas import CasParseError, ParsedHolding, parse_cas
from dhanradar.mf.cohort import CohortBenchmark, FundStats
from dhanradar.mf.scoring_bridge import score_fund, upsert_user_fund_score
from dhanradar.mf.signals import CategoryRelative, compute_fund_signals
from dhanradar.mf.snapshot import CashFlow, Holding, build_snapshot
from dhanradar.mf.taxonomy import canonical_for
from dhanradar.mf.taxonomy import summarize as taxonomy_summarize

logger = logging.getLogger(__name__)
_slog = get_logger(__name__)

_UPLOAD_TTL_SECONDS = 24 * 3600

# Batch size for bulk-upsert statements — bounds memory and statement size.
_UPSERT_CHUNK = 2000


def parsed_to_snapshot_holdings(
    parsed: list[ParsedHolding],
    nav_map: dict[str, float] | None = None,
    category_map: dict[str, str] | None = None,
) -> list[Holding]:
    """Map parsed CAS holdings → snapshot.Holding, applying the latest NAV when
    available (else falling back to the CAS-reported valuation). Pure + testable.

    ``category_map`` (isin → SEBI-canonical or raw AMFI category from mf_funds) fills
    each holding's category so the portfolio category-allocation is real; a holding
    whose ISIN is not in the master stays ``"uncategorized"`` (honest)."""
    nav_map = nav_map or {}
    category_map = category_map or {}
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
                category=(category_map.get(p.isin) or "uncategorized"),
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

    Deduplication: the AMFI feed sometimes emits duplicate (isin, nav_date) pairs
    within a single batch, which triggers asyncpg.CardinalityViolationError on the
    ON CONFLICT DO UPDATE.  Last-seen row wins (dict keyed by (isin, nav_date)).
    """
    out: dict[tuple[str, object], dict] = {}
    for row in rows:
        isin = row.isin_growth or row.isin_reinvest
        if isin is None:
            continue
        out[(isin, row.nav_date)] = {
            "isin": isin,
            "nav_date": row.nav_date,
            "nav": row.nav,
            "source": "amfi",
        }
    return list(out.values())


def _navrows_to_fund_upserts(rows: Any) -> list[dict]:
    """
    Map a list of NavRow → list of dicts ready for mf_funds upsert.

    Only the three columns this feed owns are included: amfi_code, scheme_name,
    category.  isin is the PK (isin_growth preferred, else isin_reinvest).
    Rows without a keyable ISIN are skipped.

    Deduplication: last-seen row wins for duplicate ISINs in one batch (dict keyed
    by isin), preventing ON CONFLICT DO UPDATE cardinality errors.
    """
    out: dict[str, dict] = {}
    for row in rows:
        isin = row.isin_growth or row.isin_reinvest
        if isin is None:
            continue
        out[isin] = {
            "isin": isin,
            "amfi_code": row.amfi_code,
            "scheme_name": row.scheme_name,
            "category": row.category,
            "sebi_category": canonical_for(row.category),
        }
    return list(out.values())


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


async def _fetch_fund_categories(db: Any, isins: list[str]) -> dict[str, str]:
    """Map isin → validated SEBI category (sebi_category preferred; falls back to raw
    AMFI category) from the mf_funds master (read-only). Fills holding categories so
    the portfolio category-allocation is real; an ISIN absent from the master (or with
    no category data) stays 'uncategorized' (honest)."""
    if not isins:
        return {}
    from sqlalchemy import select

    from dhanradar.models.mf import MfFund

    rows = (
        await db.execute(
            select(MfFund.isin, MfFund.sebi_category, MfFund.category)
            .where(MfFund.isin.in_(isins))
        )
    ).all()
    return {i: (sc or c) for i, sc, c in rows if (sc or c)}


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
        # Resolve each holding's AMFI category from the master so the snapshot's
        # category-allocation and the per-fund Category column are real (else every
        # holding buckets as "uncategorized" → a meaningless 100% donut).
        category_map = await _fetch_fund_categories(db, [p.isin for p in parsed])

        snapshot_holdings = parsed_to_snapshot_holdings(
            parsed, nav_map=latest_nav, category_map=category_map
        )
        snap = build_snapshot(snapshot_holdings)
        # B65 observability: an uncomputable XIRR must be visible in worker logs,
        # not discovered by eyeball in a report. Log the boolean only — a user's
        # XIRR value is personal financial data (DPDP log discipline).
        _slog.info(
            "mf.snapshot.built",
            funds=len(parsed),
            cashflows=sum(len(h.cashflows) for h in snapshot_holdings),
            xirr_computed=snap.xirr_pct is not None,
        )

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
            # Fetch the previous label BEFORE writing today's row (snapshot_date <
            # today is the filter, so today's row is excluded either way).
            # None on first upload — delta arrow is suppressed in the frontend.
            previous_label_val = await mf_history.get_prior_label(
                db, portfolio_id, p.isin, date.today()
            )
            # Write label history for ALL users (not just Plus) so the delta feature
            # (Feature 3: ↑/↓ arrow on the report) works for free users too.
            # The full history READ endpoint stays Plus-gated (router.py).
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
                "category": category_map.get(p.isin),
                "units": p.units, "invested_amount": p.cost, "current_value": p.value,
                "verb_label": result.verb_label.value, "confidence_band": result.confidence_band.value,
                "contributing_signals": result.contributing_signals,
                "contradicting_signals": result.contradicting_signals,
                "previous_label": previous_label_val,
                "confidence_factors": dict(result.confidence_factors),
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
                report_payload["commentary"] = await generate_commentary(
                    OpenRouterGateway(), user_id=user_id, db=db, snapshot=snap, funds=funds_payload,
                    request_id=request_id,
                )
            else:
                report_payload["commentary"] = {"state": "upgrade_required", "reason": "plus_feature"}
        except Exception:  # noqa: BLE001 — commentary is best-effort; report still completes
            logger.exception("AI commentary failed job=%s", job_id)
            report_payload["commentary"] = {"state": "unavailable", "reason": "internal_error"}

        await redis.set(
            f"{service._REPORT_PREFIX}{job_id}", json.dumps(report_payload), ex=service._REPORT_TTL
        )
        await db.execute(
            update(MfCasJob).where(MfCasJob.job_id == job_id).values(
                status="done", progress_pct=100, completed_at=datetime.now(UTC)
            )
        )
        # Stamp latest_job_id on the portfolio so GET /mf/portfolio/latest works
        # and the daily refresh task knows which job to rebuild. Portfolio lifecycle fix.
        import uuid as _uuid

        from dhanradar.models.mf import MfPortfolio as _MfPortfolio
        await db.execute(
            update(_MfPortfolio)
            .where(_MfPortfolio.id == _uuid.UUID(portfolio_id))
            .values(latest_job_id=_uuid.UUID(job_id))
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

# B63: peers' NAV series are loaded in batches of this many ISINs. Loading every
# peer's 1200-day series at once OOM-killed (SIGKILL) the 640M batch worker the
# moment the NAV table became complete (5.9M rows; hundreds of peers per
# category). Peak memory is now one batch; per-peer stats are identical — the
# same long_horizon_stats runs on the same per-fund series either way.
_COHORT_PEER_CHUNK = 200

# Batch size for the nightly mf_metrics_refresh upsert (ISINs per iteration).
_METRICS_REFRESH_CHUNK = 500

# Peer-cohort GROUPING KEY — VERSIONED METHODOLOGY (B6/B28 two-person gate), B66-f1
# part 2. Which mf_funds column groups peers into a category cohort:
#   * "category"      — the RAW AMFI string (v1.1). Malformed variants (bare "ELSS",
#     double-space "Other  ETFs", curly-apostrophe "Children's") and pre-2017 legacy
#     umbrellas ("Income"/"Growth"/"Gilt") each form their own string-distinct cohort
#     → fragmentation + a few bogus mega-cohorts.
#   * "sebi_category" — the VALIDATED canonical SEBI leaf (taxonomy.canonical_for,
#     B66). Malformed variants collapse into the correct canonical cohort; legacy
#     umbrellas are sebi_category NULL → excluded by SQL `IN` (NULLs never match) and
#     by the `if c` target filter → those funds stay HONESTLY UNCOHORTED (on_track +
#     the COHORT_NO_CANONICAL_CATEGORY context, B71). NEVER auto-mapped.
# This is the grouping key ONLY; the raw `category` column is never mutated
# (taxonomy.py invariant). Mirrored in ranking_configs_v1.json
# labels.cohort_grouping_key — lockstep test-enforced.
#
# v1.2 ACTIVATED 2026-06-14 (B66-f1 pt2): flipped to "sebi_category" under the B6/B28
# two-person gate (founder = approved_by ≠ created_by) + founder deploy approval, per
# ADR-0034. Read-only prod backtest measured 196 funds (1.40%) changing label (within
# the 5% churn gate). Prereqs B71 + B58-f5 landed first (PR #131). To roll back: set
# this to "category" + manifest to v1.1 and redeploy (indexes stay).
_COHORT_GROUPING_KEY = "sebi_category"


def _grouping_column(grouping_key: str):
    """Resolve the methodology cohort grouping key to its mf_funds column.

    Pure mapping (no DB access); raises on an unknown key so a typo in the
    methodology manifest fails loud rather than silently regrouping cohorts."""
    from dhanradar.models.mf import MfFund

    cols = {"category": MfFund.category, "sebi_category": MfFund.sebi_category}
    if grouping_key not in cols:
        raise ValueError(f"unknown cohort grouping key: {grouping_key!r}")
    return cols[grouping_key]


@dataclass(frozen=True)
class _CohortContext:
    """Pre-built peer-cohort benchmarks + per-fund long-horizon stats (B58-f2).

    Built ONCE per task run by :func:`_build_cohort_context`; per-portfolio label
    inputs then come from :func:`_relative_from_context` as pure lookups — the
    expensive peer NAV loads never repeat inside a per-portfolio loop."""

    category_by_isin: dict[str, str]
    stats_by_isin: dict[str, FundStats]
    benchmarks: dict[str, CohortBenchmark]
    # Targets present in mf_funds but with NO usable cohort key (NULL/blank/
    # "uncategorized" grouping value) — uncohorted, but KNOWN-uncohorted, so the
    # label carries an honest "no canonical category" context (B71) rather than a
    # silent on_track. Empty under the active "category" key (no prod fund lacks a
    # raw category); populated by the legacy umbrellas under "sebi_category".
    uncategorized_isins: frozenset[str] = frozenset()


_EMPTY_COHORT_CONTEXT = _CohortContext({}, {}, {})


async def _build_cohort_context(
    db: Any,
    target_isins: list[str],
    *,
    as_of: date | None = None,
    grouping_key: str = _COHORT_GROUPING_KEY,
) -> _CohortContext:
    """Build category peer-cohort benchmarks for the given target funds (B58).

    Read-only on the mf schema (MfFund + mf_fund_metrics) — no cross-module access.
    The peer set for a category is every fund AMFI tags in that category; the fund
    itself is included (negligible self-bias on a ≥5-peer median).

    ``grouping_key`` (B66-f1 pt2) selects the mf_funds column peers are grouped by
    — "category" (raw, v1.1 active) or "sebi_category" (validated canonical leaf).
    See ``_COHORT_GROUPING_KEY``: a fund whose grouping column is NULL/blank is
    dropped at step 1 and never appears as a peer (SQL ``IN`` excludes NULL), so it
    stays uncohorted → on_track fail-safe. The raw ``category`` column is never
    mutated regardless of the key (taxonomy.py invariant).

    Step 3 reads precomputed ``mf_fund_metrics`` rows (refreshed nightly by
    ``mf_metrics_refresh``) instead of loading peer NAV series into memory (B63).
    The stats are numerically identical — ``mf_metrics_refresh`` stores exactly
    ``long_horizon_stats()`` output on the same NAV data.

    ``as_of`` is kept for caller compatibility; stats are now precomputed so the
    value is not forwarded to the DB read.
    """
    from sqlalchemy import select

    from dhanradar.mf.cohort import build_benchmark
    from dhanradar.models.mf import MfFund, MfFundMetrics

    if not target_isins:
        return _EMPTY_COHORT_CONTEXT
    # as_of retained for signature compatibility; stats are precomputed nightly.
    group_col = _grouping_column(grouping_key)

    # 1. Resolve each target's grouping value; keep only real cohort keys. A target
    #    present in mf_funds but with a NULL/blank/"uncategorized" grouping value is
    #    KNOWN-uncohorted → it carries an honest "no canonical category" context
    #    (B71), distinct from a genuine matching-category on_track.
    cat_rows = (
        await db.execute(
            select(MfFund.isin, group_col).where(MfFund.isin.in_(target_isins))
        )
    ).all()
    target_category: dict[str, str] = {
        i: c for i, c in cat_rows if c and c != "uncategorized"
    }
    uncategorized = frozenset(
        i for i, c in cat_rows if not (c and c != "uncategorized")
    )
    categories = set(target_category.values())
    if not categories:
        # No target has a cohort key — still surface the known-uncohorted ones (B71).
        return _CohortContext({}, {}, {}, uncategorized)

    # 2. All peers in those cohorts (SQL ``IN`` excludes NULL-keyed funds).
    peer_rows = (
        await db.execute(
            select(MfFund.isin, group_col).where(group_col.in_(categories))
        )
    ).all()
    peers_by_cat: dict[str, list[str]] = {}
    all_peer_isins: list[str] = []
    for i, c in peer_rows:
        peers_by_cat.setdefault(c, []).append(i)
        all_peer_isins.append(i)

    # 3. Read precomputed long-horizon stats from mf_fund_metrics (refreshed nightly
    #    after nav_daily_fetch) in bounded chunks to stay under bind-param limits.
    #    Peers with no row default to (None, None, None) — identical to the old path's
    #    long_horizon_stats([]) for a fund AMFI tags in a category but with no NAV
    #    (that mf_funds-vs-mf_nav_history asymmetry predates this change; both paths
    #    treat it the same way).
    unique_peers = sorted(set(all_peer_isins))
    stats_by_isin: dict[str, FundStats] = {}
    found_any = False
    for start in range(0, len(unique_peers), _COHORT_PEER_CHUNK):
        batch = unique_peers[start : start + _COHORT_PEER_CHUNK]
        metric_rows = (
            await db.execute(
                select(
                    MfFundMetrics.isin,
                    MfFundMetrics.return_1y_pct,
                    MfFundMetrics.return_3y_pct,
                    MfFundMetrics.max_drawdown_pct,
                ).where(MfFundMetrics.isin.in_(batch))
            )
        ).all()
        if metric_rows:
            found_any = True
        row_map = {r.isin: (r.return_1y_pct, r.return_3y_pct, r.max_drawdown_pct) for r in metric_rows}
        for i in batch:
            stats_by_isin[i] = row_map.get(i, (None, None, None))

    # Empty-table safety net: if mf_fund_metrics has NO row for ANY peer (a fresh
    # deploy before the first mf_metrics_refresh, or a wiped table), every benchmark
    # would silently withhold → on_track for everyone. Fall back to the live NAV
    # computation for THIS run (the exact pre-refactor math — equivalent, just
    # memory-heavier) and log loudly so the missed populate is observable, not silent.
    if unique_peers and not found_any:
        from dhanradar.mf.signals import long_horizon_stats

        logger.critical(
            "mf_fund_metrics empty for %d peers — falling back to live cohort "
            "computation; run mf_metrics_refresh to populate", len(unique_peers),
        )
        ref_as_of = as_of or date.today()
        stats_by_isin = {}
        for start in range(0, len(unique_peers), _COHORT_PEER_CHUNK):
            batch = unique_peers[start : start + _COHORT_PEER_CHUNK]
            series, _ = await _load_nav_series(db, batch, lookback_days=_COHORT_LOOKBACK_DAYS)
            for i in batch:
                stats_by_isin[i] = long_horizon_stats(series.get(i, []), as_of=ref_as_of)

    # 4. Per-category median benchmark — unchanged.
    benchmarks = {
        cat: build_benchmark(cat, [stats_by_isin[i] for i in cat_isins])
        for cat, cat_isins in peers_by_cat.items()
    }
    return _CohortContext(target_category, stats_by_isin, benchmarks, uncategorized)


def _relative_from_context(
    ctx: _CohortContext, target_isins: list[str]
) -> dict[str, CategoryRelative]:
    """Each target's own stats vs its category benchmark — pure lookup against a
    pre-built context.  A fund absent from the result (no category at build time,
    thin cohort, or no NAV) is scored with no category red flag → on_track, the
    honest fail-safe.  A KNOWN-uncohorted fund (its grouping value was NULL/blank —
    a legacy umbrella with no canonical SEBI category) gets an explicit
    ``COHORT_NO_CANONICAL_CATEGORY`` context (B71) so its on_track reads
    honest-not-positive rather than implying a peer comparison was made."""
    from dhanradar.mf.cohort import compare_to_cohort
    from dhanradar.scoring.engine.signal_names import SignalName, display

    out: dict[str, CategoryRelative] = {}
    for i in target_isins:
        c = ctx.category_by_isin.get(i)
        if c is None:
            if i in ctx.uncategorized_isins:
                out[i] = CategoryRelative(
                    contributing=[display(SignalName.COHORT_NO_CANONICAL_CATEGORY)]
                )
            continue
        out[i] = compare_to_cohort(
            ctx.stats_by_isin.get(i, (None, None, None)), ctx.benchmarks.get(c)
        )
    return out


async def _compute_cohort(
    db: Any,
    target_isins: list[str],
    *,
    as_of: date | None = None,
    grouping_key: str = _COHORT_GROUPING_KEY,
) -> dict[str, CategoryRelative]:
    """Build category peer-cohort benchmarks and return each target fund's
    category-relative LABEL inputs (B58) — build + lookup in one call, for the
    single-portfolio path (CAS upload).  The monthly rescore builds the context
    once and reuses it across portfolios instead (B58-f2)."""
    ctx = await _build_cohort_context(db, target_isins, as_of=as_of, grouping_key=grouping_key)
    return _relative_from_context(ctx, target_isins)


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
    from sqlalchemy import func
    from sqlalchemy.dialects.postgresql import insert

    from dhanradar.db import TaskSessionLocal
    from dhanradar.market_data import amfi
    from dhanradar.models.mf import MfFund, MfNavHistory

    logger.info("nav_daily_fetch: fetching NAVAll.txt from AMFI")
    rows = await amfi.fetch_navall_rows_with_category()
    logger.info("nav_daily_fetch: fetched %d rows", len(rows))

    # Taxonomy validation — best-effort; never let logging raise and break ingestion.
    try:
        summary = taxonomy_summarize(r.category for r in rows)
        logger.info(
            "nav_daily_fetch: taxonomy counts %s",
            summary.counts,
        )
        if summary.counts.get("unknown", 0) > 0 or summary.counts.get("legacy", 0) > 0:
            logger.warning(
                "nav_daily_fetch: taxonomy drift detected — "
                "unknown_samples=%r legacy_samples=%r",
                summary.unknown_samples,
                summary.legacy_samples,
            )
    except Exception:  # noqa: BLE001
        logger.warning("nav_daily_fetch: taxonomy summarize failed (non-fatal)", exc_info=True)

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
                set_={
                    "nav": insert(MfNavHistory).excluded.nav,
                    "source": "amfi",
                    "ingested_at": func.now(),
                },
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
                    "sebi_category": insert(MfFund).excluded.sebi_category,
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

    from sqlalchemy import func
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
                        set_={
                            "nav": insert(MfNavHistory).excluded.nav,
                            "source": "amfi",
                            "ingested_at": func.now(),
                        },
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


@celery_app.task(name="dhanradar.tasks.mf.mf_metrics_refresh")
def mf_metrics_refresh() -> str:
    """Nightly precompute of per-fund long-horizon stats into mf_fund_metrics.

    Runs after nav_daily_fetch so metrics reflect the day's fresh NAV.
    The cohort builder reads these rows instead of loading peer NAV series
    into worker memory (B63 memory cap).  Wired to the beat schedule.
    """
    try:
        return asyncio.run(_metrics_refresh_pipeline())
    except Exception:  # noqa: BLE001
        logger.exception("mf_metrics_refresh pipeline error")
        return "mf_metrics_refresh: failed — see worker logs"


async def _metrics_refresh_pipeline() -> str:
    from sqlalchemy import func, select
    from sqlalchemy.dialects.postgresql import insert

    from dhanradar.db import TaskSessionLocal
    from dhanradar.mf.signals import long_horizon_stats
    from dhanradar.models.mf import MfFundMetrics, MfNavHistory

    today = date.today()

    async with TaskSessionLocal() as db:
        # Load all ISINs that have any NAV data.
        isin_rows = (
            await db.execute(
                select(MfNavHistory.isin).distinct()
            )
        ).all()
        all_isins = [r[0] for r in isin_rows]

    logger.info("mf_metrics_refresh: %d ISINs to process", len(all_isins))

    n_processed = 0
    for start in range(0, len(all_isins), _METRICS_REFRESH_CHUNK):
        chunk = all_isins[start : start + _METRICS_REFRESH_CHUNK]
        if not chunk:
            continue

        async with TaskSessionLocal() as db:
            # Load long NAV series for this chunk (same lookback as cohort builder).
            series, _ = await _load_nav_series(db, chunk, lookback_days=_COHORT_LOOKBACK_DAYS)

            upsert_dicts: list[dict] = []
            for isin in chunk:
                r1, r3, dd = long_horizon_stats(series.get(isin, []), as_of=today)
                upsert_dicts.append({
                    "isin": isin,
                    "return_1y_pct": r1,
                    "return_3y_pct": r3,
                    "max_drawdown_pct": dd,
                    "nav_points": len(series.get(isin, [])),
                    "as_of_date": today,
                })

            # Bulk upsert in sub-chunks to bound statement size.
            for i in range(0, len(upsert_dicts), _UPSERT_CHUNK):
                sub = upsert_dicts[i : i + _UPSERT_CHUNK]
                if not sub:
                    continue
                stmt = insert(MfFundMetrics).values(sub).on_conflict_do_update(
                    index_elements=["isin"],
                    set_={
                        "return_1y_pct": insert(MfFundMetrics).excluded.return_1y_pct,
                        "return_3y_pct": insert(MfFundMetrics).excluded.return_3y_pct,
                        "max_drawdown_pct": insert(MfFundMetrics).excluded.max_drawdown_pct,
                        "nav_points": insert(MfFundMetrics).excluded.nav_points,
                        "as_of_date": insert(MfFundMetrics).excluded.as_of_date,
                        "computed_at": func.now(),
                    },
                )
                await db.execute(stmt)
            await db.commit()
            n_processed += len(chunk)

    summary = f"mf_metrics_refresh: {n_processed} funds"
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
        # All distinct (portfolio, isin) pairs that currently have holdings.
        pid_isin_rows = (
            await db.execute(
                select(MfUserHolding.portfolio_id, MfUserHolding.isin).distinct()
            )
        ).all()
        isins_by_pid: dict[str, set[str]] = {}
        raw_pids: list[Any] = []  # native UUIDs for the owner query — no str round-trip
        for pid_raw, isin_raw in pid_isin_rows:
            key = str(pid_raw)
            if key not in isins_by_pid:
                raw_pids.append(pid_raw)
            isins_by_pid.setdefault(key, set()).add(isin_raw)
        portfolio_ids = list(isins_by_pid)

        # B58-f2: build the peer-cohort context ONCE per run, over the union of
        # Plus portfolios' holdings — not per portfolio inside the loop (the
        # build re-fetched the same category peer NAV sets for every portfolio).
        # Peer loads stay chunked (B63).  A portfolio that turns Plus mid-run is
        # absent from the union and scores without category flags this month —
        # the same honest fail-safe as an uncategorized fund.
        owner_rows = (
            await db.execute(
                select(MfPortfolio.id, MfPortfolio.user_id).where(
                    MfPortfolio.id.in_(raw_pids)
                )
            )
        ).all()
        uid_by_pid = {str(r[0]): str(r[1]) for r in owner_rows}
        plus_by_uid: dict[str, bool] = {}
        for uid in set(uid_by_pid.values()):
            plus_by_uid[uid] = await is_plus(uid, db)
        plus_isins: set[str] = set()
        for pid, uid in uid_by_pid.items():
            if plus_by_uid.get(uid):
                plus_isins |= isins_by_pid[pid]
        cohort_ctx = (
            await _build_cohort_context(db, sorted(plus_isins), as_of=today)
            if plus_isins
            else _EMPTY_COHORT_CONTEXT
        )

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
                # Category-relative label inputs — pure lookup against the
                # run-level cohort context built before the loop (B58-f2).
                cohort = _relative_from_context(cohort_ctx, isins)

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


@celery_app.task(name="dhanradar.tasks.mf.reap_stuck_cas_jobs")
def reap_stuck_cas_jobs() -> str:
    """Beat task: mark CAS jobs that have been in a non-terminal status for more
    than 10 minutes as failed with the opaque code 'stuck_timeout'.

    Safe to run every few minutes — idempotent (WHERE completed_at IS NULL guards
    against re-touching already-terminal rows).  Also clears each reaped job's Redis
    dedup key so a clean re-upload reprocesses (uses the existing service.dedup_clear
    helper, which expects (user_id, portfolio_id, source_hash) — all present on the
    MfCasJob row).
    """
    try:
        return asyncio.run(_reap_stuck_cas_jobs())
    except Exception:  # noqa: BLE001
        logger.exception("reap_stuck_cas_jobs pipeline error")
        return "reap_stuck_cas_jobs: failed — see worker logs"


async def _reap_stuck_cas_jobs() -> str:
    from sqlalchemy import select, update

    from dhanradar.db import TaskSessionLocal
    from dhanradar.models.mf import MfCasJob
    from dhanradar.redis_client import get_redis

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)  # noqa: UP017 — matches pre-existing style

    async with TaskSessionLocal() as db:
        # SELECT the rows we are about to reap so we can clear their dedup keys.
        result = await db.execute(
            select(MfCasJob.job_id, MfCasJob.user_id, MfCasJob.portfolio_id, MfCasJob.source_hash)
            .where(
                MfCasJob.status.in_(["queued", "parsing", "scoring"]),
                MfCasJob.created_at < cutoff,
                MfCasJob.completed_at.is_(None),
            )
        )
        rows = result.all()

        if not rows:
            _slog.debug("reap_stuck_cas_jobs: nothing to reap")
            return "reaped 0 stuck jobs"

        job_ids = [str(r.job_id) for r in rows]

        # Bulk UPDATE to 'failed' / 'stuck_timeout' in one statement.
        await db.execute(
            update(MfCasJob)
            .where(MfCasJob.job_id.in_(job_ids))  # type: ignore[arg-type]
            .values(status="failed", error_message="stuck_timeout")
        )
        await db.commit()

    # Best-effort: clear Redis dedup keys so re-upload reprocesses cleanly.
    # Runs OUTSIDE the DB session (Redis is independent; a failure here is non-fatal).
    try:
        redis = get_redis()
        for r in rows:
            if r.portfolio_id is not None:
                await service.dedup_clear(
                    redis,
                    str(r.user_id),
                    str(r.portfolio_id),
                    r.source_hash,
                )
    except Exception:  # noqa: BLE001 — dedup clear is best-effort; reaper result is already committed
        logger.warning("reap_stuck_cas_jobs: Redis dedup_clear failed (non-fatal)", exc_info=True)

    n = len(rows)
    _slog.info("reap_stuck_cas_jobs: reaped", count=n, job_ids=job_ids)
    return f"reaped {n} stuck jobs"


@celery_app.task(name="dhanradar.tasks.mf.daily_portfolio_refresh")
def daily_portfolio_refresh() -> str:
    """Rebuild cached reports for every portfolio that has been uploaded at least once.

    Runs at 01:30 IST — after nav_daily_fetch (23:30) and mf_metrics_refresh (00:15)
    so current_value reflects today's NAV. Users who log in after this task has run
    see a fresh portfolio without re-uploading their CAS statement.
    """
    try:
        return asyncio.run(_daily_portfolio_refresh_pipeline())
    except Exception:
        logger.exception("daily_portfolio_refresh pipeline error")
        return "daily_portfolio_refresh: failed — see worker logs"


async def _daily_portfolio_refresh_pipeline() -> str:
    from sqlalchemy import select

    from dhanradar.db import TaskSessionLocal
    from dhanradar.models.mf import MfPortfolio
    from dhanradar.redis_client import get_redis

    redis = get_redis()
    refreshed = 0
    failed = 0

    async with TaskSessionLocal() as db:
        portfolios = (
            await db.execute(
                select(MfPortfolio).where(MfPortfolio.latest_job_id.isnot(None))
            )
        ).scalars().all()

        for portfolio in portfolios:
            try:
                job_id = str(portfolio.latest_job_id)
                portfolio_id = str(portfolio.id)
                # Invalidate the stale cache so rebuild_report_from_db writes fresh data.
                await redis.delete(f"{service._REPORT_PREFIX}{job_id}")
                await service.rebuild_report_from_db(
                    job_id=job_id, portfolio_id=portfolio_id, redis=redis, db=db
                )
                refreshed += 1
            except Exception:
                logger.exception(
                    "daily_portfolio_refresh: failed for portfolio_id=%s", portfolio.id
                )
                failed += 1

    return f"daily_portfolio_refresh: refreshed={refreshed} failed={failed}"


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
