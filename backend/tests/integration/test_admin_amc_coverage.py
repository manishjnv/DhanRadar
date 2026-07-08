"""
Integration tests for the Admin AMC data-coverage aggregation endpoint.

  GET /api/v1/admin/amc/coverage

Covers:
  - 404 surface-hiding for anonymous callers.
  - 404 surface-hiding for authenticated non-admins.
  - 200 for admin; response shape (summary/rows/meta).
  - Definitions math on seeded fixtures: covered_count per field, per-AMC
    completeness_pct (equal-weighted average across 7 fields), overall
    completeness_pct (fund-weighted average), NFO count, and accuracy_pct —
    all asserted against real computed numbers from the seeded rows, never a
    mock of the endpoint itself.

Infrastructure: async_client, db_session, patch_redis, monkeypatch.setattr(settings)
— same contract as test_admin_ops.py.
"""

from __future__ import annotations

import datetime
import uuid

import pytest
from sqlalchemy import text

from dhanradar.models.mf import MfFund, MfFundConstituent, MfManualIngestFile

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def _truncate_amc_tables(db_session):
    yield
    await db_session.rollback()
    for tbl in (
        "mf.mf_fund_constituents",
        "mf.fund_manager_history",
        "mf.manual_ingest_files",
        "mf.mf_funds",
    ):
        await db_session.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))
    await db_session.commit()


async def _signup(client, email: str) -> tuple[str, str]:
    from tests.conftest import extract_cookie

    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "AmcCoverage42!"},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["user"]["id"]), extract_cookie(r, "__Host-access")


# ---------------------------------------------------------------------------
# 1. 404 surface-hiding
# ---------------------------------------------------------------------------


async def test_amc_coverage_404_for_anonymous(async_client):
    r = await async_client.get("/api/v1/admin/amc/coverage")
    assert r.status_code == 404, r.text


async def test_amc_coverage_404_for_non_admin(async_client, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "")
    _, access = await _signup(async_client, "nonadmin_amc@example.com")
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/amc/coverage", headers=headers)
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 2. 200 for admin — shape + definitions math on seeded fixtures
# ---------------------------------------------------------------------------


