"""
Unit tests for `_source_tag_for` (admin/amc_coverage_router.py) — the pure
function that derives an AMC's overall source badge ("auto"/"manual"/"mixed"/
"none") from its own per-field CoverageCell modes. No DB — this is a plain
function of a dict of CoverageCell already-built values.
"""

from __future__ import annotations

from dhanradar.admin.amc_coverage_router import _source_tag_for
from dhanradar.admin.amc_coverage_schemas import CoverageCell


def _cell(mode: str, freq: str = "M", count: int = 1) -> CoverageCell:
    return CoverageCell(covered_count=count, mode=mode, freq=freq)  # type: ignore[arg-type]


def test_source_tag_all_none_when_every_field_has_no_known_source():
    fields = {"constituents": _cell("-"), "aum": _cell("-")}
    assert _source_tag_for(fields) == "none"


def test_source_tag_auto_when_every_known_field_is_automatic():
    fields = {"constituents": _cell("A"), "aum": _cell("A"), "manager": _cell("-")}
    assert _source_tag_for(fields) == "auto"


def test_source_tag_manual_when_every_known_field_is_manual():
    fields = {"constituents": _cell("ML"), "aum": _cell("ML"), "ter": _cell("-")}
    assert _source_tag_for(fields) == "manual"


def test_source_tag_mixed_when_some_fields_auto_and_some_manual():
    fields = {"constituents": _cell("A"), "aum": _cell("ML")}
    assert _source_tag_for(fields) == "mixed"


def test_source_tag_ignores_unset_fields_when_deciding_auto_vs_manual():
    # Only known-source fields vote — an AMC with 1 auto field and 6 "-" fields
    # is still "auto", not "mixed".
    fields = {
        "constituents": _cell("A"),
        "aum": _cell("-"),
        "ter": _cell("-"),
        "riskometer": _cell("-"),
        "benchmark": _cell("-"),
        "manager": _cell("-"),
        "exit_load": _cell("-"),
    }
    assert _source_tag_for(fields) == "auto"
