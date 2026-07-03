"""B94 — hardened CAMS name→ISIN resolver (resolve_cams_isins).

Prod incident 2026-07-03: the bare best-similarity resolver mapped the founder's
"HDFC NIFTY Smallcap 250 Index Fund" to DSP's ISIN (both names contain "Nifty
Smallcap 250 Index Fund"); 12 SIPs were valued off the wrong fund's NAV. The
hardened resolver must clear three guards: AMC token gate, similarity floor +
ambiguity margin, and txn-price vs mf_nav_history consistency.

PG tests (live-PG CI). Unique ISINs AND distinctive made-up scheme names per test:
mf_funds is shared across tests in the session-scoped DB (ON CONFLICT DO NOTHING),
and the resolver's similarity query scans the whole table — reused/similar names
would leak candidates across tests.
"""

from __future__ import annotations

import logging
from datetime import date

import pytest
from sqlalchemy import text

from dhanradar.mf.cas import ParsedHolding, ParsedTxn, resolve_cams_isins

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def _ensure_trgm(db_session):
    """create_all bypasses migration 0040, so pg_trgm may be absent in the test DB."""
    await db_session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    await db_session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_fund(db, isin: str, name: str, amc: str | None) -> None:
    await db.execute(
        text(
            "INSERT INTO mf.mf_funds (isin, scheme_name, amc_name, is_segregated)"
            " VALUES (:i, :n, :a, false) ON CONFLICT (isin) DO NOTHING"
        ),
        {"i": isin, "n": name, "a": amc},
    )
    await db.commit()


async def _seed_nav(db, isin: str, d: date, nav: float) -> None:
    await db.execute(
        text(
            "INSERT INTO mf.mf_nav_history (isin, nav_date, nav) VALUES (:i, :d, :n)"
            " ON CONFLICT (isin, nav_date) DO NOTHING"
        ),
        {"i": isin, "d": d, "n": nav},
    )
    await db.commit()


_SIP_DATES = [date(2026, 1, 5), date(2026, 2, 5), date(2026, 3, 5)]


def _cams_holding(product: str, name: str, txn_navs: list[float | None]) -> ParsedHolding:
    txns = [
        ParsedTxn(when=d, amount=-1000.0, is_sip=True, txn_type="sip", units=10.0, nav=nav)
        for d, nav in zip(_SIP_DATES, txn_navs)
    ]
    return ParsedHolding(
        isin=f"CAMS:{product}",
        amfi_code=None,
        scheme_name=name,
        folio_number="F1",
        units=sum(t.units for t in txns),
        nav=None,
        value=None,
        cost=3000.0,
        as_of_date=None,
        txns=txns,
    )


# ---------------------------------------------------------------------------
# (a) B94 reproduction — similar cross-AMC name must NEVER win; the AMC- and
#     price-consistent fund resolves.
# ---------------------------------------------------------------------------


async def test_b94_repro_hdfc_never_resolves_to_dsp(db_session):
    hdfc = "INF_B94A_HDFC"
    dsp = "INF_B94A_DSP"
    cams_name = "HDFC NIFTY Smallcap 250 Index Fund - Direct Plan"
    await _seed_fund(db_session, hdfc, cams_name, "HDFC Mutual Fund")
    await _seed_fund(
        db_session, dsp, "DSP Nifty Smallcap 250 Index Fund - Direct Plan", "DSP Mutual Fund"
    )
    # HDFC NAV matches the statement's purchase prices; DSP deviates wildly (77%).
    txn_navs = [10.5, 11.2, 10.9]
    for d, nav in zip(_SIP_DATES, txn_navs):
        await _seed_nav(db_session, hdfc, d, nav)
        await _seed_nav(db_session, dsp, d, nav * 1.77)

    holding = _cams_holding("B94A", cams_name, txn_navs)
    resolved = await resolve_cams_isins(db_session, [holding])

    assert resolved == {"CAMS:B94A": hdfc}
    assert dsp not in resolved.values()


# ---------------------------------------------------------------------------
# (b) AMC token gate — only a wrong-AMC candidate exists (even with a perfect
#     name match) → placeholder kept.
# ---------------------------------------------------------------------------


async def test_amc_gate_rejects_wrong_amc_candidate(db_session):
    cams_name = "Bluechip Aurora Titanium Fund"
    # Identical scheme name (sim = 1.0) but the fund belongs to Zenkai AMC and
    # "zenkai" does not appear in the CAMS statement line.
    await _seed_fund(db_session, "INF_B94B_ZK", cams_name, "Zenkai Mutual Fund")

    holding = _cams_holding("B94B", cams_name, [10.0, 10.1, 10.2])
    resolved = await resolve_cams_isins(db_session, [holding])

    assert resolved == {}


# ---------------------------------------------------------------------------
# (c) Ambiguity margin — two same-AMC candidates with identical names (margin 0)
#     → placeholder kept.
# ---------------------------------------------------------------------------


async def test_ambiguous_same_amc_candidates_keep_placeholder(db_session):
    cams_name = "Nimbus Flexi Horizon Fund"
    await _seed_fund(db_session, "INF_B94C_1", cams_name, "Nimbus Mutual Fund")
    await _seed_fund(db_session, "INF_B94C_2", cams_name, "Nimbus Mutual Fund")

    holding = _cams_holding("B94C", cams_name, [10.0, 10.1, 10.2])
    resolved = await resolve_cams_isins(db_session, [holding])

    assert resolved == {}


# ---------------------------------------------------------------------------
# (d) Price-consistency rejection — name AND AMC match, but NAV history deviates
#     77% from the statement's purchase prices → placeholder kept.
# ---------------------------------------------------------------------------


async def test_price_mismatch_rejects_despite_name_and_amc_match(db_session, caplog):
    isin = "INF_B94D_VT"
    cams_name = "Vetrivel Discovery Opportunities Fund"
    await _seed_fund(db_session, isin, cams_name, "Vetrivel Mutual Fund")
    txn_navs = [10.0, 10.0, 10.0]
    for d, nav in zip(_SIP_DATES, txn_navs):
        await _seed_nav(db_session, isin, d, nav * 1.77)

    holding = _cams_holding("B94D", cams_name, txn_navs)
    with caplog.at_level(logging.WARNING, logger="dhanradar.mf.cas"):
        resolved = await resolve_cams_isins(db_session, [holding])

    assert resolved == {}
    assert any("cams_isin_price_mismatch" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# (e) No NAV coverage — guards 1+2 pass, no comparable price points → accepted,
#     logged cams_isin_unvalidated.
# ---------------------------------------------------------------------------


async def test_no_nav_coverage_accepts_on_name_guards_logged_unvalidated(db_session, caplog):
    isin = "INF_B94E_OR"
    cams_name = "Orchidia Balanced Advantage Fund"
    await _seed_fund(db_session, isin, cams_name, "Orchidia Mutual Fund")
    # txns carry prices but mf_nav_history has NO rows for this ISIN.

    holding = _cams_holding("B94E", cams_name, [10.0, 10.1, 10.2])
    with caplog.at_level(logging.INFO, logger="dhanradar.mf.cas"):
        resolved = await resolve_cams_isins(db_session, [holding])

    assert resolved == {"CAMS:B94E": isin}
    assert any("cams_isin_unvalidated" in r.message for r in caplog.records)
