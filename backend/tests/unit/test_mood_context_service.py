"""
Unit tests for insights mood-context service and schema — no DB required.

Guards:
  - No numeric mood_score / 0-100 value ever in the serialized response (non-neg #2)
  - No advisory verbs in any observation text (non-neg #1)
  - Disclosure bundle present in every response
  - All three observation strings always present
  - data_unavailable regime path renders correctly
  - Empty portfolio → valid shape, honest empty read
  - IDOR: wrong portfolio → ValueError
  - Source-level guard: template constants contain no banned advisory verbs
  - Anonymous (malformed uid) → graceful empty, no DB call
"""

from __future__ import annotations

import json
import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from dhanradar.insights.schemas import MoodContextResponse
from dhanradar.insights.service import (
    _build_observations,
    _concentration_band,
    _regime_display,
)
from dhanradar.scoring.engine.schemas import DISCLAIMER_VERSION, DISCLOSURE_BUNDLE, NOT_ADVICE

# ---------------------------------------------------------------------------
# Advisory verb guard
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
    r"\bconsider\b",
    r"\bde-risk\b",
    r"\bentry\b",
    r"\bhold\b",
]


def _scan_advisory(text: str) -> list[str]:
    return [v for v in ADVISORY_VERBS if re.search(v, text, re.IGNORECASE)]


# ---------------------------------------------------------------------------
# Pure helper tests
# ---------------------------------------------------------------------------

class TestRegimeDisplay:
    def test_known_regimes_have_human_labels(self) -> None:
        for regime in ("extreme_fear", "fear", "neutral", "greed", "extreme_greed",
                       "data_unavailable", "insufficient_data"):
            label = _regime_display(regime)
            assert label  # non-empty
            assert "_" not in label  # human-readable, not raw enum

    def test_unknown_regime_falls_back_gracefully(self) -> None:
        label = _regime_display("future_unknown_value")
        assert label == "Future Unknown Value"


class TestConcentrationBand:
    def test_empty_portfolio(self) -> None:
        assert _concentration_band(0, 0.0) == "empty"

    def test_single_fund_is_high(self) -> None:
        assert _concentration_band(1, 100.0) == "high"

    def test_top_pct_gte_70_is_high(self) -> None:
        assert _concentration_band(3, 70.0) == "high"
        assert _concentration_band(5, 85.0) == "high"

    def test_top_pct_40_to_69_is_moderate(self) -> None:
        assert _concentration_band(3, 40.0) == "moderate"
        assert _concentration_band(4, 65.0) == "moderate"

    def test_top_pct_below_40_is_low(self) -> None:
        assert _concentration_band(4, 30.0) == "low"
        assert _concentration_band(10, 15.0) == "low"


class TestBuildObservations:
    def test_returns_exactly_three_observations(self) -> None:
        obs = _build_observations("neutral", "2026-06-13", 3, "moderate")
        assert len(obs) == 3

    def test_data_unavailable_regime(self) -> None:
        obs = _build_observations("data_unavailable", None, 3, "moderate")
        assert "unavailable" in obs[0].lower()
        assert len(obs) == 3

    def test_normal_regime_includes_label_and_date(self) -> None:
        obs = _build_observations("fear", "2026-06-13", 2, "low")
        assert "Fear" in obs[0]
        assert "2026-06-13" in obs[0]

    def test_empty_portfolio_observation(self) -> None:
        obs = _build_observations("neutral", "2026-06-13", 0, "empty")
        assert "upload" in obs[2].lower() or "No scored" in obs[2]

    def test_non_empty_portfolio_observation(self) -> None:
        obs = _build_observations("neutral", "2026-06-13", 4, "moderate")
        assert "4" in obs[2]
        assert "moderate" in obs[2]

    def test_third_observation_always_independence_disclaimer(self) -> None:
        for regime in ("neutral", "data_unavailable", "fear", "greed"):
            obs = _build_observations(regime, "2026-06-13", 2, "low")
            assert "independent reads" in obs[1]
            assert "does not predict direction" in obs[1]

    def test_no_advisory_verbs_in_any_observation(self) -> None:
        for regime in ("extreme_fear", "fear", "neutral", "greed", "extreme_greed",
                       "data_unavailable"):
            obs = _build_observations(regime, "2026-06-13", 3, "moderate")
            for o in obs:
                hits = _scan_advisory(o)
                assert hits == [], f"Advisory verbs found in '{o}': {hits}"


class TestObservationTemplateSourceGuard:
    """
    Source-level guard: assert that every possible observation template,
    rendered with representative values, contains none of the banned verbs.
    This catches template drift before the tests above catch runtime output.
    """

    REGIMES = ["extreme_fear", "fear", "neutral", "greed", "extreme_greed", "data_unavailable"]
    FUND_COUNTS = [0, 1, 3]
    BANDS = ["empty", "high", "moderate", "low"]

    def test_all_template_combinations_advisory_free(self) -> None:
        for regime in self.REGIMES:
            for fc in self.FUND_COUNTS:
                for band in self.BANDS:
                    obs_list = _build_observations(regime, "2026-06-13", fc, band)
                    for obs in obs_list:
                        hits = _scan_advisory(obs)
                        assert hits == [], (
                            f"Advisory verb in observation "
                            f"(regime={regime}, fund_count={fc}, band={band}): "
                            f"'{obs}' — found: {hits}"
                        )


