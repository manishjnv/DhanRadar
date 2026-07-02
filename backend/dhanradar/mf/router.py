"""
DhanRadar — Mutual Fund API router (Phase 5, architecture Tier-C MF Module).

Endpoints (all under /api/v1):
  GET  /mf/portfolios              (authed) — list caller's portfolios
  POST /mf/portfolios              (authed) — create; Free capped at 1
  PATCH /mf/portfolios/{pid}       (authed) — rename (owner-only)
  DELETE /mf/portfolios/{pid}      (authed) — delete + cascade (owner-only)
  POST /mf/upload/cas              (authed + mf_analytics consent) — enqueue CAS parse
  GET  /mf/upload/cas/{job}/status (authed, own job) — poll progress (canonical path)
  GET  /mf/report/{job}            (authed, own job) — labelled report (disclosure-injected)
  GET  /mf/history                 (authed + Plus + mf_analytics consent) — label history

DPDP (B20): the CAS upload is a data-processing route handling financial PII, so
it is gated by RequireConsent("mf_analytics") — fail-closed 403 without consent.
Auth is checked first (401), then consent (403). IDOR: status/report are scoped to
the caller's own job; portfolio ops are scoped to the caller's user_id.

Idempotency-Key on POST /mf/portfolios: header accepted optionally but full
dedup is not implemented in this slice (noted for next iteration, non-neg #6).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.db import get_db
from dhanradar.deps import RequireConsent, UserContext, current_user_or_anonymous, is_plus
from dhanradar.mf import history as mf_history
from dhanradar.mf import service
from dhanradar.mf.ledger import allow_ledger_purge
from dhanradar.mf.schemas import (
    CasJobStatus,
    CasUploadResponse,
    FundCategoriesResponse,
    FundCategory,
    FundExplorerItem,
    FundExplorerResponse,
    FundSearchItem,
    MFResearchAskRequest,
    MFResearchAskResponse,
    PortfolioCreateRequest,
    PortfolioHistoryResponse,
    PortfolioLatestResponse,
    PortfolioListResponse,
    PortfolioReport,
    PortfolioSummary,
    SnapshotHistoryItem,
)
from dhanradar.models.auth import UserActivityLog
from dhanradar.models.mf import MfCasJob, MfPortfolio
from dhanradar.ratelimit import RateLimit
from dhanradar.redis_client import get_redis

router = APIRouter(prefix="/mf", tags=["mutual-fund"])
logger = logging.getLogger(__name__)

_MAX_CAS_BYTES = 15 * 1024 * 1024  # 15 MB cap on the upload
_rl_upload = RateLimit(max_requests=10, window_seconds=60)
_rl_explorer = RateLimit(max_requests=30, window_seconds=60)  # public explorer endpoints
_require_mf_consent = RequireConsent("mf_analytics")  # B20 — DPDP data-processing gate

# Validated sort-column whitelist — column expressions only, never interpolated from user input.
_SORT_COL: dict[str, str] = {
    "rank":         "r.rank",
    "return_3m":    "m.return_3m_pct",
    "return_6m":    "m.return_6m_pct",
    "return_1y":    "m.return_1y_pct",
    "return_3y":    "m.return_3y_pct",
    "return_5y":    "m.return_5y_pct",
    "max_drawdown": "m.max_drawdown_pct",
}
# Columns where ASC = "best first" (rank 1 is best; lower drawdown is better).
_SORT_BEST_ASC: frozenset[str] = frozenset({"rank", "max_drawdown"})
# Columns that need NULLS LAST (metrics may be absent; rank is always present).
_SORT_NULLS_LAST: frozenset[str] = frozenset({"return_3m", "return_6m", "return_1y", "return_3y", "return_5y", "max_drawdown"})

# Minimum NAV data-points required to surface a return figure.
# Below the threshold the field is suppressed (set to None) to avoid misleading
# partial-period return figures for young or very recently-launched funds.
_MIN_NAV_POINTS_1Y = 252   # ~1 trading year
_MIN_NAV_POINTS_3Y = 756   # ~3 trading years


def _sebi_display_name(full_category: str) -> str:
    """'Equity Scheme - Large Cap Fund' → 'Large Cap Fund'"""
    if " - " in full_category:
        return full_category.split(" - ", 1)[1]
    return full_category


def _upload_dir() -> str:
    d = os.path.join(tempfile.gettempdir(), "dhanradar_cas")
    os.makedirs(d, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Portfolio CRUD
# ---------------------------------------------------------------------------


@router.get("/portfolios", response_model=PortfolioListResponse)
async def list_portfolios(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
) -> PortfolioListResponse:
    """Return the authenticated caller's portfolios (IDOR: WHERE user_id==caller)."""
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")

    rows = (
        await db.execute(
            select(MfPortfolio)
            .where(MfPortfolio.user_id == uuid.UUID(user.user_id))
            .order_by(MfPortfolio.created_at)
        )
    ).scalars().all()

    portfolios = [
        PortfolioSummary(
            id=str(p.id),
            name=p.name,
            created_at=p.created_at.isoformat(),
        )
        for p in rows
    ]
    return PortfolioListResponse(portfolios=portfolios)


