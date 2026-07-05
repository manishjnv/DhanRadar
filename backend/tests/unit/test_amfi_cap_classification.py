"""
Unit tests for the AMFI half-yearly cap-classification parser — no DB, no
network, no Celery.

Covers:
  parse_cap_classification_rows (PURE):
    - valid rows parsed correctly (ISIN, name, cap_class, avg_market_cap_cr)
    - row with missing/blank ISIN skipped
    - row with unrecognized cap_class label skipped (never guessed)
    - row too short (fewer than 11 columns) skipped
    - non-numeric avg_market_cap cell -> avg_market_cap_cr = None (never fabricated)

  candidate_period_ends / build_url / period_label:
    - most-recent-first ordering
    - URL matches the real verified pattern
    - period_label matches '{year}H1'/'{year}H2'

asyncio_mode = "auto" (pyproject.toml) -- async test functions need no decorator.
"""

from __future__ import annotations

from datetime import date

from dhanradar.market_data.amfi_cap_classification import (
    build_url,
    candidate_period_ends,
    parse_cap_classification_rows,
    period_label,
)

# ---------------------------------------------------------------------------
# Golden fixture rows -- mirrors the real AMFI xlsx layout (already extracted
# via openpyxl, so these are plain Python tuples; row 0=title/row 1=header
# are NOT included here since the fetch wrapper strips them before calling
# the pure parser).
# ---------------------------------------------------------------------------

_VALID_ROW = (
    1,
    "Reliance Industries Ltd",
    "INE002A01018",
    "RELIANCE",
    1873294.71,
    "RELIANCE",
    1873278.83,
    "-",
    None,
    1873286.77,
    "Large Cap",
)
_VALID_ROW_2 = (
    2,
    "HDFC Bank Ltd.",
    "INE040A01034",
    "HDFCBANK",
    1286604.41,
    "HDFCBANK",
    1286302.05,
    "-",
    None,
    1286453.23,
    "Mid Cap",
)
_BLANK_ISIN_ROW = (
    3,
    "Some Company Ltd",
    "",
    "SYM",
    100.0,
    "SYM",
    100.0,
    "-",
    None,
    100.0,
    "Small Cap",
)
_BAD_CAP_CLASS_ROW = (
    4,
    "Weird Company Ltd",
    "INE999Z01234",
    "SYM",
    50.0,
    "SYM",
    50.0,
    "-",
    None,
    50.0,
    "Micro Cap",
)
_TOO_SHORT_ROW = (5, "Truncated Row", "INE111A01111")
_NON_NUMERIC_AVG_ROW = (
    6,
    "Odd Company Ltd",
    "INE222B02222",
    "SYM",
    10.0,
    "SYM",
    10.0,
    "-",
    None,
    "-",
    "Small Cap",
)


class TestParseCapClassificationRows:
    def test_valid_rows_parsed(self):
        rows = parse_cap_classification_rows([_VALID_ROW, _VALID_ROW_2], effective_period="2026H1")
        assert len(rows) == 2
        assert rows[0].stock_isin == "INE002A01018"
        assert rows[0].stock_name == "Reliance Industries Ltd"
        assert rows[0].cap_class == "Large Cap"
        assert rows[0].avg_market_cap_cr == 1873286.77
        assert rows[0].effective_period == "2026H1"
        assert rows[1].cap_class == "Mid Cap"

    def test_blank_isin_skipped(self):
        rows = parse_cap_classification_rows([_BLANK_ISIN_ROW], effective_period="2026H1")
        assert rows == []

    def test_unrecognized_cap_class_skipped(self):
        rows = parse_cap_classification_rows([_BAD_CAP_CLASS_ROW], effective_period="2026H1")
        assert rows == []

    def test_too_short_row_skipped(self):
        rows = parse_cap_classification_rows([_TOO_SHORT_ROW], effective_period="2026H1")
        assert rows == []

    def test_non_numeric_avg_market_cap_becomes_none(self):
        rows = parse_cap_classification_rows([_NON_NUMERIC_AVG_ROW], effective_period="2026H1")
        assert len(rows) == 1
        assert rows[0].avg_market_cap_cr is None

    def test_mixed_valid_and_invalid(self):
        rows = parse_cap_classification_rows(
            [_VALID_ROW, _BLANK_ISIN_ROW, _BAD_CAP_CLASS_ROW, _TOO_SHORT_ROW, _VALID_ROW_2],
            effective_period="2026H1",
        )
        assert len(rows) == 2
        assert {r.stock_isin for r in rows} == {"INE002A01018", "INE040A01034"}


class TestCandidatePeriodEnds:
    def test_after_jun_30_returns_jun_first(self):
        candidates = candidate_period_ends(date(2026, 7, 5))
        assert candidates[0] == date(2026, 6, 30)
        assert candidates[1] == date(2025, 12, 31)

    def test_before_jun_30_returns_previous_dec_first(self):
        candidates = candidate_period_ends(date(2026, 3, 15))
        assert candidates[0] == date(2025, 12, 31)
        assert candidates[1] == date(2025, 6, 30)

    def test_exactly_on_period_end(self):
        candidates = candidate_period_ends(date(2026, 6, 30))
        assert candidates[0] == date(2026, 6, 30)


class TestBuildUrlAndLabel:
    def test_build_url_matches_verified_pattern(self):
        url = build_url(date(2026, 6, 30))
        assert url == (
            "https://portal.amfiindia.com/spages/AverageMarketCapitalization30Jun2026.xlsx"
        )

    def test_period_label_h1(self):
        assert period_label(date(2026, 6, 30)) == "2026H1"

    def test_period_label_h2(self):
        assert period_label(date(2026, 12, 31)) == "2026H2"
