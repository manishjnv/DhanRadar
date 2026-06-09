"""
DhanRadar — Dashboard service (B56).

Reads the `mf` schema only (published holdings + score-result tables) — never the
scoring engine, never billing. Scoring output is consumed as already-persisted
`verb_label` + `confidence_band`; `unified_score` is never SELECTed into a payload
(non-neg #2). The DB fetch is kept thin; the dedup/rank transforms are pure so they
unit-test without a database.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from dhanradar.dashboard.schemas import (
    FundLabel,
    PortfolioSummary,
    TopScoredFund,
    TopScoredResponse,
)
from dhanradar.scoring.engine.schemas import (
    DISCLAIMER_VERSION,
    DISCLOSURE_BUNDLE,
    NOT_ADVICE,
)

logger = logging.getLogger(__name__)

# Severity ordering for ranking the user's funds (best label first, then highest
# confidence). insufficient_data sinks to the bottom. Pure presentation ordering —
# NOT a recommendation ranking and never derived from the numeric score.
_LABEL_RANK: dict[str, int] = {
    "in_form": 0,
    "on_track": 1,
    "off_track": 2,
    "out_of_form": 3,
    "insufficient_data": 4,
}
_BAND_RANK: dict[str, int] = {"high": 0, "medium": 1, "low": 2, "insufficient_data": 3}

_TOP_SCORED_LIMIT = 6


def _parse_uid(user_id: str) -> UUID | None:
    """Defensive subject parse — a malformed/anonymous id yields None (caller treats
    as 'no data'), never an unhandled 500."""
    if not isinstance(user_id, str) or user_id == "anonymous":
        return None
    try:
        return UUID(user_id)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Pure transforms (DB-free — unit testable)
# ---------------------------------------------------------------------------

# Each score row is (isin, verb_label, confidence_band, scored_at, scheme_name[, category]),
# ordered isin ASC, scored_at DESC, so the FIRST row per isin is the latest.

def latest_per_isin(rows: list[tuple]) -> list[tuple]:
    """Collapse score rows to the most-recent row per ISIN (input pre-ordered
    isin ASC, scored_at DESC)."""
    seen: set[str] = set()
    out: list[tuple] = []
    for row in rows:
        isin = row[0]
        if isin in seen:
            continue
        seen.add(isin)
        out.append(row)
    return out


def rank_top_scored(rows: list[tuple], limit: int = _TOP_SCORED_LIMIT) -> list[TopScoredFund]:
    """Build the ranked top-scored list from score+fund rows
    (isin, label, band, scored_at, scheme_name, category). Best label first, then
    confidence, then scheme name for stability. Read-only presentation order."""
    funds = [
        TopScoredFund(
            isin=isin,
            scheme_name=scheme_name or isin,
            category=category or "Uncategorized",
            label=label,
            confidence_band=band,
        )
        for isin, label, band, _scored_at, scheme_name, category in latest_per_isin(rows)
    ]
    funds.sort(
        key=lambda f: (
            _LABEL_RANK.get(f.label, 9),
            _BAND_RANK.get(f.confidence_band, 9),
            f.scheme_name,
        )
    )
    return funds[:limit]


# ---------------------------------------------------------------------------
# DB-backed reads
# ---------------------------------------------------------------------------

async def get_portfolio_summary(db: Any, user_id: str) -> PortfolioSummary | None:
    """Aggregate the requesting user's own MF portfolio. Returns None when the user
    has no portfolio/holdings (caller → RFC7807 404 cold-start). Never serializes a
    numeric score; `current_value`/`xirr_pct` are the user's own money (or null)."""
    from sqlalchemy import func, select

    from dhanradar.models.mf import (
        MfFund,
        MfPortfolio,
        MfPortfolioSnapshot,
        MfUserHolding,
        UserFundScore,
    )

    uid = _parse_uid(user_id)
    if uid is None:
        return None

    has_portfolio = await db.scalar(
        select(MfPortfolio.id).where(MfPortfolio.user_id == uid).limit(1)
    )
    if has_portfolio is None:
        return None  # cold start — no portfolio container → 404

    fund_count = (
        await db.scalar(
            select(func.count(func.distinct(MfUserHolding.isin))).where(
                MfUserHolding.user_id == uid
            )
        )
    ) or 0
    if fund_count == 0:
        return None  # container exists but no holdings → still cold start → 404

    # Latest snapshot (Plus-only writer; absent → null money figures, honest).
    snap = (
        await db.execute(
            select(
                MfPortfolioSnapshot.current_value,
                MfPortfolioSnapshot.xirr_pct,
                MfPortfolioSnapshot.snapshot_date,
            )
            .where(MfPortfolioSnapshot.user_id == uid)
            .order_by(MfPortfolioSnapshot.snapshot_date.desc())
            .limit(1)
        )
    ).first()
    current_value = float(snap.current_value) if snap and snap.current_value is not None else None
    xirr_pct = float(snap.xirr_pct) if snap and snap.xirr_pct is not None else None

    # Latest label per fund (label + band ONLY — unified_score is not selected).
    score_rows = (
        await db.execute(
            select(
                UserFundScore.isin,
                UserFundScore.verb_label,
                UserFundScore.confidence_band,
                UserFundScore.scored_at,
                MfFund.scheme_name,
            )
            .join(MfFund, MfFund.isin == UserFundScore.isin, isouter=True)
            .where(UserFundScore.user_id == uid)
            .order_by(UserFundScore.isin, UserFundScore.scored_at.desc())
        )
    ).all()

    latest = latest_per_isin([tuple(r) for r in score_rows])
    funds = [
        FundLabel(isin=isin, scheme_name=scheme_name or isin, label=label, confidence_band=band)
        for isin, label, band, _scored_at, scheme_name in latest
    ]
    # Guard: scored_at is non-null in the ORM, but never let a stray None turn
    # max(...).isoformat() into a 500 — fall back to the snapshot date or None.
    latest_scored = max((r[3] for r in latest if r[3] is not None), default=None)
    if latest_scored is not None:
        last_updated = latest_scored.isoformat()
    elif snap and snap.snapshot_date:
        last_updated = snap.snapshot_date.isoformat()
    else:
        last_updated = None

    return PortfolioSummary(
        current_value=current_value,
        xirr_pct=xirr_pct,
        fund_count=int(fund_count),
        last_updated=last_updated,
        funds=funds,
        disclosure=DISCLOSURE_BUNDLE,
        not_advice=NOT_ADVICE,
        disclaimer_version=DISCLAIMER_VERSION,
    )


