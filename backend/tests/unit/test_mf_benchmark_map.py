"""Unit tests for Phase 4c pt3 — dhanradar.mf.benchmark_map (pure name -> index_key match)."""

from __future__ import annotations

from dhanradar.mf.benchmark_map import (
    NIFTY50_TRI,
    NIFTY100_TRI,
    NIFTY500_MULTICAP_502525_TRI,
    NIFTY500_TRI,
    NIFTY_FINANCIAL_SERVICES_TRI,
    NIFTY_INDIA_CONSUMPTION_TRI,
    NIFTY_LARGEMIDCAP250_TRI,
    NIFTY_MIDCAP150_TRI,
    NIFTY_SMALLCAP250_TRI,
    candidate_index_key,
    normalize_benchmark_name,
)

# ---------------------------------------------------------------------------
# normalize_benchmark_name
# ---------------------------------------------------------------------------


def test_normalize_collapses_whitespace_and_casefolds():
    assert normalize_benchmark_name("  Nifty   50   TRI  ") == "nifty 50 tri"


def test_normalize_unifies_total_return_index_phrasing():
    assert normalize_benchmark_name("NIFTY 500 Total Return Index") == "nifty 500 tri"
    assert normalize_benchmark_name("Nifty 500 Total Returns Index") == "nifty 500 tri"


def test_normalize_unifies_parenthesized_tri():
    assert normalize_benchmark_name("Nifty 500 (TRI)") == "nifty 500 tri"


def test_normalize_strips_trailing_index_word_only():
    # trailing "index" is stripped …
    assert normalize_benchmark_name("Nifty 50 Index") == "nifty 50"
    # … but a non-trailing "index" (part of a longer disclosed name) survives.
    assert "index" in normalize_benchmark_name("NIFTY Banking & PSU Debt Index A-II")


def test_normalize_handles_no_space_before_number():
    assert normalize_benchmark_name("Nifty500TRI") == "nifty 500 tri"
    # Words already space-separated (real AMFI text); only the digit is glued on.
    assert normalize_benchmark_name("Nifty Midcap150 TRI") == "nifty midcap 150 tri"


def test_normalize_empty_string():
    assert normalize_benchmark_name("") == ""


# ---------------------------------------------------------------------------
# candidate_index_key — confident matches
# ---------------------------------------------------------------------------


def test_candidate_index_key_nifty_500_tri():
    assert candidate_index_key("Nifty 500 TRI") == NIFTY500_TRI


def test_candidate_index_key_nifty_50_tri():
    assert candidate_index_key("Nifty 50 TRI") == NIFTY50_TRI


def test_candidate_index_key_midcap_150_tri_variants():
    assert candidate_index_key("NIFTY Midcap 150 TRI") == NIFTY_MIDCAP150_TRI
    assert candidate_index_key("Nifty Mid Cap 150 Total Return Index") == NIFTY_MIDCAP150_TRI


def test_candidate_index_key_smallcap_250_tri_variants():
    assert candidate_index_key("NIFTY Smallcap 250 TRI") == NIFTY_SMALLCAP250_TRI
    assert candidate_index_key("Nifty Small Cap 250 (TRI)") == NIFTY_SMALLCAP250_TRI


def test_candidate_index_key_500_checked_before_50_in_ordering():
    # "nifty 500 tri" contains "nifty 50" as a leading substring — must resolve to
    # nifty500_tri, not a false-positive nifty50_tri match.
    assert candidate_index_key("Nifty 500 TRI") == NIFTY500_TRI


def test_candidate_index_key_exact_spelling_forms_still_map():
    # Review fix (PR #565): exact-equality-after-normalization must keep mapping the
    # legitimate spelling variants of the canonical names.
    assert candidate_index_key("NIFTY 50 TRI") == NIFTY50_TRI
    assert candidate_index_key("Nifty500 (TRI)") == NIFTY500_TRI
    assert candidate_index_key("NIFTY Midcap150 Total Return Index") == NIFTY_MIDCAP150_TRI


# ---------------------------------------------------------------------------
# candidate_index_key — honest-fallback: None on anything not confidently mapped
# ---------------------------------------------------------------------------


def test_candidate_index_key_none_for_unrelated_debt_index():
    assert candidate_index_key("NIFTY Banking & PSU Debt Index A-II") is None


def test_candidate_index_key_none_for_unmapped_tri_index():
    # Has "TRI" but "Total Market" is not one of our 4 canonical series.
    assert candidate_index_key("NIFTY Total Market TRI") is None


def test_candidate_index_key_none_without_tri_signal():
    # Bare index name, no TRI/Total Return signal — not assumed to be the TRI series.
    assert candidate_index_key("Nifty 50") is None
    assert candidate_index_key("Nifty 500") is None


