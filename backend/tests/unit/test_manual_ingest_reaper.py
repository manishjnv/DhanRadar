"""
Unit tests for the manual disclosure inbox's stuck-file reaper
(dhanradar/tasks/manual_ingest.py::reap_stuck_manual_ingest_files, added
2026-07-08 celery-resilience hardening) — the manual-ingest counterpart to
tasks/mf.py::reap_stuck_cas_jobs. Mocked DB session, no network, no real DB.

Covers:
  - An old 'pending' row (past the 30-min cutoff) is reaped: marked
    failed='stuck_timeout', summary reports count=1.
  - No rows past the cutoff → zero-count summary, only a SELECT issued (no UPDATE).
"""

from __future__ import annotations

import uuid

import pytest

from dhanradar.tasks.manual_ingest import _reap_stuck_manual_ingest_files

pytestmark = pytest.mark.asyncio


class _ReaperResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


def _make_reaper_session(rows):
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


async def test_reap_stuck_manual_ingest_marks_old_pending_file_failed(monkeypatch):
    old_row = (uuid.uuid4(),)
    sess, calls = _make_reaper_session([old_row])
    monkeypatch.setattr("dhanradar.db.admin_task_session", lambda: sess)

    summary = await _reap_stuck_manual_ingest_files()

    assert "1" in summary and "stuck" in summary
    # SELECT + UPDATE = at least 2 execute calls.
    assert len(calls) >= 2


async def test_reap_stuck_manual_ingest_does_not_touch_recent_file(monkeypatch):
    sess, calls = _make_reaper_session([])  # empty → nothing past the cutoff
    monkeypatch.setattr("dhanradar.db.admin_task_session", lambda: sess)

    summary = await _reap_stuck_manual_ingest_files()

    assert "0" in summary
    # Only the SELECT should have been issued (early return after empty-rows check).
    assert len(calls) == 1


async def test_reap_select_requires_stale_parsed_at_too(monkeypatch):
    """2026-07-10: keying on received_at alone reaped 454 of 477 RESET rows
    mid-re-parse (reset rows are days old by received_at; the beat fires every
    5 min). The SELECT must also require parsed_at NULL-or-stale so the
    runbook's reset (which stamps parsed_at=now()) gets a fresh window."""
    sess, calls = _make_reaper_session([])
    monkeypatch.setattr("dhanradar.db.admin_task_session", lambda: sess)

    await _reap_stuck_manual_ingest_files()

    select_sql = str(calls[0])
    assert "received_at" in select_sql
    assert "parsed_at" in select_sql
    assert "OR" in select_sql.upper()
