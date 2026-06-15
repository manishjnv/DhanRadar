"""Signal feature — async DB service layer."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.signal.models import SignalDeployment, SignalDipFund, SignalRules

DEFAULT_RULES: dict = {
    "nifty_threshold": Decimal("-8.00"),
    "vix_threshold": Decimal("19.00"),
    "breadth_threshold": Decimal("0.800"),
    "deploy_ladder": [20, 20, 20, 20, 20],
    "alerts_on": True,
}


async def get_or_create_rules(db: AsyncSession, user_id: str) -> SignalRules:
    uid = uuid.UUID(user_id)
    row = await db.get(SignalRules, uid)
    if row is None:
        row = SignalRules(user_id=uid, **DEFAULT_RULES)
        db.add(row)
        await db.flush()
    return row


async def update_rules(db: AsyncSession, user_id: str, data: dict) -> SignalRules:
    row = await get_or_create_rules(db, user_id)
    for key, val in data.items():
        setattr(row, key, val)
    await db.flush()
    return row


async def get_or_create_dip_fund(db: AsyncSession, user_id: str) -> SignalDipFund:
    uid = uuid.UUID(user_id)
    row = await db.get(SignalDipFund, uid)
    if row is None:
        row = SignalDipFund(
            user_id=uid,
            balance=Decimal("0"),
            monthly_addition=Decimal("0"),
            last_updated=datetime.now(UTC),
            created_at=datetime.now(UTC),
        )
        db.add(row)
        await db.flush()
    return row


async def add_dip_fund_cash(db: AsyncSession, user_id: str, amount: Decimal) -> SignalDipFund:
    row = await get_or_create_dip_fund(db, user_id)
    row.balance = row.balance + amount
    row.last_updated = datetime.now(UTC)
    await db.flush()
    return row


async def get_deployments(
    db: AsyncSession, user_id: str, limit: int = 20
) -> list[SignalDeployment]:
    stmt = (
        select(SignalDeployment)
        .where(SignalDeployment.user_id == uuid.UUID(user_id))
        .order_by(SignalDeployment.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
