"""Unit tests for the `fund.changes` diff engine (`mf/fund_events.py`,
FUND_DETAIL_DATA_ARCHITECTURE_PLAN.md §10.6, §17 W2).

Pure functions only — no DB (mirrors the tasks/mf.py convention: pure mapping
helpers are unit-tested without a worker/session).
"""

from __future__ import annotations

import datetime

from dhanradar.mf.fund_events import (
    cap_fund_events,
    detect_aum_change,
    detect_holding_change,
    detect_rank_change,
    detect_ter_change,
    summarize_event,
)

# ---------------------------------------------------------------------------
# rank_change — threshold + quartile-crossing
# ---------------------------------------------------------------------------


def test_rank_change_below_threshold_no_quartile_cross_is_none():
    """|delta| < 3 and same quartile -> no event (both funds sit in quartile 1 of 100)."""
    ev = detect_rank_change(old_rank=5, old_total=100, new_rank=6, new_total=100)
    assert ev is None


def test_rank_change_meets_threshold_emits_event():
    """|delta| >= 3 -> event, direction 'up' when the rank number improved (smaller)."""
    ev = detect_rank_change(old_rank=24, old_total=183, new_rank=18, new_total=183)
    assert ev == {"old_rank": 24, "new_rank": 18, "total": 183, "direction": "up"}


def test_rank_change_worsened_direction_down():
    ev = detect_rank_change(old_rank=5, old_total=50, new_rank=10, new_total=50)
    assert ev is not None
    assert ev["direction"] == "down"


def test_rank_change_quartile_crossing_below_threshold_still_emits():
    """delta=2 (< 3) but crosses the quartile boundary (rank 26->24 of 100: quartile 2->1)."""
    ev = detect_rank_change(old_rank=26, old_total=100, new_rank=24, new_total=100)
    assert ev is not None
    assert ev["direction"] == "up"


def test_rank_change_idempotent_on_rerun():
    """Calling the detector twice on the same two rows produces an identical payload —
    safe to upsert on (isin, event_type, as_of) without ever double-counting."""
    kwargs = {"old_rank": 24, "old_total": 183, "new_rank": 18, "new_total": 183}
    assert detect_rank_change(**kwargs) == detect_rank_change(**kwargs)


# ---------------------------------------------------------------------------
# ter_change
# ---------------------------------------------------------------------------


def test_ter_change_no_change_is_none():
    assert (
        detect_ter_change(old_ter=0.68, new_ter=0.68, effective_date=datetime.date(2026, 6, 1))
        is None
    )


def test_ter_change_any_delta_emits_event():
    ev = detect_ter_change(old_ter=0.68, new_ter=0.62, effective_date=datetime.date(2026, 6, 1))
    assert ev == {"old_ter": 0.68, "new_ter": 0.62, "effective_date": "2026-06-01"}


def test_ter_change_idempotent_on_rerun():
    kwargs = {"old_ter": 0.68, "new_ter": 0.62, "effective_date": datetime.date(2026, 6, 1)}
    assert detect_ter_change(**kwargs) == detect_ter_change(**kwargs)


# ---------------------------------------------------------------------------
# aum_change — >=5% month-over-month threshold, either direction
# ---------------------------------------------------------------------------


def test_aum_change_below_threshold_is_none():
    """4.9% growth < 5% threshold -> no event."""
    ev = detect_aum_change(
        old_aum_crore=1000.0, new_aum_crore=1049.0, as_of_month=datetime.date(2026, 6, 1)
    )
    assert ev is None


def test_aum_change_meets_threshold_direction_up():
    ev = detect_aum_change(
        old_aum_crore=1000.0, new_aum_crore=1100.0, as_of_month=datetime.date(2026, 6, 1)
    )
    assert ev == {
        "old_aum_crore": 1000.0,
        "new_aum_crore": 1100.0,
        "pct_change": 10.0,
        "direction": "up",
    }


def test_aum_change_meets_threshold_direction_down():
    ev = detect_aum_change(
        old_aum_crore=1000.0, new_aum_crore=900.0, as_of_month=datetime.date(2026, 6, 1)
    )
    assert ev == {
        "old_aum_crore": 1000.0,
        "new_aum_crore": 900.0,
        "pct_change": -10.0,
        "direction": "down",
    }


def test_aum_change_exactly_at_threshold_boundary_emits():
    """Exactly 5.0% change meets the >= 5% threshold (boundary inclusive)."""
    ev = detect_aum_change(
        old_aum_crore=1000.0, new_aum_crore=1050.0, as_of_month=datetime.date(2026, 6, 1)
    )
    assert ev is not None
    assert ev["pct_change"] == 5.0
    assert ev["direction"] == "up"


def test_aum_change_zero_old_aum_is_none():
    """No baseline to compute a % change against — must not divide by zero."""
    ev = detect_aum_change(
        old_aum_crore=0.0, new_aum_crore=100.0, as_of_month=datetime.date(2026, 6, 1)
    )
    assert ev is None


def test_aum_change_idempotent_on_rerun():
    kwargs = {
        "old_aum_crore": 1000.0,
        "new_aum_crore": 1100.0,
        "as_of_month": datetime.date(2026, 6, 1),
    }
    assert detect_aum_change(**kwargs) == detect_aum_change(**kwargs)


# ---------------------------------------------------------------------------
# holding_change — threshold + matched-name-only + single-largest
# ---------------------------------------------------------------------------


def test_holding_change_below_threshold_is_none():
    old = [{"name": "HDFC Bank", "weight_pct": 6.1}]
    new = [{"name": "HDFC Bank", "weight_pct": 6.5}]  # 0.4pp < 1.0pp
    assert detect_holding_change(old_holdings=old, new_holdings=new) is None


