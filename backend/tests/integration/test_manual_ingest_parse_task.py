"""
Integration test for the manual disclosure inbox parse task
(dhanradar/tasks/manual_ingest.py::parse_manual_disclosure_file) on a real
trimmed SEBI-format disclosure fixture — exercises the ACTUAL byte-parsing
path (openpyxl.load_workbook via _parse_sebi_xlsx, the SAME parser
mf_constituents_fetch uses), not a synthetic dict.

`_upsert_constituents` (dhanradar/tasks/mf.py) is monkeypatched: it resolves
scheme names to ISINs via a live pg_trgm similarity query against mf.mf_funds,
which this suite has no existing fixture-builder for (no test anywhere
exercises `_upsert_constituents` end-to-end yet — a pre-existing gap, not
introduced here). This test instead proves the manual-ingest ORCHESTRATION —
detect AMC/period from real bytes, route through the shared upsert function
with the RIGHT arguments (rows, amc_name, run_id), and record the outcome on
the mf.manual_ingest_files row — end to end.
"""

from __future__ import annotations

import io
import uuid

import pytest
from openpyxl import Workbook

from dhanradar.mf.manual_ingest import stored_path_for
from dhanradar.models.mf import MfManualIngestFile
from dhanradar.tasks import manual_ingest as mi

pytestmark = pytest.mark.integration


