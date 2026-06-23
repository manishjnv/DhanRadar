"""
DhanRadar — BSE Star MF 2.0 webhook JOSE security.

BSE Star MF 2.0 (API doc §6.1.7) wraps every payload in JOSE:

    inbound webhook = JWS( signed by BSE's private key )
                       └─ payload = JWE( encrypted to OUR public key )

So to read a webhook we must, IN THIS ORDER (verify-before-parse):

  1. VERIFY the outer JWS signature with **BSE's public key** (RS256). A bad or
     missing signature ⇒ reject; nothing past this point runs on unverified bytes.
  2. DECRYPT the inner JWE with **our private key** (RSA-OAEP-256 key-wrap +
     A256GCM content). The plaintext is the clear-text event JSON.

Fail-closed: if either key is unconfigured we raise `BSEKeyNotConfigured` and the
router returns 503 — we NEVER fall back to parsing an unverified/clear payload.

This module does crypto only; it imports no other DhanRadar module (isolation).
"""

from __future__ import annotations

from joserfc import jwe, jws
from joserfc.errors import JoseError
from joserfc.jwk import RSAKey

from dhanradar.config import settings

# Algorithm allowlists — pinned to exactly what BSE specifies (§6.1.7). Pinning
# prevents an attacker from down-grading to a weaker/`none` algorithm.
#
# For JWE, joserfc validates BOTH the `alg` (key-wrap) AND `enc` (content) header
# fields independently against this combined list — verified empirically with
# joserfc 1.7.1: alg/enc downgrades (RSA-OAEP, RSA1_5, A128GCM, A128CBC-HS256) all
# raise UnsupportedAlgorithmError. So a single flat list is a complete pin here.
_JWS_ALGS = ["RS256"]
_JWE_ALGS = ["RSA-OAEP-256", "A256GCM"]


class BSEWebhookSecurityError(Exception):
    """Raised when an inbound webhook fails JOSE verification or decryption.

    The router maps this to HTTP 400 (reject — do not process)."""


class BSEKeyNotConfigured(Exception):
    """Raised when the BSE keys are not configured (fail-closed).

    The router maps this to HTTP 503 — the endpoint is not ready to verify, so
    we refuse rather than process anything unverified."""


def _load_keys() -> tuple[RSAKey, RSAKey]:
    """Return (bse_public_key, our_private_key) as joserfc RSAKey objects.

    Raises BSEKeyNotConfigured if either PEM is absent."""
    bse_pub_pem = settings.bse_webhook_public_key
    our_priv_pem = settings.bse_private_key
    if not bse_pub_pem or not our_priv_pem:
        raise BSEKeyNotConfigured(
            "BSE webhook keys not configured "
            "(need BSE_WEBHOOK_PUBLIC_KEY[_FILE] + BSE_PRIVATE_KEY[_FILE])"
        )
    try:
        bse_public = RSAKey.import_key(bse_pub_pem)
        our_private = RSAKey.import_key(our_priv_pem)
    except (JoseError, ValueError) as exc:  # malformed PEM
        raise BSEKeyNotConfigured(f"BSE webhook key import failed: {exc}") from exc
    return bse_public, our_private


def verify_and_decrypt(enc_payload: str | bytes) -> bytes:
    """Verify BSE's JWS signature, then decrypt the inner JWE.

    Args:
        enc_payload: the raw JOSE compact string from the webhook body.

    Returns:
        The decrypted clear-text payload bytes (the event JSON).

    Raises:
        BSEKeyNotConfigured: keys absent/malformed (→ 503).
        BSEWebhookSecurityError: signature invalid or decryption failed (→ 400).
    """
    bse_public, our_private = _load_keys()

    if isinstance(enc_payload, str):
        enc_payload = enc_payload.encode("ascii")

    # Step 1 — verify outer JWS with BSE's public key (raises on bad signature).
    try:
        jws_obj = jws.deserialize_compact(enc_payload, bse_public, algorithms=_JWS_ALGS)
    except (JoseError, ValueError, UnicodeError) as exc:
        raise BSEWebhookSecurityError(f"JWS verification failed: {exc}") from exc

    jwe_compact: bytes = jws_obj.payload

    # Step 2 — decrypt inner JWE with our private key (only on a verified signature).
    try:
        jwe_obj = jwe.decrypt_compact(jwe_compact, our_private, algorithms=_JWE_ALGS)
    except (JoseError, ValueError) as exc:
        raise BSEWebhookSecurityError(f"JWE decryption failed: {exc}") from exc

    return jwe_obj.plaintext