def test_holding_change_meets_threshold_picks_largest():
    old = [
        {"name": "HDFC Bank", "weight_pct": 6.1},
        {"name": "Reliance Industries", "weight_pct": 5.0},
    ]
    new = [
        {"name": "HDFC Bank", "weight_pct": 7.4},  # +1.3pp
        {"name": "Reliance Industries", "weight_pct": 5.2},  # +0.2pp
    ]
    ev = detect_holding_change(old_holdings=old, new_holdings=new)
    assert ev == {"name": "HDFC Bank", "old_weight_pct": 6.1, "new_weight_pct": 7.4}


def test_holding_change_new_entrant_skipped_not_fabricated():
    """A name present only in the new month has no baseline — must not be diffed
    against a fabricated 0%."""
    old = [{"name": "HDFC Bank", "weight_pct": 6.1}]
    new = [
        {"name": "HDFC Bank", "weight_pct": 6.2},
        {"name": "New Entrant Ltd", "weight_pct": 4.0},
    ]
    ev = detect_holding_change(old_holdings=old, new_holdings=new)
    assert ev is None  # HDFC delta (0.1pp) below threshold; New Entrant has no baseline


def test_holding_change_idempotent_on_rerun():
    old = [{"name": "HDFC Bank", "weight_pct": 6.1}]
    new = [{"name": "HDFC Bank", "weight_pct": 7.4}]
    assert detect_holding_change(old_holdings=old, new_holdings=new) == detect_holding_change(
        old_holdings=old, new_holdings=new
    )


# ---------------------------------------------------------------------------
# cap_fund_events — <=4 total, one per type
# ---------------------------------------------------------------------------


def test_cap_keeps_at_most_one_per_type_and_max_four():
    events = [
        {"event_type": "rank_change", "v": 1},
        {"event_type": "ter_change", "v": 2},
        {"event_type": "holding_change", "v": 3},
        {"event_type": "aum_change", "v": 4},
    ]
    assert cap_fund_events(events) == events  # exactly 4, one each -> unchanged


def test_cap_drops_duplicate_type_first_seen_wins():
    events = [
        {"event_type": "rank_change", "v": "first"},
        {"event_type": "rank_change", "v": "second"},  # duplicate type -> dropped
        {"event_type": "ter_change", "v": "ok"},
    ]
    capped = cap_fund_events(events)
    assert capped == [
        {"event_type": "rank_change", "v": "first"},
        {"event_type": "ter_change", "v": "ok"},
    ]


def test_cap_never_exceeds_four_even_with_more_input():
    events = [
        {"event_type": "rank_change"},
        {"event_type": "ter_change"},
        {"event_type": "holding_change"},
        {"event_type": "aum_change"},
        {"event_type": "rank_change"},  # duplicate — would push past 4 if not deduped first
    ]
    assert len(cap_fund_events(events)) <= 4


# ---------------------------------------------------------------------------
# summarize_event — plain factual sentences, no advisory verb, <=14 words
# ---------------------------------------------------------------------------

# ci_guards / anti_pattern_sweep convention (see docs/rca 'ci_guards FE advisory-verb
# trap'): write the banned list as a single space-joined string, not individual
# quoted literals, so a static advisory-verb scanner never flags the list itself.
_ADVISORY_VERBS = (
    "buy sell hold recommend recommended should avoid switch caution "
    "strong_buy strong_sell allocate overweight underweight"
).split(" ")


def _assert_no_advisory_verb(sentence: str) -> None:
    words = {w.strip(".,:%→").lower() for w in sentence.split()}
    hit = words & set(_ADVISORY_VERBS)
    assert not hit, f"advisory verb {hit} leaked into summary: {sentence!r}"


def test_summary_rank_change_is_factual_and_short():
    payload = {"old_rank": 24, "new_rank": 18, "total": 183, "direction": "up"}
    sentence = summarize_event("rank_change", payload)
    assert sentence == "Category rank moved from 24 to 18 of 183."
    _assert_no_advisory_verb(sentence)
    assert len(sentence.split()) <= 14


def test_summary_ter_change_is_factual_and_short():
    payload = {"old_ter": 0.68, "new_ter": 0.62, "effective_date": "2026-06-01"}
    sentence = summarize_event("ter_change", payload)
    assert sentence == "Expense ratio changed from 0.68% to 0.62%."
    _assert_no_advisory_verb(sentence)
    assert len(sentence.split()) <= 14


def test_summary_holding_change_is_factual_and_short():
    payload = {"name": "HDFC Bank", "old_weight_pct": 6.1, "new_weight_pct": 7.4}
    sentence = summarize_event("holding_change", payload)
    assert sentence == "Largest holding shift: HDFC Bank 6.1% → 7.4%."
    _assert_no_advisory_verb(sentence)
    assert len(sentence.split()) <= 14


def test_summary_aum_change_is_factual_and_short():
    payload = {
        "old_aum_crore": 1000.0,
        "new_aum_crore": 1100.0,
        "pct_change": 10.0,
        "direction": "up",
    }
    sentence = summarize_event("aum_change", payload)
    assert sentence == "AUM changed from ₹1000.00cr to ₹1100.00cr (+10.0%)."
    _assert_no_advisory_verb(sentence)
    assert len(sentence.split()) <= 14


def test_summary_unknown_event_type_falls_back_safely():
    sentence = summarize_event("something_new", {})
    _assert_no_advisory_verb(sentence)
