"""
Unit tests for the BSE StAR scheme-master enrichment (tasks/bse_enrich.py) —
pure mapping + dormancy gates. Record shapes are verbatim from a REAL UAT
`master_scheme_list` response (2026-07-10; the guide's verified read path).
"""

from __future__ import annotations

import pytest

from dhanradar.tasks.bse_enrich import (
    _enrich_pipeline,
    _extract_min_amounts,
    _parse_exit_load_days,
    _parse_exit_load_pct,
    map_scheme_record,
)

# ---------------------------------------------------------------------------
# exit load — `scheme_exit_load` is a numeric string; remarks carry the period.
# ---------------------------------------------------------------------------


def test_exit_load_pct_zero_is_a_real_fact():
    # "0" = no exit load — knowledge worth writing, never dropped as falsy.
    assert _parse_exit_load_pct("0") == 0.0


def test_exit_load_pct_parses_common_forms():
    assert _parse_exit_load_pct("1") == 1.0
    assert _parse_exit_load_pct("1.5") == 1.5
    assert _parse_exit_load_pct("0.25%") == 0.25


def test_exit_load_pct_fails_closed():
    assert _parse_exit_load_pct("") is None
    assert _parse_exit_load_pct(None) is None
    assert _parse_exit_load_pct("see remarks") is None
    assert _parse_exit_load_pct("50") is None  # >20% is never a real exit load


def test_exit_load_days_from_remarks_prose():
    assert _parse_exit_load_days("1% if redeemed within 365 days") == 365
    assert _parse_exit_load_days("Exit load of 1% within 12 months") == 360
    assert _parse_exit_load_days("1.00% within 1 Year from allotment") == 365
    # Tiered loads: the LONGEST stated period is the binding horizon.
    assert _parse_exit_load_days("1% up to 30 days, 0.5% up to 90 days") == 90


def test_exit_load_days_fails_closed():
    assert _parse_exit_load_days("0") is None
    assert _parse_exit_load_days("") is None
    assert _parse_exit_load_days(None) is None
    assert _parse_exit_load_days("Nil") is None


# ---------------------------------------------------------------------------
# min amounts — lumpsum/systematic are per-transaction-type block LISTS.
# ---------------------------------------------------------------------------


def _amt_block(ttype: str, min_amt) -> dict:
    return {
        "scheme_transaction_type": ttype,
        "scheme_transaction_single_details": {
            "scheme_transaction_amt": {"scheme_transaction_min_amt": min_amt}
        },
    }


def test_min_amounts_pick_fresh_purchase_and_smallest_sip():
    record = {
        "lumpsum": [
            _amt_block("Redemption", 100),  # must be ignored
            _amt_block("Purchase", 5000),
            _amt_block("Additional Purchase", 1000),  # must be ignored
        ],
        "systematic": [
            _amt_block("Systematic Investment Plan", 1000),
            _amt_block("Systematic Investment Plan", 500),  # another frequency
            _amt_block("Systematic Withdrawal Plan", 100),  # must be ignored
        ],
    }
    assert _extract_min_amounts(record) == (5000.0, 500.0)


def test_min_amounts_fail_closed_on_missing_blocks():
    assert _extract_min_amounts({}) == (None, None)
    assert _extract_min_amounts({"lumpsum": [_amt_block("Purchase", 0)]}) == (None, None)


# ---------------------------------------------------------------------------
# record mapping — real UAT record shape (SBI ESG Exclusionary, 2026-07-10).
# ---------------------------------------------------------------------------

_REAL_RECORD = {
    "name": "SBI ESG EXCLUSIONARY STRATEGY FUND REGULAR IDCW PAYOUT",
    "scheme_plan": "Regular",
    "scheme_option": "IDCW Payout",
    "scheme_isin": "INF200K01198",
    "scheme_amc_name": "SBI MUTUAL FUND",
    "scheme_benchmark": "",
    "scheme_entry_load": "0",
    "scheme_exit_load": "0",
    "scheme_exit_load_remarks": "0",
    "lumpsum": [_amt_block("Purchase", 1000)],
    "systematic": [],
}


def test_map_real_record():
    mapped = map_scheme_record(_REAL_RECORD)
    assert mapped == {
        "isin": "INF200K01198",
        "exit_load_pct": 0.0,
        "exit_load_days": None,
        "min_lumpsum_amount": 1000.0,
        "min_sip_amount": None,
        "benchmark_index": None,  # empty string never written
    }


def test_map_record_without_isin_is_dropped():
    assert map_scheme_record({**_REAL_RECORD, "scheme_isin": ""}) is None
    assert map_scheme_record({**_REAL_RECORD, "scheme_isin": "BOGUS"}) is None


# ---------------------------------------------------------------------------
# dormancy gates — the task is a logged no-op until explicitly armed.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disabled_flag_skips_before_any_network(monkeypatch):
    from dhanradar.config import settings

    monkeypatch.setattr(settings, "BSE_ENRICH_ENABLED", False)
    assert await _enrich_pipeline() == "skipped: disabled"


@pytest.mark.asyncio
async def test_missing_credentials_skip_before_any_network(monkeypatch):
    from dhanradar.config import settings

    monkeypatch.setattr(settings, "BSE_ENRICH_ENABLED", True)
    monkeypatch.setattr(settings, "BSE_LOGIN_USERNAME", "")
    monkeypatch.setattr(settings, "BSE_LOGIN_PASSWORD", "")
    assert await _enrich_pipeline() == "skipped: no_credentials"
