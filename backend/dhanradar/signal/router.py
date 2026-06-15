"""
DhanRadar — Signal API router.

Endpoints (all under /api/v1/signal, auth-gated):
  GET  /signal/rules          — return (or seed) the caller's signal rules
  PUT  /signal/rules          — update the caller's signal rules
  GET  /signal/dip-fund       — return (or seed) the caller's dip-fund record
  POST /signal/dip-fund/add   — add cash to the dip-fund balance
  GET  /signal/deployments    — list the caller's deployment history (last 20)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.db import get_db
from dhanradar.deps import RequireTier, UserContext, current_user_or_anonymous
from dhanradar.signal import service
from dhanradar.signal.schemas import (
    AddDipFundBody,
    SignalDeploymentOut,
    SignalDipFundOut,
    SignalRulesOut,
    SignalRulesUpdate,
)

router = APIRouter(prefix="/signal", tags=["signal"])


@router.get("/rules", response_model=SignalRulesOut)
async def get_rules(
    _: None = Depends(RequireTier("free")),
    user: UserContext = Depends(current_user_or_anonymous),
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
    user: UserContext = Depends(current_user_or_anonymous),
    db: AsyncSession = Depends(get_db),
) -> SignalRulesOut:
    """Update the caller's signal rules."""
    row = await service.update_rules(db, user.user_id, body.model_dump())
    await db.commit()
    return SignalRulesOut.model_validate(row)


@router.get("/dip-fund", response_model=SignalDipFundOut)
async def get_dip_fund(
    _: None = Depends(RequireTier("free")),
    user: UserContext = Depends(current_user_or_anonymous),
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
    user: UserContext = Depends(current_user_or_anonymous),
    db: AsyncSession = Depends(get_db),
) -> SignalDipFundOut:
    """Add cash to the caller's dip-fund balance."""
    row = await service.add_dip_fund_cash(db, user.user_id, body.amount)
    await db.commit()
    return SignalDipFundOut.model_validate(row)


@router.get("/deployments", response_model=list[SignalDeploymentOut])
async def get_deployments(
    _: None = Depends(RequireTier("free")),
    user: UserContext = Depends(current_user_or_anonymous),
    db: AsyncSession = Depends(get_db),
) -> list[SignalDeploymentOut]:
    """List the caller's deployment history (most recent 20)."""
    rows = await service.get_deployments(db, user.user_id)
    await db.commit()
    return [SignalDeploymentOut.model_validate(r) for r in rows]
