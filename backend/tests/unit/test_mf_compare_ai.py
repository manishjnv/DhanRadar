"""Focused C3 compare AI governance and serialization tests."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Response

from dhanradar.mf.compare_ai import _screen_items, build_messages, generate_compare_ai
from dhanradar.mf.router import compare_ai
from dhanradar.mf.serialization import serialize_compare_ai_response

ISINS = "INF174K01KH7,INF200K01234"


def _user(anonymous: bool = False) -> SimpleNamespace:
    return SimpleNamespace(is_anonymous=anonymous, user_id="00000000-0000-0000-0000-000000000001")


async def test_compare_ai_requires_authentication(monkeypatch) -> None:
    with pytest.raises(HTTPException) as exc:
        await compare_ai(
            request=SimpleNamespace(state=SimpleNamespace()),
            db=SimpleNamespace(),
            response=Response(),
            user=_user(anonymous=True),
            isins=ISINS,
        )
    assert exc.value.status_code == 401


def test_compare_ai_screens_digits_and_non_descriptive_copy() -> None:
    allowed = {"alpha fund", "test amc"}
    assert _screen_items(["Alpha Fund had positive returns."], allowed)
    assert not _screen_items(["Alpha Fund returned 12 percent."], allowed)
    assert not _screen_items(["Alpha Fund was the top fund."], allowed)
    assert not _screen_items(["HDFC Fund had positive returns."], allowed)


def test_compare_ai_prompt_is_bounded_public_context() -> None:
    messages = build_messages([
        {"fund_name_short": "Alpha Fund", "category": "Equity", "return_1y_pct": 12.0, "unified_score": 99},
    ])
    assert len(messages) == 2
    assert "Alpha Fund" in messages[1]["content"]
    assert "unified_score" not in messages[1]["content"]


def test_compare_ai_serializer_strips_poisoned_fields() -> None:
    result = serialize_compare_ai_response(
        summary_items=["A factual summary."],
        insight_items=["A factual insight."],
        disclosure="Disclosure",
        not_advice="NOT_ADVICE",
        disclaimer_version="v1",
    )
    assert "unified_score" not in json.dumps(result)
    assert result["summary_items"] == ["A factual summary."]


@pytest.mark.asyncio
async def test_compare_ai_invalid_output_regenerates_once_then_empty(monkeypatch) -> None:
    class Output:
        confidence = 0.8
        confidence_band = "high"
        summary_items = ["Alpha Fund returned 12 percent.", "Another fact."]
        insight_items = ["A fact.", "Another fact."]

    class Result:
        output = Output()
        model_used = "test-model"

    gateway = SimpleNamespace(complete=AsyncMock(return_value=Result()))
    monkeypatch.setattr("dhanradar.mf.compare_ai.assert_consent", AsyncMock())
    monkeypatch.setattr("dhanradar.mf.compare_ai.is_commentary_entitled", AsyncMock(return_value=True))
    monkeypatch.setattr("dhanradar.mf.compare_ai.record_served_label", AsyncMock())
    result = await generate_compare_ai(
        gateway,
        user_id="00000000-0000-0000-0000-000000000001",
        db=SimpleNamespace(),
        fragments=[{"fund_name_short": "Alpha Fund", "amc_name": "Test AMC"}, {"fund_name_short": "Beta Fund"}],
    )
    assert result["summary_items"] == []
    assert gateway.complete.await_count == 2
