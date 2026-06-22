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
    derive_short_name,
    normalize,
    parse_idcw_frequency,
    parse_plan_option,
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


# ---------------------------------------------------------------------------
# parse_plan_option (B67 Task 3) — pure function, no DB, no network
# ---------------------------------------------------------------------------


class TestParsePlanOption:
    """parse_plan_option: case-insensitive scheme-name parsing of plan/option."""

    # --- plan_type: Direct -----------------------------------------------

    def test_direct_plan_hyphen_separated(self) -> None:
        pt, ot = parse_plan_option("Nippon India Large Cap Fund - Direct Plan - Growth")
        assert pt == "direct"

    def test_direct_without_plan_word(self) -> None:
        """'Axis ELSS Tax Saver Fund Direct Growth' — no 'Plan' separator."""
        pt, _ = parse_plan_option("Axis ELSS Tax Saver Fund Direct Growth")
        assert pt == "direct"

    def test_direct_case_insensitive(self) -> None:
        pt, _ = parse_plan_option("SBI NIFTY INDEX FUND DIRECT GROWTH")
        assert pt == "direct"

    def test_direct_mixed_case(self) -> None:
        pt, _ = parse_plan_option("Mirae Asset Large Cap Fund - DiReCt Plan - Growth")
        assert pt == "direct"

    # --- plan_type: Regular -----------------------------------------------

    def test_regular_plan_hyphen_separated(self) -> None:
        pt, _ = parse_plan_option("HDFC Mid-Cap Opportunities Fund - Regular Plan - IDCW")
        assert pt == "regular"

    def test_regular_without_plan_word(self) -> None:
        pt, _ = parse_plan_option("Aditya Birla Sun Life Regular Savings Fund - Growth")
        assert pt == "regular"

    # --- plan_type: direct wins over regular in fund name ----------------

    def test_direct_wins_over_regular_in_fund_name(self) -> None:
        """'ICICI Prudential Regular Savings Fund - Direct Plan - Growth'
        has 'regular' in the fund name but 'direct' in the plan tag."""
        pt, _ = parse_plan_option(
            "ICICI Prudential Regular Savings Fund - Direct Plan - Growth"
        )
        assert pt == "direct"

    # --- plan_type: None --------------------------------------------------

    def test_no_plan_marker_returns_none(self) -> None:
        """Legacy scheme name with no Direct/Regular tag."""
        pt, _ = parse_plan_option("Reliance Growth Fund")
        assert pt is None

    # --- option_type: Growth ----------------------------------------------

    def test_growth_option(self) -> None:
        _, ot = parse_plan_option("Nippon India Large Cap Fund - Direct Plan - Growth")
        assert ot == "growth"

    def test_growth_no_separator(self) -> None:
        _, ot = parse_plan_option("Axis ELSS Tax Saver Fund Direct Growth")
        assert ot == "growth"

    # --- option_type: IDCW ------------------------------------------------

    def test_idcw_bare(self) -> None:
        _, ot = parse_plan_option("HDFC Mid-Cap Opportunities Fund - Regular Plan - IDCW")
        assert ot == "idcw"

    def test_idcw_case_insensitive(self) -> None:
        _, ot = parse_plan_option("Some Fund - Direct Plan - iDcW")
        assert ot == "idcw"

    def test_bare_dividend_maps_to_idcw(self) -> None:
        """Pre-2021 'Dividend' option → idcw (SEBI nomenclature change)."""
        _, ot = parse_plan_option("Aditya Birla Sun Life Frontline Equity Fund - Dividend")
        assert ot == "idcw"

    # --- option_type: dividend_reinvest -----------------------------------

    def test_dividend_reinvestment_option(self) -> None:
        _, ot = parse_plan_option(
            "ICICI Prudential Value Discovery Fund - Regular Plan - Dividend Reinvestment"
        )
        assert ot == "dividend_reinvest"

    def test_idcw_reinvestment_option(self) -> None:
        _, ot = parse_plan_option("Axis Bluechip Fund - Direct Plan - IDCW Reinvestment")
        assert ot == "dividend_reinvest"

    def test_idcw_reinvest_short_form(self) -> None:
        _, ot = parse_plan_option("Some Fund - Regular - IDCW Reinvest")
        assert ot == "dividend_reinvest"

    # --- option_type: dividend_payout -------------------------------------

    def test_dividend_payout_option(self) -> None:
        _, ot = parse_plan_option(
            "HDFC Mid-Cap Opportunities Fund - Regular Plan - Dividend Payout"
        )
        assert ot == "dividend_payout"

    def test_idcw_payout_option(self) -> None:
        _, ot = parse_plan_option("Franklin India Prima Fund - Direct Plan - IDCW Payout")
        assert ot == "dividend_payout"

    # --- option_type: None ------------------------------------------------

    def test_no_option_marker_returns_none(self) -> None:
        _, ot = parse_plan_option("Reliance Gilt Securities Fund - Regular Plan")
        assert ot is None

    # --- edge cases -------------------------------------------------------

    def test_none_input_returns_none_none(self) -> None:
        assert parse_plan_option(None) == (None, None)  # type: ignore[arg-type]

    def test_empty_string_returns_none_none(self) -> None:
        assert parse_plan_option("") == (None, None)

    def test_whitespace_only_returns_none_none(self) -> None:
        assert parse_plan_option("   ") == (None, None)

    def test_non_str_returns_none_none(self) -> None:
        assert parse_plan_option(123) == (None, None)  # type: ignore[arg-type]

    def test_both_none_on_bare_scheme_name(self) -> None:
        pt, ot = parse_plan_option("UTI Nifty Index Fund")
        assert pt is None
        assert ot is None

    def test_full_name_direct_growth(self) -> None:
        """End-to-end: typical modern Direct Growth name."""
        pt, ot = parse_plan_option(
            "SBI Bluechip Fund - Direct Plan - Growth"
        )
        assert pt == "direct"
        assert ot == "growth"

    def test_full_name_regular_idcw(self) -> None:
        """End-to-end: Regular IDCW."""
        pt, ot = parse_plan_option(
            "Kotak Bluechip Fund - Regular Plan - IDCW"
        )
        assert pt == "regular"
        assert ot == "idcw"

    def test_full_name_direct_dividend_reinvest(self) -> None:
        """End-to-end: Direct + Dividend Reinvestment."""
        pt, ot = parse_plan_option(
            "Mirae Asset Large Cap Fund - Direct Plan - Dividend Reinvestment"
        )
        assert pt == "direct"
        assert ot == "dividend_reinvest"

    def test_idcw_reinvest_beats_bare_idcw(self) -> None:
        """'IDCW Reinvestment' must map to dividend_reinvest, not plain idcw."""
        _, ot = parse_plan_option("Any Fund - Direct - IDCW Reinvestment")
        assert ot == "dividend_reinvest"

    def test_dividend_reinvest_beats_bare_dividend(self) -> None:
        """'Dividend Reinvestment' must map to dividend_reinvest, not plain idcw."""
        _, ot = parse_plan_option("Any Fund - Regular - Dividend Reinvestment")
        assert ot == "dividend_reinvest"


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