def test_candidate_index_key_none_for_ambiguous_variant():
    assert candidate_index_key("Nifty 50 Equal Weight TRI") is None
    assert candidate_index_key("Nifty 500 Value 50 TRI") is None
    assert candidate_index_key("Nifty50 ESG TRI") is None


def test_candidate_index_key_none_for_empty_or_none_input():
    assert candidate_index_key("") is None


def test_candidate_index_key_none_for_hybrid_benchmark():
    assert candidate_index_key("Nifty 50 Hybrid Composite Debt 65:35 Index") is None


def test_candidate_index_key_none_for_strings_containing_a_canonical_name():
    # Review fix (PR #565): these real AMFI benchmark strings CONTAIN a canonical index
    # name but denote a DIFFERENT index — the old substring matcher mis-mapped all three.
    # Exact-equality-after-normalization is the gate; no qualifier blacklist can
    # enumerate these.
    assert candidate_index_key("NIFTY 50 Hybrid Composite Debt 65:35 Index TRI") is None
    assert candidate_index_key("Nifty 50 Arbitrage TRI") is None
    # NOTE: "NIFTY500 Multicap 50:25:25 TRI" was ALSO asserted None here pre-Phase-4c-pt5
    # — it has since become a genuine canonical key (verified live against
    # niftyindices.com 2026-07-12; same underlying index as "NIFTY 500 Multicap
    # 50:25:25 Total Return Index", just an abbreviated TRI spelling with no space
    # before "500"). See test_candidate_index_key_500_multicap_502525_tri_variants
    # below — this is a deliberate behavior change, not a regression.


# ---------------------------------------------------------------------------
# candidate_index_key — 5 new canonical keys (Phase 4c pt5, 2026-07-12)
# ---------------------------------------------------------------------------


def test_candidate_index_key_nifty_100_tri():
    assert candidate_index_key("Nifty 100 TRI") == NIFTY100_TRI


def test_candidate_index_key_largemidcap_250_tri():
    assert candidate_index_key("Nifty LargeMidcap 250 TRI") == NIFTY_LARGEMIDCAP250_TRI


def test_candidate_index_key_india_consumption_tri():
    assert candidate_index_key("Nifty India Consumption TRI") == NIFTY_INDIA_CONSUMPTION_TRI


def test_candidate_index_key_financial_services_tri():
    assert candidate_index_key("Nifty Financial Services TRI") == NIFTY_FINANCIAL_SERVICES_TRI


def test_candidate_index_key_500_multicap_502525_tri_variants():
    assert (
        candidate_index_key("NIFTY 500 Multicap 50:25:25 Total Return Index")
        == NIFTY500_MULTICAP_502525_TRI
    )
    # Abbreviated "TRI" spelling, no space before "500" — normalizes to the same key.
    assert candidate_index_key("NIFTY500 Multicap 50:25:25 TRI") == NIFTY500_MULTICAP_502525_TRI


def test_candidate_index_key_none_for_nifty_100_near_miss_variants():
    # Real AMFI strings observed in the SAME top-30 sweep — genuinely different indices.
    assert candidate_index_key("NIFTY 100 Equal Weighted TRI") is None
    assert candidate_index_key("Nifty 100 ESG TRI") is None
    assert candidate_index_key("Nifty 100 ESG Sector Leaders TRI") is None
    assert candidate_index_key("Nifty 100 Low Volatility 30 TRI") is None
    assert candidate_index_key("Nifty 100 Quality 30 TRI") is None


def test_candidate_index_key_none_for_financial_services_near_miss_variants():
    assert candidate_index_key("Nifty Financial Services Ex-Bank TRI") is None
    assert candidate_index_key("Nifty MidSmall Financial Services TRI") is None


def test_candidate_index_key_none_for_largemidcap_near_miss_variant():
    assert candidate_index_key("Nifty LargeMidcap250 Plus 8-13 yr G-Sec 70:30 TRI") is None


def test_candidate_index_key_none_for_multicap_near_miss_variants():
    # Different weighting scheme (50:30:20 vs the canonical 50:25:25) or an added
    # thematic qualifier — genuinely different indices, must stay unmapped.
    assert candidate_index_key("Nifty500 Multicap India Manufacturing 50:30:20 TRI") is None
    assert candidate_index_key("Nifty500 Multicap Infrastructure 50:30:20 TRI") is None
    assert candidate_index_key("Nifty500 Multicap Momentum Quality 50 TRI") is None


def test_candidate_index_key_none_for_india_consumption_near_miss_variant():
    assert candidate_index_key("Nifty MidSmall India Consumption TRI") is None
