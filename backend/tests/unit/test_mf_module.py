"""
Unit tests for the MF module pure logic (Phase 5) — no DB/Redis.

Covers: CAS parse normalization (ISIN filter, txn parse), SHA-256 dedup hash,
report assembly (disclosure injected, NO unified_score numeric), scoring-bridge
FactorInputs mapping (no risk_profile), holdings→snapshot mapping, and that the
upload route is wired to the mf_analytics consent gate (B20).
"""

from __future__ import annotations

from dataclasses import fields
from datetime import date

from dhanradar.mf.cas import parse_cas
from dhanradar.mf.scoring_bridge import FundSignals, to_factor_inputs
from dhanradar.mf.service import assemble_report, cas_sha256
from dhanradar.mf.schemas import FundReportItem, PortfolioReport
from dhanradar.tasks.mf import parsed_to_snapshot_holdings


# --- CAS parse ---------------------------------------------------------------
def _fake_cas(_path, _password):
    return {
        "folios": [
            {"folio": "F1", "schemes": [
                {"isin": "INF001", "amfi": "100", "scheme": "Big Cap", "close": 100.0,
                 "valuation": {"nav": 50.0, "value": 5000.0, "cost": 4000.0, "date": "2026-06-01"},
                 "transactions": [{"date": "2024-01-01", "amount": -4000.0}]},
                {"isin": "", "scheme": "Not an MF row"},  # no ISIN → skipped
            ]},
        ]
    }


def test_parse_cas_walks_folios_and_skips_non_isin():
    holdings = parse_cas("x.pdf", "pw", reader=_fake_cas)
    assert len(holdings) == 1  # the no-ISIN row was skipped
    h = holdings[0]
    assert h.isin == "INF001" and h.folio_number == "F1"
    assert h.units == 100.0 and h.value == 5000.0 and h.cost == 4000.0
    assert h.amfi_code == "100" and h.as_of_date == date(2026, 6, 1)
    assert len(h.txns) == 1 and h.txns[0].amount == -4000.0


def test_parse_cas_failure_raises():
    import pytest

    from dhanradar.mf.cas import CasParseError

    def _boom(_p, _pw):
        raise ValueError("bad password")

    with pytest.raises(CasParseError):
        parse_cas("x.pdf", "wrong", reader=_boom)


# --- dedup hash --------------------------------------------------------------
def test_cas_sha256_is_deterministic():
    assert cas_sha256(b"abc") == cas_sha256(b"abc")
    assert cas_sha256(b"abc") != cas_sha256(b"abd")
    assert len(cas_sha256(b"abc")) == 64


# --- report assembly: disclosure injected, NO numeric score ------------------
def test_report_has_no_unified_score_field():
    item_fields = {f for f in FundReportItem.model_fields}
    report_fields = {f for f in PortfolioReport.model_fields}
    assert "unified_score" not in item_fields  # no numeric score to the client
    assert "unified_score" not in report_fields
    assert "verb_label" in item_fields and "confidence_band" in item_fields


def test_assemble_report_injects_disclosure_and_strips_score():
    report = assemble_report(
        job_id="J1", status="done",
        snapshot={"total_invested": 4000.0, "current_value": 5000.0, "xirr_pct": 12.0,
                  "category_allocation": {"Equity": 100.0}, "overlap_matrix": {}},
        funds=[{"isin": "INF001", "scheme_name": "Big Cap", "folio_number": "F1", "units": 100.0,
                "invested_amount": 4000.0, "current_value": 5000.0,
                "verb_label": "on_track", "confidence_band": "medium",
                "contributing_signals": ["category match"], "contradicting_signals": []}],
        model_version="v1", generated_at="2026-06-06T00:00:00Z",
    )
    assert report.disclosure and report.not_advice == "NOT_ADVICE"
    assert report.current_value == 5000.0 and report.xirr_pct == 12.0  # user's own facts OK
    assert report.funds[0].verb_label == "on_track"
    # The serialized report must not contain a numeric unified score anywhere.
    assert "unified_score" not in report.model_dump_json()


# --- scoring bridge ----------------------------------------------------------
def test_fund_signals_exclude_risk_profile():
    names = {f.name for f in fields(FundSignals)}
    assert "risk_profile" not in names and "user_id" not in names


def test_to_factor_inputs_maps_axes_and_labels():
    fi = to_factor_inputs(FundSignals(isin="INF001", quality=70.0, outperform_1y=True,
                                      contributing=["a", "b"]))
    assert fi.instrument_type == "mf" and fi.identifier == "INF001"
    assert len(fi.axes) == 5  # all five axes present (missing values → None subfactor)
    assert fi.label_signals.outperform_1y is True
    # FactorInputs itself never carries a risk_profile (engine non-neg #3).
    assert not hasattr(fi, "risk_profile")


# --- holdings → snapshot mapping --------------------------------------------
def test_parsed_to_snapshot_applies_nav_and_builds_cashflows():
    holdings = parse_cas("x.pdf", None, reader=_fake_cas)
    snap_holdings = parsed_to_snapshot_holdings(holdings, nav_map={"INF001": 55.0})
    h = snap_holdings[0]
    assert h.current_value == 100.0 * 55.0  # NAV applied (units × latest NAV)
    assert h.invested_amount == 4000.0
    # cashflows = the purchase txn + a terminal positive current-value flow
    assert any(cf.amount < 0 for cf in h.cashflows) and any(cf.amount > 0 for cf in h.cashflows)


def test_parsed_to_snapshot_falls_back_to_cas_value_without_nav():
    holdings = parse_cas("x.pdf", None, reader=_fake_cas)
    snap_holdings = parsed_to_snapshot_holdings(holdings, nav_map={})  # no NAV feed
    assert snap_holdings[0].current_value == 5000.0  # CAS-reported valuation used


# --- consent gate wiring (B20) ----------------------------------------------
def test_upload_route_is_consent_gated_for_mf_analytics():
    from dhanradar.mf import router as mf_router

    assert mf_router._require_mf_consent.purpose == "mf_analytics"
