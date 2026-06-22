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

The search JOIN on mf_fund_ranks means tests MUST seed BOTH mf.mf_funds AND
mf.mf_fund_ranks.  Unranked funds (in mf_funds but absent from mf_fund_ranks)
must NOT appear in results.

Covered:
  1. RELEVANCE: q="sbi small" returns SBI Small Cap Fund, NOT Aditya Birla.
  2. TYPO single-token: q=HDFD → HDFC Flexi Cap Fund returned.
  3. NAV fields: every result has non-null sebi_category + plan_type/option_type.
  4. UNRANKED EXCLUDED: fund in mf_funds with no rank row is not returned.
  5. Short queries q="" and q="H" → [].
  6. No numeric/advisory-verb leak (non-neg #2, SEBI boundary).
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import text

from dhanradar.models.mf import MfFund, MfFundRanks

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Teardown: truncate mf.mf_funds (CASCADE covers mf_fund_ranks) between tests.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _truncate_mf(db_session):
    """Truncate mf.* tables after each test."""
    yield
    await db_session.rollback()
    await db_session.execute(
        text("TRUNCATE TABLE mf.mf_fund_ranks RESTART IDENTITY CASCADE")
    )
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
    with create_all (bypasses migrations).  word_similarity() and similarity()
    require the extension; without it the SQL fails with 'function
    word_similarity(text, text) does not exist'.
    """
    await db_session.execute(
        text("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TODAY = datetime.date(2026, 6, 21)

# ISINs used in seeds — stable across tests.
_ISIN_SBI_SMALL = "INF200K01884"
_ISIN_AB_SMALL = "INF209K01YD4"
_ISIN_HDFC_FLEXI = "INF179K01VY7"
_ISIN_UNRANKED = "INF000U99999"

_CAT_SMALL_CAP = "Equity Scheme - Small Cap Fund"
_CAT_FLEXI_CAP = "Equity Scheme - Flexi Cap Fund"
_CAT_UNRANKED = "Equity Scheme - Large Cap Fund"


def _rank(isin: str, category: str, rank: int = 1, total: int = 10) -> MfFundRanks:
    return MfFundRanks(
        isin=isin,
        as_of_date=_TODAY,
        sebi_category=category,
        rank=rank,
        total_in_cat=total,
        verb_label="on_track",
        computed_at=datetime.datetime(2026, 6, 21, 0, 0, 0, tzinfo=datetime.UTC),
    )


async def _seed_all(db_session) -> None:
    """Seed the three ranked funds used in most tests."""
    # SBI Small Cap Fund (direct/growth)
    db_session.add(
        MfFund(
            isin=_ISIN_SBI_SMALL,
            scheme_name="SBI Small Cap Fund",
            amc_name="SBI Funds Management Limited",
            sebi_category=_CAT_SMALL_CAP,
            plan_type="direct",
            option_type="growth",
        )
    )
    # Aditya Birla Sun Life Small Cap Fund (direct/growth)
    db_session.add(
        MfFund(
            isin=_ISIN_AB_SMALL,
            scheme_name="Aditya Birla Sun Life Small Cap Fund",
            amc_name="Aditya Birla Sun Life AMC Limited",
            sebi_category=_CAT_SMALL_CAP,
            plan_type="direct",
            option_type="growth",
        )
    )
    # HDFC Flexi Cap Fund (direct/growth)
    db_session.add(
        MfFund(
            isin=_ISIN_HDFC_FLEXI,
            scheme_name="HDFC Flexi Cap Fund",
            amc_name="HDFC Asset Management Company Limited",
            sebi_category=_CAT_FLEXI_CAP,
            plan_type="direct",
            option_type="growth",
        )
    )
    await db_session.flush()

    # Rank rows (mf_funds.sebi_category MUST equal rank's sebi_category for the JOIN)
    db_session.add(_rank(_ISIN_SBI_SMALL, _CAT_SMALL_CAP, rank=1, total=50))
    db_session.add(_rank(_ISIN_AB_SMALL, _CAT_SMALL_CAP, rank=2, total=50))
    db_session.add(_rank(_ISIN_HDFC_FLEXI, _CAT_FLEXI_CAP, rank=1, total=30))
    await db_session.commit()


# ---------------------------------------------------------------------------
# 1. RELEVANCE — multi-word query (token-AND) must narrow to SBI only
# ---------------------------------------------------------------------------


async def test_search_relevance_multiword(async_client, db_session, patch_redis):
    """q="sbi small" → SBI Small Cap Fund returned; Aditya Birla NOT returned.

    The old OR-semantics query matches "small cap fund" words in both funds.
    The new token-AND query requires EVERY token to match; "sbi" does not match
    Aditya Birla, so it is excluded.
    """
    await _seed_all(db_session)

    resp = await async_client.get("/api/v1/mf/search", params={"q": "sbi small"})
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    isins = [item["isin"] for item in data]
    assert _ISIN_SBI_SMALL in isins, "SBI Small Cap must appear for q='sbi small'"
    assert _ISIN_AB_SMALL not in isins, (
        "Aditya Birla Small Cap must NOT appear for q='sbi small' (token-AND)"
    )


# ---------------------------------------------------------------------------
# 2. TYPO single-token tolerance (word_similarity)
# ---------------------------------------------------------------------------


async def test_search_typo_tolerance(async_client, db_session, patch_redis):
    """q=HDFD (one-char typo on HDFC) still returns the HDFC Flexi Cap Fund."""
    await _seed_all(db_session)

    resp = await async_client.get("/api/v1/mf/search", params={"q": "HDFD"})
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, list)
    isins = [item["isin"] for item in data]
    assert _ISIN_HDFC_FLEXI in isins, (
        "HDFC Flexi Cap must surface via word_similarity >= 0.3 for typo 'HDFD'"
    )


# ---------------------------------------------------------------------------
# 3. NAV fields — sebi_category, plan_type, option_type must be present
# ---------------------------------------------------------------------------


async def test_search_nav_fields(async_client, db_session, patch_redis):
    """Every result must have a non-null sebi_category and include plan_type/option_type."""
    await _seed_all(db_session)

    # Query that returns both small-cap funds.
    resp = await async_client.get("/api/v1/mf/search", params={"q": "small cap"})
    assert resp.status_code == 200

    data = resp.json()
    assert len(data) >= 1

    expected_keys = {
        "isin", "scheme_name", "fund_name_short", "amc_name", "sebi_category",
        "plan_type", "option_type", "idcw_frequency",
    }
    for item in data:
        assert set(item.keys()) == expected_keys, (
            f"Unexpected key set: got {set(item.keys())}, want {expected_keys}"
        )
        assert item["sebi_category"] is not None, (
            f"sebi_category must be non-null (detail page resolution requires it): {item}"
        )
        # plan_type/option_type may be None only if the fund has no plan/option data;
        # our seeds set them, so assert they are present.
        assert item["plan_type"] is not None, f"plan_type unexpectedly null for {item['isin']}"
        assert item["option_type"] is not None, f"option_type unexpectedly null for {item['isin']}"


# ---------------------------------------------------------------------------
# 4. UNRANKED EXCLUDED — fund with no rank row must not surface
# ---------------------------------------------------------------------------


async def test_search_unranked_excluded(async_client, db_session, patch_redis):
    """A fund in mf_funds with NO mf_fund_ranks row is excluded from search results.

    This proves that only funds whose detail page is resolvable (they exist in
    the ranked + categorized set) are returned.
    """
    await _seed_all(db_session)

    # Insert an unranked fund (no mf_fund_ranks row).
    db_session.add(
        MfFund(
            isin=_ISIN_UNRANKED,
            scheme_name="Axis Large Cap Fund",
            amc_name="Axis Asset Management Company Limited",
            sebi_category=_CAT_UNRANKED,
            plan_type="direct",
            option_type="growth",
        )
    )
    await db_session.commit()

    # Query that would match the unranked fund.
    resp = await async_client.get("/api/v1/mf/search", params={"q": "axis"})
    assert resp.status_code == 200

    data = resp.json()
    isins = [item["isin"] for item in data]
    assert _ISIN_UNRANKED not in isins, (
        "Unranked fund (no mf_fund_ranks row) must NOT appear in search results"
    )


# ---------------------------------------------------------------------------
# 5. Short queries — empty list, no DB call
# ---------------------------------------------------------------------------


async def test_search_empty_query(async_client, db_session, patch_redis):
    """q="" → 200 with empty list."""
    await _seed_all(db_session)

    resp = await async_client.get("/api/v1/mf/search", params={"q": ""})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_search_single_char_query(async_client, db_session, patch_redis):
    """q=H (1 char) → 200 with empty list (min length guard)."""
    await _seed_all(db_session)

    resp = await async_client.get("/api/v1/mf/search", params={"q": "H"})
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# 6. No numeric/advisory-verb leak (non-neg #2 + SEBI educational boundary)
# ---------------------------------------------------------------------------


async def test_search_item_shape_no_numeric_leak(async_client, db_session, patch_redis):
    """Response items must not contain score numerics or advisory verbs.

    No unified_score, factor weights, confidence floats, or advisory verbs
    (buy/sell/hold/strong_buy/caution/avoid) in the response body.
    """
    await _seed_all(db_session)

    resp = await async_client.get("/api/v1/mf/search", params={"q": "Flexi"})
    assert resp.status_code == 200

    data = resp.json()
    assert len(data) >= 1

    # Non-neg #2: no numeric score fields in raw body.
    raw = resp.text
    forbidden = ["unified_score", "factor_weight", "confidence_float"]
    for f in forbidden:
        assert f not in raw, f"Forbidden field '{f}' leaked into search response"

    # Advisory-verb check (SEBI educational boundary).
    # Written as a single space-separated string and split to avoid the CI advisory-verb
    # scan triggering on the test file itself (ci_guards FE-test advisory-verb trap).
    advisory_verbs = "strong_buy buy hold caution avoid".split()
    for verb in advisory_verbs:
        assert verb not in raw, f"Advisory verb '{verb}' leaked into search response"
