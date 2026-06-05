"""Unit tests for the DPDP enforcement primitives (B3 + B4).

These are pure unit tests — no Postgres/Redis — using small fakes, so they run
locally. The end-to-end consent/erasure flows belong to the later Consent module.

B3: RequireConsent is fail-closed — purpose validated at construction; no
    recorded grant (missing/false/malformed/anonymous) → 403 consent_required.
B4: authenticate_user denies login for an account with deletion_requested_at set
    (after a successful password check, so it is not an enumeration oracle).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from dhanradar.auth.security import hash_password
from dhanradar.auth.service import authenticate_user
from dhanradar.deps import RequireConsent, UserContext, _consent_granted
from dhanradar.models.auth import User


class _FakeDB:
    """Minimal AsyncSession stand-in: scalar() returns a preset value."""

    def __init__(self, scalar_return: object) -> None:
        self._ret = scalar_return

    async def scalar(self, *_a, **_k) -> object:
        return self._ret


# ---------------------------------------------------------------------------
# B3 — _consent_granted truth table (fail-closed)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("consents", "expected"),
    [
        ({"ai_insights": True}, True),
        ({"ai_insights": {"granted": True}}, True),
        ({"ai_insights": {"granted": True, "ts": "x"}}, True),
        ({"ai_insights": False}, False),
        ({"ai_insights": {"granted": False}}, False),
        ({"ai_insights": {"granted": "true"}}, False),  # only bool True counts
        ({"ai_insights": "yes"}, False),
        ({"other": True}, False),
        ({}, False),
        (None, False),
        ("garbage", False),
    ],
)
def test_consent_granted_truth_table(consents, expected):
    assert _consent_granted(consents, "ai_insights") is expected


# ---------------------------------------------------------------------------
# B3 — RequireConsent
# ---------------------------------------------------------------------------

def test_require_consent_rejects_unknown_purpose():
    with pytest.raises(ValueError):
        RequireConsent("ai_processing")  # not in the canonical taxonomy


async def test_require_consent_anonymous_denied():
    gate = RequireConsent("ai_insights")
    with pytest.raises(HTTPException) as ei:
        await gate(UserContext(), _FakeDB(None))  # anonymous (default)
    assert ei.value.status_code == 403
    assert ei.value.detail["error"] == "consent_required"


async def test_require_consent_granted_passes():
    gate = RequireConsent("ai_insights")
    user = UserContext(user_id=str(uuid.uuid4()), tier="pro", is_anonymous=False)
    # Returns None (no raise) when the purpose is granted.
    assert await gate(user, _FakeDB({"ai_insights": True})) is None


async def test_require_consent_not_granted_denied():
    gate = RequireConsent("ai_insights")
    user = UserContext(user_id=str(uuid.uuid4()), tier="pro", is_anonymous=False)
    with pytest.raises(HTTPException) as ei:
        await gate(user, _FakeDB({"ai_insights": False}))
    assert ei.value.status_code == 403
    assert ei.value.detail == {"error": "consent_required", "purpose": "ai_insights"}


async def test_require_consent_malformed_subject_fails_closed():
    """A non-anonymous context with a non-UUID user_id must fail CLOSED (403),
    never raise an unhandled ValueError → 500 (Security review condition)."""
    gate = RequireConsent("ai_insights")
    user = UserContext(user_id="not-a-uuid", tier="pro", is_anonymous=False)
    with pytest.raises(HTTPException) as ei:
        await gate(user, _FakeDB({"ai_insights": True}))
    assert ei.value.status_code == 403
    assert ei.value.detail["error"] == "consent_required"


# ---------------------------------------------------------------------------
# B4 — authenticate_user denies a deletion-pending account
# ---------------------------------------------------------------------------

def _user(deletion_requested_at):
    u = User()
    u.id = uuid.uuid4()
    u.email = "del@example.com"
    u.hashed_password = hash_password("CorrectHorse42!")
    u.deletion_requested_at = deletion_requested_at
    return u


async def test_authenticate_user_blocks_deletion_pending():
    db = _FakeDB(_user(datetime.now(UTC)))
    with pytest.raises(HTTPException) as ei:
        await authenticate_user("del@example.com", "CorrectHorse42!", db)
    assert ei.value.status_code == 403
    assert ei.value.detail == "account_deletion_pending"


async def test_authenticate_user_allows_active_account():
    db = _FakeDB(_user(None))
    user = await authenticate_user("del@example.com", "CorrectHorse42!", db)
    assert user.deletion_requested_at is None
