"""
Unit tests for the MF module pure logic (Phase 5) — no DB/Redis.

Covers: CAS parse normalization (ISIN filter, txn parse), SHA-256 dedup hash,
report assembly (disclosure injected, NO unified_score numeric), scoring-bridge
FactorInputs mapping (no risk_profile), holdings→snapshot mapping, and that the
upload route is wired to the mf_analytics consent gate (B20).
"""

from __future__ import annotations

import enum
import io
from dataclasses import fields
from datetime import date

import pytest
from openpyxl import Workbook

from dhanradar.mf.cas import CasParseError, classify_cas_failure, parse_cas
from dhanradar.mf.schemas import FundReportItem, PortfolioReport
from dhanradar.mf.scoring_bridge import FundSignals, to_factor_inputs
from dhanradar.mf.service import assemble_report, cas_sha256, dedup_key
from dhanradar.tasks.mf import (
    _drop_over_covered_funds,
    _extract_sebi_row,
    _parse_sebi_xlsx,
    parsed_to_snapshot_holdings,
)


# --- CAS parse ---------------------------------------------------------------
def _fake_cas(_path, _password):
    # Transactions are in casparser STATEMENT convention: purchase amounts are
    # positive (amount sign follows units sign). parse_cas must normalize them to
    # INVESTOR convention (purchases → negative outflow). See B65.
    return {
        "folios": [
            {"folio": "F1", "schemes": [
                {"isin": "INF001", "amfi": "100", "scheme": "Big Cap", "close": 100.0,
                 "valuation": {"nav": 50.0, "value": 5000.0, "cost": 4000.0, "date": "2026-06-01"},
                 "transactions": [{"date": "2024-01-01", "amount": 4000.0, "type": "PURCHASE"}]},
                {"isin": "", "scheme": "Not an MF row"},  # no ISIN → skipped
            ]},
        ]
    }


def _fake_cdsl_cas(_path, _password):
    """Simulates casparser 1.1.0 CDSL CAS output (accounts structure)."""
    return {
        "file_type": "CDSL",
        "accounts": [
            {
                "name": "Test Account", "type": "CDSL Demat Account",
                "mutual_funds": [
                    {
                        "isin": "INF846K01K35",
                        "amfi": "120505",
                        "name": "AXIS AMC LTD#AXIS MF-AXIS SMALL CAP FUND-DIRECT GROWTH",
                        "balance": 214.1,
                        "nav": 123.36,
                        "value": 26411.38,
                        "total_cost": 20000.0,
                        "folio": "12345678",
                    },
                    {
                        "isin": "",  # no ISIN — skipped
                        "name": "EQUITY SHARES",
                        "balance": 100,
                        "amfi": None,
                    },
                ],
            }
        ],
    }


def test_parse_cas_walks_folios_and_skips_non_isin():
    holdings, _ = parse_cas("x.pdf", "pw", reader=_fake_cas)
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


def test_parse_cas_wrong_password_classifies_as_incorrect_password():
    """A casparser IncorrectPasswordError (the founder-reported prod case, 2026-07-03)
    must classify to 'incorrect_password' — never the opaque 'parse_failed' catch-all —
    so the FE can show a specific, actionable message instead of a raw code."""
    import pytest
    from casparser.exceptions import IncorrectPasswordError

    def _wrong_password(_p, _pw):
        raise IncorrectPasswordError("Incorrect PDF password!")

    with pytest.raises(CasParseError) as exc_info:
        parse_cas("x.pdf", "wrong", reader=_wrong_password)
    assert classify_cas_failure(exc_info.value) == "incorrect_password"


def test_classify_cas_failure_unreadable_file():
    """Corrupt/wrong-format failures (unsupported extension, empty statement, a raw
    casparser CASParseError) classify to 'unreadable_file', distinct from a wrong password."""
    assert classify_cas_failure(
        CasParseError("Unsupported file type '.docx'. Upload a CAS PDF.")
    ) == "unreadable_file"
    assert classify_cas_failure(CasParseError("No data rows found in x.txt")) == "unreadable_file"
    assert classify_cas_failure(
        CasParseError("CASParseError: Unhandled error while opening PDF: bad")
    ) == "unreadable_file"


def test_classify_cas_failure_falls_back_to_parse_failed():
    """An unrecognised failure mode keeps the generic 'parse_failed' fallback — the FE's
    catch-all copy — rather than guessing."""
    assert classify_cas_failure(CasParseError("TypeError: something odd")) == "parse_failed"


def test_parse_cas_normalises_pydantic_model_output():
    """casparser >= 1.0 returns a CASData pydantic MODEL for output="dict"
    (0.7.x returned a dict). parse_cas must model_dump() it before the dict-walk,
    else every successful parse 500s on `model.get(...)`. Regression guard."""

    class _FakeCasData:
        def model_dump(self, mode="python"):
            return _fake_cas("x.pdf", "pw")

    holdings, _ = parse_cas("x.pdf", "pw", reader=lambda _p, _pw: _FakeCasData())
    assert len(holdings) == 1  # walked the model_dump() output, not crashed
    assert holdings[0].isin == "INF001" and holdings[0].value == 5000.0


def test_parse_cas_handles_cdsl_accounts_structure():
    """casparser 1.1.0 CDSL CAS uses accounts[].mutual_funds[] not folios[].
    parse_cas must walk the accounts path when folios is absent/empty."""
    holdings, _ = parse_cas("x.pdf", "pw", reader=_fake_cdsl_cas)
    assert len(holdings) == 1  # the no-ISIN entry was skipped
    h = holdings[0]
    assert h.isin == "INF846K01K35"
    assert h.amfi_code == "120505"
    assert h.units == 214.1
    assert h.nav == 123.36
    assert h.value == 26411.38
    assert h.cost == 20000.0
    assert h.folio_number == "12345678"
    assert h.txns == []  # CDSL has no transaction history
    # Scheme name should not contain the "AXIS AMC LTD#" prefix
    assert "AXIS AMC LTD" not in h.scheme_name
    assert "AXIS" in h.scheme_name  # still mentions AXIS fund


# --- §39.4 statement-period extraction ----------------------------------------


def test_parse_cas_extracts_statement_period():
    """casparser's PDF statement_period (dd-Mmm-yyyy strings, model_dump field name `from_`)
    parses into ParsedCasIdentity.stmt_from/stmt_to."""

    def _reader(_path, _password):
        d = _fake_cas(_path, _password)
        d["statement_period"] = {"from_": "01-Apr-2023", "to": "30-Jun-2023"}
        return d

    _, identity = parse_cas("x.pdf", "pw", reader=_reader)
    assert identity.stmt_from == date(2023, 4, 1)
    assert identity.stmt_to == date(2023, 6, 30)


