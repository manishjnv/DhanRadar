"""
Unit tests for `dhanradar.mf.benchmark_mapping.map_index_fund_benchmark`
(Block 0.7 — name-derived index-fund benchmark identity, high confidence only).

Pure-function tests — no DB, no network.
"""

from __future__ import annotations

from dhanradar.mf.benchmark_mapping import map_index_fund_benchmark

_INDEX_CATEGORY = "Other Scheme - Index Funds"


class TestPositiveMatchesPerRegistryKey:
    def test_nifty_50(self):
        assert (
            map_index_fund_benchmark("HDFC Index Fund - Nifty 50 Plan - Growth", _INDEX_CATEGORY)
            == "nifty50"
        )

    def test_nifty_100(self):
        assert (
            map_index_fund_benchmark("UTI Nifty 100 Index Fund - Direct - Growth", _INDEX_CATEGORY)
            == "nifty100"
        )

    def test_nifty_500(self):
        assert (
            map_index_fund_benchmark(
                "Motilal Oswal Nifty 500 Index Fund - Direct - Growth", _INDEX_CATEGORY
            )
            == "nifty500"
        )

    def test_nifty_midcap_150(self):
        assert (
            map_index_fund_benchmark(
                "ICICI Prudential Nifty Midcap 150 Index Fund - Growth", _INDEX_CATEGORY
            )
            == "nifty_midcap_150"
        )

    def test_no_space_number_variants_still_match(self):
        """'Nifty50'/'Midcap150' (no space before the number) normalize the
        same as the spaced form."""
        assert (
            map_index_fund_benchmark("SBI Nifty50 Index Fund - Growth", _INDEX_CATEGORY)
            == "nifty50"
        )
        assert (
            map_index_fund_benchmark(
                "Motilal Oswal Nifty Midcap150 Index Fund - Growth", _INDEX_CATEGORY
            )
            == "nifty_midcap_150"
        )


class TestOrderingAvoidsSubstringCollision:
    def test_nifty_500_not_mistaken_for_nifty_50(self):
        """'nifty 500' literally contains 'nifty 50' as a substring after
        normalization — the ordered pattern table must check the longer name
        first so a genuine Nifty 500 fund never maps to nifty50."""
        assert (
            map_index_fund_benchmark("Any AMC Nifty 500 Index Fund - Growth", _INDEX_CATEGORY)
            == "nifty500"
        )

    def test_nifty_midcap_150_not_mistaken_for_bare_100(self):
        assert (
            map_index_fund_benchmark("Any AMC Nifty Midcap 150 Fund - Growth", _INDEX_CATEGORY)
            == "nifty_midcap_150"
        )


class TestAmbiguousOrUnmappedReturnsNone:
    def test_nifty_smallcap_250_not_in_registry(self):
        """Nifty Smallcap 250 has no working BENCHMARK_REGISTRY entry (dropped —
        see tasks/mf.py registry comment) — must never be guessed/mapped."""
        assert (
            map_index_fund_benchmark(
                "Any AMC Nifty Smallcap 250 Index Fund - Growth", _INDEX_CATEGORY
            )
            is None
        )

    def test_non_index_category_gates_before_name_match(self):
        """An active (non-index) fund with an index-sounding name must NEVER be
        mapped — the category gate fails first, before the name table is even
        consulted (architecture plan §19 non-negotiable)."""
        assert (
            map_index_fund_benchmark(
                "Some AMC Nifty 50 Opportunities Fund - Growth",
                "Equity Scheme - Large Cap Fund",
            )
            is None
        )

    def test_none_category_returns_none(self):
        assert map_index_fund_benchmark("Nifty 50 Index Fund - Growth", None) is None

    def test_equal_weight_variant_is_ambiguous(self):
        """A Nifty 50 EQUAL WEIGHT index fund tracks a DIFFERENT index than the
        market-cap-weighted Nifty 50 in BENCHMARK_REGISTRY — must not guess."""
        assert (
            map_index_fund_benchmark(
                "Aditya Birla Sun Life Nifty 50 Equal Weight Index Fund", _INDEX_CATEGORY
            )
            is None
        )

    def test_nifty_next_50_is_ambiguous(self):
        """Nifty Next 50 is a different index, not the plain Nifty 50."""
        assert (
            map_index_fund_benchmark("Some AMC Nifty Next 50 Index Fund", _INDEX_CATEGORY)
            is None
        )

    def test_unrecognized_index_name_returns_none(self):
        assert (
            map_index_fund_benchmark("Some AMC Gold ETF Fund", _INDEX_CATEGORY) is None
        )

    def test_empty_scheme_name_returns_none(self):
        assert map_index_fund_benchmark("", _INDEX_CATEGORY) is None