def top_scored_envelope(funds: list[TopScoredFund]) -> TopScoredResponse:
    return TopScoredResponse(
        funds=funds,
        disclosure=DISCLOSURE_BUNDLE,
        not_advice=NOT_ADVICE,
        disclaimer_version=DISCLAIMER_VERSION,
    )


async def get_top_scored(db: Any, user_id: str) -> TopScoredResponse:
    """Return the requesting user's OWN funds ranked by label (best first), label +
    band only, in an envelope carrying the disclosure bundle (non-neg #9). User-scoped
    on purpose — the user evaluating their own holdings, NOT a platform-wide fund
    recommendation (which the SEBI boundary forbids)."""
    from sqlalchemy import select

    from dhanradar.models.mf import MfFund, UserFundScore

    uid = _parse_uid(user_id)
    if uid is None:
        return top_scored_envelope([])

    rows = (
        await db.execute(
            select(
                UserFundScore.isin,
                UserFundScore.verb_label,
                UserFundScore.confidence_band,
                UserFundScore.scored_at,
                MfFund.scheme_name,
                MfFund.category,
            )
            .join(MfFund, MfFund.isin == UserFundScore.isin, isouter=True)
            .where(UserFundScore.user_id == uid)
            .order_by(UserFundScore.isin, UserFundScore.scored_at.desc())
        )
    ).all()
    return top_scored_envelope(rank_top_scored([tuple(r) for r in rows]))
