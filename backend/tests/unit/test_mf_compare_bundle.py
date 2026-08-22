"""
Unit tests — GET /mf/compare/bundle (COMPARE_LIVE_DATA_PLAN.md Wave C1).

Coverage:
  1.  400 for fewer than 2 ISINs.
  2.  400 for more than 4 ISINs.
  3.  400 for duplicate ISINs in the query string.
  4.  400 for an ISIN that fails the ^[A-Z0-9]{12}$ format check.
  5.  429 when the per-IP distinct-ISIN budget is exceeded.
  6.  Cache-hit path: MGET returns cached fragments → compositor never called.
  7.  Cold path: MGET misses → compose_compare_bundle_fragments called, result cached.
  8.  Poisoned-field test: a smuggled unified_score/score/factor_weights key in a
      fragment is scrubbed before reaching the response.
  9.  Nested benchmark allowlist: extra keys inside a benchmark dict are stripped.
  10. Cache-Control: public, max-age=300.

asyncio_mode = "auto" (pyproject.toml).  No real DB / Redis: async fakes throughout.
"""

from __future__ import annotations

import json
import re
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException, Response

from dhanradar.mf.router import _COMPARE_ISIN_BUDGET, compare_bundle
from dhanradar.mf.serialization import serialize_compare_bundle_response


@pytest.fixture(autouse=True)
def _identity_canonicalization(monkeypatch):
    """Batch C: the route canonicalizes ISINs via a DB lookup; these unit tests call the
    handler directly with db=None, so canonicalization is identity-patched (its real
    mapping logic is covered by test_compare_canonicalization.py)."""

    async def _identity(session, requested):
        return {r: r for r in requested}

    monkeypatch.setattr("dhanradar.mf.compare_read.canonicalize_compare_isins", _identity)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ISIN_A = "INF174K01KH7"
ISIN_B = "INF200K01234"
ISIN_C = "INF123K00AAA"
ISIN_D = "INF456K00BBB"
ISIN_E = "INF789K00CCC"  # 5th ISIN (too many)


def _fragment(isin: str, *, nav_date: str = "2026-08-21") -> dict[str, Any]:
    """Minimal valid compare fragment (all allowlisted fields present)."""
    return {
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
        "nav_date": nav_date,
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
            "amount": 5000,
            "years": 5,
            "months_invested": 60,
            "total_invested": 300000.0,
            "final_value": 420000.0,
            "xirr_pct": 13.5,
            "as_of": nav_date,
            "assumptions": "Past performance illustration only.",
        },
        "sip_10y": {
            "amount": 5000,
            "years": 10,
            "months_invested": 120,
            "total_invested": 600000.0,
            "final_value": 1100000.0,
            "xirr_pct": 14.0,
            "as_of": nav_date,
            "assumptions": "Past performance illustration only.",
        },
        "benchmark": {
            "label": "NIFTY 50 TRI",
            "is_fallback": False,
            "points": [{"d": "2025-08-21", "v": 100.0}, {"d": nav_date, "v": 114.2}],
            "window": "1y",
        },
    }


class _FakeRedis:
    """Minimal async Redis stub — plain dict store, SADD/SCARD/TTL/MGET supported."""

    def __init__(self, seed: dict[str, str] | None = None, *, scard_value: int = 2) -> None:
        self.store: dict[str, str] = dict(seed or {})
        self.set_calls: list[str] = []
        self.sadd_calls: list[tuple[str, list[str]]] = []
        self._scard_value = scard_value  # returned by scard (controls budget test)
        self._ttl = -2  # -2 = key doesn't exist yet; -1 = no expiry; >=0 = remaining

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def mget(self, *keys: str) -> list[str | None]:
        return [self.store.get(k) for k in keys]

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
        self.set_calls.append(key)

    async def sadd(self, key: str, *members: str) -> int:
        self.sadd_calls.append((key, list(members)))
        existing = set(self.store.get(key + ":set_data", "").split(",")) if self.store.get(key + ":set_data") else set()
        new = {m for m in members if m not in existing}
        existing |= new
        self.store[key + ":set_data"] = ",".join(existing)
        return len(new)

    async def scard(self, key: str) -> int:
        return self._scard_value

    async def ttl(self, key: str) -> int:
        return self._ttl

    async def expire(self, key: str, seconds: int) -> None:
        self._ttl = seconds


