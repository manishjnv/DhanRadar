"""DPDP / ADR-0022: the audit→R2 archival must be OFF by default.

The audit archive carries `user_id` and must be India-resident. Until an
India-resident archive target is explicitly enabled, `archive_audit_daily` must
NOT export rows cross-border — it returns early before touching storage/DB.
"""

from __future__ import annotations

import asyncio

from dhanradar.config import Settings
from dhanradar.tasks import compliance


def test_audit_archive_flag_defaults_off():
    assert Settings.model_fields["AUDIT_ARCHIVE_ENABLED"].default is False


def test_archive_returns_disabled_when_flag_off():
    # Default config has AUDIT_ARCHIVE_ENABLED=False → the task short-circuits
    # before any storage/DB access, so this runs without a broker/DB/R2.
    result = asyncio.run(compliance._archive())
    assert "disabled" in result.lower()