# ---------------------------------------------------------------------------
# parse_plan_option — retail / institutional (B72 follow-up) — pure function
# ---------------------------------------------------------------------------


class TestParsePlanOptionRetailInstitutional:
    def test_retail_plan(self) -> None:
        pt, _ = parse_plan_option("Franklin India Bluechip Fund - Retail Plan - Growth")
        assert pt == "retail"

    def test_institutional_plan(self) -> None:
        pt, _ = parse_plan_option("ICICI Prudential Liquid Fund - Institutional Plan - Growth")
        assert pt == "institutional"

    def test_direct_wins_over_retail(self) -> None:
        """Modern direct/regular tag wins over the older retail class."""
        pt, _ = parse_plan_option("Some Retail Series Fund - Direct Plan - Growth")
        assert pt == "direct"

    def test_regular_wins_over_institutional(self) -> None:
        pt, _ = parse_plan_option(
            "Some Institutional Series Fund - Regular Plan - Growth"
        )
        assert pt == "regular"

    def test_institutional_fits_widened_column(self) -> None:
        """'institutional' is 13 chars — must fit mf_funds.plan_type String(20)."""
        assert len("institutional") <= 20


# ---------------------------------------------------------------------------
# parse_idcw_frequency — pure function, no DB / no network
# ---------------------------------------------------------------------------


