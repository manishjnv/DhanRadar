"""
Unit tests for AMFI NAV ingestion pipeline — no DB, no network, no Celery worker.

Covers:
  - parse_navall_with_category: category header tracking, AMC-name no-reset,
    schemes before any header get category=None.
  - fetch_navall_rows_with_category: injected fake client, verifies URL + category.
  - _navrows_to_nav_upserts: growth-ISIN preferred, reinvest fallback,
    no-ISIN row skipped.
  - _navrows_to_fund_upserts: category carried, scheme_name/amfi_code set,
    no-ISIN row skipped.

asyncio_mode = "auto" (pyproject.toml) — async test functions need no decorator.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from dhanradar.market_data.amfi import (
    NavRow,
    fetch_navall_rows_with_category,
    parse_navall_with_category,
)
from dhanradar.market_data.exceptions import ProviderError
from dhanradar.tasks.mf import _navrows_to_fund_upserts, _navrows_to_nav_upserts

# ---------------------------------------------------------------------------
# Golden fixture — two category headers + schemes + AMC-name lines
# ---------------------------------------------------------------------------

CATEGORY_FIXTURE = """\
Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date

Open Ended Schemes(Equity Scheme - Large Cap Fund)

HDFC Mutual Fund

100016;INF179K01BB4;-;HDFC Top 100 Fund - Growth;1052.34;01-Jun-2026
100017;INF179K01CC5;INF179K01DD6;HDFC Large Cap Fund - Growth;987.65;01-Jun-2026

Open Ended Schemes ( Debt Scheme - Banking and PSU Fund )

Taurus Mutual Fund

139619;INF090I01239;INF090I01247;Taurus Short Term Income Fund - Growth;42.56;02-Jun-2026
140020;INF090I01255;-;Taurus Ultra Short Term Bond Fund - Growth;15.12;02-Jun-2026
"""

# A fixture where some rows appear BEFORE any category header.
NO_HEADER_FIRST_FIXTURE = """\
Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date

Some AMC With No Category

999001;INF001A01AA1;-;Orphan Fund - Growth;10.00;01-Jun-2026

Open Ended Schemes(Equity Scheme - Large Cap Fund)

