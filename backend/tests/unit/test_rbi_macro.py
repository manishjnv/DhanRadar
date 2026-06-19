"""
Unit tests for RBI DBIE macro provider and ingestion pipeline — no DB, no network.

Covers:
  - parse_macro: valid rows, unknown indicator_key skipped, out-of-range value
    counted, non-finite value skipped, missing as_of_date skipped.
  - fetch_macro_indicators: injected AsyncMock client verifies URL hit + return value;
    ProviderError on non-200; ProviderError on transport error.
  - _is_in_range: boundary checks for each indicator.

asyncio_mode = "auto" (pyproject.toml) — async test functions need no decorator.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from dhanradar.market_data.exceptions import ProviderError
from dhanradar.market_data.rbi import (
    CANONICAL_INDICATOR_KEYS,
    MacroRow,
    fetch_macro_indicators,
    parse_macro,
)
from dhanradar.tasks.macro_data import _is_in_range

# ---------------------------------------------------------------------------
# Fixtures — inline CSV payloads
# ---------------------------------------------------------------------------

VALID_FIXTURE = """\
indicator_key,indicator_value,unit,as_of_date
repo_rate,6.50,percent,2024-04-01
cpi_inflation,4.83,percent,2024-03-01
wpi_inflation,0.53,percent,2024-03-01
gdp_growth,8.20,percent,2024-01-01
m3_money_supply,22500000.00,crore_inr,2024-03-01
"""

# One row with unknown key (should be skipped), one out-of-range (repo_rate=99),
# one with missing as_of_date, and one valid row.
MIXED_FIXTURE = """\
indicator_key,indicator_value,unit,as_of_date
unknown_indicator,5.00,percent,2024-04-01
repo_rate,99.00,percent,2024-04-01
cpi_inflation,3.50,,
gdp_growth,7.10,percent,2024-01-01
"""

# Fixture with a non-finite value and an unparseable value.
NONFINITE_FIXTURE = """\
indicator_key,indicator_value,unit,as_of_date
repo_rate,nan,percent,2024-04-01
cpi_inflation,inf,percent,2024-03-01
wpi_inflation,not_a_number,percent,2024-03-01
gdp_growth,6.00,percent,2024-01-01
"""

# Duplicate rows — same (indicator_key, as_of_date) pair appears twice.
DUPLICATE_FIXTURE = """\
indicator_key,indicator_value,unit,as_of_date
repo_rate,6.50,percent,2024-04-01
repo_rate,6.75,percent,2024-04-01
cpi_inflation,4.83,percent,2024-03-01
"""

# Empty payload.
EMPTY_FIXTURE = ""

# Header-only (no data rows).
HEADER_ONLY_FIXTURE = "indicator_key,indicator_value,unit,as_of_date\n"


# ===========================================================================
# parse_macro
# ===========================================================================

class TestParseMacro:
    def test_valid_fixture_returns_five_rows(self):
        rows = parse_macro(VALID_FIXTURE)
        assert len(rows) == 5

    def test_all_canonical_keys_present(self):
        rows = parse_macro(VALID_FIXTURE)
        keys = {r.indicator_key for r in rows}
        assert keys == CANONICAL_INDICATOR_KEYS

    def test_row_types_correct(self):
        rows = parse_macro(VALID_FIXTURE)
        for row in rows:
            assert isinstance(row, MacroRow)
            assert isinstance(row.indicator_key, str)
            assert isinstance(row.indicator_value, float)
            assert isinstance(row.as_of_date, date)

    def test_repo_rate_value_and_date(self):
        rows = parse_macro(VALID_FIXTURE)
        rr = next(r for r in rows if r.indicator_key == "repo_rate")
        assert rr.indicator_value == pytest.approx(6.50)
        assert rr.as_of_date == date(2024, 4, 1)
        assert rr.unit == "percent"

    def test_m3_unit_present(self):
        rows = parse_macro(VALID_FIXTURE)
        m3 = next(r for r in rows if r.indicator_key == "m3_money_supply")
        assert m3.unit == "crore_inr"

    # --- MIXED_FIXTURE: unknown key + out-of-range + missing date + valid ---

    def test_unknown_indicator_key_skipped(self):
        rows = parse_macro(MIXED_FIXTURE)
        keys = {r.indicator_key for r in rows}
        assert "unknown_indicator" not in keys

    def test_out_of_range_repo_rate_still_parsed(self):
        """parse_macro does NOT do range validation — that is the task's job.
        The row with repo_rate=99.00 must be returned by parse_macro and rejected
        by the task (_is_in_range). Here we verify parse_macro returns it."""
        rows = parse_macro(MIXED_FIXTURE)
        out_of_range = [r for r in rows if r.indicator_key == "repo_rate"]
        assert len(out_of_range) == 1
        assert out_of_range[0].indicator_value == pytest.approx(99.0)

    def test_missing_as_of_date_skipped(self):
        """cpi_inflation row has empty as_of_date — must be skipped."""
        rows = parse_macro(MIXED_FIXTURE)
        cpi_rows = [r for r in rows if r.indicator_key == "cpi_inflation"]
        assert len(cpi_rows) == 0

    def test_valid_row_in_mixed_fixture_present(self):
        """gdp_growth=7.10 with valid date must survive."""
        rows = parse_macro(MIXED_FIXTURE)
        gdp = [r for r in rows if r.indicator_key == "gdp_growth"]
        assert len(gdp) == 1
        assert gdp[0].indicator_value == pytest.approx(7.10)

    # --- NONFINITE_FIXTURE ---

    def test_nan_value_skipped(self):
        rows = parse_macro(NONFINITE_FIXTURE)
        keys = {r.indicator_key for r in rows}
        assert "repo_rate" not in keys  # nan row skipped

    def test_inf_value_skipped(self):
        rows = parse_macro(NONFINITE_FIXTURE)
        keys = {r.indicator_key for r in rows}
        assert "cpi_inflation" not in keys  # inf row skipped

    def test_non_numeric_string_skipped(self):
        rows = parse_macro(NONFINITE_FIXTURE)
        keys = {r.indicator_key for r in rows}
        assert "wpi_inflation" not in keys  # "not_a_number" skipped

    def test_valid_row_in_nonfinite_fixture_survives(self):
        rows = parse_macro(NONFINITE_FIXTURE)
        gdp_rows = [r for r in rows if r.indicator_key == "gdp_growth"]
        assert len(gdp_rows) == 1

    # --- DUPLICATE_FIXTURE: parse_macro returns both; task deduplicates ---

    def test_duplicates_returned_by_parse_macro(self):
        """parse_macro itself does NOT dedup — the task does.
        Both repo_rate rows should be present."""
        rows = parse_macro(DUPLICATE_FIXTURE)
        rr_rows = [r for r in rows if r.indicator_key == "repo_rate"]
        assert len(rr_rows) == 2

    # --- Edge cases ---

    def test_empty_payload_returns_empty_list(self):
        rows = parse_macro(EMPTY_FIXTURE)
        assert rows == []

    def test_header_only_returns_empty_list(self):
        rows = parse_macro(HEADER_ONLY_FIXTURE)
        assert rows == []

    def test_unit_none_when_blank(self):
        payload = "indicator_key,indicator_value,unit,as_of_date\nrepo_rate,6.50,,2024-04-01\n"
        rows = parse_macro(payload)
        assert len(rows) == 1
        assert rows[0].unit is None


# ===========================================================================
# _is_in_range (task validation)
# ===========================================================================

class TestIsInRange:
    def test_repo_rate_zero_boundary_valid(self):
        # Spec: repo_rate range 0..20 — inclusive lower bound.
        assert _is_in_range("repo_rate", 0.0) is True

    def test_repo_rate_valid_midrange(self):
        assert _is_in_range("repo_rate", 6.5) is True

    def test_repo_rate_upper_boundary_valid(self):
        assert _is_in_range("repo_rate", 20.0) is True

    def test_repo_rate_above_upper_invalid(self):
        assert _is_in_range("repo_rate", 20.01) is False

    def test_repo_rate_negative_invalid(self):
        assert _is_in_range("repo_rate", -0.01) is False

    def test_cpi_inflation_negative_boundary(self):
        assert _is_in_range("cpi_inflation", -10.0) is True

    def test_cpi_inflation_below_lower_invalid(self):
        assert _is_in_range("cpi_inflation", -10.01) is False

    def test_cpi_inflation_upper_boundary(self):
        assert _is_in_range("cpi_inflation", 50.0) is True

    def test_gdp_growth_negative_valid(self):
        assert _is_in_range("gdp_growth", -5.0) is True

    def test_gdp_growth_below_lower_invalid(self):
        assert _is_in_range("gdp_growth", -25.01) is False

    def test_m3_money_supply_zero_invalid(self):
        assert _is_in_range("m3_money_supply", 0.0) is False

    def test_m3_money_supply_negative_invalid(self):
        assert _is_in_range("m3_money_supply", -1.0) is False

    def test_m3_money_supply_large_value_valid(self):
        # M3 is ₹ crore; no upper bound
        assert _is_in_range("m3_money_supply", 22_500_000.0) is True

    def test_unknown_key_invalid(self):
        assert _is_in_range("unknown_key", 5.0) is False


# ===========================================================================
# fetch_macro_indicators — injected AsyncMock client
# ===========================================================================

class TestFetchMacroIndicators:
    async def test_returns_response_text_on_200(self):
        """Happy path: client returns 200 with CSV text."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = VALID_FIXTURE

        fake_client = AsyncMock()
        fake_client.get = AsyncMock(return_value=mock_response)

        result = await fetch_macro_indicators(fake_client)
        assert result == VALID_FIXTURE

    async def test_raises_provider_error_on_404(self):
        """Non-200 response → ProviderError."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        fake_client = AsyncMock()
        fake_client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(ProviderError) as exc_info:
            await fetch_macro_indicators(fake_client)
        assert "404" in str(exc_info.value)

    async def test_raises_provider_error_on_503(self):
        """Service unavailable → ProviderError."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"

        fake_client = AsyncMock()
        fake_client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(ProviderError) as exc_info:
            await fetch_macro_indicators(fake_client)
        assert "503" in str(exc_info.value)

    async def test_raises_provider_error_on_transport_error(self):
        """Connection refused → ProviderError."""
        import httpx

        fake_client = AsyncMock()
        fake_client.get = AsyncMock(
            side_effect=httpx.TransportError("connection refused")
        )

        with pytest.raises(ProviderError) as exc_info:
            await fetch_macro_indicators(fake_client)
        assert "transport" in str(exc_info.value).lower()

    async def test_raises_provider_error_on_timeout(self):
        """Timeout → ProviderError."""
        import httpx

        fake_client = AsyncMock()
        fake_client.get = AsyncMock(
            side_effect=httpx.TimeoutException("timed out")
        )

        with pytest.raises(ProviderError) as exc_info:
            await fetch_macro_indicators(fake_client)
        assert "timeout" in str(exc_info.value).lower()

    async def test_get_called_with_rbi_url(self):
        """Verify the client.get call targets the RBI DBIE URL."""
        from dhanradar.market_data.rbi import _RBI_MACRO_CSV_URL

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = VALID_FIXTURE

        fake_client = AsyncMock()
        fake_client.get = AsyncMock(return_value=mock_response)

        await fetch_macro_indicators(fake_client)

        call_args = fake_client.get.call_args
        called_url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        assert "data.rbi.org.in" in called_url or called_url == _RBI_MACRO_CSV_URL