def _request(ip: str = "1.2.3.4") -> SimpleNamespace:
    """Minimal fake Request with headers and client."""
    return SimpleNamespace(
        headers={"CF-Connecting-IP": ip},
        client=SimpleNamespace(host=ip),
    )


# ---------------------------------------------------------------------------
# 1 — 400 for fewer than 2 ISINs
# ---------------------------------------------------------------------------


async def test_compare_bundle_400_too_few_isins(monkeypatch) -> None:
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: _FakeRedis())
    with pytest.raises(HTTPException) as exc:
        await compare_bundle(
            request=_request(),
            response=Response(),
            db=None,
            isins=ISIN_A,
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "compare_isin_count"


# ---------------------------------------------------------------------------
# 2 — 400 for more than 4 ISINs
# ---------------------------------------------------------------------------


async def test_compare_bundle_400_too_many_isins(monkeypatch) -> None:
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: _FakeRedis())
    five = f"{ISIN_A},{ISIN_B},{ISIN_C},{ISIN_D},{ISIN_E}"
    with pytest.raises(HTTPException) as exc:
        await compare_bundle(
            request=_request(),
            response=Response(),
            db=None,
            isins=five,
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "compare_isin_count"


# ---------------------------------------------------------------------------
# 3 — 400 for duplicate ISINs
# ---------------------------------------------------------------------------


async def test_compare_bundle_400_duplicate_isins(monkeypatch) -> None:
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: _FakeRedis())
    with pytest.raises(HTTPException) as exc:
        await compare_bundle(
            request=_request(),
            response=Response(),
            db=None,
            isins=f"{ISIN_A},{ISIN_A},{ISIN_B}",
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "compare_isin_duplicate"


# ---------------------------------------------------------------------------
# 4 — 400 for invalid ISIN format (lowercase / non-ASCII / wrong length)
# ---------------------------------------------------------------------------


async def test_compare_bundle_400_invalid_isin_format(monkeypatch) -> None:
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: _FakeRedis())
    with pytest.raises(HTTPException) as exc:
        await compare_bundle(
            request=_request(),
            response=Response(),
            db=None,
            isins=f"inf174k01kh7,{ISIN_B}",  # lowercase → invalid
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "compare_isin_invalid"


async def test_compare_bundle_400_short_isin(monkeypatch) -> None:
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: _FakeRedis())
    with pytest.raises(HTTPException) as exc:
        await compare_bundle(
            request=_request(),
            response=Response(),
            db=None,
            isins=f"TOOSHORT,{ISIN_B}",
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "compare_isin_invalid"


# ---------------------------------------------------------------------------
# 5 — 429 when per-IP distinct-ISIN budget is exceeded
# ---------------------------------------------------------------------------


async def test_compare_bundle_429_isin_budget_exceeded(monkeypatch) -> None:
    # scard_value > _COMPARE_ISIN_BUDGET triggers the 429
    fake_redis = _FakeRedis(scard_value=_COMPARE_ISIN_BUDGET + 1)
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: fake_redis)
    with pytest.raises(HTTPException) as exc:
        await compare_bundle(
            request=_request(),
            response=Response(),
            db=None,
            isins=f"{ISIN_A},{ISIN_B}",
        )
    assert exc.value.status_code == 429
    assert exc.value.detail == "isin_budget_exceeded"


# ---------------------------------------------------------------------------
# 6 — Cache-hit path: MGET returns both fragments → compositor never called
# ---------------------------------------------------------------------------