@router.post("/portfolios", response_model=PortfolioSummary, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    body: Annotated[PortfolioCreateRequest, Body()],
) -> PortfolioSummary:
    """Create a named portfolio.

    Free users are capped at 1 portfolio. Plus users are uncapped.
    Idempotency-Key header is accepted but not fully deduped in this slice (§ non-neg #6).
    """
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")

    uid = uuid.UUID(user.user_id)
    count_row = await db.execute(
        select(func.count()).where(MfPortfolio.user_id == uid)
    )
    count = count_row.scalar_one()

    if count >= 1 and not await is_plus(user.user_id, db):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"error": "upgrade_required", "upgrade_url": "/pricing"},
        )

    portfolio = MfPortfolio(user_id=uid, name=body.name)
    db.add(portfolio)
    await db.commit()
    # B85: no db.refresh — commit resets the SET LOCAL app.user_id GUC, so a refresh would re-SELECT
    # under FORCE RLS → 0 rows → 500. id/created_at are RETURNING-populated (kept by expire_on_commit=False).
    return PortfolioSummary(
        id=str(portfolio.id),
        name=portfolio.name,
        created_at=portfolio.created_at.isoformat(),
    )


@router.patch("/portfolios/{portfolio_id}", response_model=PortfolioSummary)
async def rename_portfolio(
    portfolio_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    body: Annotated[PortfolioCreateRequest, Body()],
) -> PortfolioSummary:
    """Rename a portfolio. Owner-only (404 on mismatch or bad uuid)."""
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")

    portfolio = await _own_portfolio(db, portfolio_id, user.user_id)
    portfolio.name = body.name
    await db.commit()
    # B85: no db.refresh — commit resets the SET LOCAL app.user_id GUC, so a refresh would re-SELECT
    # under FORCE RLS → 0 rows → 500. id/created_at stay loaded (kept by expire_on_commit=False).
    return PortfolioSummary(
        id=str(portfolio.id),
        name=portfolio.name,
        created_at=portfolio.created_at.isoformat(),
    )


@router.delete("/portfolios/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio(
    portfolio_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
) -> None:
    """Delete a portfolio and all its holdings/snapshots/history (CASCADE).
    Owner-only (404 on mismatch or bad uuid)."""
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")

    portfolio = await _own_portfolio(db, portfolio_id, user.user_id)
    # The ledger is append-only (I12); deleting a portfolio is a sanctioned purge, so opt this
    # transaction's CASCADE into the trigger bypass before the delete (see mf.ledger).
    await allow_ledger_purge(db)
    await db.delete(portfolio)
    await db.commit()


# ---------------------------------------------------------------------------
# CAS upload
# ---------------------------------------------------------------------------


