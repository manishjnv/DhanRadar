"""
Unit tests for the AMFI monthly category-flows parser — no DB, no network,
no Celery.

Covers:
  parse_category_flow_rows (PURE):
    - leaf lowercase-roman rows parsed correctly
    - uppercase-roman supergroup header rows skipped (e.g. 'I', 'II')
    - 'A' top-level header row skipped
    - 'Sub Total - ...' rollup rows skipped (never double-counted)
    - blank separator rows skipped
    - row too short skipped
    - non-numeric cells become None (never fabricated)

  candidate_months / build_url:
    - most-recent-first ordering (last full month, then the one before)
    - URL matches the real verified pattern (3-letter lowercase month)

asyncio_mode = "auto" (pyproject.toml) -- async test functions need no decorator.
"""

from __future__ import annotations

from datetime import date

from dhanradar.market_data.amfi_category_flows import (
    build_url,
    candidate_months,
    parse_category_flow_rows,
)

# ---------------------------------------------------------------------------
# Golden fixture rows -- mirrors the real AMFI MCR_MonthlyReport sheet layout
# (already extracted via xlrd row_values(), so these are plain Python tuples;
# the blank row (0), title row (1), and header row (2) are NOT included here
# since the fetch wrapper strips them before calling the pure parser).
# ---------------------------------------------------------------------------

_SUPERGROUP_A = ("A", "Open ended Schemes", "", "", "", "", "", "", "", "", "")
_SUPERGROUP_I = ("I", "Income/Debt Oriented Schemes", "", "", "", "", "", "", "", "", "")
_LEAF_OVERNIGHT = (
    "i",
    "Overnight Fund",
    37.0,
    769280.0,
    609290.59,
    624815.36,
    -15524.77,
    89939.73,
    125683.05,
    0.0,
    0.0,
)
_LEAF_LIQUID = (
    "ii",
    "Liquid Fund",
    42.0,
    3128442.0,
    384615.25,
    414296.19,
    -29680.94,
    609456.75,
    647737.83,
    0.0,
    0.0,
)
_SUB_TOTAL_ROW = (
    "",
    "Sub Total - I (i+ii)",
    79.0,
    3897722.0,
    993905.85,
    1039111.55,
    -45205.71,
    699396.48,
    773420.88,
    0.0,
    0.0,
)
_BLANK_ROW = ("", "", "", "", "", "", "", "", "", "", "")
_SUPERGROUP_II = ("II", "Growth/Equity Oriented Schemes", "", "", "", "", "", "", "", "", "")
_LEAF_MULTICAP = (
    "i",
    "Multi Cap Fund",
    32.0,
    11641382.0,
    4467.15,
    2176.14,
    2291.01,
    232886.94,
    231906.89,
    0.0,
    0.0,
)
_TOO_SHORT_ROW = ("i", "Truncated")


class TestParseCategoryFlowRows:
    def test_leaf_rows_parsed(self):
        rows = parse_category_flow_rows(
            [_LEAF_OVERNIGHT, _LEAF_LIQUID], period_month=date(2026, 5, 1)
        )
        assert len(rows) == 2
        assert rows[0].scheme_category == "Overnight Fund"
        assert rows[0].period_month == date(2026, 5, 1)
        assert rows[0].num_schemes == 37
        assert rows[0].num_folios == 769280
        assert rows[0].funds_mobilized_cr == 609290.59
        assert rows[0].redemption_cr == 624815.36
        assert rows[0].net_flow_cr == -15524.77
        assert rows[0].net_aum_cr == 89939.73
        assert rows[0].avg_aum_cr == 125683.05
        assert rows[1].scheme_category == "Liquid Fund"

    def test_supergroup_a_header_skipped(self):
        rows = parse_category_flow_rows([_SUPERGROUP_A], period_month=date(2026, 5, 1))
        assert rows == []

    def test_uppercase_roman_supergroup_skipped(self):
        rows = parse_category_flow_rows(
            [_SUPERGROUP_I, _SUPERGROUP_II], period_month=date(2026, 5, 1)
        )
        assert rows == []

    def test_sub_total_row_skipped(self):
        rows = parse_category_flow_rows([_SUB_TOTAL_ROW], period_month=date(2026, 5, 1))
        assert rows == []

    def test_blank_row_skipped(self):
        rows = parse_category_flow_rows([_BLANK_ROW], period_month=date(2026, 5, 1))
        assert rows == []

    def test_too_short_row_skipped(self):
        rows = parse_category_flow_rows([_TOO_SHORT_ROW], period_month=date(2026, 5, 1))
        assert rows == []

    def test_roman_numerals_reset_per_supergroup(self):
        """'i' appears once under Debt (Overnight Fund) and again under Equity
        (Multi Cap Fund) — both must be kept as distinct category rows."""
        rows = parse_category_flow_rows(
            [
                _SUPERGROUP_I,
                _LEAF_OVERNIGHT,
                _SUB_TOTAL_ROW,
                _BLANK_ROW,
                _SUPERGROUP_II,
                _LEAF_MULTICAP,
            ],
            period_month=date(2026, 5, 1),
        )
        assert len(rows) == 2
        assert {r.scheme_category for r in rows} == {"Overnight Fund", "Multi Cap Fund"}

    def test_full_mixed_fixture(self):
        rows = parse_category_flow_rows(
            [
                _SUPERGROUP_A,
                _SUPERGROUP_I,
                _LEAF_OVERNIGHT,
                _LEAF_LIQUID,
                _SUB_TOTAL_ROW,
                _BLANK_ROW,
                _SUPERGROUP_II,
                _LEAF_MULTICAP,
                _TOO_SHORT_ROW,
            ],
            period_month=date(2026, 5, 1),
        )
        assert len(rows) == 3
        assert {r.scheme_category for r in rows} == {
            "Overnight Fund",
            "Liquid Fund",
            "Multi Cap Fund",
        }


class TestCandidateMonthsAndUrl:
    def test_returns_last_full_month_first(self):
        candidates = candidate_months(date(2026, 7, 5))
        assert candidates[0] == date(2026, 6, 1)
        assert candidates[1] == date(2026, 5, 1)

    def test_year_rollover(self):
        candidates = candidate_months(date(2026, 1, 15))
        assert candidates[0] == date(2025, 12, 1)
        assert candidates[1] == date(2025, 11, 1)

    def test_build_url_matches_verified_pattern(self):
        url = build_url(date(2026, 5, 1))
        assert url == "https://portal.amfiindia.com/spages/ammay2026repo.xls"
