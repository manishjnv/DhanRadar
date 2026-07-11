"""
Unit tests for `_source_tag_for` (admin/amc_coverage_router.py) — the pure
function deriving an AMC's overall source badge from its EXPLICIT per-field
config entries (2026-07-11 contract change: it takes the AMC short name and
reads _SOURCE_CLASS directly; platform-wide AMFI defaults deliberately never
vote — a universal feed says nothing about whether THIS AMC has its own
pipeline). Also covers _class_for's platform-wide fallback.
"""

from __future__ import annotations

import pytest

from dhanradar.admin import amc_coverage_router as router
from dhanradar.admin.amc_coverage_router import _class_for, _source_tag_for


@pytest.fixture()
def _classes(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        router,
        "_SOURCE_CLASS",
        {
            "AutoOnly": {"constituents": ("A", "M")},
            "ManualOnly": {"constituents": ("ML", "M"), "aum": ("ML", "M")},
            "Mixed": {"constituents": ("A", "M"), "manager": ("ML", "M")},
        },
    )


def test_source_tag_none_for_amc_without_explicit_entries(_classes):
    # Long-tail AMC: platform-wide AMFI defaults still fill its CELLS, but the
    # badge stays "none" — it has no pipeline of its own.
    assert _source_tag_for("Sahara-like") == "none"


def test_source_tag_auto_manual_mixed(_classes):
    assert _source_tag_for("AutoOnly") == "auto"
    assert _source_tag_for("ManualOnly") == "manual"
    assert _source_tag_for("Mixed") == "mixed"


def test_class_for_prefers_explicit_entry_over_platform_default(_classes):
    # ManualOnly has its own aum entry — it wins over the platform default.
    assert _class_for("ManualOnly", "aum") == ("ML", "M")


def test_class_for_platform_defaults_for_amfi_fed_fields(_classes):
    # Any AMC without an explicit entry shows the AMFI consolidated-source
    # cadence for the four platform-wide fields...
    assert _class_for("Sahara-like", "aum") == ("ML", "Q")
    assert _class_for("Sahara-like", "ter") == ("ML", "M")
    assert _class_for("Sahara-like", "riskometer") == ("ML", "Q")
    assert _class_for("Sahara-like", "benchmark") == ("ML", "Q")
    # ...and no tag for fields with no universal source.
    assert _class_for("Sahara-like", "constituents") == ("-", "-")
    assert _class_for("Sahara-like", "manager") == ("-", "-")


def test_real_config_keys_match_rendered_short_names():
    """Every _SOURCE_CLASS key must be a REAL rendered short name — a key that
    doesn't match silently drops that AMC's tags (2026-07-11: 'Motilal' vs the
    override-rendered 'Motilal Oswal' left its AUTO badge missing in prod)."""
    from dhanradar.admin.amc_coverage_router import (
        _SHORT_NAME_OVERRIDES,
        _SOURCE_CLASS,
    )

    rendered = set(_SHORT_NAME_OVERRIDES.values())
    # First-word short names can't be enumerated without the DB; accept keys
    # that are either an override value or a single capitalized first word
    # (the derivation for non-override AMCs).
    for key in _SOURCE_CLASS:
        assert key in rendered or " " not in key, (
            f"config key {key!r} has a space but is not a rendered override "
            "short name — it will never match any row"
        )
