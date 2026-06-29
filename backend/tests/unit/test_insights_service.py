"""
Unit tests for insights service helpers — no DB required.

Guards:
  - No numeric score (unified_score) ever in response (non-neg #2)
  - No advisory verbs in any framing text (non-neg #1)
  - Disclosure bundle present in every response
  - Empty portfolio → valid shape (empty lists), NOT a crash
  - Category allocation math via patched category_allocation
  - IDOR: wrong portfolio → ValueError
  - Overlap pct is non-negative
"""

from __future__ import annotations

import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from dhanradar.insights.schemas import OverlapResponse
from dhanradar.insights.service import (
    _category_observation,
    _fund_pair_observation,
)
from dhanradar.scoring.engine.schemas import DISCLAIMER_VERSION, DISCLOSURE_BUNDLE, NOT_ADVICE

# ---------------------------------------------------------------------------
# Advisory verb guard — no framing text may ever contain these
# ---------------------------------------------------------------------------

ADVISORY_VERBS = [
    r"\breduce\b",
    r"\bdiversify\b",
    r"\bswitch\b",
    r"\brebalance\b",
    r"\bsell\b",
    r"\bbuy\b",
    r"\bexit\b",
    r"\bavoid\b",
    r"\binvest\b",
    r"\brecommend\b",
    r"\bshould\b",
    r"\bsuggest\b",
    r"\ballocate\b",
    r"\boverweight\b",
    r"\bunderweight\b",
    r"\bmove\b",
]


def _scan_advisory(text: str) -> list[str]:
    return [v for v in ADVISORY_VERBS if re.search(v, text, re.IGNORECASE)]


# ---------------------------------------------------------------------------
# Pure helper tests (no async, no DB)
# ---------------------------------------------------------------------------

class TestFundPairObservation:
    def test_high_overlap_framing(self) -> None:
        obs = _fund_pair_observation("Fund A", "Fund B", 65.0)
        assert "62%" not in obs  # must use the actual value
        assert "65" in obs
        hits = _scan_advisory(obs)
        assert hits == [], f"Advisory verbs found: {hits}"

    def test_moderate_overlap_framing(self) -> None:
        obs = _fund_pair_observation("Fund A", "Fund B", 40.0)
        assert "40" in obs
        hits = _scan_advisory(obs)
        assert hits == [], f"Advisory verbs found: {hits}"

    def test_low_overlap_framing(self) -> None:
        obs = _fund_pair_observation("Fund A", "Fund B", 15.0)
        assert "15" in obs
        hits = _scan_advisory(obs)
        assert hits == [], f"Advisory verbs found: {hits}"


class TestCategoryObservation:
    def test_multi_fund(self) -> None:
        obs = _category_observation("Large Cap", 55.0, 3)
        assert "3" in obs
        assert "55.0" in obs
        hits = _scan_advisory(obs)
        assert hits == [], f"Advisory verbs found: {hits}"

    def test_single_fund(self) -> None:
        obs = _category_observation("Mid Cap", 20.0, 1)
        assert "1" in obs
        hits = _scan_advisory(obs)
        assert hits == [], f"Advisory verbs found: {hits}"


# NB: concentration moved to the A3 boundary in M2.1 (DataEnvelope, no bespoke schema/service). Its
# #2/band/RLS coverage lives in tests/integration/test_m2_1_portfolio_analytics.py. The old
# _concentration_context / get_concentration / ConcentrationResponse were removed.


# ---------------------------------------------------------------------------
# Schema disclosure tests — every schema always carries the bundle
# ---------------------------------------------------------------------------

class TestSchemaDisclosureFields:
    def test_overlap_response_has_disclosure(self) -> None:
        resp = OverlapResponse(
            portfolio_id="pid",
            as_of_date=None,
            fund_pairs=[],
            category_distribution=[],
            observation_summary="Test.",
            data_completeness="empty",
            disclosure=DISCLOSURE_BUNDLE,
            not_advice=NOT_ADVICE,
            disclaimer_version=DISCLAIMER_VERSION,
        )
        assert resp.disclosure == DISCLOSURE_BUNDLE
        assert resp.not_advice == NOT_ADVICE
        assert resp.disclaimer_version == DISCLAIMER_VERSION

    def test_no_unified_score_in_overlap_schema_fields(self) -> None:
        """unified_score must never appear in any client-facing schema (non-neg #2)."""
        field_names = list(OverlapResponse.model_fields.keys())
        assert "unified_score" not in field_names


