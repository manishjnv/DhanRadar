"""A3 — the single serialization boundary (§10 layer 8): #2 numeric strip + visibility/tier gating +
the data envelope. COMPLIANCE-CRITICAL — these fixtures RED THE BUILD if a raw DhanRadar score reaches
a client, if a gated concept is served, or if a tier-gated concept leaks to a free user.

Pure tests (no PG) prove the boundary math + the registry-drift guard. The PG test proves the pilot
(`holdings.list`) end-to-end through the boundary under RLS via rls_async_client.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import text

from dhanradar.mf import serialization
from dhanradar.mf.concepts import UnknownConcept
from dhanradar.mf.serialization import (
    FORBIDDEN_SCORE_KEYS,
    RequestCtx,
    is_tier_withheld,
    serialize_concept,
)
from dhanradar.models.auth import User

pytestmark = pytest.mark.integration


def _all_keys(value) -> set[str]:
    """Every dict key anywhere in a nested structure (recursive) — to prove no forbidden key survives."""
    out: set[str] = set()
    if isinstance(value, dict):
        out |= set(value.keys())
        for v in value.values():
            out |= _all_keys(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            out |= _all_keys(v)
    return out


def _all_values(value):
    """Every leaf value anywhere in a nested structure (recursive) — to prove the raw score value never
    appears even under a renamed key. Structural, unlike a substring check on the raw JSON which a
    random UUID can trip (a hex UUID can contain the score's digits)."""
    if isinstance(value, dict):
        for v in value.values():
            yield from _all_values(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _all_values(v)
    else:
        yield value


# --- I1: #2 numeric strip (the headline) ----------------------------------------------------------


def test_i1_numeric_strip_removes_raw_score_keeps_label():
    """A payload carrying a raw DhanRadar score/weights/fair-value → serialize → NO forbidden key
    anywhere; the educational label/band and the user's OWN numbers (units/invested) survive.
    Reintroducing a leak (e.g. removing a key from FORBIDDEN_SCORE_KEYS) reds this test."""
    payload = {
        "holdings": [
            {
                "isin": "INF1",
                "units": 10.0,
                "invested_amount": 1000.0,
                "unified_score": 87,  # raw composite — MUST be stripped
                "factor_weights": {"momentum": 0.4},  # scoring internal — stripped
                "fair_value": 123.45,  # fair-value — stripped
                "label": "on_track",  # educational — kept
                "confidence_band": "high",  # band — kept
            }
        ]
    }
    env = serialize_concept("holdings.list", payload, RequestCtx(tier="free"))
    blob = json.dumps(env)

    leaked = FORBIDDEN_SCORE_KEYS & _all_keys(env)
    assert not leaked, f"#2 LEAK: {sorted(leaked)} reached the serialized envelope"
    assert "87" not in blob and "0.4" not in blob and "123.45" not in blob
    # the educational + user-own values survive
    h = env["data"]["holdings"][0]
    assert h["label"] == "on_track" and h["confidence_band"] == "high"
    assert h["units"] == 10.0 and h["invested_amount"] == 1000.0
    assert env["status"] == "present"


def test_i1_strip_is_recursive_and_present_in_nested():
    """The strip is recursive — a forbidden key buried deep (inside an allowlisted top-level field) is
    still removed. Nested under `holdings` (B87-allowlisted) rather than a synthetic top-level key,
    since the B87 allowlist below now filters top-level keys first."""
    env = serialize_concept(
        "holdings.list",
        {"holdings": {"b": [{"c": {"unified_score": 99, "ok": 1}}]}},
        RequestCtx(tier="free"),
    )
    assert "unified_score" not in _all_keys(env)
    assert env["data"]["holdings"]["b"][0]["c"] == {"ok": 1}


# --- I2: gated → withheld -------------------------------------------------------------------------


def test_i2_gated_concept_withheld():
    """A gated concept (portfolio.score_raw, gated-never) → withheld, reason 'gated', data null, and
    the underlying number absent. Money cannot unlock it (gate_enabled stays False)."""
    env = serialize_concept("portfolio.score_raw", {"score": 87}, RequestCtx(tier="plus"))
    assert env["status"] == "withheld"
    assert env["meta"]["reason"] == "gated"
    assert env["data"] is None
    assert "87" not in json.dumps(env)
    assert env["meta"]["gate"] == {"flag": "portfolio_score_raw", "enabled": False}


# --- TIER: plus concept gated to free, served to plus ---------------------------------------------


def test_tier_withheld_for_free_user():
    env = serialize_concept(
        "portfolio.risk_advanced", {"sharpe_ratio": 1.2}, RequestCtx(tier="free")
    )
    assert env["status"] == "withheld" and env["meta"]["reason"] == "tier" and env["data"] is None
    assert is_tier_withheld(env)  # the route raises HTTP 402 on this


def test_tier_present_for_paid_user():
    # "pro" is the real paid tier (the registry's access_tier "plus" maps to Pro+).
    env = serialize_concept(
        "portfolio.risk_advanced", {"sharpe_ratio": 1.2}, RequestCtx(tier="pro")
    )
    assert (
        env["status"] == "present"
        and env["data"] == {"sharpe_ratio": 1.2}
        and not is_tier_withheld(env)
    )


# --- REFUSED + fail-closed + meta tags ------------------------------------------------------------


def test_refused_runtime_compliance():
    env = serialize_concept(
        "fund.label", {"label": "x"}, RequestCtx(tier="free", refused="insufficient_data")
    )
    assert (
        env["status"] == "withheld" and env["meta"]["reason"] == "refused" and env["data"] is None
    )


def test_unknown_concept_fail_closed():
    """An un-registered concept id raises (fail-closed) — never served un-tagged/un-gated."""
    with pytest.raises(UnknownConcept):
        serialize_concept("does.not.exist", {"x": 1}, RequestCtx())


def test_non_plain_input_fails_closed():
    """A non-plain-JSON value (an object the scrub can't see inside) is REFUSED, not silently served —
    fail-closed (review finding 2): a score hidden in a Pydantic/ORM object cannot leak."""

    class _Obj:
        unified_score = 87

    with pytest.raises(RuntimeError):
        serialize_concept("holdings.list", {"x": _Obj()}, RequestCtx(tier="free"))


def test_meta_tags_inherited_from_registry():
    """A present envelope carries the registry-derived governance axes — the contract the frontend reads."""
    env = serialize_concept(
        "holdings.list", {"holdings": []}, RequestCtx(tier="free"), source="cas"
    )
    m = env["meta"]
    assert (m["visibility_class"], m["data_class"], m["access_tier"], m["content_class"]) == (
        "public",
        "user-personal",
        "free",
        "PERSONAL",
    )
    assert m["source"] == "cas" and m["gate"] is None and m["reason"] is None


# --- registry drift: backend copy == frontend concepts.json (the single source) -------------------


def test_backend_registry_matches_concepts_json():
    """The committed backend registry (generated) must carry the SAME governance axes as
    frontend/src/data/concepts.json — one source of truth. `npm run check:concepts` (CI) also guards it;
    this reds the BACKEND suite too if a stale copy slips in."""
    backend = Path(__file__).resolve().parents[2]
    repo = backend.parent
    src = json.loads(
        (repo / "frontend" / "src" / "data" / "concepts.json").read_text(encoding="utf-8")
    )["concepts"]
    reg = json.loads(
        (backend / "dhanradar" / "mf" / "concepts_registry.json").read_text(encoding="utf-8")
    )["concepts"]
    axes = ("visibility_class", "data_class", "access_tier", "content_class")
    expected = {
        c["concept"]: {
            **{k: c[k] for k in axes},
            "gate_flag": c.get("gate_flag"),
            "status": c["status"],
        }
        for c in src
    }
    got = {
        cid: {**{k: row[k] for k in axes}, "gate_flag": row["gate_flag"], "status": row["status"]}
        for cid, row in reg.items()
    }
    assert got == expected, f"registry drift: {set(expected) ^ set(got) or 'axis mismatch'}"


# --- B87: per-concept field ALLOWLIST (the structural #2 guarantee) --------------------------------


def test_b87_unlisted_field_is_dropped():
    """Contract (a): a top-level field NOT in the concept's ALLOWED_FIELDS entry is silently dropped —
    even though it isn't a FORBIDDEN_SCORE_KEYS name (the guarantee the denylist alone can't give; a
    score under a NOVEL key like `rating` would previously have slipped through untouched)."""
    env = serialize_concept(
        "holdings.list",
        {"holdings": [], "rating": 87, "some_new_unlisted_field": "leak"},
        RequestCtx(tier="free"),
    )
    assert env["data"] == {"holdings": []}
    assert "rating" not in env["data"] and "some_new_unlisted_field" not in env["data"]


def test_b87_forbidden_field_blocked_even_if_allowlisted(monkeypatch):
    """Contract (b): even if a concept's ALLOWED_FIELDS entry were mistakenly widened to include a
    forbidden score key, the FORBIDDEN_SCORE_KEYS scrub (the second tripwire layer, contract item 2)
    still strips it before the allowlist ever runs — allowlist membership alone can never let a raw
    score through."""
    monkeypatch.setitem(
        serialization.ALLOWED_FIELDS,
        "holdings.list",
        serialization.ALLOWED_FIELDS["holdings.list"] | {"unified_score"},
    )
    env = serialize_concept(
        "holdings.list", {"holdings": [], "unified_score": 87}, RequestCtx(tier="free")
    )
    assert "unified_score" not in _all_keys(env)
    assert "87" not in json.dumps(env)


def test_band_dict_leaves_must_be_band_words():
    """W2-A adversarial-review condition: a numeric (or any non-band value) inside a band-dict
    field (`factors`/`confidence_factors`) must fail closed at the boundary, never reach a client —
    the top-level allowlist and the name-based denylist cannot see inside these nested dicts."""
    with pytest.raises(RuntimeError, match="band-dict"):
        serialize_concept(
            "fund.factors",
            {"factors": {"consistency": 0.83}, "confidence_band": "high", "as_of": "2026-07-05"},
            RequestCtx(tier="free"),
        )
    # Happy path: real band words pass untouched.
    env = serialize_concept(
        "fund.factors",
        {
            "factors": {"consistency": "high", "recency": "low"},
            "confidence_band": "medium",
            "as_of": "2026-07-05",
        },
        RequestCtx(tier="free"),
    )
    assert env["status"] == "present"
    assert env["data"]["factors"] == {"consistency": "high", "recency": "low"}
    # Null factors (insufficient_data funds) are fine.
    env2 = serialize_concept(
        "fund.factors",
        {"factors": None, "confidence_band": None, "as_of": None},
        RequestCtx(tier="free"),
    )
    assert env2["data"]["factors"] is None


def test_b87_missing_allowlist_fails_closed():
    """A concept with no `ALLOWED_FIELDS` entry raises `MissingConceptAllowlist` naming the fix, rather
    than serving an un-allowlisted payload. `portfolio.health` is registered (build status) but not yet
    wired through this boundary, so it has no entry yet — exactly the case this guards."""
    with pytest.raises(serialization.MissingConceptAllowlist, match="portfolio.health"):
        serialize_concept("portfolio.health", {"band": "ok"}, RequestCtx(tier="free"))


def test_b87_parity_every_live_concept_allowlist_matches_real_payload():
    """Contract (c) — before/after parity: for every concept actually served through this boundary
    today (`insights/router.py`), the ALLOWED_FIELDS entry equals EXACTLY the fixed top-level key set
    each real payload builder in `mf/portfolio_read.py` emits — zero behavior change from B87."""
    from dhanradar.mf.portfolio_read import (
        EnrichedHolding,
        PortfolioReadModel,
        PortfolioRisk,
        allocation_payload,
        concentration_payload,
        diversification_payload,
        holdings_payload,
        risk_advanced_payload,
        risk_payload,
        summary_payload,
        valuation_series_payload,
    )
    from dhanradar.mf.valuation import ValuationPoint

    holding = EnrichedHolding(
        isin="INF1",
        scheme_name="X Fund",
        category="Flexi Cap Fund",
        folio_number="F1",
        units=10.0,
        invested=1000.0,
        current_nav=120.0,
        current_value=1200.0,
        label="on_track",
        confidence_band="high",
        as_of="2026-03-31",
    )
    rm = PortfolioReadModel(
        holdings=[holding],
        total_invested=1000.0,
        total_value=1200.0,
        xirr_pct=None,
        as_of="2026-03-31",
    )
    risk = PortfolioRisk(
        volatility_pct=15.0,
        max_drawdown_pct=None,
        sharpe_ratio=None,
        sortino_ratio=None,
        rolling_1y_avg_pct=12.0,
        rolling_1y_pct_positive=70.0,
        fund_count=3,
        funds_with_metrics=3,
        as_of="2026-03-31",
    )
    point = ValuationPoint(
        valuation_date=date(2026, 3, 31), total_value=1200.0, total_invested=1000.0
    )

    cases = [
        ("holdings.list", holdings_payload(rm, "pid-1"), "free"),
        ("portfolio.summary", summary_payload(rm, "pid-1"), "free"),
        ("portfolio.risk", risk_payload(risk, "pid-1"), "free"),
        ("portfolio.risk_advanced", risk_advanced_payload(risk, "pid-1"), "pro"),
        ("portfolio.allocation", allocation_payload(rm, "pid-1"), "free"),
        ("portfolio.concentration", concentration_payload(rm, "pid-1"), "free"),
        ("portfolio.diversification", diversification_payload(rm, "pid-1"), "free"),
        ("portfolio.valuation_series", valuation_series_payload([point], "pid-1"), "free"),
    ]
    for concept_id, payload, tier in cases:
        # (i) the declared allowlist is EXACTLY the real builder's fixed key set — no drift either way.
        assert serialization.ALLOWED_FIELDS[concept_id] == set(payload.keys()), concept_id
        # (ii) round-tripping through the boundary serves every field unchanged — zero behavior change.
        env = serialize_concept(concept_id, dict(payload), RequestCtx(tier=tier))
        assert env["status"] == "present", concept_id
        assert env["data"] == payload, concept_id


# --- PG: the pilot endpoint end-to-end through the boundary, under RLS ------------------------------


async def _seed_user(db_session, email: str) -> str:
    # Block 0.12: these portfolio-analytics routes are now gated on mf_analytics consent;
    # grant it by default so pre-existing fixtures keep exercising the ROUTE logic under
    # test, not the (separately, unit-tested) consent gate itself.
    u = User(email=email, dpdp_consents={"mf_analytics": True})
    db_session.add(u)
    await db_session.flush()
    uid = str(u.id)
    await db_session.commit()
    return uid


async def test_holdings_pilot_endpoint_through_boundary(db_session, rls_async_client):
    """`GET /portfolio/{id}/holdings` (the A3 pilot) served as the owner under RLS: the response is the
    envelope with the educational label/band — and the raw unified_score (which EXISTS in the DB) NEVER
    appears. Proves RLS + envelope + #2 strip together on a live path."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    uid = await _seed_user(db_session, "a3-pilot@test.dev")
    pid = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'A3') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()
    await db_session.execute(
        text(
            "INSERT INTO mf.mf_user_holdings (user_id, portfolio_id, isin, folio_number, units,"
            " invested_amount, source, as_of_date) VALUES (:u, :p, 'INF200K01VT2', '777', 10.5,"
            " 1000.00, 'cas', :d)"
        ),
        {"u": uid, "p": str(pid), "d": date(2026, 3, 31)},
    )
    # A score row WITH a raw unified_score=87 — it must never reach the response.
    await db_session.execute(
        text(
            "INSERT INTO mf.user_fund_scores (user_id, portfolio_id, isin, unified_score,"
            " confidence_band, verb_label) VALUES (:u, :p, 'INF200K01VT2', 87, 'high', 'on_track')"
        ),
        {"u": uid, "p": str(pid)},
    )
    await db_session.commit()

    token, _ = create_access_token(uid)
    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid}/holdings", headers=make_auth_headers(access_token=token)
    )
    assert r.status_code == 200, f"{r.status_code}: {r.text}"
    env = r.json()
    # envelope shape + registry tags
    assert env["status"] == "present"
    assert (
        env["meta"]["visibility_class"] == "public" and env["meta"]["content_class"] == "PERSONAL"
    )
    h = env["data"]["holdings"][0]
    # educational label/band + the user's own numbers present
    assert h["label"] == "on_track" and h["confidence_band"] == "high"
    assert h["units"] == 10.5 and h["invested_amount"] == 1000.0
    # #2: the raw score never appears — neither as a key nor as a numeric value anywhere. Structural
    # check, NOT a substring on the body: a random portfolio_id UUID can contain the score's digits.
    assert "unified_score" not in _all_keys(env)
    numbers = [
        v for v in _all_values(env) if isinstance(v, (int, float)) and not isinstance(v, bool)
    ]
    assert 87 not in numbers, "raw unified_score (87) leaked as a value (#2 violation)"


async def test_holdings_pilot_rejects_other_user(db_session, rls_async_client):
    """Another user's portfolio → 404 (IDOR + RLS); anonymous → 401."""
    from dhanradar.auth.security import create_access_token
    from tests.conftest import make_auth_headers

    a = await _seed_user(db_session, "a3-a@test.dev")
    b = await _seed_user(db_session, "a3-b@test.dev")
    pid_a = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'A') RETURNING id"),
            {"u": a},
        )
    ).scalar_one()
    await db_session.commit()

    # B asks for A's portfolio → 404
    token_b, _ = create_access_token(b)
    r = await rls_async_client.get(
        f"/api/v1/portfolio/{pid_a}/holdings", headers=make_auth_headers(access_token=token_b)
    )
    assert r.status_code == 404

    # anonymous → 401
    r2 = await rls_async_client.get(f"/api/v1/portfolio/{pid_a}/holdings")
    assert r2.status_code == 401
