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
    """The strip is recursive — a forbidden key buried deep is still removed."""
    env = serialize_concept(
        "holdings.list",
        {"a": {"b": [{"c": {"unified_score": 99, "ok": 1}}]}},
        RequestCtx(tier="free"),
    )
    assert "unified_score" not in _all_keys(env)
    assert env["data"]["a"]["b"][0]["c"] == {"ok": 1}


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
    env = serialize_concept("portfolio.risk_advanced", {"sharpe": 1.2}, RequestCtx(tier="free"))
    assert env["status"] == "withheld" and env["meta"]["reason"] == "tier" and env["data"] is None
    assert is_tier_withheld(env)  # the route raises HTTP 402 on this


def test_tier_present_for_paid_user():
    # "pro" is the real paid tier (the registry's access_tier "plus" maps to Pro+).
    env = serialize_concept("portfolio.risk_advanced", {"sharpe": 1.2}, RequestCtx(tier="pro"))
    assert env["status"] == "present" and env["data"] == {"sharpe": 1.2} and not is_tier_withheld(env)


# --- REFUSED + fail-closed + meta tags ------------------------------------------------------------


def test_refused_runtime_compliance():
    env = serialize_concept("fund.label", {"label": "x"}, RequestCtx(tier="free", refused="insufficient_data"))
    assert env["status"] == "withheld" and env["meta"]["reason"] == "refused" and env["data"] is None


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
    env = serialize_concept("holdings.list", {"holdings": []}, RequestCtx(tier="free"), source="cas")
    m = env["meta"]
    assert (m["visibility_class"], m["data_class"], m["access_tier"], m["content_class"]) == (
        "public", "user-personal", "free", "PERSONAL",
    )
    assert m["source"] == "cas" and m["gate"] is None and m["reason"] is None


# --- registry drift: backend copy == frontend concepts.json (the single source) -------------------


def test_backend_registry_matches_concepts_json():
    """The committed backend registry (generated) must carry the SAME governance axes as
    frontend/src/data/concepts.json — one source of truth. `npm run check:concepts` (CI) also guards it;
    this reds the BACKEND suite too if a stale copy slips in."""
    backend = Path(__file__).resolve().parents[2]
    repo = backend.parent
    src = json.loads((repo / "frontend" / "src" / "data" / "concepts.json").read_text(encoding="utf-8"))["concepts"]
    reg = json.loads((backend / "dhanradar" / "mf" / "concepts_registry.json").read_text(encoding="utf-8"))["concepts"]
    axes = ("visibility_class", "data_class", "access_tier", "content_class")
    expected = {
        c["concept"]: {**{k: c[k] for k in axes}, "gate_flag": c.get("gate_flag"), "status": c["status"]}
        for c in src
    }
    got = {
        cid: {**{k: row[k] for k in axes}, "gate_flag": row["gate_flag"], "status": row["status"]}
        for cid, row in reg.items()
    }
    assert got == expected, f"registry drift: {set(expected) ^ set(got) or 'axis mismatch'}"


# --- PG: the pilot endpoint end-to-end through the boundary, under RLS ------------------------------


async def _seed_user(db_session, email: str) -> str:
    u = User(email=email)
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
    body = r.text
    env = r.json()
    # envelope shape + registry tags
    assert env["status"] == "present"
    assert env["meta"]["visibility_class"] == "public" and env["meta"]["content_class"] == "PERSONAL"
    h = env["data"]["holdings"][0]
    # educational label/band + the user's own numbers present
    assert h["label"] == "on_track" and h["confidence_band"] == "high"
    assert h["units"] == 10.5 and h["invested_amount"] == 1000.0
    # #2: the raw score never appears, anywhere
    assert "unified_score" not in _all_keys(env)
    assert "87" not in body, "raw unified_score leaked into the holdings response (#2 violation)"


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