class TestParseIdcwFrequency:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("HDFC Liquid Fund - Direct Plan - Daily IDCW", "daily"),
            ("SBI Magnum Fund - Regular Plan - Weekly IDCW Reinvestment", "weekly"),
            ("Some Debt Fund - Direct - Fortnightly IDCW", "fortnightly"),
            ("Axis Fund - Regular Plan - Monthly IDCW Payout", "monthly"),
            ("Kotak Bond Fund - Direct Plan - Quarterly Dividend", "quarterly"),
            ("Nippon Fund - Regular Plan - Half Yearly IDCW", "half_yearly"),
            ("Nippon Fund - Regular Plan - Half-Yearly IDCW", "half_yearly"),
            ("UTI Fund - Direct Plan - Annual IDCW", "annual"),
            ("UTI Fund - Direct Plan - Annually IDCW", "annual"),
            ("ABC Fund - Regular Plan - Yearly IDCW", "annual"),
        ],
    )
    def test_known_frequencies(self, name: str, expected: str) -> None:
        assert parse_idcw_frequency(name) == expected

    def test_growth_name_has_no_frequency(self) -> None:
        assert parse_idcw_frequency("SBI Bluechip Fund - Direct Plan - Growth") is None

    def test_bare_name_none(self) -> None:
        assert parse_idcw_frequency("UTI Nifty Index Fund") is None

    def test_none_and_blank(self) -> None:
        assert parse_idcw_frequency(None) is None  # type: ignore[arg-type]
        assert parse_idcw_frequency("") is None
        assert parse_idcw_frequency("   ") is None
        assert parse_idcw_frequency(123) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# derive_short_name — pure function (override map loaded once from JSON)
# ---------------------------------------------------------------------------


