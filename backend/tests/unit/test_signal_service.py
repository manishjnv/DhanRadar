"""Signal service and model import smoke test."""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock


def test_signal_models_importable():
    from dhanradar.signal.models import SignalRules, SignalDipFund
    from dhanradar.signal.models import SignalDeployment, SignalJournal
    assert SignalRules.__tablename__ == "signal_rules"
    assert SignalDipFund.__tablename__ == "signal_dip_fund"
    assert SignalDeployment.__tablename__ == "signal_deployments"
    assert SignalJournal.__tablename__ == "signal_journal"


@pytest.mark.asyncio
async def test_get_or_create_rules_creates_defaults_when_not_found():
    """First call for a user with no row seeds the default thresholds."""
    from dhanradar.signal.service import get_or_create_rules, DEFAULT_RULES

    db = AsyncMock()
    db.get.return_value = None
    db.add = MagicMock()
    db.flush = AsyncMock()

    result = await get_or_create_rules(db, "00000000-0000-0000-0000-000000000001")

    db.add.assert_called_once()
    assert result.vix_threshold == DEFAULT_RULES["vix_threshold"]
    assert result.deploy_ladder == DEFAULT_RULES["deploy_ladder"]
    assert result.alerts_on is True


@pytest.mark.asyncio
async def test_get_or_create_rules_returns_existing_row():
    """Second call returns the existing row unchanged."""
    from dhanradar.signal.models import SignalRules
    from dhanradar.signal.service import get_or_create_rules

    existing = SignalRules()
    existing.vix_threshold = Decimal("21.0")
    existing.deploy_ladder = [30, 30, 20, 10, 10]

    db = AsyncMock()
    db.get.return_value = existing

    result = await get_or_create_rules(db, "00000000-0000-0000-0000-000000000001")

    db.add.assert_not_called()
    assert result.vix_threshold == Decimal("21.0")


@pytest.mark.asyncio
async def test_add_dip_fund_cash_increments_balance():
    """add_dip_fund_cash adds the amount to the existing balance."""
    from decimal import Decimal
    from datetime import datetime, timezone
    from dhanradar.signal.models import SignalDipFund
    from dhanradar.signal.service import add_dip_fund_cash

    existing = SignalDipFund()
    existing.user_id = None
    existing.balance = Decimal("10000.00")
    existing.monthly_addition = Decimal("5000.00")
    existing.last_updated = datetime.now(timezone.utc)
    existing.created_at = datetime.now(timezone.utc)

    db = AsyncMock()
    db.get.return_value = existing
    db.add = MagicMock()
    db.flush = AsyncMock()

    result = await add_dip_fund_cash(db, "00000000-0000-0000-0000-000000000001", Decimal("2500"))

    assert result.balance == Decimal("12500.00")


def test_signal_rules_out_round_trips_orm_row():
    """SignalRulesOut correctly serialises an ORM row."""
    from decimal import Decimal
    from dhanradar.signal.models import SignalRules
    from dhanradar.signal.schemas import SignalRulesOut

    row = SignalRules()
    row.nifty_threshold = Decimal("-8.00")
    row.vix_threshold = Decimal("19.00")
    row.breadth_threshold = Decimal("0.800")
    row.deploy_ladder = [20, 20, 20, 20, 20]
    row.alerts_on = True

    out = SignalRulesOut.model_validate(row)
    assert out.vix_threshold == Decimal("19.00")
    assert out.deploy_ladder == [20, 20, 20, 20, 20]
    assert out.alerts_on is True
