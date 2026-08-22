"""
Unit tests — GET /mf/compare/bundle Wave C2 (COMPARE_LIVE_DATA_PLAN.md).

Coverage:
  Pure overlap helper
  ──────────────────
  1.  compute_overlap_pct: empty inputs → 0.0
  2.  compute_overlap_pct: no common names → 0.0
  3.  compute_overlap_pct: all common, equal weights → full sum
  4.  compute_overlap_pct: partial overlap, min-weight semantics
  5.  compute_overlap_pct: None weight_pct rows ignored

  Pairwise overlap hard guard
  ───────────────────────────
  6.  build_pairwise_overlap: frag_a=None → no_data fund_not_found
  7.  build_pairwise_overlap: composition.no_data=True → no_data insufficient_coverage
  8.  build_pairwise_overlap: holdings_count=0 → no_data insufficient_coverage (HARD GUARD)
  9.  build_pairwise_overlap: both covered → overlap_pct, isin_a/b, basis present
  10. build_pairwise_overlap: result never emits 0% when coverage=0

  Serialization / poisoned-field tests
  ─────────────────────────────────────
  11. mf.compare_composition — unknown keys stripped, no forbidden score keys
  12. mf.compare_people — unknown keys stripped, no forbidden score keys
  13. mf.compare_flows — unknown keys stripped, no forbidden score keys
  14. mf.compare_events / mf.compare_event — unknown keys stripped, no forbidden
  15. mf.compare_amc — unknown keys stripped, no forbidden score keys
  16. mf.compare_alternative — unknown keys stripped, no forbidden score keys
  17. mf.compare_alternatives — peers list scrubbed
  18. mf.compare_overlap — unknown keys stripped, no forbidden score keys
  19. Full bundle response — score keys absent from all C2 shapes in serialized JSON
  20. Fragment allowlist — C2 keys present and stripped of unknowns

  Alternatives dedup
  ──────────────────
  21. Compared ISINs are excluded from each fund's alternatives list
  22. Alternatives capped at 6 after dedup

  Router — pairwise overlap cache paths
  ──────────────────────────────────────
  23. Warm overlap: cached overlap returned, no recompute
  24. Cold overlap: computed and written with TTL 6h key
  25. Overlap key batched in same MGET as per-ISIN fragment keys

asyncio_mode = "auto" (pyproject.toml).  No real DB / Redis: async fakes throughout.
"""

from __future__ import annotations

import json
import re
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import Response

from dhanradar.mf.compare_read import (
    _CMP_OVERLAP_TTL,
    build_pairwise_overlap,
    compute_overlap_pct,
)
from dhanradar.mf.router import compare_bundle
from dhanradar.mf.serialization import (
    FORBIDDEN_SCORE_KEYS,
    _apply_allowlist,
    _scrub,
    serialize_compare_bundle_response,
)


@pytest.fixture(autouse=True)
def _identity_canonicalization(monkeypatch):
    """Batch C: the route canonicalizes ISINs via a DB lookup; these unit tests call the
    handler directly with db=None, so canonicalization is identity-patched (its real
    mapping logic is covered by test_compare_canonicalization.py)."""

    async def _identity(session, requested):
        return {r: r for r in requested}

    monkeypatch.setattr("dhanradar.mf.compare_read.canonicalize_compare_isins", _identity)

# ---------------------------------------------------------------------------
# Shared ISINs
# ---------------------------------------------------------------------------

ISIN_A = "INF174K01KH7"
ISIN_B = "INF200K01234"
ISIN_C = "INF123K00AAA"
ISIN_D = "INF456K00BBB"

