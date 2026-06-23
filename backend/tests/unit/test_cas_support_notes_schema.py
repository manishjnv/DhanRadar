"""Unit tests for the CAS support-notes feature (migration 0046).

Checks (no DB — pure import + attribute inspection):
  - migration 0046 chain (revision/down_revision) + upgrade/downgrade callable
  - MfCasJob ORM gained the support_notes column
  - CasFailureRecord carries support_notes (defaults to None)
  - CasNotesRequest validates max length + allows empty string
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest
from pydantic import ValidationError


def _column_names(model_cls) -> set[str]:
    return {c.key for c in model_cls.__table__.columns}


def _load_migration(name: str):
    path = (
        pathlib.Path(__file__).parent.parent.parent
        / "alembic" / "versions" / f"{name}.py"
    )
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Migration 0046
# ---------------------------------------------------------------------------

def test_migration_0046_chain():
    mod = _load_migration("0046_cas_job_support_notes")
    assert mod.revision == "0046"
    assert mod.down_revision == "0045"


def test_migration_0046_has_upgrade_and_downgrade():
    mod = _load_migration("0046_cas_job_support_notes")
    assert callable(mod.upgrade)
    assert callable(mod.downgrade)


# ---------------------------------------------------------------------------
# ORM model
# ---------------------------------------------------------------------------

def test_mf_cas_job_has_support_notes():
    from dhanradar.models.mf import MfCasJob

    cols = _column_names(MfCasJob)
    assert "support_notes" in cols, "support_notes missing from MfCasJob"
    assert MfCasJob.__table__.c.support_notes.nullable is True


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

def test_cas_failure_record_support_notes_default_none():
    from dhanradar.admin.platform_schemas import CasFailureRecord

    rec = CasFailureRecord(
        job_id="j1",
        user_id="u1",
        status="failed",
        error_message="boom",
        created_at=None,
        completed_at=None,
    )
    assert rec.support_notes is None


def test_cas_failure_record_support_notes_roundtrip():
    from dhanradar.admin.platform_schemas import CasFailureRecord

    rec = CasFailureRecord(
        job_id="j1",
        user_id="u1",
        status="failed",
        error_message=None,
        created_at=None,
        completed_at=None,
        support_notes="looked into it",
    )
    assert rec.support_notes == "looked into it"


def test_cas_notes_request_allows_empty_string():
    from dhanradar.admin.platform_schemas import CasNotesRequest

    assert CasNotesRequest(notes="").notes == ""


def test_cas_notes_request_accepts_normal_note():
    from dhanradar.admin.platform_schemas import CasNotesRequest

    assert CasNotesRequest(notes="parser failed on folio").notes == (
        "parser failed on folio"
    )


def test_cas_notes_request_rejects_overlong_note():
    from dhanradar.admin.platform_schemas import CasNotesRequest

    with pytest.raises(ValidationError):
        CasNotesRequest(notes="x" * 2001)
