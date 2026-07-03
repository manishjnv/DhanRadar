"""Cross-format CAS dedup + per-folio ownership guard (2026-07-04 P0 data-integrity incident).

The founder uploaded the SAME portfolio via CAMS .txt/.xls TDS AND a consolidated PDF (incl.
KFin). Two distinct bugs corrupted the ledger: (1) the same folio printed with different internal
whitespace across formats ("33375865/ 73" vs "33375865/73") hashed to a DIFFERENT `source_ref`, so
the ON CONFLICT dedup never fired and SIPs landed twice; (2) the consolidated PDF carried a
DIFFERENT investor's folios (a household member sharing one RTA email) which were ingested into
this portfolio wholesale.

Pure tests (no PG): folio normalization across format variants (see also test_b2_cas_ledger.py),
the ledger's rounding-bucket natural key + format-family derivation, the ownership filter, and the
identity-PAN unanimity rule. PG tests (live-PG CI): second-stage natural-key dedup at append
(cross-format-family only — independent of the source_ref hash), a mixed batch where only
genuinely-new rows land, same-family same-day twins BOTH landing (the dedup must never eat a
legitimate twin), and the ownership guard's real DB footprint (mirrors _run_pipeline's own call
order: filter -> build -> append -> project -> checkpoint).
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text

from dhanradar.db_security import set_rls_user
from dhanradar.mf.cas import (
    ParsedHolding,
    ParsedTxn,
    build_cas_ledger_rows,
    filter_foreign_pan_folios,
    parse_cas,
    parser_version_for,
)
from dhanradar.mf.ledger import _format_family, _natural_key, append_transactions
from dhanradar.models.auth import User

pytestmark = pytest.mark.integration


async def _seed_user(db_session, email: str) -> str:
    u = User(email=email)
    db_session.add(u)
    await db_session.flush()
    uid = str(u.id)
    await db_session.commit()
    return uid


async def _seed_portfolio(db_session, uid: str) -> str:
    pid = (
        await db_session.execute(
            text("INSERT INTO mf.mf_portfolios (user_id, name) VALUES (:u, 'Dedup') RETURNING id"),
            {"u": uid},
        )
    ).scalar_one()
    await db_session.commit()
    return str(pid)


def _mini_holding(isin: str, folio: str = "X1", folio_pan: str | None = None) -> ParsedHolding:
    return ParsedHolding(
        isin=isin,
        amfi_code=None,
        scheme_name="Y",
        folio_number=folio,
        units=10.0,
        nav=10.0,
        value=100.0,
        cost=100.0,
        as_of_date=None,
        txns=[],
        folio_pan=folio_pan,
    )


# ---------------------------------------------------------------------------
# Pure — ledger natural-key rounding-bucket tolerance
# ---------------------------------------------------------------------------


def test_natural_key_rounding_bucket_tolerance():
    """units ±0.001 / amount ±1 rupee, implemented as rounding-bucket match (exact after rounding),
    per §39.3 adapted for cross-format variance — not an epsilon-neighbourhood search."""
    d = date(2026, 1, 5)
    within = _natural_key("INF1", "777", d, "purchase", 50.0004, -1000.49)
    baseline = _natural_key("INF1", "777", d, "purchase", 50.0, -1000.00)
    assert within == baseline

    outside_units = _natural_key("INF1", "777", d, "purchase", 50.5, -1000.0)
    assert outside_units != baseline

    outside_amount = _natural_key("INF1", "777", d, "purchase", 50.0, -1002.0)
    assert outside_amount != baseline

    different_folio = _natural_key("INF1", "778", d, "purchase", 50.0, -1000.0)
    assert different_folio != baseline


def test_format_family_derivation():
    """parser_version → format family: the trailing '-<n>' version bump strips; legacy 'cas-1'
    (pre-split rows) and None each land in a family distinct from every specific one, so old rows
    stay dedup-eligible vs any new upload (conservative). parser_version_for maps extensions."""
    assert _format_family("cas-pdf-1") == "cas-pdf"
    assert _format_family("cas-tds-txt-1") == "cas-tds-txt"
    assert _format_family("cas-tds-xls-1") == "cas-tds-xls"
    assert _format_family("cas-1") == "cas"
    assert _format_family(None) == ""
    assert _format_family("cas-pdf-1") != _format_family("cas-tds-txt-1")
    # .txt and .xls TDS exports are DIFFERENT format families (their byte-identical content
    # already collides via the exact-hash source_ref; the family split matters for the
    # natural-key layer only).
    assert _format_family(parser_version_for("a.txt")) != _format_family(
        parser_version_for("a.xls")
    )
    assert parser_version_for("a.pdf") == "cas-pdf-1"
    assert parser_version_for("weird.bin") == "cas-1"


# ---------------------------------------------------------------------------
# Pure — identity PAN unanimity (BLOCKER: first-folio fallback could invert ownership)
# ---------------------------------------------------------------------------


def test_identity_pan_ambiguous_folio_pans_stores_none():
    """No investor_info PAN + folios carrying DIFFERENT PANs (a consolidated household statement):
    the identity PAN must be None — an arbitrary first folio's PAN must never become the stored
    authoritative investor_pan (it could be the OTHER investor's, inverting the ownership guard).
    With pan=None nothing is excluded either (the guard fails open per the no-PAN rule)."""
    raw = {
        "investor_info": {"name": "Someone"},
        "folios": [
            {"folio": "1/1", "PAN": "ABCDE1234F", "schemes": []},
            {"folio": "2/1", "PAN": "ZZZZZ9999Z", "schemes": []},
        ],
    }
    holdings, identity = parse_cas("p.pdf", None, reader=lambda p, pw: raw)
    assert identity.pan is None
    # fails-open: with no owner PAN the filter excludes nothing
    owned, foreign = filter_foreign_pan_folios(
        [_mini_holding("INF_A", folio_pan="ABCDE1234F")], identity.pan
    )
    assert foreign == []


def test_identity_pan_unanimous_folio_pans_stored():
    """No investor_info PAN but every folio-level PAN (incl. a CDSL account) agrees → unanimity,
    the shared PAN IS the identity and the ownership guard stays active."""
    raw = {
        "investor_info": {},
        "folios": [
            {"folio": "1/1", "PAN": "ABCDE1234F", "schemes": []},
            {"folio": "2/1", "pan": "ABCDE1234F", "schemes": []},
        ],
        "accounts": [{"PAN": "ABCDE1234F", "mutual_funds": []}],
    }
    holdings, identity = parse_cas("p.pdf", None, reader=lambda p, pw: raw)
    assert identity.pan == "ABCDE1234F"


def test_identity_pan_investor_info_wins_over_folios():
    """investor_info.pan, when present and valid, is authoritative regardless of folio PANs."""
    raw = {
        "investor_info": {"pan": "ABCDE1234F"},
        "folios": [{"folio": "1/1", "PAN": "ZZZZZ9999Z", "schemes": []}],
    }
    holdings, identity = parse_cas("p.pdf", None, reader=lambda p, pw: raw)
    assert identity.pan == "ABCDE1234F"


# ---------------------------------------------------------------------------
# Pure — per-folio ownership filter
# ---------------------------------------------------------------------------


def test_filter_foreign_pan_folios_excludes_mismatched_pan():
    owner_pan = "ABCDE1234F"
    mine = _mini_holding("INF_OWN", folio_pan=owner_pan)
    mothers = _mini_holding("INF_MOTHER", folio_pan="ZZZZZ9999Z")
    no_pan = _mini_holding("INF_NOPAN", folio_pan=None)

    owned, foreign = filter_foreign_pan_folios([mine, mothers, no_pan], owner_pan)
    assert [h.isin for h in owned] == ["INF_OWN", "INF_NOPAN"]
    assert [h.isin for h in foreign] == ["INF_MOTHER"]


def test_filter_foreign_pan_folios_no_owner_pan_passes_everything():
    """No stored PAN yet (nothing to compare against) -> nothing is excluded (status quo)."""
    mothers = _mini_holding("INF_MOTHER", folio_pan="ZZZZZ9999Z")
    owned, foreign = filter_foreign_pan_folios([mothers], None)
    assert owned == [mothers]
    assert foreign == []


# ---------------------------------------------------------------------------
# PG — second-stage natural-key dedup at append (independent of source_ref hash)
# ---------------------------------------------------------------------------


async def test_cross_format_natural_key_dedup(db_session, app_session):
    """Two formats produce slightly different amount/units for the SAME real transaction (rounding
    differences between RTA product exports) — a DIFFERENT `source_ref` (so ON CONFLICT alone would
    NOT catch it) but the SAME natural key after rounding. The second append must skip it."""
    uid = await _seed_user(db_session, "dedup-cf@test.dev")
    pid = await _seed_portfolio(db_session, uid)

    txn_a = ParsedTxn(
        when=date(2026, 1, 5), amount=-1000.00, is_sip=True, txn_type="sip", units=50.0, nav=20.0
    )
    hold_a = ParsedHolding(
        isin="INF_DEDUP_CF",
        amfi_code=None,
        scheme_name="X",
        folio_number="1111/73",
        units=50.0,
        nav=20.0,
        value=1000.0,
        cost=1000.0,
        as_of_date=None,
        txns=[txn_a],
    )

    await set_rls_user(app_session, uid)
    rows1 = build_cas_ledger_rows(
        [hold_a], user_id=uid, portfolio_id=pid, parser_version="cas-tds-txt-1"
    )
    ins1, skip1 = await append_transactions(app_session, rows1)
    await app_session.commit()
    assert (ins1, skip1) == (1, 0)

    # A DIFFERENT-format re-issue (PDF vs the TDS above): same real txn, folio printed with an
    # internal space, amount/units off by sub-tolerance rounding noise — changes source_ref but
    # must still natural-key-collide because the format families differ.
    txn_b = ParsedTxn(
        when=date(2026, 1, 5), amount=-1000.49, is_sip=True, txn_type="sip", units=50.0004, nav=20.0
    )
    hold_b = ParsedHolding(
        isin="INF_DEDUP_CF",
        amfi_code=None,
        scheme_name="X",
        folio_number="1111/ 73",
        units=50.0,
        nav=20.0,
        value=1000.0,
        cost=1000.0,
        as_of_date=None,
        txns=[txn_b],
    )
    rows2 = build_cas_ledger_rows(
        [hold_b], user_id=uid, portfolio_id=pid, parser_version="cas-pdf-1"
    )
    assert rows2[0]["source_ref"] != rows1[0]["source_ref"], (
        "sanity: different exact amount/units -> different hash"
    )
    assert rows2[0]["folio_number"] == rows1[0]["folio_number"] == "1111/73", (
        "folio canonicalized identically"
    )

    await set_rls_user(app_session, uid)
    ins2, skip2 = await append_transactions(app_session, rows2)
    await app_session.commit()
    assert (ins2, skip2) == (0, 1), "natural-key dedup must skip the cross-format re-issue"

    await set_rls_user(app_session, uid)
    n = await app_session.scalar(
        text("SELECT count(*) FROM mf.portfolio_transactions WHERE portfolio_id = :p"), {"p": pid}
    )
    assert n == 1
    await app_session.rollback()


async def test_mixed_batch_only_new_rows_land(db_session, app_session):
    """A batch with ONE natural-key duplicate (a cross-format re-issue) and ONE genuinely-new txn —
    only the new one lands."""
    uid = await _seed_user(db_session, "dedup-mixed@test.dev")
    pid = await _seed_portfolio(db_session, uid)

    txn1 = ParsedTxn(
        when=date(2026, 1, 5), amount=-1000.0, is_sip=True, txn_type="sip", units=50.0, nav=20.0
    )
    hold1 = ParsedHolding(
        isin="INF_MIXED",
        amfi_code=None,
        scheme_name="X",
        folio_number="2222/73",
        units=50.0,
        nav=20.0,
        value=1000.0,
        cost=1000.0,
        as_of_date=None,
        txns=[txn1],
    )
    await set_rls_user(app_session, uid)
    rows1 = build_cas_ledger_rows(
        [hold1], user_id=uid, portfolio_id=pid, parser_version="cas-tds-txt-1"
    )
    await append_transactions(app_session, rows1)
    await app_session.commit()

    txn1_reissue = ParsedTxn(
        when=date(2026, 1, 5), amount=-1000.49, is_sip=True, txn_type="sip", units=50.0004, nav=20.0
    )
    txn2_new = ParsedTxn(
        when=date(2026, 2, 5),
        amount=-2000.0,
        is_sip=False,
        txn_type="purchase",
        units=90.0,
        nav=22.0,
    )
    hold2 = ParsedHolding(
        isin="INF_MIXED",
        amfi_code=None,
        scheme_name="X",
        folio_number="2222/ 73",
        units=140.0,
        nav=22.0,
        value=3080.0,
        cost=3000.0,
        as_of_date=None,
        txns=[txn1_reissue, txn2_new],
    )

    await set_rls_user(app_session, uid)
    rows2 = build_cas_ledger_rows(
        [hold2], user_id=uid, portfolio_id=pid, parser_version="cas-pdf-1"
    )
    ins2, skip2 = await append_transactions(app_session, rows2)
    await app_session.commit()
    assert (ins2, skip2) == (1, 1), (
        "only the genuinely-new txn lands; the cross-format re-issue is skipped"
    )

    await set_rls_user(app_session, uid)
    n = await app_session.scalar(
        text("SELECT count(*) FROM mf.portfolio_transactions WHERE portfolio_id = :p"), {"p": pid}
    )
    assert n == 2
    await app_session.rollback()


async def test_same_family_same_day_twins_both_land(db_session, app_session):
    """Two DISTINCT same-day same-rounded-amount same-units SIPs printed by ONE statement (a
    genuine twin pair — e.g. two ₹1000 SIPs into the same fund on the 5th) must BOTH land: the
    statement that printed both is authoritative, so neither within-batch natural-key dedup nor a
    same-family match against earlier rows may eat one. (Truly identical twins — every exact field
    equal — still collapse via the exact-hash source_ref: documented accepted behaviour.)"""
    uid = await _seed_user(db_session, "dedup-twins@test.dev")
    pid = await _seed_portfolio(db_session, uid)

    # Distinct at exact precision (different paise), identical at natural-key rounding — the
    # natural keys collide but the source_refs differ.
    twin_a = ParsedTxn(
        when=date(2026, 1, 5), amount=-999.60, is_sip=True, txn_type="sip", units=50.0, nav=20.0
    )
    twin_b = ParsedTxn(
        when=date(2026, 1, 5), amount=-1000.40, is_sip=True, txn_type="sip", units=50.0, nav=20.0
    )
    hold = ParsedHolding(
        isin="INF_TWINS",
        amfi_code=None,
        scheme_name="X",
        folio_number="4444/73",
        units=100.0,
        nav=20.0,
        value=2000.0,
        cost=2000.0,
        as_of_date=None,
        txns=[twin_a, twin_b],
    )

    await set_rls_user(app_session, uid)
    rows = build_cas_ledger_rows(
        [hold], user_id=uid, portfolio_id=pid, parser_version="cas-tds-txt-1"
    )
    assert rows[0]["source_ref"] != rows[1]["source_ref"], "sanity: twins hash distinctly"
    ins, skip = await append_transactions(app_session, rows)
    await app_session.commit()
    assert (ins, skip) == (2, 0), "genuine same-day twins from ONE statement must BOTH land"

    # Same-family re-upload of the same statement: exact-hash idempotency, not the natural key,
    # is what skips them — still (0, 2), and the ledger still holds exactly the two twins.
    await set_rls_user(app_session, uid)
    ins2, skip2 = await append_transactions(app_session, rows)
    await app_session.commit()
    assert (ins2, skip2) == (0, 2)

    await set_rls_user(app_session, uid)
    n = await app_session.scalar(
        text("SELECT count(*) FROM mf.portfolio_transactions WHERE portfolio_id = :p"), {"p": pid}
    )
    assert n == 2
    await app_session.rollback()


# ---------------------------------------------------------------------------
# PG — ownership guard end-to-end (mirrors _run_pipeline's real call order)
# ---------------------------------------------------------------------------


async def test_ownership_guard_end_to_end_excludes_foreign_folio(db_session, app_session):
    """Mirrors _run_pipeline's actual sequence (filter -> build -> append -> project -> checkpoint):
    a folio whose OWN PAN disagrees with the owner's authoritative PAN produces ZERO DB footprint,
    while a folio with no PAN info (assumed the owner's) ingests normally."""
    from dhanradar.tasks.mf import _project_and_write_holdings, _write_statement_checkpoints

    uid = await _seed_user(db_session, "own-e2e@test.dev")
    pid = await _seed_portfolio(db_session, uid)
    owner_pan = "ABCDE1234F"

    mine_txns = [
        ParsedTxn(
            when=date(2026, 1, 5), amount=-1000.0, is_sip=True, txn_type="sip", units=50.0, nav=20.0
        )
    ]
    mine = ParsedHolding(
        isin="INF_OWN_E2E",
        amfi_code=None,
        scheme_name="Mine",
        folio_number="3001/1",
        units=50.0,
        nav=20.0,
        value=1000.0,
        cost=1000.0,
        as_of_date=date(2026, 3, 1),
        txns=mine_txns,
        folio_pan=owner_pan,
    )

    no_pan_txns = [
        ParsedTxn(
            when=date(2026, 1, 6),
            amount=-500.0,
            is_sip=False,
            txn_type="purchase",
            units=25.0,
            nav=20.0,
        )
    ]
    no_pan = ParsedHolding(
        isin="INF_NOPAN_E2E",
        amfi_code=None,
        scheme_name="NoPan",
        folio_number="3002/1",
        units=25.0,
        nav=20.0,
        value=500.0,
        cost=500.0,
        as_of_date=date(2026, 3, 1),
        txns=no_pan_txns,
        folio_pan=None,
    )

    mothers_txns = [
        ParsedTxn(
            when=date(2026, 1, 7),
            amount=-2000.0,
            is_sip=False,
            txn_type="purchase",
            units=90.0,
            nav=22.0,
        )
    ]
    mothers = ParsedHolding(
        isin="INF_MOTHER_E2E",
        amfi_code=None,
        scheme_name="Mothers",
        folio_number="9999/1",
        units=90.0,
        nav=22.0,
        value=1980.0,
        cost=2000.0,
        as_of_date=date(2026, 3, 1),
        txns=mothers_txns,
        folio_pan="ZZZZZ9999Z",
    )

    owned, foreign = filter_foreign_pan_folios([mine, no_pan, mothers], owner_pan)
    assert len(foreign) == 1
    assert [h.isin for h in foreign] == ["INF_MOTHER_E2E"]

    await set_rls_user(app_session, uid)
    rows = build_cas_ledger_rows(owned, user_id=uid, portfolio_id=pid)
    ins, skip = await append_transactions(app_session, rows)
    await app_session.commit()
    assert (ins, skip) == (2, 0)

    await set_rls_user(app_session, uid)
    invested, projected = await _project_and_write_holdings(app_session, uid, owned, pid)
    job = str(uuid.uuid4())
    await set_rls_user(app_session, uid)  # internal commit above cleared the GUC
    await _write_statement_checkpoints(app_session, uid, pid, job, owned, projected)
    await app_session.commit()

    # The foreign folio produced ZERO DB footprint anywhere in the pipeline.
    await set_rls_user(app_session, uid)
    ledger_isins = (
        (
            await app_session.execute(
                text(
                    "SELECT DISTINCT instrument_id FROM mf.portfolio_transactions WHERE portfolio_id = :p"
                ),
                {"p": pid},
            )
        )
        .scalars()
        .all()
    )
    assert set(ledger_isins) == {"INF_OWN_E2E", "INF_NOPAN_E2E"}

    holding_isins = (
        (
            await app_session.execute(
                text("SELECT isin FROM mf.mf_user_holdings WHERE portfolio_id = :p"), {"p": pid}
            )
        )
        .scalars()
        .all()
    )
    assert set(holding_isins) == {"INF_OWN_E2E", "INF_NOPAN_E2E"}

    cp_isins = (
        (
            await app_session.execute(
                text(
                    "SELECT instrument_id FROM mf.portfolio_statement_checkpoints WHERE upload_ref = :j"
                ),
                {"j": job},
            )
        )
        .scalars()
        .all()
    )
    assert set(cp_isins) == {"INF_OWN_E2E", "INF_NOPAN_E2E"}

    await app_session.rollback()
