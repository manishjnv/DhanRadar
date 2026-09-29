"""Round-trip + failure-mode tests for dhanradar.mfu.crypto (AES-CBC/PKCS7/Base64).

Uses fake 16-char test keys — never real MFU credentials.
"""

from __future__ import annotations

import json

import pytest

from dhanradar.mfu.crypto import decrypt, encrypt

_KEY = "0123456789abcdef"  # 16 bytes
_IV = "fedcba9876543210"  # 16 bytes


@pytest.mark.parametrize(
    "plain",
    [
        "a",
        "0123456789abcdef",  # exactly one AES block
        "0123456789abcdefg",  # one block + 1 byte
        "héllo wörld — MFU 测试",  # unicode
        json.dumps({"entityId": "E1", "clientUser": "user@example.com"}),
    ],
)
def test_encrypt_decrypt_round_trip(plain: str) -> None:
    cipher_text = encrypt(plain, _KEY, _IV)
    assert decrypt(cipher_text, _KEY, _IV) == plain


def test_encrypt_output_is_base64() -> None:
    import base64

    cipher_text = encrypt("hello", _KEY, _IV)
    # Must not raise — proves standard Base64 alphabet + padding.
    base64.b64decode(cipher_text, validate=True)


@pytest.mark.parametrize("bad_key", ["short", "0123456789abcdefX", ""])
def test_bad_key_length_raises(bad_key: str) -> None:
    with pytest.raises(ValueError):
        encrypt("hello", bad_key, _IV)


@pytest.mark.parametrize("bad_iv", ["short", "0123456789abcdefX", ""])
def test_bad_iv_length_raises(bad_iv: str) -> None:
    with pytest.raises(ValueError):
        encrypt("hello", _KEY, bad_iv)


def test_valid_24_and_32_byte_keys_work() -> None:
    key24 = "0123456789abcdef01234567"  # 24 bytes
    key32 = "0123456789abcdef0123456789abcdef"  # 32 bytes
    for key in (key24, key32):
        cipher_text = encrypt("test message", key, _IV)
        assert decrypt(cipher_text, key, _IV) == "test message"


def test_tampered_ciphertext_raises() -> None:
    cipher_text = encrypt("a secret message", _KEY, _IV)
    tampered = cipher_text[:-4] + ("AAAA" if cipher_text[-4:] != "AAAA" else "BBBB")
    with pytest.raises(Exception):  # padding/UnicodeDecodeError depending on corruption
        decrypt(tampered, _KEY, _IV)