async def test_amc_coverage_200_shape_and_math(async_client, db_session, monkeypatch):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    today = datetime.date.today()

    # One AMC, 2 funds: fund A has aum_crore + a launch within the NFO window;
    # fund B has neither. Neither has constituents/ter/riskometer/benchmark/
    # manager/exit_load — every other field's covered_count must be 0.
    db_session.add(
        MfFund(
            isin="INF900A00001",
            scheme_name="Test AMC Alpha Fund A",
            amc_name="Test AMC Alpha Limited",
            plan_type="direct",
            option_type="growth",
            is_segregated=False,
            aum_crore=100.0,
            launch_date=today,
        )
    )
    db_session.add(
        MfFund(
            isin="INF900A00002",
            scheme_name="Test AMC Alpha Fund B",
            amc_name="Test AMC Alpha Limited",
            plan_type="direct",
            option_type="growth",
            is_segregated=False,
        )
    )
    db_session.add(
        MfFundConstituent(
            isin="INF900A00001",
            constituent_name="Some Holding Ltd.",
            as_of_month=today.replace(day=1),
            constituent_isin="INE000A00000",
            weight_pct=5.0,
            source_amc="TEST",
        )
    )
    for status, n in (("parsed", 3), ("failed", 1)):
        for _ in range(n):
            db_session.add(
                MfManualIngestFile(
                    id=uuid.uuid4(),
                    sha256=uuid.uuid4().hex,
                    original_filename="test.xlsx",
                    channel="upload",
                    status=status,
                    error="zero_rows_upserted_scheme_unresolved" if status == "failed" else None,
                )
            )
    await db_session.commit()

    user_id, access = await _signup(async_client, "admin_amc@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/amc/coverage", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert set(body.keys()) == {"summary", "rows", "meta"}

    summary = body["summary"]
    assert summary["total_amcs"] == 1
    assert summary["total_funds"] == 2
    assert summary["nfo_count"] == 1  # only fund A has launch_date in-window
    assert summary["accuracy_pct"] == 75.0  # 3 parsed / (3 parsed + 1 failed)

    assert len(body["rows"]) == 1
    row = body["rows"][0]
    assert row["amc_name"] == "Test AMC Alpha Limited"
    assert row["short_name"] == "Test"  # no override — falls back to first word
    assert row["fund_count"] == 2

    fields = row["fields"]
    assert fields["constituents"]["covered_count"] == 1  # only fund A
    assert fields["aum"]["covered_count"] == 1  # only fund A
    for f in ("ter", "riskometer", "benchmark", "manager", "exit_load"):
        assert fields[f]["covered_count"] == 0

    # completeness_pct: equal-weighted average of per-field covered-fraction
    # across the 7 fields = ((1/2) + (1/2) + 0 + 0 + 0 + 0 + 0) / 7 * 100.
    expected_completeness = round(100.0 * ((0.5 + 0.5) / 7), 1)
    assert row["completeness_pct"] == expected_completeness

    # Single-AMC universe → overall (fund-weighted) equals the one row's value.
    assert summary["overall_completeness_pct"] == expected_completeness

    meta = body["meta"]
    assert meta["field_order"] == [
        "constituents",
        "aum",
        "ter",
        "riskometer",
        "benchmark",
        "manager",
        "exit_load",
    ]
    assert "nfo_definition" in meta
    assert "accuracy_definition" in meta
    assert "completeness_definition" in meta


# ---------------------------------------------------------------------------
# 3. Plan-variant ISINs of the SAME scheme must count once, not once-per-ISIN
#    (2026-07-08 fix — founder-flagged 2.8% overall completeness turned out to
#    be real denominator inflation: AMFI issues many plan-variant ISINs per
#    scheme, but the enrichment pipeline only writes a field to the ONE ISIN
#    the resolver matched, never to sibling plan variants of the same scheme).
# ---------------------------------------------------------------------------


async def test_amc_coverage_dedupes_plan_variant_isins_of_same_scheme(
    async_client, db_session, monkeypatch
):
    from dhanradar.config import settings
    from tests.conftest import make_auth_headers

    # 3 plan-variant ISINs of the SAME scheme (shared fund_name_short) — only
    # ONE has aum_crore populated, mirroring the real HDFC Liquid Fund case
    # (9 plan-variant ISINs, only 1 with aum_crore). This must count as ONE
    # scheme with AUM covered, not "1 covered out of 3" (33%).
    db_session.add(
        MfFund(
            isin="INF900B00001",
            scheme_name="Test AMC Beta Fund",
            amc_name="Test AMC Beta Limited",
            fund_name_short="Test AMC Beta Fund",
            plan_type="direct",
            option_type="growth",
            is_segregated=False,
            aum_crore=500.0,
        )
    )
    db_session.add(
        MfFund(
            isin="INF900B00002",
            scheme_name="Test AMC Beta Fund - IDCW Daily",
            amc_name="Test AMC Beta Limited",
            fund_name_short="Test AMC Beta Fund",
            plan_type="direct",
            option_type="idcw",
            is_segregated=False,
        )
    )
    db_session.add(
        MfFund(
            isin="INF900B00003",
            scheme_name="Test AMC Beta Fund - Regular Plan",
            amc_name="Test AMC Beta Limited",
            fund_name_short="Test AMC Beta Fund",
            plan_type="regular",
            option_type="growth",
            is_segregated=False,
        )
    )
    await db_session.commit()

    user_id, access = await _signup(async_client, "admin_amc_dedupe@example.com")
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", user_id)
    headers = make_auth_headers(access_token=access)

    r = await async_client.get("/api/v1/admin/amc/coverage", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    row = next(r for r in body["rows"] if r["amc_name"] == "Test AMC Beta Limited")
    # 3 ISINs but ONE scheme (shared fund_name_short) — fund_count must be 1, not 3.
    assert row["fund_count"] == 1
    assert row["fields"]["aum"]["covered_count"] == 1
    # completeness for this AMC: aum covered (1/1), all other 6 fields 0/1.
    assert row["completeness_pct"] == round(100.0 * (1 / 7), 1)
