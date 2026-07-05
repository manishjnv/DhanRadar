"""
Unit tests for the ELSS per-installment lock-in pure function (P2, net new, 2026-07-06).

DB-free, network-free — `compute_elss_lockin` is a pure function over `(txn_date, units,
txn_type)` ledger flow triples, mirroring the FIFO-lot-walk discipline already golden-tested
for `weighted_avg_holding_days` (tests/integration/test_cams_parity.py) but tracking each lot's
own UNITS (not remaining cost).

Covers:
  - Empty flows -> None (nothing to lock).
  - Single lot, still within its 3-year window -> locked, correct lock_until / next_unlock_date.
  - Single lot, past its 3-year window -> free, no lock.
  - Multiple lots straddling the lock boundary -> correct locked/free split + next_unlock_date
    (the SOONEST still-locked lot, not the oldest).
  - Partial redemption FIFO-consumes the OLDEST lot first (mirrors the cost-based walk).
  - A redemption larger than the open lots' units on file -> `approximate=True`, never a
    silently-wrong precise number.
  - dividend_payout / dividend_reinvest rows never open or consume a lot.
  - Feb-29 lot open date -> Feb 28 in the (non-leap) target year (civil "+3 years" rule).
  - Non-ELSS callers simply never call this function — no null-category branch to test here
    (that gating lives in the router/loader, not this pure function).
"""

from __future__ import annotations

from datetime import date

from dhanradar.mf.portfolio_read import _lockin_end_date, compute_elss_lockin


def test_empty_flows_is_none():
    assert compute_elss_lockin([], date(2026, 7, 6)) is None


def test_single_lot_still_locked():
    flows = [(date(2025, 1, 10), 100.0, "purchase")]
    today = date(2026, 7, 6)  # well within 3 years of 2025-01-10
    result = compute_elss_lockin(flows, today)
    assert result is not None
    assert result["approximate"] is False
    assert result["locked_units"] == 100.0
    assert result["free_units"] == 0.0
    assert result["next_unlock_date"] == "2028-01-10"
    assert result["lots"] == [
        {
            "txn_date": "2025-01-10",
            "units": 100.0,
            "lock_until": "2028-01-10",
            "locked": True,
        }
    ]


def test_single_lot_lock_over():
    flows = [(date(2022, 1, 10), 100.0, "purchase")]
    today = date(2026, 7, 6)  # more than 3 years past 2022-01-10
    result = compute_elss_lockin(flows, today)
    assert result is not None
    assert result["locked_units"] == 0.0
    assert result["free_units"] == 100.0
    assert result["next_unlock_date"] is None
    assert result["lots"][0]["locked"] is False


def test_multi_lot_next_unlock_is_soonest_still_locked():
    """Three lots: one already free, two still locked with DIFFERENT unlock dates —
    next_unlock_date must be the SOONER of the two locked lots, not the oldest lot overall."""
    flows = [
        (date(2022, 1, 1), 50.0, "purchase"),  # free by 2026-07-06 (locked until 2025-01-01)
        (date(2025, 3, 1), 30.0, "purchase"),  # locked until 2028-03-01
        (date(2024, 12, 1), 20.0, "purchase"),  # locked until 2027-12-01 (sooner)
    ]
    today = date(2026, 7, 6)
    result = compute_elss_lockin(flows, today)
    assert result is not None
    assert result["free_units"] == 50.0
    assert result["locked_units"] == 50.0  # 30 + 20
    assert result["next_unlock_date"] == "2027-12-01"
    assert result["approximate"] is False


def test_partial_redemption_consumes_oldest_lot_first():
    """FIFO: a redemption consumes the OLDEST lot's units first — mirrors
    weighted_avg_holding_days' FIFO-redemption-consumes-oldest-lot golden case."""
    flows = [
        (date(2023, 1, 1), 100.0, "purchase"),  # oldest lot
        (date(2025, 1, 1), 60.0, "purchase"),  # newer lot
        (date(2026, 1, 1), 40.0, "redemption"),  # consumes 40 of the oldest 100 -> 60 remain
    ]
    today = date(2026, 7, 6)
    result = compute_elss_lockin(flows, today)
    assert result is not None
    assert result["approximate"] is False
    # Oldest lot now has 60 remaining units; newer lot untouched at 60 units.
    lots_by_date = {lot["txn_date"]: lot["units"] for lot in result["lots"]}
    assert lots_by_date == {"2023-01-01": 60.0, "2025-01-01": 60.0}


