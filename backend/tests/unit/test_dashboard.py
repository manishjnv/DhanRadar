"""
Unit tests for the Dashboard module (B56) — no DB (endpoint+DB paths are covered by
tests/integration/test_dashboard.py). Covers the DB-free seams:

  * indices  — Yahoo mocked: happy path, read-through cache, graceful empty degrade.
  * ranking  — pure label/band ordering + latest-per-isin dedup + limit cap.
  * schemas  — the no-numeric-leak guard (unified_score can never be a field).

asyncio_mode = "auto" (pyproject.toml) — async tests need no decorator.
"""

from __future__ import annotations

from dhanradar.dashboard import indices as indices_mod
from dhanradar.dashboard.indices import get_indices
from dhanradar.dashboard.schemas import FundLabel, PortfolioSummary, TopScoredFund
from dhanradar.dashboard.service import latest_per_isin, rank_top_scored


# --- indices (Yahoo mocked; fakeredis via patch_redis) -----------------------
async def test_indices_happy_path_from_yahoo(patch_redis, monkeypatch):
    prices = {"^NSEI": 24832.65, "^BSESN": 81234.78, "^NSEBANK": 53120.40, "NIFTYMIDCAP150.NS": 18945.30}

    async def fake_meta(client, symbol):
        p = prices.get(symbol)
        return {"regularMarketPrice": p, "chartPreviousClose": p * 0.99} if p else None

    monkeypatch.setattr(indices_mod, "_quote_meta", fake_meta)
    out = await get_indices()

    assert {i.name for i in out} == {"Nifty 50", "Sensex", "Nifty Bank", "Nifty Midcap 150"}
    nifty = next(i for i in out if i.name == "Nifty 50")
    assert nifty.value == 24832.65
    assert nifty.change_pct == round((0.01 / 0.99) * 100, 2)  # ~+1.01% vs prev close


async def test_indices_second_call_served_from_cache(patch_redis, monkeypatch):
    calls = {"n": 0}

    async def fake_meta(client, symbol):
        calls["n"] += 1
        return {"regularMarketPrice": 100.0, "chartPreviousClose": 99.0}

    monkeypatch.setattr(indices_mod, "_quote_meta", fake_meta)
    first = await get_indices()
    fetched = calls["n"]
    second = await get_indices()

    assert calls["n"] == fetched  # cache hit — no second Yahoo fetch
    assert [i.model_dump() for i in first] == [i.model_dump() for i in second]


async def test_indices_degrades_to_empty_on_total_failure(patch_redis, monkeypatch):
    async def fake_meta(client, symbol):
        return None  # every symbol fails

    monkeypatch.setattr(indices_mod, "_quote_meta", fake_meta)
    assert await get_indices() == []


# --- ranking (pure) ----------------------------------------------------------
def test_rank_top_scored_orders_by_label_then_band():
    # rows: (isin, label, band, scored_at, scheme_name, category)
    rows = [
        ("I1", "on_track", "high", 2, "B Fund", "Large Cap"),
        ("I2", "in_form", "medium", 2, "A Fund", "Flexi Cap"),
        ("I3", "off_track", "high", 2, "C Fund", "Value"),
        ("I4", "in_form", "high", 2, "D Fund", "Mid Cap"),
    ]
    assert [f.isin for f in rank_top_scored(rows)] == ["I4", "I2", "I1", "I3"]


def test_latest_per_isin_keeps_the_most_recent_row():
    rows = [
        ("I1", "in_form", "high", 3, "A", "X"),   # latest (pre-ordered scored_at DESC)
        ("I1", "on_track", "low", 1, "A", "X"),   # older → dropped
        ("I2", "off_track", "medium", 2, "B", "Y"),
    ]
    out = latest_per_isin(rows)
    assert len(out) == 2
    assert out[0][1] == "in_form"


def test_rank_top_scored_caps_at_limit():
    rows = [(f"I{i}", "on_track", "high", 1, f"F{i}", "Cat") for i in range(10)]
    assert len(rank_top_scored(rows)) == 6


def test_rank_uses_scheme_name_for_uncategorized_fallback():
    rows = [("I1", "on_track", "high", 1, None, None)]
    fund = rank_top_scored(rows)[0]
    assert fund.scheme_name == "I1" and fund.category == "Uncategorized"


# --- no-numeric-leak guard ---------------------------------------------------
def test_schemas_never_expose_unified_score():
    for model in (PortfolioSummary, TopScoredFund, FundLabel):
        assert "unified_score" not in model.model_fields
    # The fund projections expose ONLY label + band as the rating signal.
    assert set(FundLabel.model_fields) == {"isin", "scheme_name", "label", "confidence_band"}
    assert set(TopScoredFund.model_fields) == {
        "isin", "scheme_name", "category", "label", "confidence_band",
    }


def test_portfolio_summary_carries_disclosure_bundle():
    from dhanradar.scoring.engine.schemas import NOT_ADVICE

    s = PortfolioSummary(
        current_value=None, xirr_pct=None, fund_count=0, last_updated=None, funds=[],
        disclosure="d", not_advice=NOT_ADVICE, disclaimer_version="v1",
    )
    assert s.not_advice == NOT_ADVICE