async def test_compare_bundle_cache_hit_mget_skips_compositor(monkeypatch) -> None:
    frag_a = _fragment(ISIN_A)
    frag_b = _fragment(ISIN_B)
    seed = {
        f"mf:cmp:{ISIN_A}": json.dumps(frag_a),
        f"mf:cmp:{ISIN_B}": json.dumps(frag_b),
    }
    fake_redis = _FakeRedis(seed=seed)
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: fake_redis)

    async def fail_if_called(cold_isins: list[str]) -> dict:
        raise AssertionError("compositor must not run on a full cache hit")

    monkeypatch.setattr(
        "dhanradar.mf.compare_read.compose_compare_bundle_fragments", fail_if_called
    )

    result = await compare_bundle(
        request=_request(),
        response=Response(),
        db=None,
        isins=f"{ISIN_A},{ISIN_B}",
    )

    assert result["isins"] == [ISIN_A, ISIN_B]
    assert result["fragments"][ISIN_A]["isin"] == ISIN_A
    assert result["fragments"][ISIN_B]["isin"] == ISIN_B
    # Per-ISIN fragment keys must not be re-written (they were cache-warm)
    isin_writes = [k for k in fake_redis.set_calls if "overlap" not in k]
    assert isin_writes == []


# ---------------------------------------------------------------------------
# 7 — Cold path: MGET misses → compositor called, result cached
# ---------------------------------------------------------------------------


async def test_compare_bundle_cold_compositor_called_and_cached(monkeypatch) -> None:
    fake_redis = _FakeRedis()
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: fake_redis)

    async def fake_compose(cold_isins: list[str]) -> dict:
        return {isin: _fragment(isin) for isin in cold_isins}

    monkeypatch.setattr(
        "dhanradar.mf.compare_read.compose_compare_bundle_fragments", fake_compose
    )

    result = await compare_bundle(
        request=_request(),
        response=Response(),
        db=None,
        isins=f"{ISIN_A},{ISIN_B}",
    )

    assert result["isins"] == [ISIN_A, ISIN_B]
    # Both fragments written to Redis
    assert f"mf:cmp:{ISIN_A}" in fake_redis.set_calls
    assert f"mf:cmp:{ISIN_B}" in fake_redis.set_calls


# ---------------------------------------------------------------------------
# 8 — Poisoned-field test: score keys in a fragment are scrubbed
# ---------------------------------------------------------------------------

_FORBIDDEN_RE = re.compile(r'"unified_score"|"score"|"factor_weights"|"fair_value"')


async def test_compare_bundle_score_keys_never_reach_response(monkeypatch) -> None:
    fake_redis = _FakeRedis()
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: fake_redis)

    poisoned = dict(_fragment(ISIN_A))
    poisoned["unified_score"] = 99.9
    poisoned["factor_weights"] = {"momentum": 0.4}

    async def fake_compose(cold_isins: list[str]) -> dict:
        return {ISIN_A: poisoned, ISIN_B: _fragment(ISIN_B)}

    monkeypatch.setattr(
        "dhanradar.mf.compare_read.compose_compare_bundle_fragments", fake_compose
    )

    result = await compare_bundle(
        request=_request(),
        response=Response(),
        db=None,
        isins=f"{ISIN_A},{ISIN_B}",
    )

    serialized = json.dumps(result)
    assert not _FORBIDDEN_RE.search(serialized), serialized
    frag_a = result["fragments"][ISIN_A]
    assert "unified_score" not in frag_a
    assert "factor_weights" not in frag_a


# ---------------------------------------------------------------------------
# 9 — Nested benchmark allowlist: extra keys stripped, approved keys preserved
# ---------------------------------------------------------------------------