@router.post("/upload/cas", response_model=CasUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_cas(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    file: Annotated[UploadFile, File()],
    password: Annotated[str | None, Form()] = None,
    portfolio_id: Annotated[str | None, Form()] = None,
    _rl: Annotated[None, Depends(_rl_upload)] = None,
) -> CasUploadResponse:
    # 1. Auth (401) BEFORE consent (403). The consent gate is invoked explicitly
    #    (keyword args) to preserve the 401-then-403 ordering; it is the same
    #    fail-closed RequireConsent used as a Depends elsewhere.
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    # 2. DPDP consent gate (B20) — fail-closed.
    await _require_mf_consent(user=user, db=db)

    # 3. Resolve portfolio_id — validate ownership or resolve the default.
    uid = uuid.UUID(user.user_id)
    if portfolio_id is not None:
        # Validate ownership (raises 404 on bad uuid / not owned).
        portfolio = await _own_portfolio(db, portfolio_id, user.user_id)
        resolved_portfolio_id = str(portfolio.id)
    else:
        # Auto-resolve: count existing portfolios for this user.
        count_row = await db.execute(select(func.count()).where(MfPortfolio.user_id == uid))
        count = count_row.scalar_one()
        if count == 0:
            # First portfolio — create 'Default' for free (no cap).
            portfolio = MfPortfolio(user_id=uid, name="Default")
            db.add(portfolio)
            await db.commit()
            # B85: no db.refresh (see create_portfolio) — commit resets the GUC; id is
            # RETURNING-populated post-commit, so a refresh would only re-SELECT → 0 rows under RLS → 500.
            resolved_portfolio_id = str(portfolio.id)
        elif count == 1:
            row = (
                await db.execute(select(MfPortfolio).where(MfPortfolio.user_id == uid))
            ).scalar_one()
            resolved_portfolio_id = str(row.id)
        else:
            # Multiple portfolios — caller must specify which one.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="portfolio_id_required",
            )

    # 4. Bounded read (cap memory at ~15MB+1 — never buffer an unbounded body).
    data = await file.read(_MAX_CAS_BYTES + 1)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty_file")
    if len(data) > _MAX_CAS_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file_too_large")

    # Detect file type — support CAS PDF and CAMS Transaction Details Statement
    # (.txt tab-separated, .xls, .xlsx).
    original_name = (file.filename or "").lower()
    if data.startswith(b"%PDF-"):
        file_ext = "pdf"
    elif original_name.endswith(".xlsx"):
        file_ext = "xlsx"
    elif original_name.endswith(".xls"):
        file_ext = "xls"
    elif original_name.endswith(".txt") or (
        # txt files: first line should look like the CAMS header (tab-separated ASCII)
        b"\t" in data[:200] and b"MF_NAME" in data[:200]
    ):
        file_ext = "txt"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unsupported_file_type",
        )

    redis = get_redis()
    source_hash = service.cas_sha256(data)

    # 5. Per-user-portfolio SHA-256 dedup — re-upload of the same statement returns
    #    the existing job; a different portfolio or user gets an independent job.
    existing = await service.dedup_lookup(redis, user.user_id, resolved_portfolio_id, source_hash)
    if existing:
        # Only short-circuit to a job that SUCCEEDED *and* whose report is still
        # retrievable. A prior job that failed/got stuck — OR a done job whose
        # report cache has since expired (dedup key lives 24h, report cache only
        # 2h) — must NOT be returned: the user is re-uploading precisely because it
        # did not work, and bouncing them to a job whose /report 404s is the bug.
        # Drop the stale record and reprocess the freshly-uploaded bytes.
        prior = await db.get(MfCasJob, uuid.UUID(existing))
        prior_status = prior.status if prior is not None else None
        if await service.can_return_existing(redis, prior_status, existing):
            return CasUploadResponse(job_id=existing, deduped=True)
        await service.dedup_clear(redis, user.user_id, resolved_portfolio_id, source_hash)

    # 6. Persist the raw file for the worker (purged after parse + 24h backstop),
    #    create the job row queued, enqueue, return < 200ms.
    job_id = str(uuid.uuid4())
    path = os.path.join(_upload_dir(), f"{job_id}.{file_ext}")
    with open(path, "wb") as fh:
        fh.write(data)

    db.add(MfCasJob(
        job_id=uuid.UUID(job_id),
        user_id=uid,
        portfolio_id=uuid.UUID(resolved_portfolio_id),
        status="queued",
        progress_pct=0,
        source_hash=source_hash,
    ))
    await db.commit()
    await service.dedup_record(redis, user.user_id, resolved_portfolio_id, source_hash, job_id)

    # 7. Keep the CAS password OFF the Celery broker — stash it in a short-lived
    #    Redis key the worker consumes-and-deletes (never serialized into a task arg).
    if password:
        await redis.set(f"mf:cas:pw:{job_id}", password, ex=600)

    from dhanradar.tasks.mf import parse_cas_job

    request_id: str | None = getattr(request.state, "request_id", None)
    parse_cas_job.delay(job_id, path, user.user_id, resolved_portfolio_id, request_id=request_id)

    # Best-effort: record the upload in auth.user_activity_log so it shows in the
    # admin activity feed. The job is already committed above — this must NEVER fail
    # the upload (mirrors auth.record_login's non-fatal pattern).
    try:
        # The MfCasJob commit above reset the request's SET LOCAL app.user_id GUC; re-set it so this
        # FORCE-RLS (B81) owner-write into auth.user_activity_log passes WITH CHECK (not bypassed).
        from dhanradar.db_security import set_rls_user

        await set_rls_user(db, user.user_id)
        db.add(UserActivityLog(user_id=uid, event_type="cas_upload", request_id=request_id))
        await db.commit()
    except Exception:  # noqa: BLE001 — observational; must never break the upload
        logger.warning("mf: failed to record cas_upload activity — continuing")
        await db.rollback()

    return CasUploadResponse(job_id=job_id, estimated_seconds=60)


