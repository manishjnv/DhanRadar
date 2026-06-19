"""
DhanRadar — Signal API router.

Endpoints (all under /api/v1/signal, auth-gated):
  GET  /signal/state              — server-computed signal state (weights stay server-side)
  GET  /signal/rules              — return (or seed) the caller's signal rules
  PUT  /signal/rules              — update the caller's signal rules
  GET  /signal/dip-fund           — return (or seed) the caller's dip-fund record
  POST /signal/dip-fund/add       — add cash to the dip-fund balance
  GET  /signal/deployments        — list the caller's deployment history (last 20)
  GET  /signal/journal            — list journal entries + behaviour scores (Phase 2)
  POST /signal/journal            — add a journal entry (Phase 2)
  GET  /signal/trust-history      — historical signal states + 90-day outcomes (Phase 4)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.db import get_db
from dhanradar.deps import RequireTier, UserContext, current_user_or_anonymous
from dhanradar.signal import service
from dhanradar.signal.schemas import (
    AddDipFundBody,
    BehaviourScoresOut,
    JournalEntryCreate,
    JournalEntryCreatedOut,
    JournalEntryOut,
    JournalOut,
    LearningArticleOut,
    LearningContentOut,
    NotificationsResponse,
    SignalDeploymentOut,
    SignalDipFundOut,
    SignalNotificationOut,
    SignalRulesOut,
    SignalRulesUpdate,
    SignalStateOut,
    TrustHistoryOut,
)

router = APIRouter(prefix="/signal", tags=["signal"])

logger = logging.getLogger(__name__)


async def _require_auth(
    user: Annotated[UserContext, Depends(current_user_or_anonymous)],
) -> UserContext:
    """Raise 401 for anonymous callers — signal endpoints require a logged-in user."""
    if user.is_anonymous:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


@router.get("/state", response_model=SignalStateOut)
async def get_signal_state(
    _: None = Depends(RequireTier("free")),
    # Auth-gate only: this dependency enforces login (401 for anonymous). The state
    # is market-derived, so the user id itself is not needed in the body.
    _user: UserContext = Depends(_require_auth),
) -> SignalStateOut:
    """Return the server-computed signal state for the authenticated caller.

    Fetches live India VIX, market breadth (A/D ratio), and Nifty 50 change-%
    from the mood-service data layer, then computes the signal state server-side.
    Factor weights and the weighted aggregate are never returned (non-neg #2).

    Fallback behaviour mirrors the existing mood endpoints: if a market-data
    source is unavailable the service falls back to Redis cache then hard-coded
    safe defaults — this endpoint NEVER raises 503.
    """
    from dhanradar.mood.service import get_breadth_raw, get_vix
    from dhanradar.signal import scoring

    vix_out = await get_vix()
    breadth_raw = await get_breadth_raw()

    nifty_change_pct: float = breadth_raw.get("nifty_change_pct", 0.0)
    ad_ratio: float = breadth_raw.get("ad_ratio", 1.0)

    ns, vs, bs, state = scoring.compute_signal_state(
        nifty_change_pct=nifty_change_pct,
        vix_value=vix_out.value,
        ad_ratio=ad_ratio,
    )

    return SignalStateOut(
        state=state,
        nifty_score=ns,
        vix_score=vs,
        breadth_score=bs,
        as_of=datetime.now(UTC),
    )


@router.get("/rules", response_model=SignalRulesOut)
async def get_rules(
    _: None = Depends(RequireTier("free")),
    user: UserContext = Depends(_require_auth),
    db: AsyncSession = Depends(get_db),
) -> SignalRulesOut:
    """Return the caller's signal rules, seeding defaults on first access."""
    row = await service.get_or_create_rules(db, user.user_id)
    await db.commit()
    return SignalRulesOut.model_validate(row)


@router.put("/rules", response_model=SignalRulesOut)
async def update_rules(
    body: SignalRulesUpdate,
    _: None = Depends(RequireTier("free")),
    user: UserContext = Depends(_require_auth),
    db: AsyncSession = Depends(get_db),
) -> SignalRulesOut:
    """Update the caller's signal rules."""
    row = await service.update_rules(db, user.user_id, body.model_dump())
    await db.commit()
    return SignalRulesOut.model_validate(row)


@router.get("/dip-fund", response_model=SignalDipFundOut)
async def get_dip_fund(
    _: None = Depends(RequireTier("free")),
    user: UserContext = Depends(_require_auth),
    db: AsyncSession = Depends(get_db),
) -> SignalDipFundOut:
    """Return the caller's dip-fund record, seeding defaults on first access."""
    row = await service.get_or_create_dip_fund(db, user.user_id)
    await db.commit()
    return SignalDipFundOut.model_validate(row)


@router.post("/dip-fund/add", response_model=SignalDipFundOut)
async def add_dip_fund(
    body: AddDipFundBody,
    _: None = Depends(RequireTier("free")),
    user: UserContext = Depends(_require_auth),
    db: AsyncSession = Depends(get_db),
) -> SignalDipFundOut:
    """Add cash to the caller's dip-fund balance."""
    row = await service.add_dip_fund_cash(db, user.user_id, body.amount)
    await db.commit()
    return SignalDipFundOut.model_validate(row)


@router.get("/deployments", response_model=list[SignalDeploymentOut])
async def get_deployments(
    _: None = Depends(RequireTier("free")),
    user: UserContext = Depends(_require_auth),
    db: AsyncSession = Depends(get_db),
) -> list[SignalDeploymentOut]:
    """List the caller's deployment history (most recent 20)."""
    rows = await service.get_deployments(db, user.user_id)
    await db.commit()
    return [SignalDeploymentOut.model_validate(r) for r in rows]


@router.get("/journal", response_model=JournalOut)
async def get_journal(
    _: None = Depends(RequireTier("free")),
    user: UserContext = Depends(_require_auth),
    db: AsyncSession = Depends(get_db),
) -> JournalOut:
    """Return journal entries and computed behaviour scores."""
    entries = await service.get_journal(db, user.user_id)
    behaviour = service.compute_behaviour_scores(entries)
    return JournalOut(
        entries=[JournalEntryOut.from_orm_row(e) for e in entries],
        behaviour=BehaviourScoresOut(**behaviour),
    )


@router.post("/journal", response_model=JournalEntryCreatedOut, status_code=201)
async def create_journal_entry(
    body: JournalEntryCreate,
    _: None = Depends(RequireTier("free")),
    user: UserContext = Depends(_require_auth),
    db: AsyncSession = Depends(get_db),
) -> JournalEntryCreatedOut:
    """Add a new journal entry; derives fomo_avoided and premature from context."""
    recent_deployments = await service.get_deployments(db, user.user_id, limit=100)
    row = await service.create_journal_entry(
        db, user.user_id, body.model_dump(), recent_deployments
    )
    await db.commit()
    return JournalEntryCreatedOut(id=row.id, created_at=row.created_at)


@router.delete("/journal/{entry_id}", status_code=204)
async def delete_journal_entry(
    entry_id: UUID,
    _: None = Depends(RequireTier("free")),
    user: UserContext = Depends(_require_auth),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a journal entry owned by the caller."""
    deleted = await service.delete_journal_entry(db, user.user_id, str(entry_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    await db.commit()


@router.get("/learning", response_model=LearningContentOut)
async def get_learning_content(
    signal_state: str = "no_signal",
    _: None = Depends(RequireTier("free")),
) -> LearningContentOut:
    """Return 4 learning articles relevant to the current signal state."""
    raw = service.get_learning_articles(signal_state)
    return LearningContentOut(
        articles=[LearningArticleOut(**a) for a in raw]
    )


@router.get("/notifications", response_model=NotificationsResponse)
async def get_notifications(
    _: None = Depends(RequireTier("free")),
    user: UserContext = Depends(_require_auth),
    db: AsyncSession = Depends(get_db),
) -> NotificationsResponse:
    """Return unread signal notifications for the caller (max 5)."""
    rows = await service.get_unread_notifications(db, user.user_id)
    return NotificationsResponse(
        unread=[SignalNotificationOut.model_validate(r) for r in rows]
    )


@router.post("/notifications/{notification_id}/read", status_code=204)
async def mark_notification_read(
    notification_id: str,
    _: None = Depends(RequireTier("free")),
    user: UserContext = Depends(_require_auth),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Mark a notification as read."""
    await service.mark_notification_read(db, user.user_id, notification_id)
    await db.commit()


@router.get("/trust-history", response_model=TrustHistoryOut)
async def get_trust_history(
    _: None = Depends(RequireTier("free")),
    user: UserContext = Depends(_require_auth),
    db: AsyncSession = Depends(get_db),
) -> TrustHistoryOut:
    """Return historical signal states, the caller's action on each date, and 90-day outcomes."""
    return await service.get_trust_history(db, user.user_id)
