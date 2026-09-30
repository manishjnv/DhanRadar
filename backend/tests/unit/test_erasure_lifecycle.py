"""Unit tests — DPDP deletion-lifecycle helpers that don't need Postgres.

Covers:
  - erasure_cli: UUID-line parsing (valid / blank / comment / malformed),
    the owner-DSN database-name swap, and the reerased/absent summary via a
    mocked session (no real Postgres).
  - erasure.py email builders: correct dates in the "request received" and
    "erasure done" bodies, and a Resend/transport failure never propagates
    (never raises) — mirrors test_email_otp.py's deliver_email patching.

Infrastructure: monkeypatch only — no Postgres, no HTTP, no Redis.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

# ---------------------------------------------------------------------------
# erasure_cli — id-file parsing
# ---------------------------------------------------------------------------


class TestParseIds:
    def test_valid_uuids_parsed(self):
        from dhanradar.auth.erasure_cli import _parse_ids

        a, b = uuid.uuid4(), uuid.uuid4()
        ids, bad = _parse_ids([f"{a}\n", f"{b}\n"])
        assert ids == [a, b]
        assert bad == []

    def test_blank_and_comment_lines_ignored(self):
        from dhanradar.auth.erasure_cli import _parse_ids

        a = uuid.uuid4()
        ids, bad = _parse_ids(["\n", "  \n", "# a comment\n", f"{a}\n", "# trailing\n"])
        assert ids == [a]
        assert bad == []

    def test_malformed_line_reported_with_line_number(self):
        from dhanradar.auth.erasure_cli import _parse_ids

        a = uuid.uuid4()
        ids, bad = _parse_ids([f"{a}\n", "not-a-uuid\n", "\n", "also-bad\n"])
        assert ids == [a]
        assert bad == [(2, "not-a-uuid"), (4, "also-bad")]

    def test_main_exits_1_and_touches_nothing_on_malformed_input(self, tmp_path, capsys):
        from dhanradar.auth.erasure_cli import main

        ids_file = tmp_path / "ids.txt"
        ids_file.write_text(f"{uuid.uuid4()}\nnope\n")

        rc = main(["--database", "restored_db", "--ids-file", str(ids_file)])
        assert rc == 1
        err = capsys.readouterr().err
        assert "nope" in err


# ---------------------------------------------------------------------------
# erasure_cli — DSN construction (owner DSN, database name swapped)
# ---------------------------------------------------------------------------


class TestCliDsn:
    def test_swaps_database_name_on_owner_dsn(self, monkeypatch):
        from dhanradar.auth import erasure_cli
        from dhanradar.config import settings

        monkeypatch.setattr(
            type(settings),
            "migration_database_url",
            property(lambda self: "postgresql+asyncpg://owner:pw@host:5432/dhanradar"),
        )
        dsn = erasure_cli._cli_dsn("restored_snapshot")
        assert dsn == "postgresql+asyncpg://owner:pw@host:5432/restored_snapshot"


# ---------------------------------------------------------------------------
# erasure_cli — reerased/absent summary via a mocked session
# ---------------------------------------------------------------------------


class TestRunSummary:
    async def test_reerased_and_absent_counted(self, monkeypatch):
        from dhanradar.auth import erasure_cli

        present_id = uuid.uuid4()
        absent_id = uuid.uuid4()

        async def fake_reapply(db, user_id):
            return {"auth.users": 1} if user_id == present_id else None

        monkeypatch.setattr(erasure_cli, "reapply_erasure", fake_reapply)

        class _FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

        class _FakeSessionFactory:
            def __call__(self):
                return _FakeSession()

        fake_engine = AsyncMock()
        monkeypatch.setattr(erasure_cli, "create_async_engine", lambda *a, **k: fake_engine)
        monkeypatch.setattr(
            erasure_cli, "async_sessionmaker", lambda *a, **k: _FakeSessionFactory()
        )

        reerased, absent = await erasure_cli._run("some_db", [present_id, absent_id])
        assert reerased == 1
        assert absent == 1
        fake_engine.dispose.assert_awaited_once()

    def test_main_prints_summary_line(self, tmp_path, monkeypatch, capsys):
        from dhanradar.auth import erasure_cli

        uid = uuid.uuid4()
        ids_file = tmp_path / "ids.txt"
        ids_file.write_text(f"{uid}\n")

        async def fake_run(database, ids):
            return 3, 2

        monkeypatch.setattr(erasure_cli, "_run", fake_run)
        rc = erasure_cli.main(["--database", "restored_db", "--ids-file", str(ids_file)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "reerased=3 absent=2" in out


# ---------------------------------------------------------------------------
# erasure.py — email content (dates) + never-raises on delivery failure
# ---------------------------------------------------------------------------


class TestDeletionEmails:
    async def test_requested_email_has_correct_dates_and_cancel_link(self, monkeypatch):
        from dhanradar.auth import erasure
        from dhanradar.compliance.data_policy import ERASURE_DUE, ERASURE_WAIT

        sent: dict = {}

        async def fake_send(to, subject, text, html):
            sent["to"] = to
            sent["subject"] = subject
            sent["text"] = text
            sent["html"] = html

        monkeypatch.setattr(
            "dhanradar.notifications.channels.send_transactional_email", fake_send
        )
        monkeypatch.setattr(
            "dhanradar.auth.security.create_deletion_cancel_token", lambda uid, drq: "tok123"
        )

        requested_at = datetime(2026, 1, 1, tzinfo=UTC)
        uid = uuid.uuid4()
        await erasure._send_deletion_requested_email("user@example.com", uid, requested_at)

        earliest = requested_at + ERASURE_WAIT
        due = requested_at + ERASURE_DUE
        assert sent["to"] == "user@example.com"
        assert erasure._fmt_date(requested_at) in sent["text"]
        assert erasure._fmt_date(earliest) in sent["text"]
        assert erasure._fmt_date(due) in sent["text"]
        assert "tok123" in sent["html"]
        assert "8 years" in sent["text"]
        assert "1 year" in sent["text"]

    async def test_erasure_done_email_has_correct_date(self, monkeypatch):
        from dhanradar.auth import erasure

        sent: dict = {}

        async def fake_send(to, subject, text, html):
            sent["text"] = text

        monkeypatch.setattr(
            "dhanradar.notifications.channels.send_transactional_email", fake_send
        )

        erased_at = datetime(2026, 2, 15, tzinfo=UTC)
        await erasure._send_erasure_done_email("user@example.com", erased_at)
        assert erasure._fmt_date(erased_at) in sent["text"]

    async def test_send_transactional_email_failure_never_raises(self, monkeypatch):
        """A Resend/transport failure is logged, never raised — a caller
        awaiting this after a committed erasure must never see an exception."""
        from dhanradar.notifications.channels import DeliveryResult, send_transactional_email

        async def failing_deliver(**kwargs):
            return DeliveryResult(ok=False, transient=True, code="transport_error")

        monkeypatch.setattr(
            "dhanradar.notifications.channels.deliver_email", failing_deliver
        )
        # Must not raise.
        await send_transactional_email("user@example.com", "subj", "text", "<p>html</p>")

    async def test_send_transactional_email_swallows_unexpected_exception(self, monkeypatch):
        async def boom(**kwargs):
            raise RuntimeError("network exploded")

        monkeypatch.setattr("dhanradar.notifications.channels.deliver_email", boom)

        from dhanradar.notifications.channels import send_transactional_email

        # Must not raise even on a totally unexpected exception.
        await send_transactional_email("user@example.com", "subj", "text", "<p>html</p>")
