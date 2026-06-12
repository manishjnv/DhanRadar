"""
Unit tests for Google OAuth helpers (pure — no network, no DB, no Redis).

Covers:
  - PKCE challenge derivation (known test vector).
  - validate_next path-sanitisation.
  - build_auth_url parameter presence.
"""

from __future__ import annotations

import base64
import hashlib

from dhanradar.auth.google import build_auth_url, pkce_challenge, validate_next

# ---------------------------------------------------------------------------
# PKCE challenge
# ---------------------------------------------------------------------------

class TestPkceChallenge:
    def test_known_vector(self) -> None:
        """
        RFC 7636 §B test vector (closest public reference):
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        expected_challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
        """
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        assert pkce_challenge(verifier) == expected

    def test_no_padding_equals(self) -> None:
        """Challenge must contain no '=' padding characters."""
        challenge = pkce_challenge("some-random-verifier-string-1234567890abcdef")
        assert "=" not in challenge

    def test_url_safe_alphabet(self) -> None:
        """Challenge must only contain URL-safe base64 characters."""
        challenge = pkce_challenge("another-verifier-value-xyz-987654321")
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        assert all(c in allowed for c in challenge)

    def test_deterministic(self) -> None:
        """Same verifier must always produce the same challenge."""
        v = "stable-verifier-for-determinism-test"
        assert pkce_challenge(v) == pkce_challenge(v)

    def test_different_verifiers_different_challenges(self) -> None:
        assert pkce_challenge("verifier-one") != pkce_challenge("verifier-two")


# ---------------------------------------------------------------------------
# validate_next
# ---------------------------------------------------------------------------

class TestValidateNext:
    def test_valid_simple_path(self) -> None:
        assert validate_next("/dashboard") == "/dashboard"

    def test_valid_path_with_segments(self) -> None:
        assert validate_next("/mf/portfolio") == "/mf/portfolio"

    def test_valid_path_with_query(self) -> None:
        assert validate_next("/settings?tab=profile") == "/settings?tab=profile"

    def test_double_slash_rejected(self) -> None:
        """'//evil.com' is an open redirect; must fall back to /dashboard."""
        assert validate_next("//evil.com") == "/dashboard"

    def test_absolute_http_rejected(self) -> None:
        assert validate_next("http://evil.com") == "/dashboard"

    def test_absolute_https_rejected(self) -> None:
        assert validate_next("https://attacker.io/steal") == "/dashboard"

    def test_none_gives_dashboard(self) -> None:
        assert validate_next(None) == "/dashboard"

    def test_empty_string_gives_dashboard(self) -> None:
        assert validate_next("") == "/dashboard"

    def test_backslash_rejected(self) -> None:
        """Browsers fold '\\' into '/': '/\\evil.com' would leave the origin."""
        assert validate_next("/\\evil.com") == "/dashboard"

    def test_backslash_slash_rejected(self) -> None:
        assert validate_next("/\\/evil.com") == "/dashboard"

    def test_embedded_backslash_rejected(self) -> None:
        assert validate_next("/dash\\board") == "/dashboard"

    def test_control_char_rejected(self) -> None:
        assert validate_next("/dash\nboard") == "/dashboard"
        assert validate_next("/dash\tboard") == "/dashboard"

    def test_root_slash_accepted(self) -> None:
        assert validate_next("/") == "/"

    def test_javascript_scheme_rejected(self) -> None:
        assert validate_next("javascript:alert(1)") == "/dashboard"


# ---------------------------------------------------------------------------
# build_auth_url
# ---------------------------------------------------------------------------

class TestBuildAuthUrl:
    def _url_params(self, url: str) -> dict[str, str]:
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(url)
        # parse_qs returns lists; take the first value.
        return {k: v[0] for k, v in parse_qs(parsed.query).items()}

    def test_base_url(self) -> None:
        url = build_auth_url("st", "nn", "cc", "https://example.com/callback")
        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth")

    def test_required_params_present(self) -> None:
        url = build_auth_url("my-state", "my-nonce", "my-challenge", "https://example.com/cb")
        params = self._url_params(url)
        assert params["state"] == "my-state"
        assert params["nonce"] == "my-nonce"
        assert params["code_challenge"] == "my-challenge"
        assert params["code_challenge_method"] == "S256"
        assert params["redirect_uri"] == "https://example.com/cb"
        assert params["response_type"] == "code"
        assert params["prompt"] == "select_account"

    def test_scope_contains_openid_email(self) -> None:
        url = build_auth_url("s", "n", "c", "https://example.com/cb")
        params = self._url_params(url)
        scope = params["scope"]
        assert "openid" in scope
        assert "email" in scope

    def test_no_fragment(self) -> None:
        url = build_auth_url("s", "n", "c", "https://example.com/cb")
        assert "#" not in url