# ---------------------------------------------------------------------------
# Schema guard — no numeric score field
# ---------------------------------------------------------------------------

class TestMoodContextSchemaFields:
    def test_no_unified_score_field(self) -> None:
        fields = list(MoodContextResponse.model_fields.keys())
        assert "unified_score" not in fields
        assert "mood_score" not in fields

    def test_no_numeric_0_100_field(self) -> None:
        """Paranoia check: none of the numeric internal fields are present."""
        fields = list(MoodContextResponse.model_fields.keys())
        forbidden = {"unified_score", "mood_score", "confidence_score", "confidence"}
        assert not forbidden.intersection(fields)

    def test_serialized_response_has_no_numeric_score(self) -> None:
        resp = MoodContextResponse(
            portfolio_id="pid",
            regime="neutral",
            regime_as_of="2026-06-13",
            fund_count=2,
            concentration_band="moderate",
            top_category="Large Cap",
            observations=["obs1", "obs2", "obs3"],
            disclosure=DISCLOSURE_BUNDLE,
            not_advice=NOT_ADVICE,
            disclaimer_version=DISCLAIMER_VERSION,
        )
        payload = json.loads(resp.model_dump_json())
        assert "mood_score" not in payload
        assert "unified_score" not in payload
        assert "confidence_score" not in payload
        # fund_count is an int in DOM — allowed (it's the user's own portfolio count)
        # but the regime field must be a string, not a 0-100 float
        assert isinstance(payload["regime"], str)
        assert isinstance(payload["fund_count"], int)

    def test_disclosure_fields_present(self) -> None:
        resp = MoodContextResponse(
            portfolio_id="pid",
            regime="data_unavailable",
            regime_as_of=None,
            fund_count=0,
            concentration_band="empty",
            top_category=None,
            observations=["a", "b", "c"],
            disclosure=DISCLOSURE_BUNDLE,
            not_advice=NOT_ADVICE,
            disclaimer_version=DISCLAIMER_VERSION,
        )
        assert resp.disclosure == DISCLOSURE_BUNDLE
        assert resp.not_advice == NOT_ADVICE
        assert resp.disclaimer_version == DISCLAIMER_VERSION


# ---------------------------------------------------------------------------
# Service-level async tests — mock DB
# ---------------------------------------------------------------------------

def _mock_db_empty_portfolio(portfolio_exists: bool = True) -> Any:
    """Mock DB: existing portfolio but zero holdings."""
    db = AsyncMock()
    port_mock = MagicMock()
    port_mock.scalar_one_or_none.return_value = MagicMock() if portfolio_exists else None
    hold_mock = MagicMock()
    hold_mock.fetchall.return_value = []
    db.execute.side_effect = [port_mock, hold_mock]
    return db


def _mock_mood_latest(regime: str = "neutral", snapshot_date: str = "2026-06-13") -> Any:
    """Mock MoodPublic returned by mood.service.get_latest."""
    mood = MagicMock()
    mood.regime = regime
    mood.snapshot_date = snapshot_date
    mood.confidence_band = "medium"
    mood.data_quality = "ok"
    mood.contributing_factors = []
    mood.contradicting_factors = []
    mood.ai_commentary = None
    return mood


@pytest.mark.asyncio
async def test_mood_context_anon_returns_empty() -> None:
    """Malformed/anonymous user_id → graceful empty response."""
    import unittest.mock as mock

    from dhanradar.insights.service import get_mood_context

    mock_mood = _mock_mood_latest()
    db = AsyncMock()

    with mock.patch("dhanradar.mood.service.get_latest", return_value=mock_mood):
        result = await get_mood_context(db, "not-a-uuid", "00000000-0000-0000-0000-000000000002")

    assert isinstance(result, MoodContextResponse)
    assert result.fund_count == 0
    assert result.concentration_band == "empty"
    assert len(result.observations) == 3
    assert result.disclosure == DISCLOSURE_BUNDLE


@pytest.mark.asyncio
async def test_mood_context_foreign_portfolio_raises_valueerror() -> None:
    """Non-existent / foreign portfolio → ValueError (router maps to 404)."""
    import unittest.mock as mock

    from dhanradar.insights.service import get_mood_context

    mock_mood = _mock_mood_latest()
    db = _mock_db_empty_portfolio(portfolio_exists=False)

    with mock.patch("dhanradar.mood.service.get_latest", return_value=mock_mood):
        with pytest.raises(ValueError, match="portfolio_not_found"):
            await get_mood_context(
                db,
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
            )