def _build_hdfc_disclosure_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["Portfolio as on 30-June-2026"])
    ws.append(["HDFC Flexi Cap Fund"])
    ws.append(["Name of Instrument", "ISIN", "% to NAV", "Market Value"])
    ws.append(["HDFC Bank Ltd", "INE040A01034", "5.00", "1234.56"])
    ws.append(["Reliance Industries Ltd", "INE002A01018", "4.50", "1000.00"])
    ws.append(["Net Assets", "", "100.00", "24000.00"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def _insert_pending_row(
    db_session, *, filename: str, channel: str = "folder"
) -> tuple[str, bytes]:
    from dhanradar.mf.manual_ingest import sha256_bytes

    data = _build_hdfc_disclosure_xlsx()
    file_id = uuid.uuid4()
    db_session.add(
        MfManualIngestFile(
            id=file_id,
            sha256=sha256_bytes(data),
            original_filename=filename,
            channel=channel,
            status="pending",
        )
    )
    await db_session.commit()
    return str(file_id), data


@pytest.fixture(autouse=True)
def _tmp_store(monkeypatch: pytest.MonkeyPatch, tmp_path):
    from dhanradar.config import settings

    monkeypatch.setattr(settings, "MANUAL_INGEST_DIR", str(tmp_path))


async def test_parse_pipeline_parses_real_xlsx_and_marks_row_parsed(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    file_id, data = await _insert_pending_row(db_session, filename="HDFC_June2026.xlsx")
    stored_path_for(file_id, "HDFC_June2026.xlsx").write_bytes(data)

    captured: dict = {}

    async def _fake_upsert(rows, amc_name, run_id=None):
        captured["rows"] = rows
        captured["amc_name"] = amc_name
        captured["run_id"] = run_id
        return len(rows), 1  # (rows_upserted, aum_updates)

    monkeypatch.setattr("dhanradar.tasks.mf._upsert_constituents", _fake_upsert)

    result = await mi._parse_pipeline(file_id)

    assert result.startswith("parsed:")
    assert captured["amc_name"] == "HDFC"
    assert len(captured["rows"]) == 3  # 2 holdings + 1 total row — real parser output
    assert captured["run_id"] is not None  # ingestion_run() provenance threaded through

    # _parse_pipeline wrote via a DIFFERENT session (TaskSessionLocal) — this
    # session's identity map still holds the pre-parse object (expire_on_commit=
    # False), so it must be told to re-read from the DB rather than serve a cache hit.
    db_session.expire_all()
    row = await db_session.get(MfManualIngestFile, uuid.UUID(file_id))
    assert row.status == "parsed"
    assert row.amc_detected == "HDFC"
    assert row.rows_ingested == 3
    assert row.period_detected is not None
    assert row.parsed_at is not None


async def test_parse_pipeline_amc_undetectable_marks_unsupported(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    """A scheme name that names no known AMC → 'unsupported', never a guess, and
    _upsert_constituents is never called (nothing to route through)."""
    from dhanradar.mf.manual_ingest import sha256_bytes

    wb = Workbook()
    ws = wb.active
    ws.append(["Portfolio as on 30-June-2026"])
    ws.append(["XYZ Multi Cap Fund"])
    ws.append(["Name of Instrument", "ISIN", "% to NAV", "Market Value"])
    ws.append(["Some Stock Ltd", "INE999Z99999", "5.00", "100.00"])
    buf = io.BytesIO()
    wb.save(buf)
    data = buf.getvalue()

    file_id = uuid.uuid4()
    db_session.add(
        MfManualIngestFile(
            id=file_id,
            sha256=sha256_bytes(data),
            original_filename="unknown_amc.xlsx",
            channel="folder",
            status="pending",
        )
    )
    await db_session.commit()
    stored_path_for(str(file_id), "unknown_amc.xlsx").write_bytes(data)

    def _boom(*_a, **_kw):
        raise AssertionError("_upsert_constituents must never run for an undetectable AMC")

    monkeypatch.setattr("dhanradar.tasks.mf._upsert_constituents", _boom)

    result = await mi._parse_pipeline(str(file_id))

    assert result.startswith("unsupported:")
    db_session.expire_all()
    row = await db_session.get(MfManualIngestFile, file_id)
    assert row.status == "unsupported"
    assert row.error == "amc_or_period_undetectable"
    assert row.amc_detected is None


async def test_parse_pipeline_missing_stored_file_marks_failed(db_session):
    """The DB row exists but the on-disk file is gone (e.g. a manual delete) —
    fail closed, never crash silently."""
    file_id = uuid.uuid4()
    db_session.add(
        MfManualIngestFile(
            id=file_id,
            sha256="deadbeef" * 8,
            original_filename="missing.xlsx",
            channel="folder",
            status="pending",
        )
    )
    await db_session.commit()

    result = await mi._parse_pipeline(str(file_id))

    assert result == "failed: stored_file_missing"
    db_session.expire_all()
    row = await db_session.get(MfManualIngestFile, file_id)
    assert row.status == "failed"
    assert row.error == "stored_file_missing"


async def test_parse_pipeline_pdf_marks_archived_never_parsed(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    """Contract §2 — the SEBI parser is xlsx-only; a PDF is stored + row kept,
    marked 'archived' immediately, and NEVER routed through detect_amc_and_parse
    / _upsert_constituents (no fake parsing, no OCR)."""
    from dhanradar.mf.manual_ingest import sha256_bytes

    data = b"%PDF-1.4 fake factsheet bytes"
    file_id = uuid.uuid4()
    db_session.add(
        MfManualIngestFile(
            id=file_id,
            sha256=sha256_bytes(data),
            original_filename="HDFC_factsheet_June2026.pdf",
            channel="upload",
            status="pending",
        )
    )
    await db_session.commit()
    stored_path_for(str(file_id), "HDFC_factsheet_June2026.pdf").write_bytes(data)

    def _boom(*_a, **_kw):
        raise AssertionError("a PDF must never be routed through detect_amc_and_parse")

    monkeypatch.setattr("dhanradar.tasks.manual_ingest.detect_amc_and_parse", _boom)
    monkeypatch.setattr(
        "dhanradar.tasks.mf._upsert_constituents",
        lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("must never upsert a PDF")),
    )

    result = await mi._parse_pipeline(str(file_id))

    assert result == "archived: pdf_saved_for_later"
    db_session.expire_all()
    row = await db_session.get(MfManualIngestFile, file_id)
    assert row.status == "archived"
    assert row.amc_detected is None
    assert row.rows_ingested is None


async def test_parse_pipeline_threads_amc_hint_into_detection(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    """The optional amc_hint argument reaches detect_amc_and_parse as its
    3rd positional/keyword arg — the fallback plumbing contract §3 relies on."""
    file_id, data = await _insert_pending_row(db_session, filename="generic.xlsx")
    stored_path_for(file_id, "generic.xlsx").write_bytes(data)

    captured: dict = {}

    def _fake_detect(data, filename, amc_hint=None):
        captured["amc_hint"] = amc_hint
        return "HDFC", None, []

    monkeypatch.setattr("dhanradar.tasks.manual_ingest.detect_amc_and_parse", _fake_detect)

    result = await mi._parse_pipeline(file_id, amc_hint="HDFC")

    assert captured["amc_hint"] == "HDFC"
    # rows == [] -> amc_or_period_undetectable path (not the point of this test,
    # only that the hint was threaded through).
    assert result == "unsupported: amc_or_period_undetectable"


async def test_parse_pipeline_skips_already_terminal_row(db_session):
    """Idempotency guard: a re-enqueued/duplicate task run must never re-parse a
    row that already reached a terminal status."""
    file_id = uuid.uuid4()
    db_session.add(
        MfManualIngestFile(
            id=file_id,
            sha256="alreadydone" * 6,
            original_filename="already_parsed.xlsx",
            channel="folder",
            status="parsed",
            rows_ingested=5,
        )
    )
    await db_session.commit()

    result = await mi._parse_pipeline(str(file_id))
    assert result == "skip:parsed"


# ---------------------------------------------------------------------------
# File-class dispatcher (2026-07-07) — aaum / riskometer / performance files
# route to their own parsers + mf_funds writers, never the constituents path.
# Real DB writes asserted (no false positives): the actual mf_funds columns
# must change value.
# ---------------------------------------------------------------------------


def _build_riskometer_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "SR No.",
            "Scheme name",
            "Risk-o-meter level as on March 31, 2025",
            "Risk-o-meter level as on March 31, 2026",
            "Changes",
        ]
    )
    ws.append(["1", "ICICI Prudential Multicap Fund", "High", "Very High", "1"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _build_aaum_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "AAUM disclosure"
    ws.append([])
    ws.append(
        [
            "Sl. No.",
            "Scheme Category/ Scheme Name",
            "ICICI Mutual Fund : Net AAUM as on  2026-05-31",
            None,
            "GRAND TOTAL",
        ]
    )
    ws.append(["A)", "EQUITY SCHEMES", None, None, None])
    ws.append([None, "ICICI Prudential Multicap Fund", 1.0, 2.0, 15432.10])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def _seed_fund(db_session, isin: str, name: str) -> None:
    from dhanradar.models.mf import MfFund

    db_session.add(MfFund(isin=isin, scheme_name=name, amc_name="ICICI Prudential Mutual Fund"))
    await db_session.commit()


async def _insert_pending_bytes(db_session, *, filename: str, data: bytes) -> str:
    from dhanradar.mf.manual_ingest import sha256_bytes

    file_id = uuid.uuid4()
    db_session.add(
        MfManualIngestFile(
            id=file_id,
            sha256=sha256_bytes(data),
            original_filename=filename,
            channel="folder",
            status="pending",
        )
    )
    await db_session.commit()
    stored_path_for(str(file_id), filename).write_bytes(data)
    return str(file_id)


async def test_dispatcher_riskometer_writes_mf_funds_band(db_session, monkeypatch):
    isin = "INF109KTEST1"
    await _seed_fund(db_session, isin, "ICICI Prudential Multicap Fund")
    data = _build_riskometer_xlsx()
    file_id = await _insert_pending_bytes(
        db_session,
        filename="ICICIAnnual Disclosure of Scheme Riskometer_FY 2025-26.xlsx",
        data=data,
    )

    async def _fake_resolve(names, amc_name):
        assert amc_name == "ICICI_PRU"
        return {"ICICI Prudential Multicap Fund": isin}

    monkeypatch.setattr("dhanradar.tasks.mf._resolve_scheme_isins", _fake_resolve)

    result = await mi._parse_pipeline(file_id)
    assert result.startswith("parsed: riskometer")

    db_session.expire_all()
    from dhanradar.models.mf import MfFund

    fund = await db_session.get(MfFund, isin)
    assert fund.risk_o_meter == "Very High"  # LATEST FY column, verbatim regulatory band
    row = await db_session.get(MfManualIngestFile, uuid.UUID(file_id))
    assert row.status == "parsed"
    assert row.rows_ingested == 1


async def test_dispatcher_aaum_fills_null_aum_and_history(db_session, monkeypatch):
    from datetime import date as _date

    isin = "INF109KTEST2"
    await _seed_fund(db_session, isin, "ICICI Prudential Multicap Fund")
    data = _build_aaum_xlsx()
    file_id = await _insert_pending_bytes(
        db_session, filename="ICICI Monthly AAUM Disclosure - May 2026.xlsx", data=data
    )

    async def _fake_resolve(names, amc_name):
        return {"ICICI Prudential Multicap Fund": isin}

    monkeypatch.setattr("dhanradar.tasks.mf._resolve_scheme_isins", _fake_resolve)

    result = await mi._parse_pipeline(file_id)
    assert result.startswith("parsed: aaum")

    db_session.expire_all()
    from sqlalchemy import select

    from dhanradar.models.mf import MfAumHistory, MfFund

    fund = await db_session.get(MfFund, isin)
    assert float(fund.aum_crore) == 15432.10
    assert fund.aum_as_of == _date(2026, 5, 1)
    hist = (
        (await db_session.execute(select(MfAumHistory).where(MfAumHistory.isin == isin)))
        .scalars()
        .all()
    )
    assert len(hist) == 1 and float(hist[0].aum_crore) == 15432.10


async def test_dispatcher_aaum_never_clobbers_fresher_net_assets(db_session, monkeypatch):
    """The portfolio disclosure's stated net-assets (same field, fresher month)
    must win over an AAUM figure — fill-if-null-or-older only."""
    from datetime import date as _date

    from dhanradar.models.mf import MfFund

    isin = "INF109KTEST3"
    db_session.add(
        MfFund(
            isin=isin,
            scheme_name="ICICI Prudential Multicap Fund",
            amc_name="ICICI Prudential Mutual Fund",
            aum_crore=16000.00,
            aum_as_of=_date(2026, 6, 1),  # fresher than the AAUM file's May
        )
    )
    await db_session.commit()
    data = _build_aaum_xlsx()
    file_id = await _insert_pending_bytes(
        db_session, filename="ICICI Monthly AAUM Disclosure - May 2026 v2.xlsx", data=data
    )

    async def _fake_resolve(names, amc_name):
        return {"ICICI Prudential Multicap Fund": isin}

    monkeypatch.setattr("dhanradar.tasks.mf._resolve_scheme_isins", _fake_resolve)

    result = await mi._parse_pipeline(file_id)
    # Schemes RESOLVED but zero rows eligible to write (fresher figure already
    # in place) -> a legitimate parsed no-op, never a failure.
    assert result.startswith("parsed: aaum updates=0")

    db_session.expire_all()
    fund = await db_session.get(MfFund, isin)
    assert float(fund.aum_crore) == 16000.00  # untouched
    assert fund.aum_as_of == _date(2026, 6, 1)