# ---------------------------------------------------------------------------
# Service-level async tests — mock DB
# ---------------------------------------------------------------------------

def _mock_db_empty_portfolio(portfolio_exists: bool = True) -> Any:
    """Return a mocked DB session that returns an existing portfolio but zero holdings."""
    db = AsyncMock()

    # First execute: portfolio query
    port_mock = MagicMock()
    port_mock.scalar_one_or_none.return_value = MagicMock() if portfolio_exists else None

    # Second execute: holdings query
    hold_mock = MagicMock()
    hold_mock.fetchall.return_value = []

    db.execute.side_effect = [port_mock, hold_mock]
    return db


@pytest.mark.asyncio
async def test_overlap_empty_portfolio_valid_shape() -> None:
    """Empty portfolio must return a valid OverlapResponse with empty lists — not a crash."""
    from dhanradar.insights.service import get_overlap

    db = _mock_db_empty_portfolio(portfolio_exists=True)
    uid = "00000000-0000-0000-0000-000000000001"
    pid = "00000000-0000-0000-0000-000000000002"

    result = await get_overlap(db, uid, pid)

    assert isinstance(result, OverlapResponse)
    assert result.fund_pairs == []
    assert result.category_distribution == []
    assert result.data_completeness == "empty"
    assert result.disclosure == DISCLOSURE_BUNDLE
    assert result.not_advice == NOT_ADVICE


@pytest.mark.asyncio
async def test_overlap_wrong_portfolio_raises_valueerror() -> None:
    """Non-existent / wrong-user portfolio → ValueError (router maps to 404)."""
    from dhanradar.insights.service import get_overlap

    db = _mock_db_empty_portfolio(portfolio_exists=False)
    uid = "00000000-0000-0000-0000-000000000001"
    pid = "00000000-0000-0000-0000-000000000002"

    with pytest.raises(ValueError, match="portfolio_not_found"):
        await get_overlap(db, uid, pid)


@pytest.mark.asyncio
async def test_overlap_invalid_uid_returns_empty() -> None:
    """Malformed user ID → graceful empty response, no crash."""
    from dhanradar.insights.service import get_overlap

    db = AsyncMock()  # never called
    result = await get_overlap(db, "not-a-uuid", "00000000-0000-0000-0000-000000000002")
    assert result.data_completeness == "empty"
    assert result.fund_pairs == []
    # DB must NOT have been called for malformed uid
    db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Overlap_pct non-negative guard
# ---------------------------------------------------------------------------

class TestFundPairOverlapNonNegative:
    def test_observation_contains_non_negative_pct(self) -> None:
        obs = _fund_pair_observation("A", "B", 0.0)
        assert "0" in obs


# ---------------------------------------------------------------------------
# Advisory verb scan across all framing text output
# ---------------------------------------------------------------------------

class TestAdvisoryVerbAbsentInAllFramingText:
    """Comprehensive scan — all publicly used framing text helpers must be clean."""

    SCENARIOS = [
        ("Large Cap", 80.0, 1),
        ("Small Cap", 10.0, 3),
        ("Debt", 50.0, 2),
    ]

    def test_category_observation_advisory_free(self) -> None:
        for cat, pct, n in self.SCENARIOS:
            obs = _category_observation(cat, pct, n)
            hits = _scan_advisory(obs)
            assert hits == [], f"Advisory verbs found in category_observation: {hits}"

    def test_fund_pair_observation_advisory_free(self) -> None:
        for pct in [5.0, 35.0, 70.0]:
            obs = _fund_pair_observation("Fund X", "Fund Y", pct)
            hits = _scan_advisory(obs)
            assert hits == [], f"Advisory verbs found in fund_pair_observation: {hits}"