# ---------------------------------------------------------------------------
# Job status + report
# ---------------------------------------------------------------------------


@router.get("/upload/cas/{job_id}/status", response_model=CasJobStatus)
async def cas_status(
    job_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
) -> CasJobStatus:
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    job = await _own_job(db, job_id, user.user_id)
    return CasJobStatus(
        job_id=str(job.job_id),
        status=job.status,
        progress_pct=job.progress_pct,
        error_message=job.error_message,
    )


@router.get("/report/{job_id}", response_model=PortfolioReport)
async def cas_report(
    job_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
) -> PortfolioReport:
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    job = await _own_job(db, job_id, user.user_id)  # IDOR guard
    portfolio_id = str(job.portfolio_id) if job.portfolio_id else None
    redis = get_redis()
    cached = await redis.get(f"{service._REPORT_PREFIX}{job_id}")
    if cached:
        payload = json.loads(cached)
        payload["portfolio_id"] = portfolio_id  # use DB-authoritative value; adds if absent, overwrites if stale
        # Fetch market ranks at read time — ranks are not baked into the Redis
        # cache so they remain fresh after nightly compute_market_ranks runs.
        isins = [f["isin"] for f in payload.get("funds", [])]
        rank_by_isin: dict[str, dict] = {}
        if isins:
            try:
                rank_by_isin = await service.fetch_fund_ranks(db, isins)
            except Exception:
                logger.warning("cas_report: rank fetch failed (non-fatal)", exc_info=True)
        return service.assemble_report(**payload, rank_by_isin=rank_by_isin)
    if job.status != "done":
        # Not ready yet — return the current status with the disclosure injected.
        return service.assemble_report(
            job_id=job_id, status=job.status, snapshot=None, funds=[], portfolio_id=portfolio_id
        )
    # Cache miss on a completed job: rebuild from stored holdings + today's NAV so
    # the user sees their portfolio without re-uploading (CAS lifecycle fix).
    if portfolio_id:
        rebuilt = await service.rebuild_report_from_db(
            job_id=job_id, portfolio_id=portfolio_id, redis=redis, db=db
        )
        if rebuilt:
            return rebuilt
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report_expired")


# ---------------------------------------------------------------------------
# Portfolio latest — lets the frontend navigate without a job_id
# ---------------------------------------------------------------------------


@router.get("/portfolio/latest", response_model=PortfolioLatestResponse)
async def portfolio_latest(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
) -> PortfolioLatestResponse:
    """Return the latest completed job_id for the caller's portfolio.

    Allows the frontend to navigate to GET /report/{job_id} (which rebuilds from
    stored holdings if the cache has expired) without the user needing to supply
    or re-upload a CAS statement.  Returns 404 when no portfolio exists yet.
    """
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")

    result = await db.execute(
        select(MfPortfolio)
        .where(MfPortfolio.user_id == user.user_id)
        .where(MfPortfolio.latest_job_id.isnot(None))
        .order_by(MfPortfolio.created_at.desc())
        .limit(1)
    )
    portfolio = result.scalar_one_or_none()

    if not portfolio or not portfolio.latest_job_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no_portfolio")

    return PortfolioLatestResponse(
        job_id=str(portfolio.latest_job_id),
        portfolio_id=str(portfolio.id),
        portfolio_name=portfolio.name,
    )


# ---------------------------------------------------------------------------
# History (Plus-gated)
# ---------------------------------------------------------------------------


