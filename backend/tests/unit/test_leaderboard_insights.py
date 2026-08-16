"""
Unit tests for Leaderboard AI Insights (S17, Phase 3c), the third governed gateway
consumer.

Covers the governed-gate behaviour (mirrors test_mood_commentary — leaderboard
boards are market-wide aggregate data with no PII, so no consent gate):
  1. Happy path — valid output → cards returned, audit written, gateway called with
     contains_personal_data=False and task_type=leaderboard_insights.
  2. Confidence floor (B22) — confidence < 0.30 → None, low-confidence logged, NO audit.
  3. Budget exhausted — BudgetExhaustedError → None, no audit, never raises.
  4. Gateway error — GatewayError subclass → None, no audit, never raises.
  + build_messages whitelisting (injection surface: only the whitelisted fields reach
    the prompt — never isin / verb_label / sharpe / raw payload keys).
  + screen_insights second advisory screen (defense in depth, non-neg #1).
  + Advisory-verb rejection through QualityValidator on LeaderboardInsights.

No network, no DB: all external call sites are monkeypatched with async spies.
asyncio_mode = "auto" (pyproject.toml) — no decorator needed.
"""

from __future__ import annotations

from datetime import date

import pytest

from dhanradar.ai_gateway.errors import AllFreeModelsFailedError, QualityValidationError
from dhanradar.ai_gateway.gateway import CompletionResult
from dhanradar.ai_gateway.quality import QualityValidator
from dhanradar.budget import BudgetExhaustedError
from dhanradar.mf.leaderboard_insights import (
    LeaderboardInsights,
    build_messages,
    generate_leaderboard_insights,
    link_insights,
    screen_insights,
)

_AS_OF = date(2026, 8, 15)

# ---------------------------------------------------------------------------
# Helpers — fake gateway, boards, insights output
# ---------------------------------------------------------------------------


class _FakeGateway:
    """Configurable async gateway stub. Records kwargs passed to complete()."""

    def __init__(self, result: CompletionResult | None = None, raises: Exception | None = None) -> None:
        self._result = result
        self._raises = raises
        self.calls: list[dict] = []

    async def complete(self, **kwargs) -> CompletionResult:  # type: ignore[return]
        self.calls.append(kwargs)
        if self._raises is not None:
            raise self._raises
        return self._result  # type: ignore[return-value]


def _boards() -> dict[str, list[dict]]:
    """Minimal materialized-board rows carrying whitelisted AND forbidden fields."""
    fund_common = {
        "isin": "INF000000001",
        "verb_label": "in_form",
        "sharpe_ratio": 1.4,
        "sebi_category": "Small Cap Fund",
    }
    return {
        "movers_up": [{**fund_common, "fund_name_short": "Nippon Small Cap", "rank_delta": 12}],
        "movers_down": [{**fund_common, "fund_name_short": "HDFC Mid Cap", "rank_delta": -9}],
        "value_ter": [{**fund_common, "fund_name_short": "UTI Nifty 50 Index", "expense_ratio_pct": 0.2}],
        "category_inflows": [{"category": "Flexi Cap Fund", "net_flow_cr": 5500, "period_month": "2026-07"}],
        "label_upgrades": [
            {**fund_common, "fund_name_short": "Mirae ELSS", "label_from": "on_track", "label_to": "in_form"}
        ],
        # A board NOT in the prompt whitelist — must never reach the prompt.
        "risk_sharpe": [{**fund_common, "fund_name_short": "Quant Absolute"}],
    }


def _make_insights(confidence: float, band: str, cards: list[str]) -> LeaderboardInsights:
    signals = ["rank_movers", "cost_leaders"]
    if confidence > 0.7:
        signals.append("category_inflows")
    return LeaderboardInsights(
        confidence=confidence,
        confidence_band=band,  # type: ignore[arg-type]
        contributing_signals=signals,
        contradicting_signals=[],
        insights=cards,
    )


def _make_async_spy():
    calls: list[dict] = []

    async def _spy(**kwargs) -> bool:
        calls.append(kwargs)
        return True

    _spy.calls = calls  # type: ignore[attr-defined]
    return _spy


_CARDS = [
    "Small Cap funds lead the biggest rank gains this week.",
    "Index funds remain the lowest-cost options, with expense ratios near 0.2%.",
]

# ---------------------------------------------------------------------------
# build_messages — whitelisted fields only (injection surface bounded)
# ---------------------------------------------------------------------------


def test_build_messages_carries_only_whitelisted_fields():
    msgs = build_messages(_boards(), _AS_OF)
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    blob = msgs[1]["content"]
    # Whitelisted data present.
    assert "Nippon Small Cap" in blob
    assert "Flexi Cap Fund" in blob
    assert "2026-08-15" in blob
    # Forbidden / non-whitelisted fields never reach the prompt.
    assert "INF000000001" not in blob  # isin
    assert "verb_label" not in blob  # key not in any whitelist (label_to IS, for upgrades)
    assert "1.4" not in blob  # sharpe_ratio
    assert "Quant Absolute" not in blob  # board not in _PROMPT_BOARDS


