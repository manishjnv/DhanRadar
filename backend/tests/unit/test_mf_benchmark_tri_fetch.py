"""Unit tests for Phase 4c pt3 — the niftyindices TRI response parser + date windowing.

_parse_niftyindices_tri_response is a pure function (no DB/network) tested against a
REAL captured response (tests/fixtures/niftyindices_tri_nifty50_sample.json), fetched
live from https://niftyindices.com/BackPage/getTotalReturnIndexString 2026-07-12 (see
the PR description for the full probe transcript).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from dhanradar.tasks.mf import (
    _BENCHMARK_TRI_MAX_WINDOW_DAYS,
    _parse_niftyindices_tri_response,
    _tri_date_windows,
)

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture_bytes() -> bytes:
    return (_FIXTURES / "niftyindices_tri_nifty50_sample.json").read_bytes()


def _load_nifty100_fixture_bytes() -> bytes:
    """Phase 4c pt5 (2026-07-12) — real captured response for one of the 5 new
    canonical indices, fetched live the same session (see PR description for the
    full probe transcript). NTR_Value is "-" for this index (unlike Nifty 50's
    populated NTR_Value) — the parser must ignore it either way (gross TRI only)."""
    return (_FIXTURES / "niftyindices_tri_nifty100_sample.json").read_bytes()


# ---------------------------------------------------------------------------
# _parse_niftyindices_tri_response — real captured sample, new canonical index
# ---------------------------------------------------------------------------


def test_parse_nifty100_real_sample_returns_5_rows_in_source_order():
    rows = _parse_niftyindices_tri_response(_load_nifty100_fixture_bytes(), "nifty100_tri")
    assert len(rows) == 5
    assert [r[1] for r in rows] == [
        date(2026, 7, 10),
        date(2026, 7, 9),
        date(2026, 7, 8),
        date(2026, 7, 7),
        date(2026, 7, 6),
    ]


def test_parse_nifty100_real_sample_handles_dash_ntr_value():
    # NTR_Value is "-" for every row of this real response — must not raise/crash and
    # must still use TotalReturnsIndex (gross) exclusively.
    rows = _parse_niftyindices_tri_response(_load_nifty100_fixture_bytes(), "nifty100_tri")
    by_date = {d: v for _key, d, v in rows}
    assert by_date[date(2026, 7, 10)] == Decimal("34949.79")


def test_parse_real_sample_returns_5_rows_in_source_order():
    rows = _parse_niftyindices_tri_response(_load_fixture_bytes(), "nifty50_tri")
    assert len(rows) == 5
    assert [r[1] for r in rows] == [
        date(2026, 6, 5),
        date(2026, 6, 4),
        date(2026, 6, 3),
        date(2026, 6, 2),
        date(2026, 6, 1),
    ]


def test_parse_real_sample_uses_gross_tri_not_ntr():
    rows = _parse_niftyindices_tri_response(_load_fixture_bytes(), "nifty50_tri")
    by_date = {d: v for _key, d, v in rows}
    # TotalReturnsIndex (gross) for 05 Jun 2026 is "35295.11" — NOT NTR_Value "30701.36".
    assert by_date[date(2026, 6, 5)] == Decimal("35295.11")


def test_parse_real_sample_stamps_the_requested_index_key():
    rows = _parse_niftyindices_tri_response(_load_fixture_bytes(), "nifty50_tri")
    assert all(r[0] == "nifty50_tri" for r in rows)


def test_parse_strips_thousands_separator_commas():
    data = json.dumps(
        [{"Index Name": "Nifty 50", "Date": "10 Jun 2026", "TotalReturnsIndex": "1,23,456.78"}]
    ).encode()
    rows = _parse_niftyindices_tri_response(data, "nifty50_tri")
    assert rows == [("nifty50_tri", date(2026, 6, 10), Decimal("123456.78"))]


def test_parse_empty_array_returns_empty_list():
    assert _parse_niftyindices_tri_response(b"[]", "nifty50_tri") == []


# ---------------------------------------------------------------------------
# _tri_date_windows
# ---------------------------------------------------------------------------


def test_windows_single_day_range_is_one_window():
    d = date(2026, 6, 1)
    assert _tri_date_windows(d, d) == [(d, d)]


def test_windows_short_range_is_one_window():
    start, end = date(2026, 1, 1), date(2026, 3, 1)
    windows = _tri_date_windows(start, end)
    assert windows == [(start, end)]


def test_windows_splits_a_multi_year_range_at_the_365_day_cap():
    start, end = date(2015, 1, 1), date(2026, 7, 12)
    windows = _tri_date_windows(start, end)
    assert windows[0][0] == start
    assert windows[-1][1] == end
    # windows are contiguous, non-overlapping, none exceeds the cap.
    for i in range(len(windows) - 1):
        assert windows[i][1] + timedelta(days=1) == windows[i + 1][0]
    for w_start, w_end in windows:
        assert (w_end - w_start).days < _BENCHMARK_TRI_MAX_WINDOW_DAYS
    assert len(windows) > 1
