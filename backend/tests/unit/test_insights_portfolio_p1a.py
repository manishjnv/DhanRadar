"""Unit tests for Wave P1a portfolio endpoints (/performance, /cost).

Coverage:
  1. portfolio.performance route sets Cache-Control: private.
  2. portfolio.cost route sets Cache-Control: private.
  3. Poisoned-field strip on portfolio.performance payload.
  4. Poisoned-field strip on portfolio.cost payload.
  5. Allowlist entries exist for both new concepts.
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import Response

import dhanradar.insights.router as insights_router
from dhanradar.mf.serialization import ALLOWED_FIELDS


def _user() -> SimpleNamespace:
    return SimpleNamespace(is_anonymous=False, user_id="00000000-0000-0000-0000-000000000001", tier="free")


async def test_portfolio_performance_private_header_and_poison_strip(monkeypatch) -> None:
    async def _noop(*_args, **_kwargs):
        return None

    async def _payload(*_args, **_kwargs):
        return {
            "portfolio_id": "p1",
            "as_of": "2026-08-22",
            "lifetime_xirr_pct": 10.4,
            "lifetime_coverage_pct": 92,
            "windows": [],
            "no_data_reason": None,
            "unified_score": 91,
            "factor_weights": {"quality": 0.2},
            "hidden_extra": "drop-me",
        }

    monkeypatch.setattr(insights_router, "_require_mf_consent", _noop)
    monkeypatch.setattr(insights_router, "_owned_portfolio_id", _noop)
    monkeypatch.setattr(insights_router, "_portfolio_performance_payload", _payload)

    response = Response()
    result = await insights_router.portfolio_performance(
        portfolio_id="p1",
        user=_user(),
        db=SimpleNamespace(),
        response=response,
    )

    assert response.headers["Cache-Control"] == "private"
    assert result["status"] == "present"
    assert "unified_score" not in result["data"]
    assert "factor_weights" not in result["data"]
    assert "hidden_extra" not in result["data"]


async def test_portfolio_cost_private_header_and_poison_strip(monkeypatch) -> None:
    async def _noop(*_args, **_kwargs):
        return None

    async def _payload(*_args, **_kwargs):
        return {
            "portfolio_id": "p1",
            "as_of": "2026-08-22",
            "weighted_ter_pct": 0.84,
            "ter_coverage_pct": 100,
            "direct_plan_share_pct": 62.5,
            "direct_plan_coverage_pct": 100,
            "holdings": [],
            "no_data_reason": None,
            "score": 77,
            "unified_score": 89,
            "rogue": True,
        }

    monkeypatch.setattr(insights_router, "_require_mf_consent", _noop)
    monkeypatch.setattr(insights_router, "_owned_portfolio_id", _noop)
    monkeypatch.setattr(insights_router, "_portfolio_cost_payload", _payload)

    response = Response()
    result = await insights_router.portfolio_cost(
        portfolio_id="p1",
        user=_user(),
        db=SimpleNamespace(),
        response=response,
    )

    assert response.headers["Cache-Control"] == "private"
    assert result["status"] == "present"
    assert "score" not in result["data"]
    assert "unified_score" not in result["data"]
    assert "rogue" not in result["data"]


def test_allowlists_registered_for_p1a_concepts() -> None:
    assert "portfolio.performance" in ALLOWED_FIELDS
    assert "portfolio.cost" in ALLOWED_FIELDS

    perf = ALLOWED_FIELDS["portfolio.performance"]
    cost = ALLOWED_FIELDS["portfolio.cost"]

    for field in ("portfolio_id", "as_of", "windows", "lifetime_xirr_pct"):
        assert field in perf
    for field in ("portfolio_id", "as_of", "weighted_ter_pct", "holdings"):
        assert field in cost

    for bad in ("unified_score", "score", "factor_weights", "fair_value"):
        assert bad not in perf
        assert bad not in cost