def test_parse_cas_statement_period_absent_is_none():
    """No statement_period in the raw output (or an empty one) → stmt_from/stmt_to stay None —
    §39.4 says never guess."""
    _, identity = parse_cas("x.pdf", "pw", reader=_fake_cas)
    assert identity.stmt_from is None
    assert identity.stmt_to is None


# --- dedup hash --------------------------------------------------------------
def test_cas_sha256_is_deterministic():
    assert cas_sha256(b"abc") == cas_sha256(b"abc")
    assert cas_sha256(b"abc") != cas_sha256(b"abd")
    assert len(cas_sha256(b"abc")) == 64


def test_dedup_key_is_namespaced_per_user_and_portfolio():
    # Same CAS bytes → DIFFERENT dedup keys across users AND across a user's
    # portfolios (no cross-user leak; the same statement can go to two portfolios).
    h = cas_sha256(b"same-cas-bytes")
    assert dedup_key("userA", "pf1", h) != dedup_key("userB", "pf1", h)  # cross-user
    assert dedup_key("userA", "pf1", h) != dedup_key("userA", "pf2", h)  # cross-portfolio
    assert dedup_key("userA", "pf1", h) == dedup_key("userA", "pf1", h)  # stable
    assert "userA" in dedup_key("userA", "pf1", h) and h in dedup_key("userA", "pf1", h)


class _FakeRedis:
    def __init__(self) -> None:
        self._d: dict[str, str] = {}

    async def get(self, k):
        return self._d.get(k)

    async def set(self, k, v, ex=None):
        self._d[k] = v

    async def delete(self, k):
        self._d.pop(k, None)

    async def exists(self, k):
        return 1 if k in self._d else 0


async def test_dedup_clear_removes_record_so_reupload_reprocesses():
    """A re-upload after a failed/stuck job must NOT be deduped to the dead job:
    the upload route drops the stale dedup record (only a `done` job short-circuits).
    dedup_clear is the primitive that enables that reprocess path."""
    from dhanradar.mf import service

    r = _FakeRedis()
    await service.dedup_record(r, "u1", "pf1", "hash1", "job-old")
    assert await service.dedup_lookup(r, "u1", "pf1", "hash1") == "job-old"
    await service.dedup_clear(r, "u1", "pf1", "hash1")
    assert await service.dedup_lookup(r, "u1", "pf1", "hash1") is None


async def test_can_return_existing_requires_done_and_cached_report():
    """Regression (TTL gap): the dedup key lives 24h (`_DEDUP_TTL`) but the report
    cache only 2h (`_REPORT_TTL`). A re-upload in that 22h gap must NOT short-circuit
    to the done job whose report has EXPIRED — doing so bounced the user to a
    GET /report 404 ('report_expired'), the very 'dead job' the dedup self-heal was
    meant to prevent. Short-circuit ONLY when the job is done AND its report is still
    cached; otherwise fall through to reprocess the freshly-uploaded bytes."""
    from dhanradar.mf import service

    r = _FakeRedis()
    job = "job-done-1"
    # done, but report cache has expired (absent) → must NOT short-circuit.
    assert await service.can_return_existing(r, "done", job) is False
    # report still cached → short-circuit is allowed.
    await r.set(f"{service._REPORT_PREFIX}{job}", "{}")
    assert await service.can_return_existing(r, "done", job) is True
    # non-done statuses never short-circuit, even if some report key exists.
    await r.set(f"{service._REPORT_PREFIX}job-x", "{}")
    assert await service.can_return_existing(r, "failed", "job-x") is False
    assert await service.can_return_existing(r, None, "job-x") is False


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
    holdings, _ = parse_cas("x.pdf", None, reader=_fake_cas)
    snap_holdings = parsed_to_snapshot_holdings(holdings, nav_map={"INF001": 55.0})
    h = snap_holdings[0]
    assert h.current_value == 100.0 * 55.0  # NAV applied (units × latest NAV)
    assert h.invested_amount == 4000.0
    # cashflows = the purchase txn + a terminal positive current-value flow
    assert any(cf.amount < 0 for cf in h.cashflows) and any(cf.amount > 0 for cf in h.cashflows)


def test_parsed_to_snapshot_falls_back_to_cas_value_without_nav():
    holdings, _ = parse_cas("x.pdf", None, reader=_fake_cas)
    snap_holdings = parsed_to_snapshot_holdings(holdings, nav_map={})  # no NAV feed
    assert snap_holdings[0].current_value == 5000.0  # CAS-reported valuation used


def test_parsed_to_snapshot_fills_category_from_map():
    # Holding category is filled from the mf_funds master so the portfolio
    # category-allocation + per-fund Category column are real (else every holding
    # buckets as "uncategorized" → a meaningless 100% donut).
    holdings, _ = parse_cas("x.pdf", None, reader=_fake_cas)
    filled = parsed_to_snapshot_holdings(
        holdings, category_map={"INF001": "Equity Scheme - Small Cap Fund"}
    )
    assert filled[0].category == "Equity Scheme - Small Cap Fund"
    # An ISIN absent from the master stays honestly uncategorized (not guessed).
    bare = parsed_to_snapshot_holdings(holdings, category_map={})
    assert bare[0].category == "uncategorized"


# --- consent gate wiring (B20) ----------------------------------------------
def test_upload_route_is_consent_gated_for_mf_analytics():
    from dhanradar.mf import router as mf_router

    assert mf_router._require_mf_consent.purpose == "mf_analytics"


# --- reap_stuck_cas_jobs unit tests -----------------------------------------
# Helpers shared across the three reaper tests.

class _ReaperRow:
    """Mimics a SQLAlchemy Row returned by the reaper SELECT."""

    def __init__(self, job_id, user_id, portfolio_id, source_hash):
        self.job_id = job_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id
        self.source_hash = source_hash


class _ReaperResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


