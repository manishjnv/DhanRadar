"""
Unit tests for fraction→percent weight normalization (tasks/mf.py, 2026-07-10).

Measured live: ABSL/EDELWEISS/ICICI_PRU/MIRAE/NIPPON publish "% to NAV" as a
FRACTION (portfolio sums ~1.0) while HDFC/KOTAK/TATA/UTI publish percents
(sums ~100) — the fraction AMCs' fund pages rendered weights 100× too small
(BHARAT 22 ETF showed "0.153%" for a 15.3% holding). Normalization is decided
per (isin, month) GROUP by its summed weight — never a per-row `< 1` check,
which would corrupt genuinely tiny holdings inside percent portfolios.
"""

from __future__ import annotations

import io
from datetime import date

from openpyxl import Workbook

from dhanradar.tasks.mf import _normalize_fraction_weight_groups, _parse_sebi_xlsx

_M = date(2026, 5, 1)


def _row(isin: str, name: str, w: float | None) -> dict:
    return {"isin": isin, "constituent_name": name, "as_of_month": _M, "weight_pct": w}


def test_fraction_group_is_scaled_to_percent():
    # Real BHARAT 22 ETF shape: 6 holdings summing ~1.0 → fractions.
    batch = [
        _row("INF109KB15Y7", f"S{i}", w)
        for i, w in enumerate([0.153, 0.14, 0.105, 0.081, 0.075, 0.446])
    ]
    out = _normalize_fraction_weight_groups(batch, "ICICI_PRU")
    assert [r["weight_pct"] for r in out] == [15.3, 14.0, 10.5, 8.1, 7.5, 44.6]


def test_percent_group_with_tiny_holding_is_untouched():
    # Percent semantics incl. a genuinely tiny 0.4% holding — the MOTILAL trap:
    # a per-row `< 1` check would have corrupted the last row.
    weights = [25.0, 20.0, 30.0, 24.6, 0.4]
    batch = [_row("INF200TEST01", f"S{i}", w) for i, w in enumerate(weights)]
    out = _normalize_fraction_weight_groups(batch, "HDFC")
    assert [r["weight_pct"] for r in out] == weights


def test_small_group_is_never_scaled():
    # <5 weighted rows: too little evidence to infer semantics — leave alone.
    batch = [_row("INF200TEST02", f"S{i}", w) for i, w in enumerate([0.5, 0.4])]
    out = _normalize_fraction_weight_groups(batch, "ICICI_PRU")
    assert [r["weight_pct"] for r in out] == [0.5, 0.4]


def test_groups_are_independent():
    # One fraction fund + one percent fund in the same batch: only the
    # fraction group scales.
    frac = [_row("INF109KB15Y7", f"F{i}", 0.2) for i in range(5)]
    pct = [_row("INF200TEST03", f"P{i}", 20.0) for i in range(5)]
    out = _normalize_fraction_weight_groups(frac + pct, "ICICI_PRU")
    by_isin = {}
    for r in out:
        by_isin.setdefault(r["isin"], []).append(r["weight_pct"])
    assert by_isin["INF109KB15Y7"] == [20.0] * 5
    assert by_isin["INF200TEST03"] == [20.0] * 5


def test_null_weights_stay_null():
    batch = [_row("INF109KB15Y7", f"S{i}", 0.2) for i in range(5)] + [
        _row("INF109KB15Y7", "NoWeight", None)
    ]
    out = _normalize_fraction_weight_groups(batch, "ICICI_PRU")
    assert out[-1]["weight_pct"] is None
    assert out[0]["weight_pct"] == 20.0


def test_sbi_percent_to_aum_header_now_extracts_weight():
    # Real SBI "Portfolio Details" layout (2026-07-10): header "% to AUM" was
    # missing from the weight key list — every SBI row wrote weight_pct NULL.
    wb = Workbook()
    ws = wb.active
    ws.append(["SCHEME NAME :", "SBI Large Cap Fund"])
    ws.append(["PORTFOLIO STATEMENT AS ON :", "2021-02-28"])
    ws.append(["Name of the Instrument / Issuer", "ISIN", "Quantity", "Market value", "% to AUM"])
    ws.append(["HDFC Bank Ltd.", "INE040A01034", "19462739", "230351.25", "6.15"])
    buf = io.BytesIO()
    wb.save(buf)
    rows = _parse_sebi_xlsx(buf.getvalue(), "SBI")
    holdings = [r for r in rows if not r.get("is_total_row")]
    assert holdings
    assert holdings[0]["weight_pct"] == 6.15
