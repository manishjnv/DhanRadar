"""Signal feature — async DB service layer."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.signal.models import SignalDeployment, SignalDipFund, SignalJournal, SignalRules

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


# ---------------------------------------------------------------------------
# Journal (Phase 2)
# ---------------------------------------------------------------------------

async def get_journal(db: AsyncSession, user_id: str, limit: int = 50) -> list[SignalJournal]:
    stmt = (
        select(SignalJournal)
        .where(SignalJournal.user_id == uuid.UUID(user_id))
        .order_by(SignalJournal.date.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def compute_behaviour_scores(entries: list[SignalJournal]) -> dict:
    """Derive Investor / Discipline / Patience scores from journal entries.

    Scores are user-behaviour metrics (0–100 integer). Not SEBI-regulated.
    Trust engine is deferred until 90-day history is available — investor score
    uses 50/50 discipline+patience split until then.
    """
    total = len(entries)
    if total == 0:
        return {
            "discipline_score": 100,
            "patience_score": 100,
            "investor_score": 100,
            "trust_wins": 0,
            "trust_total": 0,
            "has_trust_data": False,
        }

    premature_count = sum(1 for e in entries if e.premature)
    fomo_avoided_count = sum(1 for e in entries if e.fomo_avoided)

    # Discipline: fraction of entries that were NOT premature deployments
    days_on_rules = total - premature_count
    discipline = round(days_on_rules / max(total, 1) * 100)

    # Patience: fomo_avoided / (fomo_avoided + premature); 100 when both are 0
    patience_denom = fomo_avoided_count + premature_count
    patience = 100 if patience_denom == 0 else round(fomo_avoided_count / patience_denom * 100)

    # Trust engine — market outcome computation requires 90-day-old signals.
    # MVP: no historical price lookup; always returns empty until Phase 4.
    trust_wins = 0
    trust_total = 0
    has_trust_data = False
    trust_pct = 0

    # Investor score: redistribute to 50/50 when trust engine has no data
    if not has_trust_data:
        investor = round(0.5 * discipline + 0.5 * patience)
    else:
        investor = round(0.4 * discipline + 0.4 * patience + 0.2 * trust_pct)

    return {
        "discipline_score": discipline,
        "patience_score": patience,
        "investor_score": investor,
        "trust_wins": trust_wins,
        "trust_total": trust_total,
        "has_trust_data": has_trust_data,
    }


async def delete_journal_entry(db: AsyncSession, user_id: str, entry_id: str) -> bool:
    """Delete a journal entry. Returns False if not found or not owned by user."""
    uid = uuid.UUID(user_id)
    eid = uuid.UUID(entry_id)
    row = await db.get(SignalJournal, eid)
    if row is None or row.user_id != uid:
        return False
    await db.delete(row)
    await db.flush()
    return True


async def create_journal_entry(
    db: AsyncSession,
    user_id: str,
    data: dict,
    recent_deployments: list[SignalDeployment],
) -> SignalJournal:
    uid = uuid.UUID(user_id)
    decision: str = data["decision"]
    emotions: list[str] = data.get("emotions", [])
    entry_date = data["date"]

    # Look up signal state for this date from deployment history
    signal_state: str | None = None
    for dep in recent_deployments:
        if dep.date == entry_date:
            signal_state = dep.signal_state
            break

    # Derive fomo_avoided and premature
    fomo_avoided = decision == "skipped" and "fomo" in emotions
    if decision == "deployed":
        premature: bool | None = (signal_state == "no_signal") if signal_state is not None else None
    else:
        premature = False

    market_snapshot = {
        "nifty_pct": data.get("nifty_pct"),
        "vix_level": data.get("vix_level"),
        "breadth_ratio": data.get("breadth_ratio"),
    }

    row = SignalJournal(
        id=uuid.uuid4(),
        user_id=uid,
        date=entry_date,
        decision=decision,
        amount=data.get("amount_deployed"),
        emotion=emotions,
        notes=data.get("notes"),
        market_snapshot=market_snapshot,
        signal_state=signal_state,
        fomo_avoided=fomo_avoided,
        premature=premature,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    await db.flush()
    return row