@pytest.mark.asyncio
async def test_mood_context_empty_portfolio_happy_path() -> None:
    """Empty portfolio → valid 200 with 3 observations and full disclosure."""
    import unittest.mock as mock

    from dhanradar.insights.service import get_mood_context

    mock_mood = _mock_mood_latest("neutral", "2026-06-13")
    db = _mock_db_empty_portfolio(portfolio_exists=True)

    with mock.patch("dhanradar.mood.service.get_latest", return_value=mock_mood):
        result = await get_mood_context(
            db,
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
        )

    assert isinstance(result, MoodContextResponse)
    assert result.fund_count == 0
    assert result.concentration_band == "empty"
    assert result.regime == "neutral"
    assert result.regime_as_of == "2026-06-13"
    assert len(result.observations) == 3
    # Observation 1 mentions the regime label and date
    assert "Neutral" in result.observations[0]
    assert "2026-06-13" in result.observations[0]
    # Observation 2 is the independence disclaimer
    assert "independent reads" in result.observations[1]
    # Observation 3 mentions upload prompt (empty portfolio)
    assert "upload" in result.observations[2].lower() or "No scored" in result.observations[2]
    assert result.disclosure == DISCLOSURE_BUNDLE
    assert result.not_advice == NOT_ADVICE


@pytest.mark.asyncio
async def test_mood_context_data_unavailable_regime() -> None:
    """data_unavailable mood → obs1 says unavailable, rest still valid."""
    import unittest.mock as mock

    from dhanradar.insights.service import get_mood_context

    mock_mood = _mock_mood_latest("data_unavailable", "")
    db = _mock_db_empty_portfolio(portfolio_exists=True)

    with mock.patch("dhanradar.mood.service.get_latest", return_value=mock_mood):
        result = await get_mood_context(
            db,
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
        )

    assert result.regime == "data_unavailable"
    assert len(result.observations) == 3
    assert "unavailable" in result.observations[0].lower()
    assert result.disclosure == DISCLOSURE_BUNDLE


@pytest.mark.asyncio
async def test_mood_context_no_mood_snapshot_falls_back_to_unavailable() -> None:
    """No mood snapshot in DB (get_latest returns None) → data_unavailable fallback."""
    import unittest.mock as mock

    from dhanradar.insights.service import get_mood_context

    db = _mock_db_empty_portfolio(portfolio_exists=True)

    with mock.patch("dhanradar.mood.service.get_latest", return_value=None):
        result = await get_mood_context(
            db,
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
        )

    assert result.regime == "data_unavailable"
    assert len(result.observations) == 3
    assert result.disclosure == DISCLOSURE_BUNDLE


@pytest.mark.asyncio
async def test_mood_context_happy_path_with_holdings() -> None:
    """Portfolio with holdings → fund_count > 0, band != empty, all 3 observations."""
    import unittest.mock as mock
    from decimal import Decimal

    from dhanradar.insights.service import get_mood_context

    mock_mood = _mock_mood_latest("greed", "2026-06-13")

    db = AsyncMock()

    # portfolio exists
    port_mock = MagicMock()
    port_mock.scalar_one_or_none.return_value = MagicMock()

    # holdings: 2 ISINs with invested amounts
    holding_row_1 = MagicMock()
    holding_row_1.isin = "INF000K01WU9"
    holding_row_1.invested_amount = Decimal("50000")

    holding_row_2 = MagicMock()
    holding_row_2.isin = "INF200K01QN7"
    holding_row_2.invested_amount = Decimal("30000")

    hold_mock = MagicMock()
    hold_mock.fetchall.return_value = [holding_row_1, holding_row_2]

    # fund metadata
    fund_meta_row_1 = MagicMock()
    fund_meta_row_1.isin = "INF000K01WU9"
    fund_meta_row_1.category = "Large Cap"

    fund_meta_row_2 = MagicMock()
    fund_meta_row_2.isin = "INF200K01QN7"
    fund_meta_row_2.category = "Mid Cap"

    fund_meta_mock = MagicMock()
    fund_meta_mock.fetchall.return_value = [fund_meta_row_1, fund_meta_row_2]

    db.execute.side_effect = [port_mock, hold_mock, fund_meta_mock]

    with mock.patch("dhanradar.mood.service.get_latest", return_value=mock_mood):
        result = await get_mood_context(
            db,
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
        )

    assert result.fund_count == 2
    assert result.concentration_band in ("high", "moderate", "low")
    assert result.top_category in ("Large Cap", "Mid Cap")
    assert result.regime == "greed"
    assert len(result.observations) == 3
    # Observation 1: regime label
    assert "Greed" in result.observations[0]
    # Observation 3: fund count present (structure read is now index 2)
    assert "2" in result.observations[2]
    # No advisory verbs in any observation
    for obs in result.observations:
        hits = _scan_advisory(obs)
        assert hits == [], f"Advisory verbs in observation: {obs!r} — {hits}"
    # No numeric score in serialized response
    serialized = result.model_dump()
    assert "mood_score" not in serialized
    assert "unified_score" not in serialized
    assert result.disclosure == DISCLOSURE_BUNDLE
