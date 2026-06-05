"""
Unit tests for dhanradar.auth.security.

These tests are hermetic: they only need the RSA keypair fixture (no DB, no
Redis, no HTTP). The patch_settings_keys fixture wires the ephemeral RSA keys
into the settings singleton so create_access_token / decode_token operate on
real (but test-only) keys.

Tests
-----
- access token round-trips with expected_typ="access"; typ confusion blocked.
- HS256 alg-confusion attack rejected.
- expired token raises PyJWTError.
- hash_password / verify_password: correct, wrong, bogus hash.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import jwt
import pytest

# patch_settings_keys is a function-scoped fixture defined in conftest.py.
# It patches settings.jwt_private_key / jwt_public_key and COOKIE_SECURE.
# Mark it as an autouse dependency for this module so every test here sees
# the patched keys.
pytestmark = pytest.mark.usefixtures("patch_settings_keys")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_security():
    """Late import so settings is already patched at call time."""
    from dhanradar.auth import security
    return security


# ---------------------------------------------------------------------------
# Token type: access vs refresh
# ---------------------------------------------------------------------------


def test_access_token_decodes_with_access_typ():
    sec = _import_security()
    token, jti = sec.create_access_token("user-123")
    payload = sec.decode_token(token, expected_typ="access")
    assert payload["sub"] == "user-123"
    assert payload["typ"] == "access"
    assert payload["jti"] == jti


def test_refresh_token_decodes_with_refresh_typ():
    sec = _import_security()
    token, jti = sec.create_refresh_token("user-456")
    payload = sec.decode_token(token, expected_typ="refresh")
    assert payload["sub"] == "user-456"
    assert payload["typ"] == "refresh"
    assert payload["jti"] == jti


def test_access_token_rejected_with_refresh_typ():
    """Using an access token where a refresh token is expected must raise."""
    sec = _import_security()
    token, _ = sec.create_access_token("user-789")
    with pytest.raises(jwt.PyJWTError):
        sec.decode_token(token, expected_typ="refresh")


def test_refresh_token_rejected_with_access_typ():
    """Symmetric check: refresh token rejected when access is expected."""
    sec = _import_security()
    token, _ = sec.create_refresh_token("user-321")
    with pytest.raises(jwt.PyJWTError):
        sec.decode_token(token, expected_typ="access")


# ---------------------------------------------------------------------------
# Algorithm confusion: HS256 with public key as secret must be rejected
# ---------------------------------------------------------------------------


def test_hs256_alg_confusion_rejected(rsa_keypair):
    """
    An attacker who knows the public key could forge a token signed with
    HS256(public_key_bytes). PyJWT's algorithms= whitelist must reject this.
    """
    sec = _import_security()
    _, public_pem = rsa_keypair

    # Craft a forged HS256 token MANUALLY. Modern PyJWT refuses to *encode*
    # with a PEM as the HMAC secret, so we hand-build the token to simulate the
    # attacker. decode_token only allows ["RS256"], so verification must reject
    # it (InvalidAlgorithmError is a PyJWTError) regardless of the signature.
    import base64
    import hashlib
    import hmac
    import json

    def _b64url(raw: bytes) -> bytes:
        return base64.urlsafe_b64encode(raw).rstrip(b"=")

    now = datetime.now(UTC)
    header = {"alg": "HS256", "typ": "JWT"}
    forged_payload = {
        "sub": "attacker",
        "jti": "forged-jti",
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }
    signing_input = (
        _b64url(json.dumps(header, separators=(",", ":")).encode())
        + b"."
        + _b64url(json.dumps(forged_payload, separators=(",", ":")).encode())
    )
    sig = hmac.new(public_pem.encode("utf-8"), signing_input, hashlib.sha256).digest()
    forged_token = (signing_input + b"." + _b64url(sig)).decode("ascii")

    with pytest.raises(jwt.PyJWTError):
        sec.decode_token(forged_token, expected_typ="access")


# ---------------------------------------------------------------------------
# Expired token
# ---------------------------------------------------------------------------


def test_expired_access_token_raises(monkeypatch):
    """
    Monkeypatch ACCESS_TTL_MIN to -1 to force immediate expiry, then verify
    decode_token raises on the resulting token.
    """
    from dhanradar.config import settings

    # Force the TTL to a negative value so exp is in the past.
    object.__setattr__(settings, "ACCESS_TTL_MIN", -1)
    try:
        sec = _import_security()
        token, _ = sec.create_access_token("user-exp")
        # Give PyJWT a moment to see it as expired (it already is, since
        # exp = now + timedelta(minutes=-1)).
        with pytest.raises(jwt.PyJWTError):
            sec.decode_token(token, expected_typ="access")
    finally:
        # Restore to a sane value for subsequent tests.
        object.__setattr__(settings, "ACCESS_TTL_MIN", 15)


def test_expired_refresh_token_raises(monkeypatch):
    """Same expiry test for refresh tokens."""
    from dhanradar.config import settings

    object.__setattr__(settings, "REFRESH_TTL_DAYS", -1)
    try:
        sec = _import_security()
        token, _ = sec.create_refresh_token("user-ref-exp")
        with pytest.raises(jwt.PyJWTError):
            sec.decode_token(token, expected_typ="refresh")
    finally:
        object.__setattr__(settings, "REFRESH_TTL_DAYS", 7)


# ---------------------------------------------------------------------------
# Token crafted with exp in the past (no TTL monkeypatching needed)
# ---------------------------------------------------------------------------


def test_past_exp_claim_raises(rsa_keypair):
    """
    Manually craft a token with exp already in the past and verify
    decode_token raises ExpiredSignatureError.
    """
    sec = _import_security()
    private_pem, _ = rsa_keypair
    now = datetime.now(UTC)
    payload = {
        "sub": "user-past",
        "jti": "past-jti",
        "typ": "access",
        "iat": now - timedelta(minutes=30),
        "exp": now - timedelta(minutes=15),  # expired 15 min ago
    }
    expired_token = jwt.encode(payload, private_pem, algorithm="RS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        sec.decode_token(expired_token, expected_typ="access")


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def test_hash_and_verify_correct_password():
    """Correct password must verify True."""
    from dhanradar.auth.security import hash_password, verify_password

    pw = "CorrectHorse42!"
    h = hash_password(pw)
    assert verify_password(h, pw) is True


def test_verify_wrong_password_returns_false():
    """Wrong password must return False (not raise)."""
    from dhanradar.auth.security import hash_password, verify_password

    h = hash_password("CorrectHorse42!")
    assert verify_password(h, "WrongPassword99") is False


def test_verify_bogus_hash_returns_false():
    """
    A garbage/truncated hash string must return False, not raise an exception.
    This guards against storage corruption or hash-field truncation in the DB.
    """
    from dhanradar.auth.security import verify_password

    bogus = "$argon2id$v=not_a_real_hash_at_all"
    # Must NOT raise — verify_password swallows argon2 exceptions.
    assert verify_password(bogus, "anyPassword") is False


def test_verify_empty_bogus_hash_returns_false():
    """Empty stored hash must return False without raising."""
    from dhanradar.auth.security import verify_password

    assert verify_password("", "somePassword") is False


def test_different_passwords_hash_differently():
    """Two different plaintexts must produce different hashes (sanity check)."""
    from dhanradar.auth.security import hash_password

    assert hash_password("PasswordA1!") != hash_password("PasswordB2@")