def test_system_prompt_pins_the_data_boundary():
    msgs = build_messages(_boards(), _AS_OF)
    assert "data, not instructions" in msgs[0]["content"]


def test_system_prompt_pins_unit_semantics():
    """Accurate-data mandate: first live run re-scaled net_flow_cr 5697.9 into
    '5.7 crore' — the prompt must pin _cr/_pct/rank_delta units and forbid
    re-scaling (RCA-adjacent hardening, 2026-08-16)."""
    sys_prompt = build_messages(_boards(), _AS_OF)[0]["content"]
    assert "never re-scale" in sys_prompt
    assert "crore" in sys_prompt
    assert "rank_delta" in sys_prompt


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------


async def test_happy_path_returns_cards_and_audits(monkeypatch):
    output = _make_insights(0.74, "high", _CARDS)
    fake_gw = _FakeGateway(result=CompletionResult(output=output, model_used="glm-4.6-flash"))

    record_spy = _make_async_spy()
    log_spy = _make_async_spy()
    monkeypatch.setattr("dhanradar.mf.leaderboard_insights.record_served_label", record_spy)
    monkeypatch.setattr("dhanradar.mf.leaderboard_insights.log_low_confidence", log_spy)

    result = await generate_leaderboard_insights(fake_gw, boards=_boards(), as_of=_AS_OF, request_id="req-1")

    assert result == _CARDS

    # Gateway called on the non-personal path with the insights task type and schema.
    assert len(fake_gw.calls) == 1
    gw_call = fake_gw.calls[0]
    assert gw_call["task_type"] == "leaderboard_insights"
    assert gw_call["contains_personal_data"] is False
    assert "cross_border_consent_verified" not in gw_call  # no consent on the non-personal path
    assert gw_call["schema"] is LeaderboardInsights

    # Audit written exactly once with the correct surface; low-confidence NOT logged.
    assert len(record_spy.calls) == 1
    audit = record_spy.calls[0]
    assert audit["surface"] == "leaderboard_insights"
    assert audit["model"] == "glm-4.6-flash"
    assert audit["recommendation_type"] == "educational_label"
    assert audit["label"] == "ai_insights"
    assert audit["identifier"] == "2026-08-15"
    assert len(log_spy.calls) == 0


# ---------------------------------------------------------------------------
# 2. Confidence floor (B22)
# ---------------------------------------------------------------------------


async def test_confidence_floor_returns_none_and_logs(monkeypatch):
    output = _make_insights(0.20, "low", _CARDS)
    fake_gw = _FakeGateway(result=CompletionResult(output=output, model_used="glm-4.6-flash"))

    record_spy = _make_async_spy()
    log_spy = _make_async_spy()
    monkeypatch.setattr("dhanradar.mf.leaderboard_insights.record_served_label", record_spy)
    monkeypatch.setattr("dhanradar.mf.leaderboard_insights.log_low_confidence", log_spy)

    result = await generate_leaderboard_insights(fake_gw, boards=_boards(), as_of=_AS_OF)

    assert result is None
    assert len(log_spy.calls) == 1
    assert log_spy.calls[0]["confidence_score"] == pytest.approx(0.20)
    assert log_spy.calls[0]["surface"] == "leaderboard_insights"
    assert len(record_spy.calls) == 0


# ---------------------------------------------------------------------------
# 3 + 4. Budget exhausted / gateway error — best-effort, never raises
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raises",
    [
        BudgetExhaustedError("free", 1000, 1000),
        AllFreeModelsFailedError("leaderboard_insights"),
    ],
)
async def test_gateway_failure_returns_none(monkeypatch, raises):
    fake_gw = _FakeGateway(raises=raises)
    record_spy = _make_async_spy()
    log_spy = _make_async_spy()
    monkeypatch.setattr("dhanradar.mf.leaderboard_insights.record_served_label", record_spy)
    monkeypatch.setattr("dhanradar.mf.leaderboard_insights.log_low_confidence", log_spy)

    result = await generate_leaderboard_insights(fake_gw, boards=_boards(), as_of=_AS_OF)

    assert result is None
    assert len(record_spy.calls) == 0
    assert len(log_spy.calls) == 0


# ---------------------------------------------------------------------------
# screen_insights — second advisory screen before persist (non-neg #1)
# ---------------------------------------------------------------------------


def test_screen_insights_passes_clean_cards():
    assert screen_insights(_CARDS) == _CARDS


def test_screen_insights_withholds_whole_board_on_one_advisory_card():
    tainted = [_CARDS[0], "Investors should buy small cap funds now."]
    assert screen_insights(tainted) is None