async def test_compare_bundle_benchmark_extra_keys_stripped(monkeypatch) -> None:
    fake_redis = _FakeRedis()
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: fake_redis)

    frag = dict(_fragment(ISIN_A))
    frag["benchmark"] = {
        "label": "NIFTY 50 TRI",
        "is_fallback": False,
        "points": [{"d": "2026-08-21", "v": 114.2}],
        "window": "1y",
        "extra_key": "must_be_stripped",      # not in mf.compare_benchmark allowlist
        "unified_score": 88,                  # score field: scrubbed by _scrub first
    }

    async def fake_compose(cold_isins: list[str]) -> dict:
        return {ISIN_A: frag, ISIN_B: _fragment(ISIN_B)}

    monkeypatch.setattr(
        "dhanradar.mf.compare_read.compose_compare_bundle_fragments", fake_compose
    )

    result = await compare_bundle(
        request=_request(),
        response=Response(),
        db=None,
        isins=f"{ISIN_A},{ISIN_B}",
    )

    bench = result["fragments"][ISIN_A]["benchmark"]
    assert set(bench.keys()) == {"label", "is_fallback", "points", "window"}
    assert "extra_key" not in bench
    assert "unified_score" not in bench


# ---------------------------------------------------------------------------
# 10 — Cache-Control: public, max-age=300
# ---------------------------------------------------------------------------


async def test_compare_bundle_cache_control_is_public(monkeypatch) -> None:
    seed = {
        f"mf:cmp:{ISIN_A}": json.dumps(_fragment(ISIN_A)),
        f"mf:cmp:{ISIN_B}": json.dumps(_fragment(ISIN_B)),
    }
    monkeypatch.setattr("dhanradar.mf.router.get_redis", lambda: _FakeRedis(seed=seed))
    resp = Response()

    await compare_bundle(
        request=_request(),
        response=resp,
        db=None,
        isins=f"{ISIN_A},{ISIN_B}",
    )

    assert resp.headers["Cache-Control"] == "public, max-age=300"


# ---------------------------------------------------------------------------
# Serialization unit tests (serialize_compare_bundle_response directly)
# ---------------------------------------------------------------------------


def test_serialize_compare_bundle_scrubs_score_keys() -> None:
    """Score keys are scrubbed from fragments before the response."""
    frag = dict(_fragment(ISIN_A))
    frag["unified_score"] = 55

    result = serialize_compare_bundle_response(
        isins=[ISIN_A],
        fragments={ISIN_A: frag},
        as_of="2026-08-21",
    )
    assert "unified_score" not in result["fragments"][ISIN_A]


def test_serialize_compare_bundle_none_fragment_preserved() -> None:
    """A None fragment (fund not found) is preserved as None in the output."""
    result = serialize_compare_bundle_response(
        isins=[ISIN_A, ISIN_B],
        fragments={ISIN_A: _fragment(ISIN_A), ISIN_B: None},
        as_of=None,
    )
    assert result["fragments"][ISIN_B] is None
    assert result["fragments"][ISIN_A]["isin"] == ISIN_A


def test_serialize_compare_bundle_sip_nested_allowlist() -> None:
    """Extra keys inside a sip_* dict are stripped by the nested allowlist."""
    frag = dict(_fragment(ISIN_A))
    frag["sip_5y"] = dict(frag["sip_5y"])
    frag["sip_5y"]["hidden_field"] = "must_be_stripped"

    result = serialize_compare_bundle_response(
        isins=[ISIN_A], fragments={ISIN_A: frag}, as_of=None
    )
    sip = result["fragments"][ISIN_A]["sip_5y"]
    assert "hidden_field" not in sip
    assert "amount" in sip


def test_serialize_compare_bundle_isins_in_output() -> None:
    """The `isins` list is preserved verbatim in the response."""
    result = serialize_compare_bundle_response(
        isins=[ISIN_A, ISIN_B],
        fragments={ISIN_A: _fragment(ISIN_A), ISIN_B: _fragment(ISIN_B)},
        as_of="2026-08-21",
    )
    assert result["isins"] == [ISIN_A, ISIN_B]
    assert result["as_of"] == "2026-08-21"