def test_redemption_fully_consumes_a_lot_and_spills_to_next():
    """A redemption larger than the oldest lot fully consumes it and spills into the next
    oldest lot (still attributable — NOT approximate)."""
    flows = [
        (date(2023, 1, 1), 50.0, "purchase"),
        (date(2024, 1, 1), 50.0, "purchase"),
        (date(2026, 1, 1), 70.0, "redemption"),  # consumes all of lot 1 (50) + 20 of lot 2
    ]
    today = date(2026, 7, 6)
    result = compute_elss_lockin(flows, today)
    assert result is not None
    assert result["approximate"] is False
    assert result["lots"] == [
        {"txn_date": "2024-01-01", "units": 30.0, "lock_until": "2027-01-01", "locked": True}
    ]


def test_redemption_exceeding_open_lots_sets_approximate():
    """A redemption for MORE units than the open lots on file cannot be cleanly attributed —
    the ledger is data-starved for this holding's full history. approximate=True, never a
    silently-wrong precise number (§8.4)."""
    flows = [
        (date(2023, 1, 1), 50.0, "purchase"),
        (date(2026, 1, 1), 80.0, "redemption"),  # 30 units unaccounted for
    ]
    today = date(2026, 7, 6)
    result = compute_elss_lockin(flows, today)
    # All lots consumed (50 of the 80) and nothing survives -> None (nothing to report),
    # but the ambiguity must still have been detected internally. Use a case with a
    # surviving lot to assert the flag is visible on the returned shape.
    assert result is None


def test_redemption_exceeding_open_lots_with_surviving_lot_flags_approximate():
    """The redemption exceeds the ONE open lot on file (50 available, 80 sold) — 30 units are
    unaccounted for (approximate=True) — but a LATER lot, opened after the ambiguous
    redemption, is untouched and survives cleanly."""
    flows = [
        (date(2023, 1, 1), 50.0, "purchase"),  # lot1 — fully consumed, 30 units unaccounted
        (date(2024, 6, 1), 80.0, "redemption"),
        (date(2025, 1, 1), 40.0, "purchase"),  # lot2 — opened AFTER the ambiguous redemption
    ]
    today = date(2026, 7, 6)
    result = compute_elss_lockin(flows, today)
    assert result is not None
    assert result["approximate"] is True
    assert result["lots"] == [
        {"txn_date": "2025-01-01", "units": 40.0, "lock_until": "2028-01-01", "locked": True}
    ]


def test_dividend_payout_and_reinvest_do_not_affect_lots():
    """Mirrors weighted_avg_holding_days' ADR-0039 golden case: a dividend_payout is
    B65-signed positive (same sign as a redemption) but must NOT consume lot units; a
    dividend_reinvest carries amount 0 and units 0 for THIS purpose (units-based walk) and
    contributes no lot."""
    flows = [
        (date(2024, 1, 1), 100.0, "purchase"),
        (date(2025, 1, 1), 50.0, "dividend_payout"),
        (date(2025, 6, 1), 0.0, "dividend_reinvest"),
    ]
    today = date(2026, 7, 6)
    result = compute_elss_lockin(flows, today)
    assert result is not None
    assert result["locked_units"] == 100.0
    assert len(result["lots"]) == 1


def test_non_elss_category_never_reaches_this_function():
    """Documents the gating contract: `compute_elss_lockin` has no category parameter at all —
    the router/loader (`load_holdings_elss_lockin`) only calls it for holdings whose category
    is ELSS_CATEGORY. A non-ELSS holding's `lockin` key is None purely because it's absent
    from the caller's `elss_keys` filter, never because this function returned something
    falsy for it."""
    from dhanradar.mf.taxonomy import ELSS_CATEGORY

    assert ELSS_CATEGORY == "Equity Scheme - ELSS"


# ---------------------------------------------------------------------------
# _lockin_end_date — the civil "+3 years" rule, including the Feb-29 edge case.
# ---------------------------------------------------------------------------


def test_lockin_end_date_ordinary():
    assert _lockin_end_date(date(2025, 3, 12)) == date(2028, 3, 12)


def test_lockin_end_date_leap_day_falls_back_to_feb28():
    # 2024 is a leap year; 2024 + 3 = 2027, NOT a leap year.
    assert _lockin_end_date(date(2024, 2, 29)) == date(2027, 2, 28)
