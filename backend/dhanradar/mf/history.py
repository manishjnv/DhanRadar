"""
DhanRadar — MF score history + portfolio snapshot persistence (Plus tracking).

Writes only mf.* tables. The public projection written here is label + band
only — never unified_score or any numeric factor (non-neg #2).

Module isolation: imports only mf models, SQLAlchemy, and ScoringResult type.
No billing, no auth-table writes, no engine import, no scoring recompute.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert

if TYPE_CHECKING:
    from dhanradar.scoring.engine.schemas import ScoringResult

_MAX_SNAPSHOT_DATES = 24


async def append_score_history(
    db: Any,
    *,
    user_id: str,
    result: ScoringResult,
    snapshot_date: date,
    source: str,
    portfolio_id: str | UUID,
) -> None:
    """INSERT a label-only history row for one fund.

    Public projection only: verb_label, confidence_band, model_version, isin.
    unified_score is NEVER written. Idempotent on the same day via ON CONFLICT
    DO NOTHING (uq_mf_score_history).
    """
    from dhanradar.models.mf import MfUserFundScoreHistory

    stmt = (
        insert(MfUserFundScoreHistory)
        .values(
            user_id=user_id,
            portfolio_id=portfolio_id,
            isin=result.identifier,
            snapshot_date=snapshot_date,
            verb_label=result.verb_label.value,
            confidence_band=result.confidence_band.value,
            model_version=result.model_version,
            source=source,
        )
        .on_conflict_do_nothing(constraint="uq_mf_score_history")
    )
    await db.execute(stmt)
    await db.commit()


async def persist_portfolio_snapshot(
    db: Any,
    *,
    user_id: str,
    snapshot_date: date,
    snap: Any,
    portfolio_id: str | UUID,
) -> None:
    """INSERT one MfPortfolioSnapshot row.

    Numbers (total_invested, current_value, xirr_pct) stay server-side — they
    are NEVER serialized to a client via this module. Idempotent same-day via
    ON CONFLICT DO NOTHING (uq_mf_snapshot).
    """
    from dhanradar.models.mf import MfPortfolioSnapshot

    stmt = (
        insert(MfPortfolioSnapshot)
        .values(
            user_id=user_id,
            portfolio_id=portfolio_id,
            snapshot_date=snapshot_date,
            total_invested=snap.total_invested,
            current_value=snap.current_value,
            xirr_pct=snap.xirr_pct,
            category_allocation=snap.category_allocation,
            overlap_matrix=snap.overlap_matrix,
        )
        .on_conflict_do_nothing(constraint="uq_mf_snapshot")
    )
    await db.execute(stmt)
    await db.commit()


async def get_snapshot_history(db: Any, user_id: str, portfolio_id: str | UUID) -> list[dict]:
    """Return the most recent snapshot dates with per-fund label + band only.

    Returns at most ``_MAX_SNAPSHOT_DATES`` snapshot_dates, descending.
    NEVER includes unified_score or any numeric field (non-neg #2).
    Filtered by both user_id (defence-in-depth) and portfolio_id (scoping).

    Shape::

        [
          {
            "snapshot_date": "2026-06-01",
            "funds": [
              {"isin": "...", "verb_label": "on_track", "confidence_band": "medium"},
              ...
            ]
          },
          ...
        ]
    """
    from sqlalchemy import select

    from dhanradar.models.mf import MfUserFundScoreHistory

    # Fetch all rows for this portfolio, ordered by date DESC then isin for stability.
    rows = (
        await db.execute(
            select(
                MfUserFundScoreHistory.snapshot_date,
                MfUserFundScoreHistory.isin,
                MfUserFundScoreHistory.verb_label,
                MfUserFundScoreHistory.confidence_band,
            )
            .where(
                MfUserFundScoreHistory.user_id == user_id,
                MfUserFundScoreHistory.portfolio_id == portfolio_id,
            )
            .order_by(
                MfUserFundScoreHistory.snapshot_date.desc(),
                MfUserFundScoreHistory.isin,
            )
        )
    ).all()

    # Group by snapshot_date; respect the cap on distinct dates.
    grouped: dict[str, list[dict]] = {}
    date_order: list[str] = []
    for snapshot_date, isin, verb_label, confidence_band in rows:
        date_str = snapshot_date.isoformat() if hasattr(snapshot_date, "isoformat") else str(snapshot_date)
        if date_str not in grouped:
            if len(date_order) >= _MAX_SNAPSHOT_DATES:
                continue
            grouped[date_str] = []
            date_order.append(date_str)
        grouped[date_str].append(
            {
                "isin": isin,
                "verb_label": verb_label,
                "confidence_band": confidence_band,
            }
        )

    return [{"snapshot_date": d, "funds": grouped[d]} for d in date_order]
