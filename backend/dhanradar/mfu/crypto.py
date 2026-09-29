"""DhanRadar — MFU wire-format crypto: AES/CBC/PKCS7Padding, Base64 wire encoding.

Spec-literal, single point of change. MFU's V3.0 spec says: key + IV are
16-character strings used as UTF-8 bytes, AES/CBC/PKCS7Padding, output standard
Base64. UAT login currently fails with HTTP 400 errorCode 1 ("General
Exceptions while decrypt the text") because MFU has not confirmed this is
exactly their format — so this module does ONLY the spec-literal thing, with
no format-guessing/variant fallback logic. If MFU confirms a different wire
format, change it HERE only.
"""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives import padding as _padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_VALID_KEY_LENGTHS = (16, 24, 32)


def _cipher(key: str, iv: str) -> Cipher:
    key_bytes = key.encode("utf-8")
    iv_bytes = iv.encode("utf-8")
    if len(key_bytes) not in _VALID_KEY_LENGTHS:
        raise ValueError(f"AES key must be 16/24/32 bytes, got {len(key_bytes)}")
    if len(iv_bytes) != 16:
        raise ValueError(f"AES IV must be 16 bytes, got {len(iv_bytes)}")
    return Cipher(algorithms.AES(key_bytes), modes.CBC(iv_bytes))


# ponytail: wire format per spec (Base64); MFU confirmation pending — UAT login
# returns errorCode 1 decrypt error (report v0.2, 2026-09-29); change only here
def _encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _decode(text: str) -> bytes:
    return base64.b64decode(text)


def encrypt(plain: str, key: str, iv: str) -> str:
    """AES-CBC/PKCS7 encrypt `plain` (UTF-8), return standard Base64."""
    encryptor = _cipher(key, iv).encryptor()
    padder = _padding.PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(plain.encode("utf-8")) + padder.finalize()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return _encode(ciphertext)


def decrypt(cipher_text: str, key: str, iv: str) -> str:
    """Base64-decode, AES-CBC decrypt, PKCS7-unpad, return the UTF-8 plaintext."""
    decryptor = _cipher(key, iv).decryptor()
    padded = decryptor.update(_decode(cipher_text)) + decryptor.finalize()
    unpadder = _padding.PKCS7(algorithms.AES.block_size).unpadder()
    plain = unpadder.update(padded) + unpadder.finalize()
    return plain.decode("utf-8")
