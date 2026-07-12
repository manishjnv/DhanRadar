"""
Unit tests for the AMFI-portal SSD bulk-enumeration sweep
(dhanradar/tasks/manual_ingest.py::amfi_ssd_sweep, Channel D — MANUAL-ONLY,
never scheduled). No network, no DB — httpx.AsyncClient and intake_upload are
both mocked; looks_like_ssd_pdf is exercised for real (it needs no PDF-parse
detail beyond a monkeypatched pypdf extraction, mirrored from
test_disclosure_parsers.py's own `_patch_ssd` pattern).

Covers:
  - id -> URL builder (SSD_URL_TMPL).
  - Response sniffing: PDF magic bytes vs the AMFI-portal's real IIS 404 page.
  - Range validation: end < start, and the MAX_SWEEP_RANGE cap (network never
    touched for either).
  - The routing call: only a real "SCHEME SUMMARY DOCUMENT" PDF hit reaches
    intake_upload(); a plain 404 and a non-SSD PDF (SID/SAI sharing the same
    id space) never do.
  - amc_filter narrows before intake_upload is called.
  - intake_upload's returned status (duplicate/unsupported/pending) is
    reflected in the summary counters.
  - One bad id's fetch exception never aborts the sweep.
"""

from __future__ import annotations

import re

import pytest

from dhanradar.tasks import manual_ingest as mi

# The real AMFI-portal 404 shape (IIS default), captured verbatim during the
# 2026-07-12 probe — used here so the "miss" fixture is realistic, not just
# an empty string.
_HTML_404 = (
    b'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN">'
    b"<html><head><title>404 - File or directory not found.</title></head>"
    b"<body>404 - File or directory not found.</body></html>"
)

_SSD_TEXT = "Page 1 Fields SCHEME SUMMARY DOCUMENT 1 Fund Name HDFC Small Cap Fund 2 Options"


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes) -> None:
        self.status_code = status_code
        self.content = content