_FORBIDDEN_RE = re.compile(
    "|".join(re.escape(f'"{k}"') for k in sorted(FORBIDDEN_SCORE_KEYS))
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _holding(name: str, weight: float | None) -> dict:
    return {"name": name, "sector": "Equity", "weight_pct": weight}


def _composition(holdings: list[dict], count: int | None = None) -> dict:
    n = count if count is not None else len(holdings)
    return {
        "holdings": holdings,
        "sectors": [{"name": "Equity", "weight_pct": 80.0}],
        "as_of_month": "2026-07-01",
        "coverage": {"holdings_count": n, "weight_covered_pct": sum(h["weight_pct"] for h in holdings if h["weight_pct"])},
    }


def _fragment_c2(isin: str) -> dict:
    """Minimal valid C1+C2 compare fragment."""
    holdings = [_holding("HDFC Bank", 8.5), _holding("Reliance", 7.2)]
    return {
        # C1 core (just enough for the scrub + bundle to work)
        "isin": isin,
        "scheme_name": f"{isin} Fund - Direct - Growth",
        "fund_name_short": f"{isin} Fund",
        "amc_name": "Test AMC",
        "sebi_category": "Large Cap Fund",
        "category": "Equity",
        "plan_type": "Direct",
        "option_type": "Growth",
        "launch_date": "2015-01-01",
        "expense_ratio_pct": 0.5,
        "is_segregated": False,
        "verb_label": "on_track",
        "confidence_band": "medium",
        "category_rank": 3,
        "category_total": 30,
        "return_3m_pct": 3.1,
        "return_6m_pct": 7.4,
        "return_1y_pct": 14.2,
        "return_3y_pct": 16.1,
        "return_5y_pct": 12.0,
        "nav_latest": 120.5,
        "nav_date": "2026-08-21",
        "nav_change_pct": 0.42,
        "aum_crore": 5000.0,
        "sharpe_ratio": 0.9,
        "sortino_ratio": 1.1,
        "volatility_pct": 12.5,
        "max_drawdown_pct": -18.3,
        "rolling_1y_avg_pct": 14.0,
        "rolling_1y_min_pct": 8.0,
        "rolling_1y_max_pct": 22.0,
        "rolling_1y_pct_positive": 0.72,
        "rolling_3y_avg_pct": 15.0,
        "rolling_3y_min_pct": 9.0,
        "rolling_3y_max_pct": 21.0,
        "rolling_3y_pct_positive": 0.85,
        "category_median_return_1y_pct": 12.0,
        "category_median_return_3y_pct": 13.5,
        "category_median_ter_pct": 0.7,
        "sip_5y": {
            "amount": 5000, "years": 5, "months_invested": 60,
            "total_invested": 300000.0, "final_value": 420000.0,
            "xirr_pct": 13.5, "as_of": "2026-08-21",
            "assumptions": "Past performance illustration only.",
        },
        "sip_10y": {
            "amount": 5000, "years": 10, "months_invested": 120,
            "total_invested": 600000.0, "final_value": 1100000.0,
            "xirr_pct": 14.0, "as_of": "2026-08-21",
            "assumptions": "Past performance illustration only.",
        },
        "benchmark": {
            "label": "NIFTY 50 TRI", "is_fallback": False,
            "points": [{"d": "2025-08-21", "v": 100.0}], "window": "1y",
        },
        # C2 depth
        "composition": _composition(holdings),
        "people": {
            "managers": [{"name": "John Doe", "start_date": "2020-01-01", "tenure_years": 4.6}],
            "manager_changes_5y": 1,
        },
        "flows": {
            "points": [{"period_month": "2026-07-01", "net_flow_cr": 120.5, "net_aum_cr": None}],
            "scheme_category": "Open Ended Equity Scheme",
            "as_of_month": "2026-07-01",
        },
        "events": {
            "events": [
                {"event_type": "rank_change", "as_of": "2026-08-01", "summary": "Rank improved from 5 to 3.", "severity": "info"},
            ]
        },
        "amc": {"amc_name": "Test AMC", "scheme_count": 30, "category_count": 8},
        "alternatives": {
            "peers": [
                {
                    "isin": ISIN_C, "scheme_name": "Fund C", "fund_name_short": "Fund C",
                    "amc_name": "AMC C", "verb_label": "on_track", "category_rank": 5,
                    "return_1y_pct": 13.0, "return_3y_pct": 14.0, "expense_ratio_pct": 0.6, "volatility_pct": 11.0,
                },
                {
                    "isin": ISIN_D, "scheme_name": "Fund D", "fund_name_short": "Fund D",
                    "amc_name": "AMC D", "verb_label": "off_track", "category_rank": 8,
                    "return_1y_pct": 10.0, "return_3y_pct": 11.0, "expense_ratio_pct": 0.8, "volatility_pct": 14.0,
                },
            ]
        },
    }


class _FakeRedis:
    def __init__(self, seed: dict[str, str] | None = None, *, scard_value: int = 2) -> None:
        self.store: dict[str, str] = dict(seed or {})
        self.set_calls: list[tuple[str, int]] = []  # (key, ex)
        self._scard_value = scard_value
        self._ttl = -2

    async def mget(self, *keys: str) -> list[str | None]:
        return [self.store.get(k) for k in keys]

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
        self.set_calls.append((key, ex or 0))

    async def sadd(self, key: str, *members: str) -> int:
        return 1

    async def scard(self, key: str) -> int:
        return self._scard_value

    async def ttl(self, key: str) -> int:
        return self._ttl

    async def expire(self, key: str, seconds: int) -> None:
        self._ttl = seconds


def _request(ip: str = "1.2.3.4") -> SimpleNamespace:
    return SimpleNamespace(
        headers={"CF-Connecting-IP": ip},
        client=SimpleNamespace(host=ip),
    )


# ===========================================================================
# 1-5 — compute_overlap_pct (pure helper)
# ===========================================================================


def test_overlap_empty_inputs() -> None:
    assert compute_overlap_pct([], []) == 0.0


def test_overlap_no_common_names() -> None:
    a = [_holding("HDFC Bank", 8.5)]
    b = [_holding("Reliance", 7.0)]
    assert compute_overlap_pct(a, b) == 0.0


def test_overlap_all_common_equal_weights() -> None:
    a = [_holding("HDFC Bank", 8.5), _holding("Reliance", 7.0)]
    b = [_holding("HDFC Bank", 8.5), _holding("Reliance", 7.0)]
    assert compute_overlap_pct(a, b) == round(8.5 + 7.0, 2)


def test_overlap_partial_uses_min_weight() -> None:
    a = [_holding("HDFC Bank", 10.0), _holding("Reliance", 5.0)]
    b = [_holding("HDFC Bank", 6.0)]  # lower weight for HDFC Bank; Reliance absent
    assert compute_overlap_pct(a, b) == 6.0


def test_overlap_none_weight_ignored() -> None:
    a = [_holding("HDFC Bank", None), _holding("Reliance", 7.0)]
    b = [_holding("HDFC Bank", 8.0), _holding("Reliance", 7.0)]
    # HDFC Bank skipped (None weight in a); only Reliance overlaps
    assert compute_overlap_pct(a, b) == 7.0


# ===========================================================================
# 6-10 — build_pairwise_overlap (hard guard)
# ===========================================================================


def test_pairwise_frag_none_is_no_data() -> None:
    result = build_pairwise_overlap(None, _fragment_c2(ISIN_B), ISIN_A, ISIN_B)
    assert result["no_data"] is True
    assert result["reason"] == "fund_not_found"


def test_pairwise_composition_no_data_flag() -> None:
    frag = _fragment_c2(ISIN_A)
    frag["composition"] = {"no_data": True}
    result = build_pairwise_overlap(frag, _fragment_c2(ISIN_B), ISIN_A, ISIN_B)
    assert result["no_data"] is True
    assert result["reason"] == "insufficient_coverage"


def test_pairwise_zero_holdings_count_triggers_guard() -> None:
    """HARD GUARD: holdings_count=0 must return no_data, never 0%."""
    frag_a = _fragment_c2(ISIN_A)
    frag_a["composition"] = {
        "holdings": [],
        "sectors": [],
        "as_of_month": None,
        "coverage": {"holdings_count": 0, "weight_covered_pct": None},
    }
    result = build_pairwise_overlap(frag_a, _fragment_c2(ISIN_B), ISIN_A, ISIN_B)
    assert result["no_data"] is True
    assert "overlap_pct" not in result


def test_pairwise_both_covered_returns_overlap() -> None:
    result = build_pairwise_overlap(_fragment_c2(ISIN_A), _fragment_c2(ISIN_B), ISIN_A, ISIN_B)
    assert result.get("no_data") is None or "no_data" not in result
    assert "overlap_pct" in result
    assert result["common_holdings"][0]["name"] == "HDFC Bank"
    assert result["isin_a"] == ISIN_A
    assert result["isin_b"] == ISIN_B
    assert result["basis"] == "top_holdings_weight"


def test_pairwise_never_emits_zero_pct_for_uncovered() -> None:
    """Regression: 0% must never appear for an uncovered pair."""
    frag_empty = _fragment_c2(ISIN_A)
    frag_empty["composition"]["coverage"]["holdings_count"] = 0
    result = build_pairwise_overlap(frag_empty, _fragment_c2(ISIN_B), ISIN_A, ISIN_B)
    assert result.get("overlap_pct") is None
    assert result["no_data"] is True


# ===========================================================================
# 11-18 — per-shape poisoned-field tests (allowlist strips unknowns + score keys)
# ===========================================================================


def _assert_no_forbidden_in_json(obj: Any) -> None:
    s = json.dumps(obj)
    m = _FORBIDDEN_RE.search(s)
    assert m is None, f"Forbidden key found in output: {m.group()} — full: {s[:300]}"


def test_composition_allowlist_strips_unknown() -> None:
    raw = {
        "holdings": [{"name": "HDFC Bank", "sector": "Fin", "weight_pct": 8.5, "unified_score": 99}],
        "sectors": [], "as_of_month": "2026-07-01",
        "coverage": {"holdings_count": 1, "weight_covered_pct": 8.5},
        "extra_key": "drop_me", "score": 77,
    }
    scrubbed = _scrub(raw)
    comp = _apply_allowlist("mf.compare_composition", scrubbed)
    holding = _apply_allowlist("mf.compare_composition_holding", comp["holdings"][0])
    assert "extra_key" not in comp
    assert "unified_score" not in holding
    _assert_no_forbidden_in_json(comp)


def test_people_allowlist_strips_unknown() -> None:
    raw = {"managers": [], "manager_changes_5y": 1, "score": 99, "extra": "x"}
    scrubbed = _scrub(raw)
    out = _apply_allowlist("mf.compare_people", scrubbed)
    assert "extra" not in out
    assert "score" not in out
    _assert_no_forbidden_in_json(out)


def test_flows_allowlist_strips_unknown() -> None:
    raw = {
        "points": [], "scheme_category": "Equity", "as_of_month": None,
        "source_blocked": True, "unified_score": 55, "hidden": True,
    }
    scrubbed = _scrub(raw)
    out = _apply_allowlist("mf.compare_flows", scrubbed)
    assert "hidden" not in out
    assert "unified_score" not in out
    _assert_no_forbidden_in_json(out)


def test_events_allowlist_strips_payload_and_unknown() -> None:
    raw_event = {
        "event_type": "rank_change", "as_of": "2026-08-01",
        "summary": "Rank improved.", "severity": "info",
        "payload": {"direction": "up", "score": 99},  # payload must be stripped by event allowlist
        "extra": "drop",
    }
    scrubbed = _scrub(raw_event)
    out = _apply_allowlist("mf.compare_event", scrubbed)
    assert "payload" not in out
    assert "extra" not in out
    _assert_no_forbidden_in_json(out)


def test_amc_allowlist_strips_unknown() -> None:
    raw = {"amc_name": "Test AMC", "scheme_count": 30, "category_count": 8, "score": 99, "x": 1}
    scrubbed = _scrub(raw)
    out = _apply_allowlist("mf.compare_amc", scrubbed)
    assert "x" not in out
    assert "score" not in out
    _assert_no_forbidden_in_json(out)


def test_alternative_allowlist_strips_unknown() -> None:
    raw = {
        "isin": ISIN_C, "scheme_name": "Fund", "fund_name_short": "Fund",
        "amc_name": "AMC", "verb_label": "on_track", "category_rank": 5,
        "return_1y_pct": 12.0, "return_3y_pct": 14.0, "expense_ratio_pct": 0.6,
        "volatility_pct": 11.0, "unified_score": 77, "hidden": "x",
    }
    scrubbed = _scrub(raw)
    out = _apply_allowlist("mf.compare_alternative", scrubbed)
    assert "hidden" not in out
    assert "unified_score" not in out
    _assert_no_forbidden_in_json(out)


def test_alternatives_wrapper_allowlist() -> None:
    raw = {"peers": [], "no_data": True, "score": 9, "extra": "y"}
    scrubbed = _scrub(raw)
    out = _apply_allowlist("mf.compare_alternatives", scrubbed)
    assert "extra" not in out
    assert "score" not in out


def test_overlap_allowlist_strips_unknown() -> None:
    raw = {
        "isin_a": ISIN_A, "isin_b": ISIN_B, "overlap_pct": 23.5,
        "as_of_month_a": "2026-07-01", "as_of_month_b": "2026-07-01",
        "basis": "top_holdings_weight", "score": 99, "extra": True,
    }
    scrubbed = _scrub(raw)
    out = _apply_allowlist("mf.compare_overlap", scrubbed)
    assert "extra" not in out
    assert "score" not in out
    _assert_no_forbidden_in_json(out)


# ===========================================================================
# 19 — full bundle serialization: no score keys anywhere in JSON
# ===========================================================================


def test_full_bundle_c2_no_score_keys_in_serialized_json() -> None:
    """A poisoned fragment with score keys in every C2 shape must be fully scrubbed."""
    frag = _fragment_c2(ISIN_A)
    # Inject forbidden keys into every C2 nested shape
    frag["composition"]["unified_score"] = 99
    frag["composition"]["holdings"][0]["score"] = 88
    frag["people"]["factor_weights"] = {"q": 0.5}
    frag["flows"]["fair_value"] = 123
    frag["events"]["events"][0]["score"] = 77
    frag["amc"]["unified_score"] = 66
    frag["alternatives"]["peers"][0]["score"] = 55

    result = serialize_compare_bundle_response(
        isins=[ISIN_A, ISIN_B],
        fragments={ISIN_A: frag, ISIN_B: _fragment_c2(ISIN_B)},
        as_of="2026-08-21",
        pairwise={f"{ISIN_A}|{ISIN_B}": {"overlap_pct": 15.0, "isin_a": ISIN_A, "isin_b": ISIN_B,
                                           "as_of_month_a": "2026-07-01", "as_of_month_b": "2026-07-01",
                                           "basis": "top_holdings_weight", "score": 99}},
    )
    _assert_no_forbidden_in_json(result)


# ===========================================================================
# 20 — mf.compare_fragment allowlist includes C2 keys
# ===========================================================================


def test_compare_fragment_allowlist_includes_c2_keys() -> None:
    from dhanradar.mf.serialization import ALLOWED_FIELDS

    c2_keys = {"composition", "people", "flows", "events", "amc", "alternatives"}
    assert c2_keys.issubset(ALLOWED_FIELDS["mf.compare_fragment"])


# ===========================================================================
# 21-22 — alternatives dedup and cap
# ===========================================================================


def test_alternatives_excludes_compared_isins() -> None:
    """Alternatives must not include any ISIN in the compared set."""
    frag_a = _fragment_c2(ISIN_A)
    # Add ISIN_B as a peer of ISIN_A — it must be filtered out since ISIN_B is compared
    frag_a["alternatives"]["peers"].append({
        "isin": ISIN_B, "scheme_name": "Fund B", "fund_name_short": "Fund B",
        "amc_name": "AMC B", "verb_label": "on_track", "category_rank": 2,
        "return_1y_pct": 15.0, "return_3y_pct": 16.0, "expense_ratio_pct": 0.5, "volatility_pct": 12.0,
    })

    result = serialize_compare_bundle_response(
        isins=[ISIN_A, ISIN_B],
        fragments={ISIN_A: frag_a, ISIN_B: _fragment_c2(ISIN_B)},
        as_of="2026-08-21",
        pairwise={},
    )
    peer_isins_a = {p["isin"] for p in result["fragments"][ISIN_A]["alternatives"]["peers"]}
    assert ISIN_B not in peer_isins_a
    assert ISIN_A not in peer_isins_a  # own ISIN never appears (get_fund_peers already excludes it)


def test_alternatives_capped_at_6() -> None:
    """More than 6 peers are capped to 6 (after compared-ISIN dedup)."""
    frag = _fragment_c2(ISIN_A)
    # Build 8 peers with ISINs not in the compared set
    many_peers = [
        {
            "isin": f"INF{i:010d}A", "scheme_name": f"Fund {i}", "fund_name_short": f"Fund {i}",
            "amc_name": "AMC", "verb_label": "on_track", "category_rank": i,
            "return_1y_pct": 12.0, "return_3y_pct": 13.0, "expense_ratio_pct": 0.5, "volatility_pct": 10.0,
        }
        for i in range(8)
    ]
    frag["alternatives"]["peers"] = many_peers

    result = serialize_compare_bundle_response(
        isins=[ISIN_A, ISIN_B],
        fragments={ISIN_A: frag, ISIN_B: _fragment_c2(ISIN_B)},
        as_of="2026-08-21",
        pairwise={},
    )
    assert len(result["fragments"][ISIN_A]["alternatives"]["peers"]) <= 6


# ===========================================================================
# 23-25 — router: pairwise overlap cache paths
# ===========================================================================


async def test_warm_overlap_returned_without_recompute(monkeypatch) -> None:
    """A cached overlap entry is returned directly without calling build_pairwise_overlap."""
    pair_key = f"{ISIN_A}|{ISIN_B}"
    overlap_data = {
        "isin_a": ISIN_A, "isin_b": ISIN_B, "overlap_pct": 18.5,
        "as_of_month_a": "2026-07-01", "as_of_month_b": "2026-07-01",
        "basis": "top_holdings_weight",
    }
    seed = {
        f"mf:cmp:{ISIN_A}": json.dumps(_fragment_c2(ISIN_A)),
        f"mf:cmp:{ISIN_B}": json.dumps(_fragment_c2(ISIN_B)),
        f"mf:cmp:overlap:{ISIN_A}:{ISIN_B}": json.dumps(overlap_data),
    }
    fake_redis = _FakeRedis(seed=seed)
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: fake_redis)

    result = await compare_bundle(
        request=_request(), response=Response(), db=None, isins=f"{ISIN_A},{ISIN_B}",
    )
    assert result["pairwise"][pair_key]["overlap_pct"] == 18.5
    # No new overlap key written (was cached)
    written_overlap_keys = [k for k, _ in fake_redis.set_calls if "overlap" in k]
    assert written_overlap_keys == []