def _make_reaper_session(rows):
    """Return an async context-manager session that yields `rows` on every execute."""
    execute_calls: list = []

    class _Sess:
        async def execute(self, stmt):
            execute_calls.append(stmt)
            return _ReaperResult(rows)

        async def commit(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

    return _Sess(), execute_calls


async def test_reap_stuck_cas_jobs_marks_old_queued_job_failed():
    """An old queued job (> 10 min, completed_at IS NULL) must be reaped and the
    summary must report count=1.  The session must receive both a SELECT and an
    UPDATE (two execute calls)."""
    import uuid
    from unittest.mock import AsyncMock, patch

    from dhanradar.tasks.mf import _reap_stuck_cas_jobs

    old_row = _ReaperRow(
        job_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        portfolio_id=uuid.uuid4(),
        source_hash="deadbeef",
    )
    sess, calls = _make_reaper_session([old_row])
    dedup_clear_mock = AsyncMock()

    with (
        patch("dhanradar.db.admin_task_session", return_value=sess),
        patch("dhanradar.redis_client.get_redis", return_value=AsyncMock()),
        patch("dhanradar.mf.service.dedup_clear", dedup_clear_mock),
    ):
        summary = await _reap_stuck_cas_jobs()

    assert "1" in summary and "stuck" in summary
    # SELECT + UPDATE = at least 2 execute calls.
    assert len(calls) >= 2


async def test_reap_stuck_cas_jobs_does_not_touch_recent_job():
    """When the DB returns no rows (recent job does not cross the cutoff), the reaper
    must return a zero-count summary and must NOT issue an UPDATE."""
    from unittest.mock import patch

    from dhanradar.tasks.mf import _reap_stuck_cas_jobs

    sess, calls = _make_reaper_session([])  # empty → nothing to reap

    with patch("dhanradar.db.admin_task_session", return_value=sess):
        summary = await _reap_stuck_cas_jobs()

    assert "0" in summary
    # Only the SELECT should have been issued (early return after empty rows check).
    assert len(calls) == 1


async def test_reap_stuck_cas_jobs_does_not_touch_done_job():
    """A 'done' job is excluded by the WHERE status IN (...) predicate; the DB
    returns zero rows, so the reaper produces a zero-count summary."""
    from unittest.mock import patch

    from dhanradar.tasks.mf import _reap_stuck_cas_jobs

    # Simulate DB correctly excluding 'done' jobs → empty result set.
    sess, calls = _make_reaper_session([])

    with patch("dhanradar.db.admin_task_session", return_value=sess):
        summary = await _reap_stuck_cas_jobs()

    assert "0" in summary
    assert len(calls) == 1


# --- B61: AMFI batch deduplication ------------------------------------------

class _FakeNavRow:
    """Minimal NavRow stand-in — carries only the attributes the helpers read."""

    def __init__(
        self,
        isin_growth: str | None,
        isin_reinvest: str | None,
        nav_date: object,
        nav: float,
        amfi_code: str,
        scheme_name: str,
        category: str,
    ) -> None:
        self.isin_growth = isin_growth
        self.isin_reinvest = isin_reinvest
        self.nav_date = nav_date
        self.nav = nav
        self.amfi_code = amfi_code
        self.scheme_name = scheme_name
        self.category = category


def test_navrows_to_nav_upserts_deduplicates_same_isin_nav_date():
    """Duplicate (isin, nav_date) in the batch → exactly one output row, last-seen wins."""
    from datetime import date as _date

    from dhanradar.tasks.mf import _navrows_to_nav_upserts

    d = _date(2026, 6, 10)
    rows = [
        _FakeNavRow("INF001", None, d, 100.0, "A001", "Fund A", "Equity"),
        _FakeNavRow("INF001", None, d, 105.0, "A001", "Fund A", "Equity"),  # duplicate
    ]
    result = _navrows_to_nav_upserts(rows)

    assert len(result) == 1, "duplicate (isin, nav_date) must be collapsed to one row"
    assert result[0]["isin"] == "INF001"
    assert result[0]["nav"] == 105.0, "last-seen value must win"
    assert result[0]["nav_date"] == d
    assert result[0]["source"] == "amfi"


def test_navrows_to_nav_upserts_skips_none_isin():
    """Rows where both ISINs are None must be silently dropped."""
    from datetime import date as _date

    from dhanradar.tasks.mf import _navrows_to_nav_upserts

    rows = [
        _FakeNavRow(None, None, _date(2026, 6, 10), 99.0, "X", "Y", "Z"),
        _FakeNavRow("INF002", None, _date(2026, 6, 10), 50.0, "B001", "Fund B", "Debt"),
    ]
    result = _navrows_to_nav_upserts(rows)
    assert len(result) == 1
    assert result[0]["isin"] == "INF002"


def test_navrows_to_fund_upserts_deduplicates_same_isin():
    """Duplicate isin in the batch → exactly one output row, last-seen wins."""
    from datetime import date as _date

    from dhanradar.tasks.mf import _navrows_to_fund_upserts

    d = _date(2026, 6, 10)
    rows = [
        _FakeNavRow("INF003", None, d, 200.0, "C001", "Fund C v1", "Hybrid"),
        _FakeNavRow("INF003", None, d, 210.0, "C001", "Fund C v2", "Hybrid"),  # duplicate
    ]
    result = _navrows_to_fund_upserts(rows)

    assert len(result) == 1, "duplicate isin must be collapsed to one row"
    assert result[0]["isin"] == "INF003"
    assert result[0]["scheme_name"] == "Fund C v2", "last-seen scheme_name must win"


# --- FIX 2: control-char sanitization ----------------------------------------

def test_clean_text_strips_control_chars_from_scheme_name():
    """_clean_text must remove ASCII control characters and preserve real punctuation."""
    from dhanradar.mf.cas import _clean_text

    raw = "AXIS\x02FUND"          # U+0002 STX embedded in the name
    cleaned = _clean_text(raw)

    assert "\x02" not in cleaned, "control char must be removed"
    assert "AXIS" in cleaned and "FUND" in cleaned, "words must be preserved"
    assert "  " not in cleaned, "double-space must be collapsed"


def test_clean_text_preserves_legitimate_punctuation():
    """_clean_text must not alter hyphens, slashes, parentheses, or periods."""
    from dhanradar.mf.cas import _clean_text

    name = "HDFC Top-100 Fund (Direct) / Growth 3.5%"
    assert _clean_text(name) == name


def test_clean_text_handles_falsy_input():
    """_clean_text must return the original value unchanged when s is falsy."""
    from dhanradar.mf.cas import _clean_text

    assert _clean_text("") == ""


def test_parse_cas_strips_control_chars_from_scheme_name():
    """End-to-end: parse_cas must deliver a scheme_name free of control chars."""

    def _reader_with_ctrl(_path, _password):
        return {
            "folios": [
                {"folio": "F99", "schemes": [
                    {"isin": "INF999", "amfi": "999", "scheme": "AXIS\x02FUND",
                     "close": 10.0,
                     "valuation": {"nav": 50.0, "value": 500.0, "cost": 400.0,
                                   "date": "2026-06-10"},
                     "transactions": []},
                ]},
            ]
        }

    holdings, _ = parse_cas("x.pdf", "pw", reader=_reader_with_ctrl)
    assert len(holdings) == 1
    h = holdings[0]
    assert "\x02" not in h.scheme_name
    assert "AXIS" in h.scheme_name and "FUND" in h.scheme_name


# --- B65: statement→investor sign normalization ------------------------------

def test_b65_statement_purchases_normalize_to_outflows():
    """PURCHASE txns with positive statement-convention amounts must become negative
    investor-convention outflows after parse_cas normalization (B65)."""

    def _reader(_p, _pw):
        return {"folios": [{"folio": "F1", "schemes": [
            {"isin": "INF100", "amfi": "100", "scheme": "Fund A", "close": 50.0,
             "valuation": {"nav": 80.0, "value": 4000.0, "cost": 8000.0, "date": "2026-06-01"},
             "transactions": [
                 {"date": "2024-01-01", "amount": 4000.0, "type": "PURCHASE"},
                 {"date": "2024-07-01", "amount": 4000.0, "type": "PURCHASE"},
             ]},
        ]}]}

    holdings, _ = parse_cas("x.pdf", None, reader=_reader)
    txns = holdings[0].txns
    assert len(txns) == 2
    assert txns[0].amount == -4000.0
    assert txns[1].amount == -4000.0


def test_b65_all_purchase_portfolio_xirr_computable():
    """THE B65 bug repro: an all-purchase portfolio must have a computable XIRR after
    normalization (before B65, all-positive flows triggered the all-same-sign guard
    in xirr() and returned None)."""
    from dhanradar.mf.snapshot import build_snapshot

    def _reader(_p, _pw):
        return {"folios": [{"folio": "F1", "schemes": [
            {"isin": "INF200", "amfi": "200", "scheme": "Fund B", "close": 100.0,
             "valuation": {"nav": 90.0, "value": 9000.0, "cost": 8000.0, "date": "2026-06-01"},
             "transactions": [
                 {"date": "2024-01-01", "amount": 4000.0, "type": "PURCHASE"},
                 {"date": "2024-07-01", "amount": 4000.0, "type": "PURCHASE"},
             ]},
        ]}]}

    holdings, _ = parse_cas("x.pdf", None, reader=_reader)
    # current_value > invested (9000 > 8000) → XIRR should be computable and positive.
    snap_holdings = parsed_to_snapshot_holdings(holdings, nav_map={"INF200": 90.0})
    snap = build_snapshot(snap_holdings)
    # Before B65 this returned None (all purchase flows were positive → all-same-sign guard).
    assert snap.xirr_pct is not None
    assert snap.xirr_pct > 0


def test_b65_redemption_becomes_inflow():
    """REDEMPTION txns have negative amounts in statement convention (units leave).
    After normalization (negate) they must be positive investor-convention inflows."""

    def _reader(_p, _pw):
        return {"folios": [{"folio": "F1", "schemes": [
            {"isin": "INF300", "amfi": "300", "scheme": "Fund C", "close": 0.0,
             "valuation": {"nav": 90.0, "value": 0.0, "cost": 0.0, "date": "2026-06-01"},
             "transactions": [
                 {"date": "2025-01-01", "amount": -2500.0, "type": "REDEMPTION"},
             ]},
        ]}]}

    holdings, _ = parse_cas("x.pdf", None, reader=_reader)
    assert holdings[0].txns[0].amount == 2500.0


def test_b65_dividend_payout_kept_as_inflow():
    """DIVIDEND_PAYOUT is cash credited to the investor — kept as printed (positive),
    not negated."""

    def _reader(_p, _pw):
        return {"folios": [{"folio": "F1", "schemes": [
            {"isin": "INF400", "amfi": "400", "scheme": "Fund D", "close": 50.0,
             "valuation": {"nav": 10.0, "value": 500.0, "cost": 500.0, "date": "2026-06-01"},
             "transactions": [
                 {"date": "2025-03-01", "amount": 120.0, "type": "DIVIDEND_PAYOUT"},
             ]},
        ]}]}

    holdings, _ = parse_cas("x.pdf", None, reader=_reader)
    assert holdings[0].txns[0].amount == 120.0


def test_b65_internal_and_tax_rows_excluded():
    """B65 cashflow exclusion preserved + B3 ledger capture:
    - STAMP_DUTY_TAX / STT_TAX / MISC carry no external cash AND no units → fully excluded.
    - DIVIDEND_REINVEST carries reinvested UNITS but no external cash → captured for the ledger (B3)
      with amount=0, so it stays XIRR-neutral (the cashflow path filters amount==0). The PURCHASE is
      the only cashflow-bearing txn."""

    def _reader(_p, _pw):
        return {"folios": [{"folio": "F1", "schemes": [
            {"isin": "INF500", "amfi": "500", "scheme": "Fund E", "close": 100.0,
             "valuation": {"nav": 50.0, "value": 5000.0, "cost": 4000.0, "date": "2026-06-01"},
             "transactions": [
                 {"date": "2024-01-01", "amount": 4000.0, "type": "PURCHASE"},
                 {"date": "2024-01-01", "amount": 8.0,    "type": "STAMP_DUTY_TAX"},
                 {"date": "2024-01-01", "amount": 0.5,    "type": "STT_TAX"},
                 {"date": "2024-06-01", "amount": 200.0, "units": 4.0, "type": "DIVIDEND_REINVEST"},
                 {"date": "2025-01-01", "amount": 5.0,    "type": "MISC"},
             ]},
        ]}]}

    holdings, _ = parse_cas("x.pdf", None, reader=_reader)
    txns = holdings[0].txns
    by_type = {t.txn_type: t for t in txns}
    # tax/misc fully excluded; purchase (cashflow) + dividend_reinvest (ledger) survive.
    assert set(by_type) == {"purchase", "dividend_reinvest"}, by_type
    assert by_type["purchase"].amount == -4000.0
    # reinvest captured for the ledger: units kept, amount 0 (XIRR-neutral).
    assert by_type["dividend_reinvest"].amount == 0.0
    assert by_type["dividend_reinvest"].units == 4.0
    # the only cashflow-bearing (non-zero amount) txn is the purchase — B65 preserved.
    assert [t for t in txns if t.amount] == [by_type["purchase"]]


def test_b65_missing_type_defaults_to_negate():
    """A txn dict with no 'type' key (casparser 0.7.x plain-dict compatibility)
    defaults to the negate path — outflow convention (amount negated)."""

    def _reader(_p, _pw):
        return {"folios": [{"folio": "F1", "schemes": [
            {"isin": "INF600", "amfi": "600", "scheme": "Fund F", "close": 10.0,
             "valuation": {"nav": 10.0, "value": 100.0, "cost": 100.0, "date": "2026-06-01"},
             "transactions": [
                 {"date": "2024-01-01", "amount": 1000.0},  # no "type" key
             ]},
        ]}]}

    holdings, _ = parse_cas("x.pdf", None, reader=_reader)
    assert holdings[0].txns[0].amount == -1000.0


def test_b65_enum_like_type_handled():
    """casparser 1.0+ model_dump(mode="python") leaves 'type' as a str-subclass enum
    member (e.g. TransactionType.PURCHASE where .value == 'PURCHASE').
    parse_cas must handle this via getattr(.value) — not break on the enum object."""

    # Deliberately (str, Enum) — NOT StrEnum: str(member) yields
    # "_FakeType.PURCHASE" (exactly as casparser's TransactionType does), so
    # only the getattr(.value) path resolves the bare "PURCHASE". A str()-based
    # implementation would fail this test.
    class _FakeType(str, enum.Enum):  # noqa: UP042 — deliberately (str, Enum), not StrEnum: mirrors casparser's TransactionType where str(member) != .value
        PURCHASE = "PURCHASE"

    def _reader(_p, _pw):
        return {"folios": [{"folio": "F1", "schemes": [
            {"isin": "INF700", "amfi": "700", "scheme": "Fund G", "close": 10.0,
             "valuation": {"nav": 10.0, "value": 100.0, "cost": 500.0, "date": "2026-06-01"},
             "transactions": [
                 {"date": "2024-01-01", "amount": 500.0, "type": _FakeType.PURCHASE},
             ]},
        ]}]}

    holdings, _ = parse_cas("x.pdf", None, reader=_reader)
    # The getattr(.value) path must resolve PURCHASE → negate → -500.0.
    assert holdings[0].txns[0].amount == -500.0


def _b65_single_txn_reader(ttype: str | None, amount: float):
    """Build a fake reader with one txn of the given type/amount (B65 helpers)."""
    txn: dict = {"date": "2024-05-01", "amount": amount}
    if ttype is not None:
        txn["type"] = ttype

    def _reader(_p, _pw):
        return {"folios": [{"folio": "F1", "schemes": [
            {"isin": "INF800", "amfi": "800", "scheme": "Fund H", "close": 10.0,
             "valuation": {"nav": 10.0, "value": 100.0, "cost": 100.0, "date": "2026-06-01"},
             "transactions": [txn]},
        ]}]}

    return _reader


def test_b65_switch_and_reversal_types_negated():
    """Each units-bearing type is negated: switches become out/inflows that cancel
    pairwise at portfolio level; reversal rows invert their statement sign."""
    cases = [
        ("SWITCH_IN", 3000.0, -3000.0),        # outflow into the target fund
        ("SWITCH_OUT", -3000.0, 3000.0),       # inflow back to the investor
        ("SWITCH_IN_MERGER", 1500.0, -1500.0),
        ("SWITCH_OUT_MERGER", -1500.0, 1500.0),
        ("REVERSAL", -700.0, 700.0),           # cancels its original when in-window
    ]
    for ttype, statement_amount, expected in cases:
        holdings, _ = parse_cas("x.pdf", None, reader=_b65_single_txn_reader(ttype, statement_amount))
        assert holdings[0].txns[0].amount == expected, ttype


def test_b65_remaining_excluded_types():
    """TDS_TAX / SEGREGATION / UNKNOWN rows carry no usable external cash flow and
    are excluded (completes the _TXN_FLOW_EXCLUDED coverage)."""
    for ttype in ("TDS_TAX", "SEGREGATION", "UNKNOWN"):
        holdings, _ = parse_cas("x.pdf", None, reader=_b65_single_txn_reader(ttype, 50.0))
        assert holdings[0].txns == [], ttype


# --- Constituents parser: section-header / subtotal row filter --------------
# Bug repro: mf.mf_fund_constituents for INF789F01WY2 (UTI), as_of_month
# 2026-05-01, had 107 rows whose weight_pct summed to ~199.66% because
# section-header/subtotal disclosure-sheet rows were ingested as holdings.
# See docs/rca/README.md.


def _col_map(*headers: str) -> dict[str, int]:
    return {h.lower(): i for i, h in enumerate(headers)}


def test_extract_sebi_row_skips_lettered_section_header():
    """A section header like "(a) Listed/awaiting listing on Stock Exchanges" carries
    the section's own subtotal weight — must not be ingested alongside the holdings
    it summarizes."""
    col_map = _col_map("Name of Instrument", "ISIN", "% to NAV", "Market Value")
    row = ["(a)  Listed/awaiting listing on Stock Exchanges", "", "99.83", "23456.78"]
    assert _extract_sebi_row(row, col_map, "UTI Equity Fund", "UTI", date(2026, 5, 1)) is None


def test_extract_sebi_row_skips_unlisted_header():
    col_map = _col_map("Name of Instrument", "ISIN", "% to NAV", "Market Value")
    row = ["Unlisted", "", "0.17", "40.12"]
    assert _extract_sebi_row(row, col_map, "UTI Equity Fund", "UTI", date(2026, 5, 1)) is None


def test_extract_sebi_row_skips_subtotal_by_keyword():
    col_map = _col_map("Name of Instrument", "ISIN", "% to NAV", "Market Value")
    row = ["Sub Total", "", "99.83", "23456.78"]
    assert _extract_sebi_row(row, col_map, "UTI Equity Fund", "UTI", date(2026, 5, 1)) is None


def test_extract_sebi_row_skips_label_only_row_with_no_data():
    """A bare category label with no ISIN and no numbers at all is structurally
    not a holding, even when its name matches no "total"/header keyword."""
    col_map = _col_map("Name of Instrument", "ISIN", "% to NAV", "Market Value")
    row = ["Money Market Instruments", "", "", ""]
    assert _extract_sebi_row(row, col_map, "UTI Equity Fund", "UTI", date(2026, 5, 1)) is None


def test_extract_sebi_row_keeps_no_isin_row_with_real_data():
    """Cash/receivable lines legitimately carry no ISIN but do carry a weight — the
    structural no-ISIN guard must not drop these (no over-strip)."""
    col_map = _col_map("Name of Instrument", "ISIN", "% to NAV", "Market Value")
    row = ["Net Receivables/(Payables)", "", "0.42", "98.5"]
    result = _extract_sebi_row(row, col_map, "UTI Equity Fund", "UTI", date(2026, 5, 1))
    assert result is not None
    assert result["constituent_name"] == "Net Receivables/(Payables)"


def test_extract_sebi_row_strips_eq_prefix():
    """UTI writes "EQ - ABB INDIA LTD." in the Name-of-Instrument cell — strip the
    display-only instrument-type prefix so the UI shows a clean stock name."""
    col_map = _col_map("Name of Instrument", "ISIN", "% to NAV", "Market Value", "Sector")
    row = ["EQ - ABB INDIA LTD.", "INE117A01022", "5.234", "1234.56", "Capital Goods"]
    result = _extract_sebi_row(row, col_map, "UTI Equity Fund", "UTI", date(2026, 5, 1))
    assert result is not None
    assert result["constituent_name"] == "ABB INDIA LTD."
    assert result["constituent_isin"] == "INE117A01022"
    assert result["weight_pct"] == 5.234
    assert result["market_value_cr"] == 12.3456


# --- AUM extraction (root-cause fix 2026-07-05: aum_crore was 100% NULL) -----
def test_extract_sebi_row_keeps_grand_total_as_total_row():
    """NIPPON's literal "GRAND TOTAL" row must survive both the no-ISIN guard and
    the section-header drop, flagged is_total_row=True, so _upsert_constituents can
    use it as the scheme's AUM — the root cause of the 100%-NULL aum_crore bug was
    this row being unconditionally dropped before ever reaching that logic."""
    col_map = _col_map("Name of Instrument", "ISIN", "% to NAV", "Market Value")
    row = ["GRAND TOTAL", "", "100.00", "3587039.00"]
    result = _extract_sebi_row(row, col_map, "Nippon India Liquid Fund", "NIPPON", date(2026, 6, 1))
    assert result is not None
    assert result["is_total_row"] is True
    assert result["market_value_cr"] == 35870.39


def test_extract_sebi_row_keeps_net_assets_as_total_row():
    col_map = _col_map("Name of Instrument", "ISIN", "% to NAV", "Market Value")
    row = ["Net Assets", "", "100.00", "96750.00"]
    result = _extract_sebi_row(
        row, col_map, "Nippon India Conservative Hybrid Fund", "NIPPON", date(2026, 6, 1)
    )
    assert result is not None
    assert result["is_total_row"] is True
    assert result["market_value_cr"] == 967.5


def test_extract_sebi_row_does_not_flag_bare_subtotal_as_total_row():
    """A bare asset-class subtotal (UTI: "TOTAL: EQUITY AND EQUITY RELATED") must NOT
    be flagged is_total_row — only "grand total"/"net assets" identify the scheme's
    true AUM. Broadening to bare "total" was tried and reverted: it caused a
    sub-category subtotal to be written as the scheme's AUM for UTI (2026-07-05)."""
    col_map = _col_map("Name of Instrument", "ISIN", "% to NAV", "Market Value")
    row = ["TOTAL:  EQUITY AND EQUITY RELATED", "", "50.00", "194304.71"]
    assert (
        _extract_sebi_row(row, col_map, "UTI - Unit Linked Insurance Plan", "UTI", date(2026, 6, 1))
        is None
    )


def test_extract_sebi_row_market_fair_value_header_variant():
    """NIPPON debt schemes header the value column "Market/Fair Value\\n( Rs. in
    Lacs)" — the embedded "/fair" breaks a plain "market value" substring match."""
    col_map = _col_map(
        "Name of Instrument", "ISIN", "% to NAV", "Market/Fair Value\n( Rs. in Lacs)"
    )
    row = ["7.18% GOI 2033", "IN0020230019", "10.00", "9433.32"]
    result = _extract_sebi_row(
        row, col_map, "Nippon India Corporate Bond Fund", "NIPPON", date(2026, 6, 1)
    )
    assert result is not None
    assert result["market_value_cr"] == pytest.approx(94.3332)


def test_extract_sebi_row_hyphenated_market_value_header_variant():
    """UTI hyphenates the value column header: "MARKET-VALUE"."""
    col_map = _col_map("Name of Instrument", "ISIN", "% to NAV", "MARKET-VALUE")
    row = ["HDFC BANK LIMITED", "INE040A01034", "5.00", "11454.10"]
    result = _extract_sebi_row(row, col_map, "UTI - Large Cap Fund", "UTI", date(2026, 6, 1))
    assert result is not None
    assert result["market_value_cr"] == 114.541


def test_extract_sebi_row_hdfc_market_fair_value_space_variant():
    """HDFC's per-scheme manual-ingest files (2026-07-06 triage) header the value
    column "Market/ Fair Value (Rs. in Lacs.)" -- WITH a space after the slash,
    which the existing no-space "market/fair value" (NIPPON) variant doesn't match."""
    col_map = _col_map(
        "ISIN",
        "Coupon (%)",
        "Name Of the Instrument",
        "Market/ Fair Value (Rs. in Lacs.)",
    )
    row = ["INE134E08MC7", "7.77", "Power Finance Corporation Ltd.^", "28016.41"]
    result = _extract_sebi_row(
        row, col_map, "HDFC Liquid Fund", "HDFC", date(2026, 6, 1)
    )
    assert result is not None
    assert result["market_value_cr"] == pytest.approx(280.1641)


def test_parse_sebi_xlsx_hdfc_per_scheme_merged_title_banner():
    """HDFC's per-scheme manual-ingest files (~88 files, 2026-07-06 triage) title
    each sheet with a scheme-name banner that openpyxl's read_only mode repeats
    across MOST (not all) of the row's columns (a merged cell), with a couple of
    unrelated trailing metadata values (e.g. "Income", "Hybrid") -- not the single
    non-empty cell the original single-scheme-row detection expected. The banner
    also carries a boilerplate SEBI scheme-TYPE disclaimer in parens that must be
    stripped so the cleaned name resolves via pg_trgm fuzzy matching."""
    banner = "HDFC Liquid Fund (An Open ended Liquid scheme)"
    wb = Workbook()
    ws = wb.active
    ws.append([banner] * 10 + ["Income", "Hybrid"])
    ws.append(["Portfolio as on 15-Jun-2026"] * 10 + [None, None])
    ws.append([None] * 12)
    ws.append(
        [
            None,
            "ISIN",
            "Coupon (%)",
            "Name Of the Instrument",
            "Industry+ /Rating",
            "Quantity",
            "Market/ Fair Value (Rs. in Lacs.)",
            "% to NAV",
        ]
    )
    ws.append(
        [
            "",
            "INE134E08MC7",
            7.77,
            "Power Finance Corporation Ltd.^",
            "CRISIL - AAA",
            28000,
            28016.41,
            0.4,
        ]
    )
    ws.append(
        ["", "INE134E08ML8", 7.55, "REC LTD", "CRISIL - AAA", 25000, 25011.43, 0.36]
    )
    buf = io.BytesIO()
    wb.save(buf)

    rows = _parse_sebi_xlsx(buf.getvalue(), "HDFC")

    assert len(rows) == 2
    assert all(r["scheme_name"] == "HDFC Liquid Fund" for r in rows)
    assert rows[0]["constituent_isin"] == "INE134E08MC7"
    assert rows[0]["as_of_month"] == date(2026, 6, 1)
    assert rows[0]["market_value_cr"] == pytest.approx(280.1641)


def test_parse_sebi_xlsx_sbi_scheme_name_label_value_row():
    """SBI's per-scheme manual-ingest files (B80, 2026-07-07 triage — 461 files)
    put the real scheme name in a SEPARATE cell from its "SCHEME NAME :" label,
    inside a "Portfolio Details" sheet:
        ['', '', 'SCHEME NAME :', 'SBI Test Equity Fund', ...]
    Before the fix this row's 2 distinct non-empty values failed the
    merged-banner heuristic (candidate stayed ""), so `current_scheme` was never
    set from the real name — and because the sheet is literally named
    "Portfolio Details" (which contains the "portfolio" keyword), the per-scheme
    sheet-name FALLBACK kicked in and used the sheet name itself as the scheme,
    producing scheme_name="Portfolio Details" for every row (never resolves in
    mf_funds, however good the pg_trgm threshold). This test proves the label
    row is recovered and the sheet-name fallback never fires.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Portfolio Details"
    ws.append(["", "", "SBI MUTUAL FUND", "101", "", "", "", ""])
    ws.append(["", "", "SCHEME NAME :", "SBI Test Equity Fund", "", "", "", ""])
    ws.append(["", "", "Portfolio as on Mar 31, 2020", "", "", "", "", ""])
    ws.append(["", "", "", "", "", "", "", ""])
    ws.append(
        [
            "",
            "",
            "Name of the Instrument / Issuer",
            "ISIN",
            "Rating / Industry ^",
            "Quantity",
            "Market value (Rs. in Lakhs)",
            "% to AUM",
        ]
    )
    ws.append(["", "", "", "", "", "", "", ""])
    ws.append(
        ["", "100006", "HDFC Bank Ltd.", "INE040A01034", "Banks", "64293567", "554146.25", "10.42"]
    )
    buf = io.BytesIO()
    wb.save(buf)

    rows = _parse_sebi_xlsx(buf.getvalue(), "SBI")

    assert len(rows) == 1
    assert rows[0]["scheme_name"] == "SBI Test Equity Fund"
    assert rows[0]["as_of_month"] == date(2020, 3, 1)


def test_parse_sebi_xlsx_rejects_section_header_as_scheme_name_midfile():
    """A SEBI section-header row ("a) Mutual Fund Units / Exchange Traded
    Funds") appearing between two asset-class blocks of the SAME scheme must
    never overwrite `current_scheme` — confirmed 2026-07-07 in a real SBI
    multi-asset-allocation file, where this exact row satisfied the
    single-value scheme-name-candidate heuristic (and the "fund" keyword gate)
    and silently became the new scheme_name for every subsequent holding row.
    Reuses the existing `_SECTION_HEADER_RE` (already used to keep these rows
    out of constituent_name) as the rejection gate for scheme-name candidates.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Portfolio Details"
    ws.append(["", "", "SCHEME NAME :", "SBI Test Multi Asset Fund", "", "", "", ""])
    ws.append(["", "", "Portfolio as on Mar 31, 2020", "", "", "", "", ""])
    ws.append(["", "", "", "", "", "", "", ""])
    ws.append(
        [
            "",
            "",
            "Name of the Instrument / Issuer",
            "ISIN",
            "Rating / Industry ^",
            "Quantity",
            "Market value (Rs. in Lakhs)",
            "% to AUM",
        ]
    )
    ws.append(["", "", "", "", "", "", "", ""])
    ws.append(
        ["", "100006", "HDFC Bank Ltd.", "INE040A01034", "Banks", "64293567", "554146.25", "10.42"]
    )
    ws.append(["", "", "", "", "", "", "", ""])  # blank row — resets col_map
    ws.append(["", "", "a) Mutual Fund Units / Exchange Traded Funds", "", "", "", "", ""])
    ws.append(
        [
            "",
            "",
            "Name of the Instrument / Issuer",
            "ISIN",
            "Rating / Industry ^",
            "Quantity",
            "Market value (Rs. in Lakhs)",
            "% to AUM",
        ]
    )
    ws.append(
        ["", "100010", "SBI Liquid Fund - Direct - Growth", "INE123A01011", "MF", "1000", "100.0", "1.0"]
    )
    buf = io.BytesIO()
    wb.save(buf)

    rows = _parse_sebi_xlsx(buf.getvalue(), "SBI")

    assert len(rows) == 2
    assert all(r["scheme_name"] == "SBI Test Multi Asset Fund" for r in rows)


def test_parse_sebi_xlsx_month_dd_yyyy_no_space_after_comma():
    """ICICI_PRU's per-scheme manual-ingest files (B80, 2026-07-07 triage — 269
    files) banner the as-of date WITHOUT a space after the comma:
    "Portfolio as on May 31,2026" / "Figures as on Mar 31,2026" — the prior
    `,?\\s+` regex required at least one space there and never matched, so
    every row kept as_of_month=None and `_upsert_constituents` silently drops
    any row with no as_of_month (zero_rows_upserted_scheme_unresolved), even
    though the scheme name itself resolves fine via pg_trgm."""
    wb = Workbook()
    ws = wb.active
    ws.append(["", "ICICI Prudential Mutual Fund", "", "", "", "", "", "", "", ""])
    ws.append(["", "ICICI Prudential Test ETF", "", "", "", "", "", "", "", ""])
    ws.append(["", "Portfolio as on May 31,2026", "", "", "", "", "", "", "", ""])
    ws.append(
        [
            "",
            "Company/Issuer/Instrument Name",
            "ISIN",
            "Coupon",
            "Industry/Rating",
            "Quantity",
            "Exposure/Market Value(Rs.Lakh)",
            "% to Nav",
            "",
            "",
        ]
    )
    ws.append(
        ["", "ITC Ltd.", "INE154A01025", "", "Diversified Fmcg", "7208379", "20680.84", "26.98", "", ""]
    )
    buf = io.BytesIO()
    wb.save(buf)

    rows = _parse_sebi_xlsx(buf.getvalue(), "ICICI_PRU")

    assert len(rows) == 1
    assert rows[0]["as_of_month"] == date(2026, 5, 1)


def test_parse_sebi_xlsx_closed_ended_series_name_left_unmangled():
    """A genuinely closed-ended/matured scheme name (no live ISIN in mf_funds —
    verified 2026-07-07 against live prod: 'SBI Debt Fund Series C-16' /
    'SBI Debt Fund Series B-35' score <0.27 similarity against every SBI fund,
    confirming these are not in the catalog at all, not a formatting mismatch)
    must be extracted EXACTLY as written — the "SCHEME NAME :" label-row
    recovery must not mangle or truncate a real name it doesn't specifically
    target, so a downstream fuzzy match (or its correct absence) never gets a
    false positive from over-eager cleanup."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Portfolio Details"
    ws.append(["", "", "SCHEME NAME :", "SBI Debt Fund Series C-16", "", "", "", ""])
    ws.append(["", "", "Portfolio as on Aug 16, 2018", "", "", "", "", ""])
    ws.append(["", "", "", "", "", "", "", ""])
    ws.append(
        [
            "",
            "",
            "Name of the Instrument / Issuer",
            "ISIN",
            "Rating / Industry ^",
            "Quantity",
            "Market value (Rs. in Lakhs)",
            "% to AUM",
        ]
    )
    ws.append(["", "", "", "", "", "", "", ""])
    ws.append(
        ["", "100006", "HDFC Bank Ltd.", "INE040A01034", "Banks", "64293567", "554146.25", "10.42"]
    )
    buf = io.BytesIO()
    wb.save(buf)

    rows = _parse_sebi_xlsx(buf.getvalue(), "SBI")

    assert len(rows) == 1
    assert rows[0]["scheme_name"] == "SBI Debt Fund Series C-16"


def test_parse_sebi_xlsx_xlrd_fallback_for_legacy_binary_xls(monkeypatch):
    """A genuine legacy binary .xls (openpyxl raises BadZipFile trying to read
    it as a zip container — confirmed 2026-07-08 against ABSL's real
    ~107-sheet monthly portfolio) falls back to xlrd via the module's shim
    classes, so the SAME parsing loop runs unchanged. Mirrors ABSL's real
    per-scheme banner: a 2-distinct-value row pairing a short fund CODE with
    the real scheme name, followed by a bare scheme-TYPE description row that
    must NOT overwrite the correctly-detected name."""
    import xlrd

    from dhanradar.tasks.mf import _parse_sebi_xlsx as target_fn

    class _FakeSheet:
        def __init__(self, rows: list[list]) -> None:
            self._rows = rows
            self.nrows = len(rows)

        def row_values(self, r: int) -> list:
            return list(self._rows[r])

    class _FakeBook:
        def __init__(self, sheets: dict[str, list[list]]) -> None:
            self._sheets = sheets

        def sheet_names(self) -> list[str]:
            return list(self._sheets)

        def sheet_by_name(self, name: str) -> _FakeSheet:
            return _FakeSheet(self._sheets[name])

    scheme_rows = [
        [
            "ABBSEIIF",
            "ADITYA BIRLA SUN LIFE BSE INDIA INFRASTRUCTURE INDEX FUND",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ],
        [
            "",
            "An open ended Index Fund replicating the BSE India Infrastructure Total Return Index",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ],
        ["", "Portfolio Statement as on May 31,2026", "", "", "", "", "", "", ""],
        [
            "",
            "Name of the Instrument",
            "ISIN",
            "Industry^ / Rating",
            "Quantity",
            "Market/Fair Value\n(Rs.in Lacs)",
            "% to Net Assets",
            "Yield",
            "Yield to Call",
        ],
        ["", "Larsen & Toubro Limited", "INE018A01030", "Construction", 8218.0, 335.02, 0.0989, "", ""],
    ]
    fake_book = _FakeBook({"Index": [["Sr", "Code", "Name"]], "ABBSEIIF": scheme_rows})
    monkeypatch.setattr(xlrd, "open_workbook", lambda file_contents: fake_book)

    # Not a real xlsx — openpyxl raises BadZipFile, triggering the xlrd fallback.
    rows = target_fn(b"not a real xlsx file", "ABSL")

    assert len(rows) == 1
    assert rows[0]["scheme_name"] == "ADITYA BIRLA SUN LIFE BSE INDIA INFRASTRUCTURE INDEX FUND"
    assert rows[0]["constituent_isin"] == "INE018A01030"


def test_parse_sebi_xlsx_2value_banner_disambiguates_via_whitespace(monkeypatch):
    """A fund CODE can coincidentally contain a scheme-name keyword as a bare
    substring (e.g. ABSL's 'C10YGETF' ends in 'ETF' — confirmed 2026-07-08),
    making the keyword-match rule ambiguous (both values match). The
    whitespace tie-breaker must still pick the real (spaced) name, since a
    fund code is always a single space-free token."""
    import xlrd

    from dhanradar.tasks.mf import _parse_sebi_xlsx as target_fn

    class _FakeSheet:
        def __init__(self, rows: list[list]) -> None:
            self._rows = rows
            self.nrows = len(rows)

        def row_values(self, r: int) -> list:
            return list(self._rows[r])

    class _FakeBook:
        def __init__(self, sheets: dict[str, list[list]]) -> None:
            self._sheets = sheets

        def sheet_names(self) -> list[str]:
            return list(self._sheets)

        def sheet_by_name(self, name: str) -> _FakeSheet:
            return _FakeSheet(self._sheets[name])

    scheme_rows = [
        ["C10YGETF", "ADITYA BIRLA SUN LIFE CRISIL 10 YEAR GILT ETF", "", "", "", "", "", "", ""],
        [
            "",
            "An open ended Debt Exchange Traded Fund tracking the CRISIL 10 Year Gilt Index.",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ],
        ["", "Portfolio Statement as on May 31,2026", "", "", "", "", "", "", ""],
        [
            "",
            "Name of the Instrument",
            "ISIN",
            "Rating",
            "Quantity",
            "Market/Fair Value\n(Rs.in Lacs)",
            "% to Net Assets",
            "Yield",
            "Yield to Call",
        ],
        ["", "Government of India (06/10/2035)", "IN0020250091", "Sovereign", 3145000.0, 3032.87, 0.9577, "", ""],
    ]
    fake_book = _FakeBook({"Index": [["Sr", "Code", "Name"]], "C10YGETF": scheme_rows})
    monkeypatch.setattr(xlrd, "open_workbook", lambda file_contents: fake_book)

    rows = target_fn(b"not a real xlsx file", "ABSL")

    assert len(rows) == 1
    assert rows[0]["scheme_name"] == "ADITYA BIRLA SUN LIFE CRISIL 10 YEAR GILT ETF"


def test_parse_sebi_xlsx_reraises_when_neither_format_readable():
    """A file that is NEITHER a real .xlsx NOR a real legacy binary .xls —
    e.g. an AMC website 'Fund Details' page saved with a misleading .xls
    extension (confirmed 2026-07-08: ~52 SBI files are plain HTML, not a
    spreadsheet at all — a different data source entirely, tracked
    separately) — must raise, not silently return zero rows. The caller
    (tasks/manual_ingest.py) then marks the file failed with an honest parse
    error instead of the misleading zero_rows_upserted_scheme_unresolved."""
    with pytest.raises(Exception):  # noqa: B017 — exact type varies (xlrd's own error)
        _parse_sebi_xlsx(b"<html><body>not a spreadsheet</body></html>", "SBI")


def test_drop_over_covered_funds_skips_fund_over_105_pct():
    """ADR-0039 fail-closed guard: a fund whose weight_pct rows already sum past
    105% is dropped entirely rather than written half-garbage."""
    batch = [
        {"isin": "INF789F01WY2", "weight_pct": 99.83},
        {"isin": "INF789F01WY2", "weight_pct": 99.83},  # header-leak duplicates the weight
        {"isin": "INF000OTHER", "weight_pct": 40.0},
        {"isin": "INF000OTHER", "weight_pct": 50.0},
    ]
    result = _drop_over_covered_funds(batch, "UTI")
    isins = {r["isin"] for r in result}
    assert "INF789F01WY2" not in isins
    assert "INF000OTHER" in isins
    assert len(result) == 2