class TestDeriveShortName:
    """Conservative short-name derivation. The frontend reads the populated
    column instead of re-deriving, so these cases are the cross-surface contract."""

    @pytest.mark.parametrize(
        ("scheme_name", "expected"),
        [
            # Modern Direct/Regular + Growth/IDCW → brand survives, plan/option drop.
            (
                "Nippon India Large Cap Fund - Direct Plan - Growth",
                "Nippon India Large Cap Fund",
            ),
            (
                "HDFC Mid-Cap Opportunities Fund - Regular Plan - IDCW",
                "HDFC Mid-Cap Opportunities Fund",
            ),
            (
                "SBI Bluechip Fund - Direct Plan - Growth",
                "SBI Bluechip Fund",
            ),
            # No " - " separators: trailing plan/option tokens are trimmed.
            (
                "Axis ELSS Tax Saver Fund Direct Growth",
                "Axis ELSS Tax Saver Fund",
            ),
            # Reinvestment / Payout / Dividend variants stripped.
            (
                "ICICI Prudential Value Discovery Fund - Regular Plan - Dividend Reinvestment",
                "ICICI Prudential Value Discovery Fund",
            ),
            (
                "Franklin India Prima Fund - Direct Plan - IDCW Payout",
                "Franklin India Prima Fund",
            ),
            # Frequency word + option stripped together.
            (
                "HDFC Liquid Fund - Direct Plan - Daily IDCW Reinvestment",
                "HDFC Liquid Fund",
            ),
            # Retail plan stripped.
            (
                "Franklin India Bluechip Fund - Retail Plan - Growth",
                "Franklin India Bluechip Fund",
            ),
            # "(Formerly ...)" parenthetical removed; brand kept.
            (
                "Aditya Birla Sun Life Frontline Equity Fund (Formerly Birla SL Frontline) - Direct - Growth",
                "Aditya Birla Sun Life Frontline Equity Fund",
            ),
        ],
    )
    def test_derives_clean_name(self, scheme_name: str, expected: str) -> None:
        assert derive_short_name(scheme_name) == expected

    def test_brand_words_never_stripped(self) -> None:
        """'Regular Savings' / 'Growth' inside the brand must survive (first
        segment is always kept; trailing-trim stops at the first brand word)."""
        assert (
            derive_short_name(
                "ICICI Prudential Regular Savings Fund - Direct Plan - Growth"
            )
            == "ICICI Prudential Regular Savings Fund"
        )
        # 'Growth' as a brand word at the end is kept (no plan/option context).
        assert derive_short_name("Reliance Growth Fund") == "Reliance Growth Fund"

    @pytest.mark.parametrize(
        ("scheme_name", "expected"),
        [
            # Real AMFI names with UN-SPACED hyphen separators (live-feed audit:
            # these were the ~10% the ' - '-only split previously mangled).
            (
                "Aditya Birla Sun Life Banking & PSU Debt Fund - Regular Plan-Growth",
                "Aditya Birla Sun Life Banking & PSU Debt Fund",
            ),
            (
                "Bajaj Finserv Banking and PSU Fund-Direct Plan- Growth",
                "Bajaj Finserv Banking and PSU Fund",
            ),
            (
                "LIC MF Banking & PSU Fund-Direct Plan-Daily IDCW",
                "LIC MF Banking & PSU Fund",
            ),
            (
                "Nippon India Banking and PSU  Fund- Direct Plan-Growth Plan- Growth Option",
                "Nippon India Banking and PSU Fund",
            ),
            (
                "Motilal Oswal Liquid Fund Direct - IDCW Monthly Payout/Reinvestment",
                "Motilal Oswal Liquid Fund",
            ),
            # Brand-internal hyphen must survive the right-scan (cut is by index).
            (
                "HDFC Mid-Cap Opportunities Fund-Direct Plan-Growth",
                "HDFC Mid-Cap Opportunities Fund",
            ),
            # Connector word ('of') inside the option long-form must not stop the
            # scan — real live-feed name that previously left "… Plan - Payout of".
            (
                "TATA Resources & Energy Fund Direct Plan - Payout of Income "
                "Distribution cum capital withdrawal option",
                "TATA Resources & Energy Fund",
            ),
            # 'of' as a genuine brand connector must SURVIVE (scan stops at 'Fund').
            (
                "Mirae Asset ETF Fund of Fund - Regular Plan - IDCW",
                "Mirae Asset ETF Fund of Fund",
            ),
        ],
    )
    def test_unspaced_hyphen_separators(self, scheme_name: str, expected: str) -> None:
        assert derive_short_name(scheme_name) == expected

    def test_legacy_name_unchanged(self) -> None:
        assert derive_short_name("UTI Nifty Index Fund") == "UTI Nifty Index Fund"

    def test_none_and_blank(self) -> None:
        assert derive_short_name(None) is None  # type: ignore[arg-type]
        assert derive_short_name("") is None
        assert derive_short_name("   ") is None
        assert derive_short_name(123) is None  # type: ignore[arg-type]

    def test_never_over_strips_to_empty(self) -> None:
        """A name that is ALL plan/option noise falls back to the original."""
        original = "Direct Plan - Growth"
        # First segment ("Direct Plan") is always kept, so we never get "".
        assert derive_short_name(original)

    def test_override_by_isin_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Operator ISIN override pins the clean name over the heuristic."""
        import dhanradar.mf.taxonomy as tax

        monkeypatch.setattr(
            tax,
            "_OVERRIDES_CACHE",
            {"by_isin": {"INF000TEST01": "Pinned Clean Name"}, "by_scheme_name": {}},
        )
        assert (
            derive_short_name("Messy Raw Scheme Name - Direct - Growth", "INF000TEST01")
            == "Pinned Clean Name"
        )
        # Without the matching ISIN, the heuristic runs.
        assert (
            derive_short_name("Messy Raw Scheme Name - Direct - Growth", "INF000OTHER")
            == "Messy Raw Scheme Name"
        )

    def test_override_by_scheme_name_normalized(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Scheme-name override matches after normalize() (case/whitespace-folded)."""
        import dhanradar.mf.taxonomy as tax

        monkeypatch.setattr(
            tax,
            "_OVERRIDES_CACHE",
            {
                "by_isin": {},
                "by_scheme_name": {"weird fund - direct - growth": "Weird Fund (Pinned)"},
            },
        )
        # Different spacing + case still hits the normalized key.
        assert (
            derive_short_name("Weird  Fund - Direct - Growth")
            == "Weird Fund (Pinned)"
        )

    def test_override_file_loads_without_error(self) -> None:
        """The shipped JSON override file parses and yields the expected shape."""
        import dhanradar.mf.taxonomy as tax

        tax._OVERRIDES_CACHE = None  # force a real load from disk
        loaded = tax._load_overrides()
        assert set(loaded) == {"by_isin", "by_scheme_name"}
        assert isinstance(loaded["by_isin"], dict)
        assert isinstance(loaded["by_scheme_name"], dict)