@router.get("/history", response_model=PortfolioHistoryResponse)
async def portfolio_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
    portfolio_id: Annotated[str | None, Query()] = None,
) -> PortfolioHistoryResponse:
    """Return Plus users' label history grouped by snapshot date.

    ``portfolio_id`` query param is required (caller must specify which portfolio).
    Gating order: 401 (anonymous) → 402 (not Plus) → 403 (no consent).
    No numeric fields in the response (non-neg #2).
    """
    from dhanradar.scoring.engine.schemas import (
        DISCLAIMER_VERSION,
        DISCLOSURE_BUNDLE,
        NOT_ADVICE,
    )

    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    if not await is_plus(user.user_id, db):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"error": "upgrade_required", "upgrade_url": "/pricing"},
        )
    await _require_mf_consent(user=user, db=db)

    if portfolio_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="portfolio_id_required",
        )
    # Validate ownership (raises 404 on bad uuid / not owned).
    portfolio = await _own_portfolio(db, portfolio_id, user.user_id)

    raw = await mf_history.get_snapshot_history(db, user.user_id, str(portfolio.id))
    snapshots = [
        SnapshotHistoryItem(snapshot_date=item["snapshot_date"], funds=item["funds"])
        for item in raw
    ]
    return PortfolioHistoryResponse(
        snapshots=snapshots,
        disclosure=DISCLOSURE_BUNDLE,
        not_advice=NOT_ADVICE,
        disclaimer_version=DISCLAIMER_VERSION,
    )


# ---------------------------------------------------------------------------
# F2 — MF research assistant (Plus-gated, grounded, non-advisory)
# ---------------------------------------------------------------------------


@router.post("/report/{job_id}/ask", response_model=MFResearchAskResponse)
async def ask_mf_research(
    job_id: str,
    body: Annotated[MFResearchAskRequest, Body()],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
) -> MFResearchAskResponse:
    """Grounded MF research assistant — educational, non-advisory (F2).

    Gate order: 401 (anon) → IDOR (job ownership) → 422 (report not done) →
    402 (not Plus) → consent → daily cap → gateway → confidence floor → audit.
    No numeric confidence float in the response (non-neg #2).
    """
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    job = await _own_job(db, job_id, user.user_id)  # IDOR: own job only
    if job.status != "done":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="report_not_ready",
        )
    if not await is_plus(user.user_id, db):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"error": "upgrade_required", "upgrade_url": "/pricing"},
        )

    # Load cached report for grounding context.
    redis_client = get_redis()
    cached_bytes = await redis_client.get(f"{service._REPORT_PREFIX}{job_id}")
    if not cached_bytes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report_expired")

    payload = json.loads(cached_bytes)
    snapshot_data: dict = payload.get("snapshot") or {}
    funds_data: list[dict] = payload.get("funds") or []

    # Lightweight snapshot object for the research module (attribute access).
    from types import SimpleNamespace

    snapshot = SimpleNamespace(
        category_allocation=snapshot_data.get("category_allocation") or {},
        xirr_pct=snapshot_data.get("xirr_pct"),
    )

    from datetime import UTC, datetime

    from dhanradar.ai_gateway.gateway import OpenRouterGateway
    from dhanradar.mf.research import generate_research_answer

    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    result = await generate_research_answer(
        OpenRouterGateway(),
        user_id=user.user_id,
        db=db,
        redis=redis_client,
        snapshot=snapshot,
        funds=funds_data,
        question=body.question,
        date_str=date_str,
        request_id=getattr(request.state, "request_id", None),
    )

    return MFResearchAskResponse(**result)


# ---------------------------------------------------------------------------
# Fund Explorer — public endpoints (no auth, no user data)
# ---------------------------------------------------------------------------


