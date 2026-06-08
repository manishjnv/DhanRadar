"""Unit tests for ConsentChangeRequest schema validation (B44 — DPDP writer).

Pure pydantic unit tests — no DB, no Redis, no HTTP.  Validates that:
  - An empty purposes list is rejected (min_length=1).
  - An unknown purpose string is rejected (field_validator).
  - A valid list of canonical purposes is accepted.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dhanradar.consent.schemas import ConsentChangeRequest


def test_rejects_empty_list():
    with pytest.raises(ValidationError):
        ConsentChangeRequest(purposes=[])


def test_rejects_unknown_purpose():
    with pytest.raises(ValidationError):
        ConsentChangeRequest(purposes=["not_a_purpose"])


def test_rejects_mixed_valid_invalid():
    with pytest.raises(ValidationError):
        ConsentChangeRequest(purposes=["mf_analytics", "bad_purpose"])


def test_accepts_single_valid_purpose():
    req = ConsentChangeRequest(purposes=["mf_analytics"])
    assert req.purposes == ["mf_analytics"]


def test_accepts_multiple_valid_purposes():
    req = ConsentChangeRequest(purposes=["mf_analytics", "ai_insights", "cross_border_ai"])
    assert len(req.purposes) == 3


def test_accepts_all_canonical_purposes():
    all_purposes = [
        "mf_analytics",
        "ai_insights",
        "marketing",
        "portfolio_sync",
        "behavioral_nudges",
        "cross_border_ai",
        "cross_border_notify",
    ]
    req = ConsentChangeRequest(purposes=all_purposes)
    assert set(req.purposes) == set(all_purposes)
