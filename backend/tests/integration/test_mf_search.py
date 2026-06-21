"""
Integration tests for GET /api/v1/mf/search (fund search endpoint).

Endpoint: GET /api/v1/mf/search?q=<query>[&limit=N]
Public — no auth required.

Infrastructure contract (same as test_dashboard / test_changes):
  - async_client        — httpx.AsyncClient over ASGITransport(app); no lifespan.
  - db_session          — function-scoped AsyncSession.
  - patch_redis         — fakeredis.aioredis.FakeRedis.
  - patch_settings_keys — ephemeral RSA keypair; COOKIE_SECURE=False.

pg_trgm note: create_all (used by db_tables) does NOT run migrations, so the
pg_trgm extension is NOT automatically present.  Each test (via the autouse
fixture _ensure_trgm) executes ``CREATE EXTENSION IF NOT EXISTS pg_trgm`` before
any query that invokes word_similarity.  The GIN indexes are NOT required for
functional correctness (they are a performance optimisation only).

Non-numeric-leak invariant (non-neg #2): assert no numeric score keys appear
in the search response (unified_score, factor_weights, etc.).

Covered:
  1. exact substring match — q=HDFC returns the HDFC fund (isin present, shape ok).
  2. typo tolerance — q=HDFD (one-char typo) still returns the HDFC fund.
  3. short query — q="" and q=H (1 char) → empty list, no DB call triggered.
  4. item shape — keys exactly {isin, scheme_name, amc_name, sebi_category},
     no score/numeric/advisory-verb leak.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from dhanradar.models.mf import MfFund

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Teardown: truncate mf.mf_funds between tests.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _truncate_mf(db_session):
    """Truncate mf.* tables after each test."""
    yield
    await db_session.rollback()
    await db_session.execute(
        text("TRUNCATE TABLE mf.mf_funds RESTART IDENTITY CASCADE")
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# pg_trgm guard: ensure the extension exists in the test DB before queries.
# create_all does not create it (only pgcrypto is created by db_tables).
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _ensure_trgm(db_session):
    """Ensure pg_trgm extension is present in the test DB.

    The migration 0040 creates it in production, but the test DB is built
    with create_all (bypasses migrations).  word_similarity() requires the
    extension; without it the SQL fails with 'function word_similarity(text,
    text) does not exist'.
    """
    await db_session.execute(
        text("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_funds(db_session) -> None:
    """Insert two funds for search tests."""
    db_session.add(
        MfFund(
            isin="INF111A11111",
            scheme_name="HDFC Flexi Cap Fund",
            amc_name="HDFC Mutual Fund",
            sebi_category="Flexi Cap",
        )
    )
    db_session.add(
        MfFund(
            isin="INF222A22222",
            scheme_name="SBI Bluechip Fund",
            amc_name="SBI Mutual Fund",
            sebi_category="Large Cap",
        )
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# 1. Exact substring match
# ---------------------------------------------------------------------------


async def test_search_exact_substring(async_client, db_session, patch_redis):
    """q=HDFC returns the HDFC fund; isin present, shape correct."""
    await _seed_funds(db_session)

    resp = await async_client.get("/api/v1/mf/search", params={"q": "HDFC"})
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    isins = [item["isin"] for item in data]
    assert "INF111A11111" in isins

    # Verify shape of the matching item.
    item = next(i for i in data if i["isin"] == "INF111A11111")
    assert item["scheme_name"] == "HDFC Flexi Cap Fund"
    assert item["amc_name"] == "HDFC Mutual Fund"
    assert item["sebi_category"] == "Flexi Cap"


# ---------------------------------------------------------------------------
# 2. Typo tolerance (word_similarity)
# ---------------------------------------------------------------------------


async def test_search_typo_tolerance(async_client, db_session, patch_redis):
    """q=HDFD (one-char typo on HDFC) still returns the HDFC fund."""
    await _seed_funds(db_session)

    resp = await async_client.get("/api/v1/mf/search", params={"q": "HDFD"})
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, list)
    # The HDFC fund should surface via word_similarity >= 0.3 on the typo.
    isins = [item["isin"] for item in data]
    assert "INF111A11111" in isins


# ---------------------------------------------------------------------------
# 3. Short queries — empty list, no DB call
# ---------------------------------------------------------------------------


async def test_search_empty_query(async_client, db_session, patch_redis):
    """q="" → 200 with empty list."""
    await _seed_funds(db_session)

    resp = await async_client.get("/api/v1/mf/search", params={"q": ""})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_search_single_char_query(async_client, db_session, patch_redis):
    """q=H (1 char) → 200 with empty list (min length guard)."""
    await _seed_funds(db_session)

    resp = await async_client.get("/api/v1/mf/search", params={"q": "H"})
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# 4. Item shape — no numeric / score / advisory-verb leak (non-neg #2)
# ---------------------------------------------------------------------------


async def test_search_item_shape_no_numeric_leak(async_client, db_session, patch_redis):
    """Response items have exactly {isin, scheme_name, amc_name, sebi_category}.

    No unified_score, factor weights, confidence floats, or advisory verbs
    (buy/sell/hold/strong_buy/caution/avoid) in the response body.
    """
    await _seed_funds(db_session)

    resp = await async_client.get("/api/v1/mf/search", params={"q": "Flexi"})
    assert resp.status_code == 200

    data = resp.json()
    assert len(data) >= 1

    expected_keys = {"isin", "scheme_name", "amc_name", "sebi_category"}
    for item in data:
        assert set(item.keys()) == expected_keys, (
            f"Unexpected keys in response item: {set(item.keys()) - expected_keys}"
        )

    # Non-neg #2: no numeric score fields in raw body.
    raw = resp.text
    forbidden = ["unified_score", "factor_weight", "confidence_float"]
    for f in forbidden:
        assert f not in raw, f"Forbidden field '{f}' leaked into search response"

    # Advisory-verb check (SEBI educational boundary).
    advisory_verbs = ["strong_buy", "buy", "hold", "caution", "avoid"]
    for verb in advisory_verbs:
        assert verb not in raw, f"Advisory verb '{verb}' leaked into search response"