class _FakeAsyncClient:
    """Stand-in for httpx.AsyncClient — keyed by scheme id parsed out of the
    requested URL, same style as test_manual_ingest_email_poller.py's
    _FakeImap."""

    def __init__(self, responses: dict[int, _FakeResponse | Exception]) -> None:
        self.responses = responses
        self.requested_ids: list[int] = []

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def get(self, url: str, headers: dict[str, str] | None = None) -> _FakeResponse:
        scheme_id = int(re.search(r"SSD_(\d+)\.pdf", url).group(1))  # type: ignore[union-attr]
        self.requested_ids.append(scheme_id)
        resp = self.responses.get(scheme_id, _FakeResponse(404, _HTML_404))
        if isinstance(resp, Exception):
            raise resp
        return resp


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test in this file skips the real 1s/id rate-limit delay."""
    monkeypatch.setattr(mi, "_SWEEP_DELAY_SECONDS", 0)


def _install_fake_client(
    monkeypatch: pytest.MonkeyPatch, responses: dict[int, _FakeResponse | Exception]
) -> _FakeAsyncClient:
    fake = _FakeAsyncClient(responses)
    monkeypatch.setattr(mi.httpx, "AsyncClient", lambda **_kw: fake)
    return fake


def _patch_looks_like_ssd(monkeypatch: pytest.MonkeyPatch, ssd_ids: set[int]) -> None:
    """Content-sniff stand-in: real SSD PDFs are those whose fixture bytes
    embed the marker b"SSD-MARKER:<id>" — avoids needing a real pypdf-parsable
    PDF for orchestration-level tests (the parser itself is unit-tested in
    test_disclosure_parsers.py)."""

    def _fake_looks_like_ssd_pdf(data: bytes) -> bool:
        m = re.search(rb"SSD-MARKER:(\d+)", data)
        return bool(m) and int(m.group(1)) in ssd_ids

    monkeypatch.setattr(
        "dhanradar.mf.disclosure_parsers.looks_like_ssd_pdf", _fake_looks_like_ssd_pdf
    )


def _pdf(scheme_id: int, extra_text: str = "") -> bytes:
    return f"%PDF-1.4 SSD-MARKER:{scheme_id} {extra_text}".encode()


# ---------------------------------------------------------------------------
# id -> URL builder
# ---------------------------------------------------------------------------


def test_url_builder() -> None:
    assert mi.SSD_URL_TMPL.format(id=8547) == "https://portal.amfiindia.com/spages/SSD_8547.pdf"
    assert mi.SSD_URL_TMPL.format(id=1) == "https://portal.amfiindia.com/spages/SSD_1.pdf"


# ---------------------------------------------------------------------------
# Response sniffing — PDF magic bytes vs the real AMFI-portal 404 HTML page
# ---------------------------------------------------------------------------


def test_response_sniffing_distinguishes_pdf_from_404_page() -> None:
    assert _pdf(1).startswith(b"%PDF")
    assert not _HTML_404.startswith(b"%PDF")


# ---------------------------------------------------------------------------
# Range validation — network never touched for either
# ---------------------------------------------------------------------------


def test_invalid_range_rejected_without_touching_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(**_kw):
        raise AssertionError("httpx.AsyncClient must never be constructed for an invalid range")

    monkeypatch.setattr(mi.httpx, "AsyncClient", _boom)

    result = mi.amfi_ssd_sweep(200, 100)
    assert result == "failed: invalid_range start_id=200 end_id=100"


def test_range_too_large_rejected_without_touching_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(**_kw):
        raise AssertionError("httpx.AsyncClient must never be constructed for an oversized range")

    monkeypatch.setattr(mi.httpx, "AsyncClient", _boom)

    result = mi.amfi_ssd_sweep(1, 1 + mi.MAX_SWEEP_RANGE)  # span = MAX+1
    assert result.startswith("failed: range_too_large")
    assert f"max={mi.MAX_SWEEP_RANGE}" in result


def test_range_at_cap_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """span == MAX_SWEEP_RANGE (not span - 1) is the valid boundary."""
    _install_fake_client(monkeypatch, {})
    _patch_looks_like_ssd(monkeypatch, ssd_ids=set())

    result = mi.amfi_ssd_sweep(1, mi.MAX_SWEEP_RANGE)  # span == MAX exactly
    assert not result.startswith("failed:")


# ---------------------------------------------------------------------------
# Routing — only a real SSD hit reaches intake_upload()
# ---------------------------------------------------------------------------


def test_only_real_ssd_hit_is_ingested(monkeypatch: pytest.MonkeyPatch) -> None:
    # id 10: 404 (miss). id 11: 200 PDF but NOT the SSD template (a SID
    # sharing the id space). id 12: 200 PDF, real SSD template.
    responses = {
        11: _FakeResponse(200, b"%PDF-1.4 SCHEME INFORMATION DOCUMENT not-an-ssd"),
        12: _FakeResponse(200, _pdf(12)),
    }
    _install_fake_client(monkeypatch, responses)
    _patch_looks_like_ssd(monkeypatch, ssd_ids={12})

    calls: list[tuple[bytes, str, str]] = []

    async def _fake_intake_upload(data, filename, channel, uploaded_by, amc_hint=None):
        calls.append((data, filename, channel))
        from dhanradar.mf.manual_ingest import IntakeResult

        return [(filename, IntakeResult("fake-id", "pending", None))], []

    monkeypatch.setattr(mi, "intake_upload", _fake_intake_upload)

    result = mi.amfi_ssd_sweep(10, 12)

    assert len(calls) == 1
    assert calls[0][1] == "SSD_12.pdf"
    assert calls[0][2] == "amfi_ssd_sweep"
    assert "pdf_hits=2" in result  # 11 and 12 were both real PDFs
    assert "ssd=1" in result  # only 12 passed the SSD banner sniff
    assert "ingested=1" in result


def test_fetch_error_on_one_id_does_not_abort_the_sweep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        5: RuntimeError("connection reset"),
        6: _FakeResponse(200, _pdf(6)),
    }
    _install_fake_client(monkeypatch, responses)
    _patch_looks_like_ssd(monkeypatch, ssd_ids={6})

    async def _fake_intake_upload(data, filename, channel, uploaded_by, amc_hint=None):
        from dhanradar.mf.manual_ingest import IntakeResult

        return [(filename, IntakeResult("fake-id", "pending", None))], []

    monkeypatch.setattr(mi, "intake_upload", _fake_intake_upload)

    result = mi.amfi_ssd_sweep(5, 6)

    assert "errors=1" in result
    assert "ingested=1" in result


# ---------------------------------------------------------------------------
# amc_filter narrows before intake_upload
# ---------------------------------------------------------------------------


def test_amc_filter_skips_non_matching_amc(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = {20: _FakeResponse(200, _pdf(20))}
    _install_fake_client(monkeypatch, responses)
    _patch_looks_like_ssd(monkeypatch, ssd_ids={20})
    # detect_amc() keyword-matches "hdfc" in the extracted first-page text.
    monkeypatch.setattr(mi, "_pdf_first_page_text", lambda data: "HDFC Small Cap Fund")

    def _boom(*_a, **_kw):
        raise AssertionError("intake_upload must never be called for a filtered-out AMC")

    monkeypatch.setattr(mi, "intake_upload", _boom)

    result = mi.amfi_ssd_sweep(20, 20, amc_filter="HSBC")

    assert "amc_filtered=1" in result
    assert "ingested=0" in result


def test_amc_filter_matching_amc_is_ingested(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = {21: _FakeResponse(200, _pdf(21))}
    _install_fake_client(monkeypatch, responses)
    _patch_looks_like_ssd(monkeypatch, ssd_ids={21})
    monkeypatch.setattr(mi, "_pdf_first_page_text", lambda data: "HDFC Small Cap Fund")

    calls: list[str] = []

    async def _fake_intake_upload(data, filename, channel, uploaded_by, amc_hint=None):
        calls.append(filename)
        from dhanradar.mf.manual_ingest import IntakeResult

        return [(filename, IntakeResult("fake-id", "pending", None))], []

    monkeypatch.setattr(mi, "intake_upload", _fake_intake_upload)

    result = mi.amfi_ssd_sweep(21, 21, amc_filter="hdfc")  # case-insensitive

    assert calls == ["SSD_21.pdf"]
    assert "ingested=1" in result


# ---------------------------------------------------------------------------
# intake_upload's returned status feeds the summary counters
# ---------------------------------------------------------------------------


def test_duplicate_status_counted_not_ingested(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = {30: _FakeResponse(200, _pdf(30))}
    _install_fake_client(monkeypatch, responses)
    _patch_looks_like_ssd(monkeypatch, ssd_ids={30})

    async def _fake_intake_upload(data, filename, channel, uploaded_by, amc_hint=None):
        from dhanradar.mf.manual_ingest import IntakeResult

        return [(filename, IntakeResult("existing-id", "duplicate", None))], []

    monkeypatch.setattr(mi, "intake_upload", _fake_intake_upload)

    result = mi.amfi_ssd_sweep(30, 30)

    assert "duplicate=1" in result
    assert "ingested=0" in result
