"""
Unit tests for the What Changed module (Plan Group 2).

Tests:
  - classify_change logic (all cases: improved, weakened, unchanged, new,
    insufficient_to, insufficient_from, band strengthen, band ease)
  - FundChange schema allowlist guard (no unified_score / numeric-score field)
  - Advisory-verb guard on classify_change output
"""

from __future__ import annotations

import pytest

from dhanradar.changes.schemas import FundChange
from dhanradar.changes.service import classify_change

# ---------------------------------------------------------------------------
# Exact allowlist for FundChange fields (mirrors the contract spec)
# ---------------------------------------------------------------------------

_FUND_CHANGE_ALLOWLIST = {
    "isin",
    "scheme_name",
    "label_from",
    "label_to",
    "band_from",
    "band_to",
    "changed",
    "change_kind",
    "reasons",
    "as_of_from",
    "as_of_to",
    "nav_as_of",
    "nav_days_ago",
    "nav_is_stale",
}

# Advisory verbs that must never appear in reason strings (non-neg #1 / SEBI boundary)
_ADVISORY_VERBS = (
    "buy",
    "sell",
    "hold",
    "switch",
    "reduce",
    "rebalance",
    "redeem",
    "exit",
    "book",
    "consider",
    "recommend",
    "should",
    "suggest",
    "avoid",
    "caution",
    "opportunity",
    "take action",
)


# ---------------------------------------------------------------------------
# Schema guard tests
# ---------------------------------------------------------------------------


def test_fund_change_no_unified_score_field():
    """unified_score must be absent from FundChange (non-neg #2)."""
    assert "unified_score" not in FundChange.model_fields, (
        "unified_score must not exist as a FundChange field"
    )


def test_fund_change_exact_allowlist():
    """FundChange.model_fields must match the exact contract allowlist."""
    actual = set(FundChange.model_fields.keys())
    assert actual == _FUND_CHANGE_ALLOWLIST, (
        f"FundChange fields mismatch.\n"
        f"  Extra:   {actual - _FUND_CHANGE_ALLOWLIST}\n"
        f"  Missing: {_FUND_CHANGE_ALLOWLIST - actual}"
    )


def test_fund_change_no_score_in_field_names():
    """No FundChange field name should contain 'score'."""
    score_fields = [f for f in FundChange.model_fields if "score" in f.lower()]
    assert not score_fields, (
        f"FundChange has field(s) containing 'score': {score_fields}"
    )


# ---------------------------------------------------------------------------
# classify_change: label transition cases
# ---------------------------------------------------------------------------


def test_classify_improved():
    """off_track → on_track should be 'improved'."""
    kind, changed, reasons = classify_change("off_track", "low", "on_track", "medium")
    assert kind == "improved"
    assert changed is True
    assert len(reasons) >= 1
    assert "off_track" in reasons[0]
    assert "on_track" in reasons[0]


def test_classify_weakened():
    """in_form → off_track should be 'weakened'."""
    kind, changed, reasons = classify_change("in_form", "high", "off_track", "medium")
    assert kind == "weakened"
    assert changed is True
    assert "in_form" in reasons[0]
    assert "off_track" in reasons[0]


def test_classify_unchanged():
    """on_track → on_track should be 'unchanged'."""
    kind, changed, reasons = classify_change("on_track", "medium", "on_track", "medium")
    assert kind == "unchanged"
    assert changed is False
    assert "on_track" in reasons[0]


def test_classify_new_single_snapshot():
    """label_from=None → 'new', changed=False."""
    kind, changed, reasons = classify_change(None, None, "on_track", "high")
    assert kind == "new"
    assert changed is False
    assert len(reasons) == 1
    assert "first" in reasons[0].lower()


def test_classify_insufficient_to():
    """Real label → insufficient_data: kind='insufficient_data', changed=True."""
    kind, changed, reasons = classify_change("on_track", "medium", "insufficient_data", "insufficient_data")
    assert kind == "insufficient_data"
    assert changed is True
    assert "enough data" in reasons[0].lower() or "latest snapshot" in reasons[0].lower()


def test_classify_insufficient_from():
    """insufficient_data → real label: kind='insufficient_data', changed=True."""
    kind, changed, reasons = classify_change("insufficient_data", "insufficient_data", "on_track", "medium")
    assert kind == "insufficient_data"
    assert changed is True
    assert "earlier snapshot" in reasons[0].lower() or "first comparable" in reasons[0].lower()


def test_classify_band_strengthen():
    """Same label, band low → medium: should append band-strengthen reason."""
    kind, changed, reasons = classify_change("on_track", "low", "on_track", "medium")
    assert kind == "unchanged"
    assert changed is False
    # Should have a band reason (second entry)
    band_reason = " ".join(reasons).lower()
    assert "strengthened" in band_reason
    assert "low" in band_reason
    assert "medium" in band_reason


def test_classify_band_ease():
    """Same label, band high → medium: should append band-ease reason."""
    kind, changed, reasons = classify_change("on_track", "high", "on_track", "medium")
    assert kind == "unchanged"
    assert changed is False
    band_reason = " ".join(reasons).lower()
    assert "eased" in band_reason
    assert "high" in band_reason
    assert "medium" in band_reason


def test_classify_band_same_no_extra_reason():
    """Same label, same band: no band reason appended."""
    kind, changed, reasons = classify_change("on_track", "medium", "on_track", "medium")
    assert kind == "unchanged"
    assert len(reasons) == 1  # only the label reason, no band reason


def test_classify_band_insufficient_no_extra_reason():
    """Band reason not appended when either band is insufficient_data."""
    kind, changed, reasons = classify_change("on_track", "medium", "on_track", "insufficient_data")
    # band_to is insufficient_data → not in _BAND_RANK → no band reason
    assert kind == "unchanged"
    assert len(reasons) == 1


# ---------------------------------------------------------------------------
# Advisory-verb guard on all classify_change outputs
# ---------------------------------------------------------------------------


_CLASSIFY_CASES = [
    ("off_track", "low", "on_track", "medium"),
    ("in_form", "high", "off_track", "medium"),
    ("on_track", "medium", "on_track", "medium"),
    (None, None, "on_track", "high"),
    ("on_track", "medium", "insufficient_data", "insufficient_data"),
    ("insufficient_data", "insufficient_data", "on_track", "medium"),
    ("on_track", "low", "on_track", "medium"),
    ("on_track", "high", "on_track", "medium"),
    ("in_form", "high", "in_form", "high"),
    ("out_of_form", "low", "out_of_form", "low"),
]


@pytest.mark.parametrize("label_from,band_from,label_to,band_to", _CLASSIFY_CASES)
def test_no_advisory_verb_in_reasons(label_from, band_from, label_to, band_to):
    """No advisory verb must appear in any reason string produced by classify_change."""
    _, _, reasons = classify_change(label_from, band_from, label_to, band_to)
    combined = " ".join(reasons).lower()
    for verb in _ADVISORY_VERBS:
        assert verb not in combined, (
            f"Advisory verb '{verb}' found in reasons for "
            f"classify_change({label_from!r}, {band_from!r}, {label_to!r}, {band_to!r}): "
            f"{reasons}"
        )