@router.get("/funds/categories", response_model=FundCategoriesResponse)
async def fund_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    _rl: Annotated[None, Depends(_rl_explorer)] = None,
) -> FundCategoriesResponse:
    """Return distinct SEBI categories that have at least one ranked fund.

    Public — no auth required. Sourced from the most recent compute_market_ranks
    run. Returns an empty list before the nightly task has seeded mf_fund_ranks.
    """
    from sqlalchemy import text as sa_text

    from dhanradar.scoring.engine.schemas import DISCLOSURE_BUNDLE, NOT_ADVICE  # noqa: F401

    rows = (
        await db.execute(
            sa_text(
                "SELECT r.sebi_category, COUNT(DISTINCT r.isin)::int AS fund_count"
                " FROM mf.mf_fund_ranks r"
                " WHERE r.as_of_date = (SELECT MAX(as_of_date) FROM mf.mf_fund_ranks)"
                " GROUP BY r.sebi_category"
                " ORDER BY r.sebi_category"
            )
        )
    ).all()

    cats = [
        FundCategory(
            key=r.sebi_category,
            display_name=_sebi_display_name(r.sebi_category),
            fund_count=r.fund_count,
        )
        for r in rows
    ]
    return FundCategoriesResponse(categories=cats)


@router.get("/search", response_model=list[FundSearchItem])
async def fund_search(
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str, Query()],
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
    _rl: Annotated[None, Depends(_rl_explorer)] = None,
) -> list[FundSearchItem]:
    """Trigram-fuzzy fund search for the global cmdk search bar.

    Public — no auth required.  Returns scheme_name, amc_name, isin, and
    sebi_category only.  Never includes unified_score, factor weights, or any
    numeric value (non-neg #2).

    SQL is fully parameterised; the user query is bound via ``:q`` — never
    interpolated into the statement string (SQL-injection safe).

    Uses pg_trgm word_similarity for typo tolerance plus ILIKE for exact
    substring priority.  The GIN index on scheme_name/amc_name (migration
    0040) accelerates both predicates.
    """
    from sqlalchemy import text as sa_text

    qn = q.strip()
    if len(qn) < 2:
        return []

    # Split query into tokens (cap at 6) for token-AND relevance.
    # Every token must match scheme_name OR amc_name (ILIKE substring OR
    # word_similarity >= 0.3 for typo tolerance).  Only the param NAME
    # (t0, t1, …) is f-string-interpolated; the VALUE is always a bind param.
    tokens = [t for t in qn.split() if t][:6]
    if not tokens:
        return []

    params: dict[str, object] = {"q": qn, "qprefix": qn + "%", "lim": limit}
    clauses: list[str] = []
    for i, tok in enumerate(tokens):
        k = f"t{i}"
        params[k] = tok
        clauses.append(
            f"(f.scheme_name ILIKE '%' || :{k} || '%'"
            f" OR coalesce(f.amc_name, '') ILIKE '%' || :{k} || '%'"
            f" OR word_similarity(:{k}, f.scheme_name) >= 0.3"
            f" OR word_similarity(:{k}, coalesce(f.amc_name, '')) >= 0.3)"
        )
    where_tokens = " AND ".join(clauses)

    # Source only RANKED + CATEGORIZED funds via the latest rank per ISIN.
    # The JOIN condition f.sebi_category = r.sebi_category ensures the returned
    # sebi_category is the one the detail page can resolve via /mf/funds?category=.
    # Funds present in mf_funds but absent from mf_fund_ranks (unranked) are excluded.
    sql = (
        "SELECT f.isin, f.scheme_name, f.fund_name_short, f.amc_name, f.sebi_category,"
        "       f.plan_type, f.option_type, f.idcw_frequency"
        " FROM mf.mf_funds f"
        " JOIN ("
        "   SELECT DISTINCT ON (isin) isin, sebi_category"
        "   FROM mf.mf_fund_ranks"
        "   ORDER BY isin, as_of_date DESC"
        " ) r ON f.isin = r.isin AND f.sebi_category = r.sebi_category"
        f" WHERE {where_tokens}"
        " ORDER BY (f.scheme_name ILIKE :qprefix) DESC,"
        "          similarity(f.scheme_name, :q) DESC,"
        "          f.scheme_name ASC"
        " LIMIT :lim"
    )

    rows = (await db.execute(sa_text(sql), params)).all()

    return [
        FundSearchItem(
            isin=r.isin,
            scheme_name=r.scheme_name,
            fund_name_short=r.fund_name_short,
            amc_name=r.amc_name,
            sebi_category=r.sebi_category,
            plan_type=r.plan_type,
            option_type=r.option_type,
            idcw_frequency=r.idcw_frequency,
        )
        for r in rows
    ]