999002;INF002A01BB2;INF002A01CC3;Keyed Fund - Growth;20.00;01-Jun-2026
"""


# ===========================================================================
# parse_navall_with_category
# ===========================================================================

class TestParseNavallWithCategory:
    def test_returns_correct_row_count(self):
        rows = parse_navall_with_category(CATEGORY_FIXTURE)
        assert len(rows) == 4

    def test_first_category_header_extracted(self):
        rows = parse_navall_with_category(CATEGORY_FIXTURE)
        assert rows[0].category == "Equity Scheme - Large Cap Fund"
        assert rows[1].category == "Equity Scheme - Large Cap Fund"

    def test_second_category_header_extracted_with_spaces(self):
        """Header "Open Ended Schemes ( Debt Scheme - Banking and PSU Fund )"
        — extra spaces inside parens must be stripped."""
        rows = parse_navall_with_category(CATEGORY_FIXTURE)
        assert rows[2].category == "Debt Scheme - Banking and PSU Fund"
        assert rows[3].category == "Debt Scheme - Banking and PSU Fund"

    def test_amc_name_line_does_not_reset_category(self):
        """AMC-name lines ("HDFC Mutual Fund", "Taurus Mutual Fund") have no
        parentheses and must NOT change the current category."""
        rows = parse_navall_with_category(CATEGORY_FIXTURE)
        # Both HDFC rows must still carry Equity Scheme, not reset to None.
        assert rows[0].category == "Equity Scheme - Large Cap Fund"

    def test_schemes_before_any_header_get_none(self):
        rows = parse_navall_with_category(NO_HEADER_FIRST_FIXTURE)
        orphan = next(r for r in rows if r.amfi_code == "999001")
        assert orphan.category is None

    def test_schemes_after_header_get_category(self):
        rows = parse_navall_with_category(NO_HEADER_FIRST_FIXTURE)
        keyed = next(r for r in rows if r.amfi_code == "999002")
        assert keyed.category == "Equity Scheme - Large Cap Fund"

    def test_existing_fields_unaffected(self):
        rows = parse_navall_with_category(CATEGORY_FIXTURE)
        row = rows[0]
        assert row.amfi_code == "100016"
        assert row.isin_growth == "INF179K01BB4"
        assert row.isin_reinvest is None
        assert row.nav == pytest.approx(1052.34)
        assert row.nav_date == datetime.date(2026, 6, 1)

    def test_na_nav_row_still_skipped(self):
        fixture = (
            "Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;"
            "Scheme Name;Net Asset Value;Date\n"
            "Open Ended Schemes(Equity Scheme - Large Cap Fund)\n"
            "99;INF001;INF002;Bad NAV Fund;N.A.;01-Jun-2026\n"
        )
        rows = parse_navall_with_category(fixture)
        assert rows == []

    def test_parse_navall_unchanged_no_category(self):
        """Existing parse_navall must still work and return category=None."""
        from dhanradar.market_data.amfi import parse_navall
        rows = parse_navall(CATEGORY_FIXTURE)
        assert len(rows) == 4
        assert all(r.category is None for r in rows)

    def test_navrow_category_field_is_last_and_defaults_none(self):
        """NavRow can still be constructed without category (backward compat)."""
        r = NavRow(
            amfi_code="X",
            isin_growth="INF001",
            isin_reinvest=None,
            scheme_name="Test",
            nav=10.0,
            nav_date=datetime.date(2026, 6, 1),
        )
        assert r.category is None


# ===========================================================================
# fetch_navall_rows_with_category — fake client, no network
# ===========================================================================

def _make_fake_client(text: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    return client


class TestFetchNavallRowsWithCategory:
    async def test_parses_category_from_injected_response(self):
        fake_client = _make_fake_client(CATEGORY_FIXTURE)
        rows = await fetch_navall_rows_with_category(client=fake_client)
        assert len(rows) == 4
        assert rows[0].category == "Equity Scheme - Large Cap Fund"

    async def test_calls_navall_url(self):
        from dhanradar.market_data.amfi import NAVALL_URL
        fake_client = _make_fake_client(CATEGORY_FIXTURE)
        await fetch_navall_rows_with_category(client=fake_client)
        call_args = fake_client.get.call_args
        url = call_args.args[0] if call_args.args else call_args.kwargs.get("url", "")
        assert url == NAVALL_URL

    async def test_raises_provider_error_on_non_200(self):
        fake_client = _make_fake_client("bad", status_code=503)
        with pytest.raises(ProviderError) as exc_info:
            await fetch_navall_rows_with_category(client=fake_client)
        assert exc_info.value.provider == "amfi_nav"
        assert "503" in str(exc_info.value)

    async def test_raises_provider_error_on_transport_error(self):
        import httpx
        fake_client = MagicMock()
        fake_client.get = AsyncMock(side_effect=httpx.TransportError("refused"))
        with pytest.raises(ProviderError):
            await fetch_navall_rows_with_category(client=fake_client)


# ===========================================================================
# _navrows_to_nav_upserts — pure mapping, no DB
# ===========================================================================

def _row(
    amfi_code: str = "100",
    isin_growth: str | None = "INF001",
    isin_reinvest: str | None = None,
    nav: float = 10.0,
    nav_date: datetime.date | None = None,
    category: str | None = None,
) -> NavRow:
    return NavRow(
        amfi_code=amfi_code,
        isin_growth=isin_growth,
        isin_reinvest=isin_reinvest,
        scheme_name="Test Fund",
        nav=nav,
        nav_date=nav_date or datetime.date(2026, 6, 1),
        category=category,
    )


class TestNavrowsToNavUpserts:
    def test_growth_isin_preferred_over_reinvest(self):
        rows = [_row(isin_growth="INF_GROWTH", isin_reinvest="INF_REINVEST")]
        out = _navrows_to_nav_upserts(rows)
        assert len(out) == 1
        assert out[0]["isin"] == "INF_GROWTH"

    def test_reinvest_isin_used_when_growth_none(self):
        rows = [_row(isin_growth=None, isin_reinvest="INF_REINVEST")]
        out = _navrows_to_nav_upserts(rows)
        assert len(out) == 1
        assert out[0]["isin"] == "INF_REINVEST"

    def test_no_isin_row_skipped(self):
        rows = [_row(isin_growth=None, isin_reinvest=None)]
        out = _navrows_to_nav_upserts(rows)
        assert out == []

    def test_nav_and_date_and_source_set(self):
        d = datetime.date(2026, 6, 5)
        rows = [_row(nav=42.56, nav_date=d)]
        out = _navrows_to_nav_upserts(rows)
        assert out[0]["nav"] == pytest.approx(42.56)
        assert out[0]["nav_date"] == d
        assert out[0]["source"] == "amfi"

    def test_multiple_rows_all_included(self):
        rows = [
            _row(amfi_code="A", isin_growth="INF_A"),
            _row(amfi_code="B", isin_growth="INF_B"),
            _row(amfi_code="C", isin_growth=None, isin_reinvest=None),  # skipped
        ]
        out = _navrows_to_nav_upserts(rows)
        assert len(out) == 2
        assert {r["isin"] for r in out} == {"INF_A", "INF_B"}


# ===========================================================================
# _navrows_to_fund_upserts — pure mapping, no DB
# ===========================================================================

class TestNavrowsToFundUpserts:
    def test_growth_isin_preferred(self):
        rows = [_row(isin_growth="INF_G", isin_reinvest="INF_R")]
        out = _navrows_to_fund_upserts(rows)
        assert out[0]["isin"] == "INF_G"

    def test_reinvest_fallback(self):
        rows = [_row(isin_growth=None, isin_reinvest="INF_R")]
        out = _navrows_to_fund_upserts(rows)
        assert out[0]["isin"] == "INF_R"

    def test_no_isin_row_skipped(self):
        rows = [_row(isin_growth=None, isin_reinvest=None)]
        assert _navrows_to_fund_upserts(rows) == []

    def test_category_carried(self):
        rows = [_row(category="Equity Scheme - Large Cap Fund")]
        out = _navrows_to_fund_upserts(rows)
        assert out[0]["category"] == "Equity Scheme - Large Cap Fund"

    def test_none_category_carried(self):
        rows = [_row(category=None)]
        out = _navrows_to_fund_upserts(rows)
        assert out[0]["category"] is None

    def test_amfi_code_and_scheme_name_set(self):
        rows = [NavRow(
            amfi_code="139619",
            isin_growth="INF090I01239",
            isin_reinvest=None,
            scheme_name="Taurus Short Term Income Fund",
            nav=42.56,
            nav_date=datetime.date(2026, 6, 1),
            category="Debt Scheme - Banking and PSU Fund",
        )]
        out = _navrows_to_fund_upserts(rows)
        assert out[0]["amfi_code"] == "139619"
        assert out[0]["scheme_name"] == "Taurus Short Term Income Fund"

    def test_only_amfi_owned_columns_plus_isin(self):
        """Must NOT include columns the feed does not own (expense_ratio, aum, etc.).

        `sebi_category` is the validated/canonical form of the feed's own `category`
        (B66 taxonomy layer). `plan_type` and `option_type` are parsed from the
        feed's own `scheme_name` (B67 Task 3) — derived, not a different source.
        Scheme-master columns that require a separate data source (aum, expense_ratio,
        benchmark_index) must NOT appear here."""
        rows = [_row()]
        out = _navrows_to_fund_upserts(rows)
        assert set(out[0].keys()) == {
            "isin", "amfi_code", "scheme_name", "category", "sebi_category",
            "plan_type", "option_type",
        }

    def test_plan_type_and_option_type_populated(self):
        """plan_type and option_type are parsed from the scheme_name."""
        row = NavRow(
            amfi_code="119551",
            isin_growth="INF179KB1HA2",
            isin_reinvest=None,
            scheme_name="Nippon India Large Cap Fund - Direct Plan - Growth",
            nav=78.43,
            nav_date=datetime.date(2026, 6, 1),
            category="Equity Scheme - Large Cap Fund",
        )
        out = _navrows_to_fund_upserts([row])
        assert out[0]["plan_type"] == "direct"
        assert out[0]["option_type"] == "growth"

    def test_plan_type_none_for_legacy_scheme(self):
        """Legacy scheme names without Direct/Regular produce plan_type=None."""
        row = NavRow(
            amfi_code="100033",
            isin_growth="INF209K01YQ6",
            isin_reinvest=None,
            scheme_name="Reliance Growth Fund",
            nav=92.12,
            nav_date=datetime.date(2026, 6, 1),
            category="Equity Scheme - Large Cap Fund",
        )
        out = _navrows_to_fund_upserts([row])
        assert out[0]["plan_type"] is None
        assert out[0]["option_type"] == "growth"


# ===========================================================================
# Provenance contract — mf_nav_history.ingested_at (migration 0019)
# ===========================================================================

class TestNavHistoryProvenanceColumn:
    """The ingestion-provenance column is part of the data-platform contract
    (six-question rule: "when received"). Guard its shape so it can't be silently
    dropped or have its nullable/default semantics changed."""

    def test_ingested_at_column_exists_nullable_with_default(self):
        from sqlalchemy import DateTime

        from dhanradar.models.mf import MfNavHistory

        col = MfNavHistory.__table__.columns["ingested_at"]
        assert isinstance(col.type, DateTime)
        assert col.type.timezone is True
        # Nullable: backfilled rows with an unknown ingestion time stay NULL —
        # never imputed (no-fabrication invariant).
        assert col.nullable is True
        # New rows auto-stamp via the server default.
        assert col.server_default is not None

    def test_nav_upsert_mapping_excludes_ingested_at(self):
        """The pure mapping helper must NOT carry ingested_at — it is stamped
        server-side (column default on insert; func.now() in the upsert set_),
        so historical backfills can't smuggle a client clock into provenance."""
        rows = [_row()]
        out = _navrows_to_nav_upserts(rows)
        assert "ingested_at" not in out[0]
