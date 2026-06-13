"""
Unit tests for dhanradar.mf.taxonomy (B66).

DB-free, network-free. Covers:
  - All 42 canonical SEBI leaves → status=="canonical"
  - Legacy map ("ELSS") → canonical
  - Double-space normalization → canonical
  - Curly apostrophe normalization → canonical
  - Padded whitespace → canonical
  - Unmappable legacy strings → status=="legacy", canonical is None
  - Unknown string → status=="unknown"
  - None / "" / whitespace → status=="empty"
  - scheme_class extraction
  - summarize() tallies and samples
  - _navrows_to_fund_upserts guard: raw category cohort key is never mutated,
    sebi_category populated correctly.
"""

from __future__ import annotations

import pytest

from dhanradar.mf.taxonomy import (
    _CANONICAL_LEAVES,
    _LEGACY_UNMAPPABLE,
    canonical_for,
    classify,
    normalize,
    summarize,
)

# ---------------------------------------------------------------------------
# Normalize helpers
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_none_returns_none(self) -> None:
        assert normalize(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert normalize("") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert normalize("   ") is None

    def test_non_str_input_returns_none_never_raises(self) -> None:
        # Hardening (B66 adversarial finding 3a): canonical_for runs unwrapped in
        # the per-row nightly upsert mapping; a non-str from an upstream parser
        # regression must be treated as empty, not crash ingestion.
        assert normalize(123) is None  # type: ignore[arg-type]
        assert normalize(b"Equity Scheme - Large Cap Fund") is None  # type: ignore[arg-type]
        assert classify(123).status == "empty"  # type: ignore[arg-type]
        assert canonical_for(123) is None  # type: ignore[arg-type]

    def test_strips_leading_trailing(self) -> None:
        assert normalize("  hello  ") == "hello"

    def test_collapses_double_space(self) -> None:
        assert normalize("Other Scheme -  Other  ETFs") == "Other Scheme - Other ETFs"

    def test_collapses_tab(self) -> None:
        assert normalize("Debt\tScheme - Liquid Fund") == "Debt Scheme - Liquid Fund"

    def test_curly_right_apostrophe(self) -> None:
        result = normalize("Solution Oriented Scheme - Children’s Fund")
        assert result == "Solution Oriented Scheme - Children's Fund"

    def test_curly_left_apostrophe(self) -> None:
        result = normalize("Solution Oriented Scheme - Children‘s Fund")
        assert result == "Solution Oriented Scheme - Children's Fund"


# ---------------------------------------------------------------------------
# All 42 canonical leaves
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("leaf", sorted(_CANONICAL_LEAVES))
def test_canonical_leaf_exact_match(leaf: str) -> None:
    """Every canonical leaf classifies as canonical and round-trips to itself."""
    result = classify(leaf)
    assert result.status == "canonical", f"Expected canonical for {leaf!r}, got {result.status!r}"
    assert result.canonical == leaf
    assert result.scheme_class is not None
    # scheme_class must be the part before " - "
    assert leaf.startswith(result.scheme_class)


# ---------------------------------------------------------------------------
# Specific canonical cases
# ---------------------------------------------------------------------------


def test_elss_legacy_maps_to_canonical() -> None:
    result = classify("ELSS")
    assert result.status == "canonical"
    assert result.canonical == "Equity Scheme - ELSS"
    assert result.scheme_class == "Equity Scheme"


def test_double_space_normalizes_to_canonical() -> None:
    """'Other Scheme - Other  ETFs' (double space) → canonical."""
    result = classify("Other Scheme - Other  ETFs")
    assert result.status == "canonical"
    assert result.canonical == "Other Scheme - Other ETFs"


def test_curly_apostrophe_normalizes_to_canonical() -> None:
    """Children’s Fund (curly right apostrophe) → canonical."""
    result = classify("Solution Oriented Scheme - Children’s Fund")
    assert result.status == "canonical"
    assert result.canonical == "Solution Oriented Scheme - Children's Fund"


def test_padded_whitespace_canonical() -> None:
    """Leading/trailing spaces stripped → canonical."""
    result = classify("  Equity Scheme - Large Cap Fund  ")
    assert result.status == "canonical"
    assert result.canonical == "Equity Scheme - Large Cap Fund"


def test_sectoral_thematic_with_space_after_slash() -> None:
    """The canonical form keeps the space after the slash."""
    result = classify("Equity Scheme - Sectoral/ Thematic")
    assert result.status == "canonical"
    assert result.canonical == "Equity Scheme - Sectoral/ Thematic"


# ---------------------------------------------------------------------------
# Scheme class extraction
# ---------------------------------------------------------------------------


def test_scheme_class_debt() -> None:
    result = classify("Debt Scheme - Liquid Fund")
    assert result.scheme_class == "Debt Scheme"


def test_scheme_class_equity_from_legacy() -> None:
    """ELSS maps to canonical; its class should be Equity Scheme."""
    result = classify("ELSS")
    assert result.scheme_class == "Equity Scheme"


def test_scheme_class_hybrid() -> None:
    result = classify("Hybrid Scheme - Arbitrage Fund")
    assert result.scheme_class == "Hybrid Scheme"


def test_scheme_class_solution_oriented() -> None:
    result = classify("Solution Oriented Scheme - Retirement Fund")
    assert result.scheme_class == "Solution Oriented Scheme"


def test_scheme_class_other() -> None:
    result = classify("Other Scheme - Gold ETF")
    assert result.scheme_class == "Other Scheme"


# ---------------------------------------------------------------------------
# Legacy unmappable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", sorted(_LEGACY_UNMAPPABLE))
def test_legacy_unmappable(raw: str) -> None:
    result = classify(raw)
    assert result.status == "legacy", f"Expected legacy for {raw!r}"
    assert result.canonical is None
    assert result.scheme_class is None


def test_gilt_legacy() -> None:
    result = classify("Gilt")
    assert result.status == "legacy"
    assert result.canonical is None


def test_growth_legacy() -> None:
    result = classify("Growth")
    assert result.status == "legacy"
    assert result.canonical is None


def test_income_legacy() -> None:
    result = classify("Income")
    assert result.status == "legacy"
    assert result.canonical is None


def test_money_market_legacy() -> None:
    result = classify("Money Market")
    assert result.status == "legacy"
    assert result.canonical is None


# ---------------------------------------------------------------------------
# Unknown
# ---------------------------------------------------------------------------


def test_unknown_category() -> None:
    result = classify("Equity Scheme - Banana Fund")
    assert result.status == "unknown"
    assert result.canonical is None
    assert result.scheme_class is None


def test_unknown_arbitrary_string() -> None:
    result = classify("something completely made up")
    assert result.status == "unknown"


# ---------------------------------------------------------------------------
# Empty
# ---------------------------------------------------------------------------


def test_empty_none() -> None:
    result = classify(None)
    assert result.status == "empty"
    assert result.canonical is None
    assert result.normalized is None
    assert result.scheme_class is None


def test_empty_string() -> None:
    result = classify("")
    assert result.status == "empty"


def test_empty_whitespace_only() -> None:
    result = classify("   ")
    assert result.status == "empty"


# ---------------------------------------------------------------------------
# canonical_for convenience
# ---------------------------------------------------------------------------


def test_canonical_for_known() -> None:
    assert canonical_for("Debt Scheme - Liquid Fund") == "Debt Scheme - Liquid Fund"


def test_canonical_for_elss() -> None:
    assert canonical_for("ELSS") == "Equity Scheme - ELSS"


def test_canonical_for_unknown_returns_none() -> None:
    assert canonical_for("Not A Real Category") is None


def test_canonical_for_none_returns_none() -> None:
    assert canonical_for(None) is None


# ---------------------------------------------------------------------------
# summarize()
# ---------------------------------------------------------------------------


def test_summarize_empty_iterable() -> None:
    s = summarize([])
    assert s.total == 0
    assert s.counts == {"canonical": 0, "legacy": 0, "unknown": 0, "empty": 0}
    assert s.unknown_samples == []
    assert s.legacy_samples == []


def test_summarize_mixed_batch() -> None:
    batch: list[str | None] = [
        "Equity Scheme - Large Cap Fund",   # canonical
        "Debt Scheme - Liquid Fund",         # canonical
        "ELSS",                              # canonical (via legacy map)
        "Gilt",                              # legacy
        "Growth",                            # legacy
        "Equity Scheme - Banana Fund",       # unknown
        None,                                # empty
        "",                                  # empty
        "   ",                               # empty
    ]
    s = summarize(batch)
    assert s.total == 9
    assert s.counts["canonical"] == 3
    assert s.counts["legacy"] == 2
    assert s.counts["unknown"] == 1
    assert s.counts["empty"] == 3


def test_summarize_unknown_samples_distinct_sorted() -> None:
    batch = [
        "Fake Cat Z",
        "Fake Cat A",
        "Fake Cat Z",  # duplicate — only one sample
        "Fake Cat M",
    ]
    s = summarize(batch)
    assert s.counts["unknown"] == 4
    # Distinct samples, sorted
    assert s.unknown_samples == ["Fake Cat A", "Fake Cat M", "Fake Cat Z"]


def test_summarize_legacy_samples_distinct_sorted() -> None:
    batch = ["Gilt", "Growth", "Gilt", "Income"]
    s = summarize(batch)
    assert s.counts["legacy"] == 4
    assert s.legacy_samples == ["Gilt", "Growth", "Income"]


def test_summarize_samples_capped_at_20() -> None:
    # 25 distinct unknown values → only 20 samples returned
    batch = [f"Unknown Fund {i:02d}" for i in range(25)]
    s = summarize(batch)
    assert s.counts["unknown"] == 25
    assert len(s.unknown_samples) == 20


def test_summarize_all_canonical() -> None:
    s = summarize(list(_CANONICAL_LEAVES))
    assert s.total == len(_CANONICAL_LEAVES)
    assert s.counts["canonical"] == len(_CANONICAL_LEAVES)
    assert s.counts["unknown"] == 0
    assert s.counts["legacy"] == 0


# ---------------------------------------------------------------------------
# Guard test: _navrows_to_fund_upserts never mutates the raw category key
# ---------------------------------------------------------------------------


def test_navrows_to_fund_upserts_cohort_key_invariant() -> None:
    """The raw ``category`` cohort key must be preserved exactly; ``sebi_category``
    must carry the canonical value (or None for unmappable inputs).

    This test imports the real NavRow dataclass and the real mapping function so
    any future edit that inadvertently mutates ``category`` in the upsert dict
    will cause this test to fail immediately.
    """
    import datetime

    from dhanradar.market_data.amfi import NavRow
    from dhanradar.tasks.mf import _navrows_to_fund_upserts

    row_canonical = NavRow(
        amfi_code="119551",
        isin_growth="INF179KB1HA2",
        isin_reinvest=None,
        scheme_name="Nippon India Large Cap Fund - Growth",
        nav=78.4321,
        nav_date=datetime.date(2026, 6, 13),
        category="Equity Scheme - Large Cap Fund",
    )
    row_legacy = NavRow(
        amfi_code="100033",
        isin_growth="INF209K01YQ6",
        isin_reinvest=None,
        scheme_name="Aditya Birla Sun Life Gilt Fund - Regular Growth",
        nav=92.1234,
        nav_date=datetime.date(2026, 6, 13),
        category="Gilt",
    )

    result = _navrows_to_fund_upserts([row_canonical, row_legacy])
    by_isin = {d["isin"]: d for d in result}

    # Canonical row
    d_canonical = by_isin["INF179KB1HA2"]
    assert d_canonical["category"] == "Equity Scheme - Large Cap Fund", (
        "Raw category cohort key must not be mutated"
    )
    assert d_canonical["sebi_category"] == "Equity Scheme - Large Cap Fund"

    # Legacy/unmappable row
    d_legacy = by_isin["INF209K01YQ6"]
    assert d_legacy["category"] == "Gilt", (
        "Raw category cohort key must not be mutated"
    )
    assert d_legacy["sebi_category"] is None