@router.get("/funds", response_model=FundExplorerResponse)
async def fund_explorer_list(
    db: Annotated[AsyncSession, Depends(get_db)],
    category: Annotated[str | None, Query()] = None,
    sort: Annotated[str, Query()] = "rank",
    sort_dir: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    plan_type: Annotated[str | None, Query(pattern="^(direct|regular)$")] = None,
    option_type: Annotated[str | None, Query(pattern="^(growth|idcw)$")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=500)] = 20,
    _rl: Annotated[None, Depends(_rl_explorer)] = None,
) -> FundExplorerResponse:
    """Paginated, sortable fund list for the public Fund Explorer.

    Filters to a single sebi_category (required). Joins mf_funds with the latest
    mf_fund_ranks row and latest mf_fund_metrics row for each ISIN.

    unified_score is NEVER included in the response (non-neg #2).
    No user data — safe to cache at the edge and expose publicly.
    """
    from sqlalchemy import text as sa_text

    from dhanradar.scoring.engine.schemas import DISCLOSURE_BUNDLE, NOT_ADVICE

    if not category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="category_required",
        )
    if sort not in _SORT_COL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid_sort: must be one of {list(_SORT_COL)}",
        )

    # Build ORDER BY: sort_dir='desc' means "best first"; 'asc' means "worst first".
    # For rank/max_drawdown, SQL ASC = best-first; for returns, SQL DESC = best-first.
    want_sql_asc = (sort_dir == "desc") == (sort in _SORT_BEST_ASC)
    sql_dir = "ASC" if want_sql_asc else "DESC"
    nulls = " NULLS LAST" if sort in _SORT_NULLS_LAST else ""
    order_clause = f"{_SORT_COL[sort]} {sql_dir}{nulls}"
    offset = (page - 1) * limit

    # Build optional server-side filters (plan_type, option_type).
    # Values come from regex-validated params — hardcoded SQL literals are safe here.
    extra_where: list[str] = []
    filter_params: dict[str, object] = {"category": category}
    if plan_type:
        extra_where.append("f.plan_type = :plan_type")
        filter_params["plan_type"] = plan_type
    if option_type == "growth":
        extra_where.append("f.option_type = 'growth'")
    elif option_type == "idcw":
        extra_where.append("f.option_type IN ('idcw', 'dividend_reinvest', 'dividend_payout')")
    extra_filter = (" AND " + " AND ".join(extra_where)) if extra_where else ""

    base_sql = (
        "SELECT"
        "  f.isin, f.scheme_name, f.fund_name_short, f.amc_name, f.sebi_category,"
        "  f.plan_type, f.option_type, f.idcw_frequency,"
        "  r.rank, r.total_in_cat, r.verb_label,"
        "  m.return_3m_pct, m.return_6m_pct, m.return_1y_pct, m.return_3y_pct, m.return_5y_pct, m.nav_points"
        " FROM mf.mf_funds f"
        " JOIN ("
        "   SELECT DISTINCT ON (isin) isin, rank, total_in_cat, verb_label"
        "   FROM mf.mf_fund_ranks"
        "   WHERE sebi_category = :category"
        "   ORDER BY isin, as_of_date DESC"
        " ) r ON f.isin = r.isin"
        " LEFT JOIN ("
        "   SELECT DISTINCT ON (isin) isin, return_3m_pct, return_6m_pct, return_1y_pct, return_3y_pct, return_5y_pct, max_drawdown_pct, nav_points"
        "   FROM mf.mf_fund_metrics"
        "   ORDER BY isin, as_of_date DESC"
        " ) m ON f.isin = m.isin"
        f" WHERE f.sebi_category = :category{extra_filter}"
        f" ORDER BY {order_clause}"
        " LIMIT :lim OFFSET :off"
    )
    count_sql = (
        "SELECT COUNT(*)::int"
        " FROM mf.mf_funds f"
        " JOIN ("
        "   SELECT DISTINCT ON (isin) isin"
        "   FROM mf.mf_fund_ranks"
        "   WHERE sebi_category = :category"
        "   ORDER BY isin, as_of_date DESC"
        " ) r ON f.isin = r.isin"
        f" WHERE f.sebi_category = :category{extra_filter}"
    )

    params = {**filter_params, "lim": limit, "off": offset}
    rows = (await db.execute(sa_text(base_sql), params)).all()
    total: int = (await db.execute(sa_text(count_sql), filter_params)).scalar_one()

    items = [
        FundExplorerItem(
            isin=r.isin,
            scheme_name=r.scheme_name,
            fund_name_short=r.fund_name_short,
            amc_name=r.amc_name,
            sebi_category=r.sebi_category,
            verb_label=r.verb_label,
            confidence_band=None,
            confidence_factors=None,
            category_rank=r.rank,
            category_total=r.total_in_cat,
            return_3m_pct=r.return_3m_pct,
            return_6m_pct=r.return_6m_pct,
            return_1y_pct=r.return_1y_pct if (r.nav_points or 0) >= _MIN_NAV_POINTS_1Y else None,
            return_3y_pct=r.return_3y_pct if (r.nav_points or 0) >= _MIN_NAV_POINTS_3Y else None,
            return_5y_pct=r.return_5y_pct,
            plan_type=r.plan_type,
            option_type=r.option_type,
            idcw_frequency=r.idcw_frequency,
            amc_level_aum_crore=None,  # ADR-0035: endpoint unconfirmed; stays None
        )
        for r in rows
    ]
    return FundExplorerResponse(
        funds=items,
        total=total,
        page=page,
        limit=limit,
        disclosure=DISCLOSURE_BUNDLE,
        not_advice=NOT_ADVICE,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _own_job(db: AsyncSession, job_id: str, user_id: str) -> MfCasJob:
    try:
        jid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
    job = await db.scalar(
        select(MfCasJob).where(MfCasJob.job_id == jid, MfCasJob.user_id == uuid.UUID(user_id))
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
    return job


async def _own_portfolio(db: AsyncSession, portfolio_id: str, user_id: str) -> MfPortfolio:
    """Return the portfolio if it exists and belongs to user_id; 404 otherwise.

    Also raises 404 for a malformed UUID — never leaks whether the row exists.
    """
    try:
        pid = uuid.UUID(portfolio_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found")
    portfolio = await db.scalar(
        select(MfPortfolio).where(
            MfPortfolio.id == pid,
            MfPortfolio.user_id == uuid.UUID(user_id),
        )
    )
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found")
    return portfolio


# ---------------------------------------------------------------------------
# Benchmark reference-data endpoint (public — no auth, no RLS)
# ---------------------------------------------------------------------------

@router.get("/benchmark/nifty50")
async def benchmark_nifty50(
    db: Annotated[AsyncSession, Depends(get_db)],
    from_date: str | None = Query(None, alias="from", description="ISO date YYYY-MM-DD"),
    to_date: str | None = Query(None, alias="to", description="ISO date YYYY-MM-DD"),
    _rl: Annotated[None, Depends(_rl_explorer)] = None,
) -> dict:
    """Public reference endpoint — Nifty 50 price-index daily closes.

    Returns ``[{close_date, close_value}]`` ordered ascending by date.  An
    optional ``from`` / ``to`` date range (ISO YYYY-MM-DD) filters the results.
    Empty list when no rows exist yet (pre-backfill cold-start).

    DOM-allowed: Nifty 50 price closes are public market facts (founder 2026-06-22).
    No auth required.  No RLS (non-personal reference data).
    Disclosure: price index only — excludes dividends (see ADR-0037 part b).
    """
    from datetime import date as _date

    from sqlalchemy import select as sa_select

    from dhanradar.models.mf import MfBenchmarkDaily
    from dhanradar.tasks.mf import BENCHMARK_KEY_NIFTY50

    stmt = (
        sa_select(MfBenchmarkDaily.close_date, MfBenchmarkDaily.close_value)
        .where(MfBenchmarkDaily.benchmark == BENCHMARK_KEY_NIFTY50)
        .order_by(MfBenchmarkDaily.close_date.asc())
    )

    if from_date:
        try:
            stmt = stmt.where(MfBenchmarkDaily.close_date >= _date.fromisoformat(from_date))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_from_date"
            )
    if to_date:
        try:
            stmt = stmt.where(MfBenchmarkDaily.close_date <= _date.fromisoformat(to_date))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_to_date"
            )

    rows = (await db.execute(stmt)).all()
    points = [
        {"close_date": r.close_date.isoformat(), "close_value": float(r.close_value)}
        for r in rows
    ]
    return {
        "benchmark": BENCHMARK_KEY_NIFTY50,
        "disclosure": "Nifty 50 price index · excludes dividends",
        "point_count": len(points),
        "points": points,
    }
