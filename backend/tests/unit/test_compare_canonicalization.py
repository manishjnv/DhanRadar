"""Batch C (audit 2026-08-22): canonical-variant selection for /mf/compare/bundle
and the ±50% AUM-change artifact guard.

Repro: an IDCW "HDFC Small Cap" variant showed 1Y −9.45% / rank 142/143 (payout-
distorted NAV series), and a "−99.5%" AUM event was a plan-variant scale artifact.
"""

from __future__ import annotations

from datetime import date

from dhanradar.mf.compare_read import _pick_canonicals, variant_rank
from dhanradar.mf.fund_events import detect_aum_change
from dhanradar.mf.fund_read import _is_aum_artifact


def test_variant_rank_prefers_direct_growth_then_growth_then_lowest_isin() -> None:
    ranks = sorted(
        [
            variant_rank("regular", "idcw", "AAA"),
            variant_rank("direct", "growth", "ZZZ"),
            variant_rank(None, "growth", "BBB"),
            variant_rank("direct", "idcw", "CCC"),
        ]
    )
    assert ranks[0] == variant_rank("direct", "growth", "ZZZ")
    assert ranks[1] == variant_rank("direct", "idcw", "CCC")
    assert ranks[2] == variant_rank(None, "growth", "BBB")


def test_pick_canonicals_maps_variant_to_direct_growth_sibling() -> None:
    siblings = [
        ("IDCW00000001", "HDFC Small Cap", "regular", "idcw"),
        ("DIRGROWTH001", "HDFC Small Cap", "direct", "growth"),
    ]
    out = _pick_canonicals(["IDCW00000001"], {"IDCW00000001": "HDFC Small Cap"}, siblings)
    assert out == {"IDCW00000001": "DIRGROWTH001"}


def test_pick_canonicals_unknown_isin_passes_through() -> None:
    out = _pick_canonicals(["UNKNOWN00001"], {}, [])
    assert out == {"UNKNOWN00001": "UNKNOWN00001"}


def test_pick_canonicals_collision_keeps_second_requests_original() -> None:
    siblings = [
        ("VAR100000001", "Same Scheme", "regular", "growth"),
        ("VAR200000002", "Same Scheme", "regular", "idcw"),
        ("CANON0000001", "Same Scheme", "direct", "growth"),
    ]
    short_by = {"VAR100000001": "Same Scheme", "VAR200000002": "Same Scheme"}
    out = _pick_canonicals(["VAR100000001", "VAR200000002"], short_by, siblings)
    # First request gets the canonical; second keeps its own ISIN — never a self-compare.
    assert out["VAR100000001"] == "CANON0000001"
    assert out["VAR200000002"] == "VAR200000002"


def test_detect_aum_change_suppresses_redenomination_artifacts() -> None:
    as_of = date(2026, 8, 1)
    # −99.5% (the founder-observed artifact) → suppressed.
    assert detect_aum_change(old_aum_crore=38918.19, new_aum_crore=209.58, as_of_month=as_of) is None
    # A real 20% move still emits.
    emitted = detect_aum_change(old_aum_crore=100.0, new_aum_crore=120.0, as_of_month=as_of)
    assert emitted is not None and emitted["direction"] == "up"


def test_read_side_filter_hides_stored_aum_artifacts() -> None:
    assert _is_aum_artifact("aum_change", {"pct_change": -99.5}) is True
    assert _is_aum_artifact("aum_change", {"pct_change": -20.0}) is False
    assert _is_aum_artifact("ter_change", {"pct_change": -99.5}) is False
