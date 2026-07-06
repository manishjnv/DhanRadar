"""
Unit tests for the manual disclosure inbox's email poller (Channel C —
dhanradar/tasks/manual_ingest.py::poll_email_inbox). Mocked imaplib — no
network, no DB (a rejected/dormant run never reaches intake_upload(), so these
never touch TaskSessionLocal).

Covers:
  - Dormant no-op when MANUAL_INGEST_IMAP_* is unset (never touches imaplib).
  - Fail-closed no-op when the sender allowlist is empty (default — "accept none").
  - Sender-allowlist rejection: a message from a non-allowlisted sender is
    marked seen (never reprocessed) but never handed to intake_upload().
  - A .zip attachment is accepted and counted per-eligible-member (contract §1).
"""

from __future__ import annotations

import email.message

import pytest

from dhanradar.tasks import manual_ingest as mi


def _raw_email(sender: str, filename: str | None = None) -> bytes:
    msg = email.message.EmailMessage()
    msg["From"] = sender
    msg["To"] = "inbox@dhanradar.com"
    msg["Subject"] = "Monthly disclosure"
    msg.set_content("see attached")
    if filename:
        msg.add_attachment(
            b"fake-bytes", maintype="application", subtype="octet-stream", filename=filename
        )
    return bytes(msg)


class _FakeImap:
    """Minimal imaplib.IMAP4_SSL stand-in — records calls, returns canned responses."""

    def __init__(self, messages: dict[bytes, bytes]):
        self.messages = messages
        self.logged_in = False
        self.seen: list[bytes] = []
        self.logged_out = False

    def login(self, user, password):
        self.logged_in = True
        return "OK", [b"logged in"]

    def select(self, mailbox):
        return "OK", [b"1"]

    def search(self, charset, criterion):
        return "OK", [b" ".join(self.messages.keys())]

    def fetch(self, mid, parts):
        raw = self.messages.get(mid)
        if raw is None:
            return "NO", [None]
        return "OK", [(b"1 (RFC822 {%d}" % len(raw), raw)]

    def store(self, mid, flags, value):
        self.seen.append(mid)
        return "OK", [b"done"]

    def logout(self):
        self.logged_out = True


@pytest.fixture()
def _configured_imap(monkeypatch: pytest.MonkeyPatch):
    """Set all 3 IMAP env vars so the poller is no longer dormant."""
    from dhanradar.config import settings

    monkeypatch.setattr(settings, "MANUAL_INGEST_IMAP_HOST", "imap.example.com")
    monkeypatch.setattr(settings, "MANUAL_INGEST_IMAP_USER", "inbox@dhanradar.com")
    monkeypatch.setattr(settings, "MANUAL_INGEST_IMAP_PASSWORD", "test-password")
    return settings


# ---------------------------------------------------------------------------
# Dormant no-op — env unset
# ---------------------------------------------------------------------------


def test_dormant_when_imap_env_unset(monkeypatch: pytest.MonkeyPatch):
    from dhanradar.config import settings

    monkeypatch.setattr(settings, "MANUAL_INGEST_IMAP_HOST", "")
    monkeypatch.setattr(settings, "MANUAL_INGEST_IMAP_USER", "")
    monkeypatch.setattr(settings, "MANUAL_INGEST_IMAP_PASSWORD", "")

    def _boom(*_a, **_kw):
        raise AssertionError("imaplib.IMAP4_SSL must never be called while dormant")

    monkeypatch.setattr(mi.imaplib, "IMAP4_SSL", _boom)

    result = mi.poll_email_inbox()
    assert result == "skipped: not_configured"


# ---------------------------------------------------------------------------
# Fail-closed: configured but sender allowlist empty
# ---------------------------------------------------------------------------


def test_skips_when_sender_allowlist_empty(_configured_imap, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(_configured_imap, "MANUAL_INGEST_SENDER_ALLOWLIST", "")

    def _boom(*_a, **_kw):
        raise AssertionError("imaplib.IMAP4_SSL must never be called with an empty allowlist")

    monkeypatch.setattr(mi.imaplib, "IMAP4_SSL", _boom)

    result = mi.poll_email_inbox()
    assert result == "skipped: empty_allowlist"


# ---------------------------------------------------------------------------
# Sender-allowlist rejection — marked seen, never ingested
# ---------------------------------------------------------------------------


def test_sender_not_in_allowlist_is_rejected_and_marked_seen(
    _configured_imap, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(_configured_imap, "MANUAL_INGEST_SENDER_ALLOWLIST", "trusted@amc.com")

    raw = _raw_email("attacker@evil.com", filename="disclosure.xlsx")
    fake = _FakeImap({b"1": raw})
    monkeypatch.setattr(mi.imaplib, "IMAP4_SSL", lambda host: fake)

    async def _boom(*_a, **_kw):
        raise AssertionError("intake_upload must never be called for a rejected sender")

    monkeypatch.setattr(mi, "intake_upload", _boom)

    result = mi.poll_email_inbox()

    assert result == "polled: ingested=0 rejected_sender=1"
    assert fake.seen == [b"1"]  # marked seen so it is never reprocessed forever
    assert fake.logged_out is True


def test_allowlisted_sender_attachment_is_ingested(
    _configured_imap, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(_configured_imap, "MANUAL_INGEST_SENDER_ALLOWLIST", "Trusted@AMC.com")

    raw = _raw_email("trusted@amc.com", filename="HDFC_disclosure.xlsx")
    fake = _FakeImap({b"1": raw})
    monkeypatch.setattr(mi.imaplib, "IMAP4_SSL", lambda host: fake)

    calls: list[tuple[bytes, str, str]] = []

    async def _fake_intake_upload(data, filename, channel, uploaded_by, amc_hint=None):
        calls.append((data, filename, channel))
        from dhanradar.mf.manual_ingest import IntakeResult

        return [(filename, IntakeResult("fake-id", "pending", None))], []

    monkeypatch.setattr(mi, "intake_upload", _fake_intake_upload)

    result = mi.poll_email_inbox()

    assert result == "polled: ingested=1 rejected_sender=0"
    assert len(calls) == 1
    assert calls[0][1] == "HDFC_disclosure.xlsx"
    assert calls[0][2] == "email"
    assert fake.seen == [b"1"]


def test_allowlisted_sender_zip_attachment_expands_to_multiple_ingested(
    _configured_imap, monkeypatch: pytest.MonkeyPatch
):
    """A .zip email attachment is accepted and counted per-eligible-member,
    not as one attachment (contract §1 — all 3 channels get zip intake)."""
    monkeypatch.setattr(_configured_imap, "MANUAL_INGEST_SENDER_ALLOWLIST", "trusted@amc.com")

    raw = _raw_email("trusted@amc.com", filename="bundle.zip")
    fake = _FakeImap({b"1": raw})
    monkeypatch.setattr(mi.imaplib, "IMAP4_SSL", lambda host: fake)

    async def _fake_intake_upload(data, filename, channel, uploaded_by, amc_hint=None):
        from dhanradar.mf.manual_ingest import IntakeResult

        return [
            ("HDFC_June2026.xlsx", IntakeResult("id-1", "pending", None)),
            ("SBI_June2026.xlsx", IntakeResult("id-2", "pending", None)),
        ], [("notes.txt", "unsupported_extension:.txt")]

    monkeypatch.setattr(mi, "intake_upload", _fake_intake_upload)

    result = mi.poll_email_inbox()

    assert result == "polled: ingested=2 rejected_sender=0"