async def test_cold_overlap_computed_and_cached(monkeypatch) -> None:
    """A cold overlap miss triggers build_pairwise_overlap and caches the result."""
    fake_redis = _FakeRedis()
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: fake_redis)

    async def fake_compose(cold_isins: list[str]) -> dict:
        return {isin: _fragment_c2(isin) for isin in cold_isins}

    monkeypatch.setattr(
        "dhanradar.mf.compare_read.compose_compare_bundle_fragments", fake_compose
    )

    result = await compare_bundle(
        request=_request(), response=Response(), db=None, isins=f"{ISIN_A},{ISIN_B}",
    )
    pair_key = f"{ISIN_A}|{ISIN_B}"
    assert pair_key in result["pairwise"]
    # Verify the overlap was written with TTL 6h
    overlap_writes = [(k, ex) for k, ex in fake_redis.set_calls if "overlap" in k]
    assert len(overlap_writes) == 1
    written_key, written_ttl = overlap_writes[0]
    assert written_key == f"mf:cmp:overlap:{ISIN_A}:{ISIN_B}"
    assert written_ttl == _CMP_OVERLAP_TTL


async def test_overlap_keys_batched_in_same_mget(monkeypatch) -> None:
    """Overlap cache keys must be batched into the same MGET as per-ISIN fragment keys."""
    mget_calls: list[tuple[str, ...]] = []

    class _TrackedRedis(_FakeRedis):
        async def mget(self, *keys: str) -> list[str | None]:
            mget_calls.append(keys)
            return await super().mget(*keys)

    fake_redis = _TrackedRedis()
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: fake_redis)

    async def fake_compose(cold_isins: list[str]) -> dict:
        return {isin: _fragment_c2(isin) for isin in cold_isins}

    monkeypatch.setattr(
        "dhanradar.mf.compare_read.compose_compare_bundle_fragments", fake_compose
    )

    await compare_bundle(
        request=_request(), response=Response(), db=None, isins=f"{ISIN_A},{ISIN_B}",
    )
    # Must be exactly ONE mget call containing both per-ISIN keys and the overlap key
    assert len(mget_calls) == 1
    single_call_keys = mget_calls[0]
    assert f"mf:cmp:{ISIN_A}" in single_call_keys
    assert f"mf:cmp:{ISIN_B}" in single_call_keys
    assert f"mf:cmp:overlap:{ISIN_A}:{ISIN_B}" in single_call_keys