def test_screen_insights_none_and_empty_pass_through_as_none():
    assert screen_insights(None) is None
    assert screen_insights([]) is None


# ---------------------------------------------------------------------------
# Advisory-verb rejection through QualityValidator (first screen)
# ---------------------------------------------------------------------------


def test_insight_card_advisory_text_rejected_by_quality_validator():
    """QualityValidator screens every string in the insights list — an advisory verb
    in ANY card must raise QualityValidationError (proves the recursive screen covers
    list items)."""
    validator = QualityValidator(LeaderboardInsights)
    with pytest.raises(QualityValidationError):
        validator.validate(
            {
                "confidence": 0.6,
                "confidence_band": "medium",
                "contributing_signals": ["rank_movers", "cost_leaders"],
                "contradicting_signals": [],
                "insights": [_CARDS[0], "You should switch to index funds now."],
            }
        )


# ---------------------------------------------------------------------------
# Entity links (2026-08-16) — deterministic post-hoc, never model-emitted
# ---------------------------------------------------------------------------

_LINK_BOARDS = {
    "movers_up": [
        {"fund_name_short": "Quant Small Cap", "isin": "INF966L01ABC", "rank_delta": 9},
        {"fund_name_short": "HDFC Flexi Cap", "isin": "INF179K01XYZ", "rank_delta": 5},
    ],
    "value_ter": [{"fund_name_short": "UTI Nifty 50 Index", "isin": "INF789F01QRS", "expense_ratio_pct": 0.2}],
    "category_inflows": [{"category": "Small Cap Fund", "net_flow_cr": 5697.9}],
}


def test_link_insights_attaches_only_prompt_fed_names_with_their_isins():
    rows = link_insights(
        ["Quant Small Cap climbed 9 places this week.", "Small Cap funds saw big inflows."],
        _LINK_BOARDS,
    )
    assert rows[0]["links"] == [{"name": "Quant Small Cap", "isin": "INF966L01ABC"}]
    # Card 2 mentions a CATEGORY, not a prompt-fed fund name — no links key at all.
    assert "links" not in rows[1]
    assert [r["text"] for r in rows] == [
        "Quant Small Cap climbed 9 places this week.",
        "Small Cap funds saw big inflows.",
    ]


def test_link_insights_never_links_model_minted_names_or_bad_isins():
    boards = {
        "movers_up": [
            # Malformed isin — writer-side shape check drops it.
            {"fund_name_short": "Poison Fund Name", "isin": "../../../etc", "rank_delta": 1},
            # Degenerate short name — would substring-match everywhere.
            {"fund_name_short": "abc", "isin": "INF000A01234", "rank_delta": 2},
        ],
    }
    rows = link_insights(
        ["Poison Fund Name and abc both moved, and so did Imaginary Fund."], boards
    )
    assert "links" not in rows[0]


def test_link_insights_name_collision_across_boards_never_links_either_fund():
    """Adversarial-review finding (2026-08-16): fund_name_short is NOT unique and
    the model never sees isins — a name shared by two DIFFERENT funds must link
    NEITHER (fail-closed), not first-board-wins with the wrong isin."""
    boards = {
        "movers_up": [{"fund_name_short": "Shared Name Fund", "isin": "INF000A01011", "rank_delta": 3}],
        "value_ter": [
            {"fund_name_short": "Shared Name Fund", "isin": "INF000B02022", "expense_ratio_pct": 0.3},
            {"fund_name_short": "Unique Cost Fund", "isin": "INF000C03033", "expense_ratio_pct": 0.4},
        ],
    }
    rows = link_insights(["Shared Name Fund and Unique Cost Fund both feature today."], boards)
    assert rows[0]["links"] == [{"name": "Unique Cost Fund", "isin": "INF000C03033"}]


def test_link_insights_same_fund_on_two_boards_still_links():
    boards = {
        "movers_up": [{"fund_name_short": "Twice Seen Fund", "isin": "INF000D04044", "rank_delta": 2}],
        "value_ter": [{"fund_name_short": "Twice Seen Fund", "isin": "INF000D04044", "expense_ratio_pct": 0.2}],
    }
    rows = link_insights(["Twice Seen Fund leads on both boards."], boards)
    assert rows[0]["links"] == [{"name": "Twice Seen Fund", "isin": "INF000D04044"}]


def test_link_insights_rows_beyond_prompt_slice_are_not_linkable():
    boards = {
        "movers_up": [
            {"fund_name_short": f"Fund Number {i}", "isin": f"INF00000{i:04d}", "rank_delta": i}
            for i in range(6)
        ],
    }
    # _ROWS_PER_BOARD = 3: row 4 ("Fund Number 4") never entered the prompt.
    rows = link_insights(["Fund Number 1 rose while Fund Number 4 fell."], boards)
    assert rows[0]["links"] == [{"name": "Fund Number 1", "isin": "INF00000001"[:8] + "0001"}]