def test_navrows_to_fund_upserts_populates_short_name_and_frequency() -> None:
    """The nightly upsert mapping carries fund_name_short + idcw_frequency, and
    leaves the official scheme_name intact (display-only contract)."""
    import datetime

    from dhanradar.market_data.amfi import NavRow
    from dhanradar.tasks.mf import _navrows_to_fund_upserts

    row = NavRow(
        amfi_code="119551",
        isin_growth="INF179KB1HA2",
        isin_reinvest=None,
        scheme_name="HDFC Liquid Fund - Direct Plan - Monthly IDCW Reinvestment",
        nav=78.4321,
        nav_date=datetime.date(2026, 6, 22),
        category="Debt Scheme - Liquid Fund",
    )
    out = {d["isin"]: d for d in _navrows_to_fund_upserts([row])}
    d = out["INF179KB1HA2"]
    assert d["scheme_name"] == "HDFC Liquid Fund - Direct Plan - Monthly IDCW Reinvestment"
    assert d["fund_name_short"] == "HDFC Liquid Fund"
    assert d["idcw_frequency"] == "monthly"
    assert d["plan_type"] == "direct"
    assert d["option_type"] == "dividend_reinvest"


# ---------------------------------------------------------------------------
# Property-based fuzz: derive_short_name must never mangle a brand
# ---------------------------------------------------------------------------
# No hypothesis dependency (stack-lock): we enumerate the full
# brand × plan × option × frequency × separator space deterministically.
# The invariant: appending ANY combination of plan/option/frequency noise to a
# brand must derive back to exactly that brand. Brands deliberately include the
# tricky cases where a NOISE word lives INSIDE the brand ('Regular Savings',
# 'Growth', 'Income') — those must survive because the brand is the first
# segment and trailing-trim stops at 'Fund'.

# Real-world brands; each ends in a non-noise head word ('Fund'/'ETF'), as every
# AMFI scheme name does.
_FUZZ_BRANDS: tuple[str, ...] = (
    "Nippon India Large Cap Fund",
    "ICICI Prudential Regular Savings Fund",   # 'Regular' inside the brand
    "Reliance Growth Fund",                    # 'Growth' inside the brand
    "SBI Magnum Income Fund",                  # 'Income' inside the brand
    "Aditya Birla Sun Life Frontline Equity Fund",
    "Quant Small Cap Fund",
    "UTI Nifty 50 Index Fund",
    "HDFC Mid-Cap Opportunities Fund",
    "Mirae Asset Aggressive Hybrid Fund",
    "Axis Banking & PSU Debt Fund",            # '&' in the brand
    "Kotak Gold ETF",
)
_FUZZ_PLANS = ("", "Direct", "Regular", "Retail", "Institutional")
_FUZZ_OPTIONS = (
    "", "Growth", "IDCW", "Dividend", "IDCW Reinvestment", "IDCW Payout",
    "Dividend Reinvestment", "Dividend Payout",
)
_FUZZ_FREQS = ("", "Daily", "Weekly", "Monthly", "Quarterly", "Half Yearly", "Annual")

# Advisory verbs must NEVER appear in a derived display name (non-neg #1).
_ADVISORY_VERBS = ("buy", "sell", "hold", "strong buy", "avoid", "caution")


def _fuzz_names():
    """Yield (brand, constructed_scheme_name) over the full noise space, for
    both the ' - '-separated and space-separated AMFI naming styles."""
    for brand in _FUZZ_BRANDS:
        for plan in _FUZZ_PLANS:
            for option in _FUZZ_OPTIONS:
                for freq in _FUZZ_FREQS:
                    opt_full = f"{freq} {option}".strip() if option else freq
                    parts = []
                    if plan:
                        parts.append(f"{plan} Plan")
                    if opt_full:
                        parts.append(opt_full)
                    if not parts:
                        yield brand, brand
                        continue
                    yield brand, brand + " - " + " - ".join(parts)
                    yield brand, brand + " " + " ".join(parts)


def test_derive_short_name_never_mangles_brand_property() -> None:
    """For EVERY brand × plan × option × frequency × separator combo, the brand
    survives exactly, and the result is non-empty, idempotent, and advisory-free."""
    checked = 0
    for brand, name in _fuzz_names():
        short = derive_short_name(name)
        assert short == brand, f"mangled: {name!r} -> {short!r} (want {brand!r})"
        # Non-empty + idempotent (feeding a clean name back is a fixed point).
        assert short
        assert derive_short_name(short) == short, f"not idempotent: {short!r}"
        # Compliance: no advisory verb may leak into a display name.
        low = short.lower()
        assert not any(v in low.split() for v in _ADVISORY_VERBS), f"advisory leak: {short!r}"
        checked += 1
    # Sanity: the space actually got enumerated (guards a silently-empty generator).
    assert checked > 1500, f"fuzz space too small: {checked}"
