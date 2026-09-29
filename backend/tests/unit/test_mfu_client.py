"""Unit tests for dhanradar.mfu.client — pure helpers + login/cooldown flow.

HTTP is mocked with a tiny fake httpx.AsyncClient (no respx dependency in this
repo's test stack; see tests/unit/test_bse_uat_router.py for the sibling
BSE-side convention of testing pure functions + parsing contracts only).
Redis uses the repo's `patch_redis`/`fake_redis` conftest fixtures (fakeredis).
Uses fake 16-char test keys — never real MFU credentials.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import pytest

from dhanradar.mfu import client as mfu_client
from dhanradar.mfu.client import (
    MfuError,
    _none_to_empty,
    _scrub,
    base_url,
    build_envelope,
    call,
    login,
    new_unique_id,
)
from dhanradar.mfu.crypto import encrypt

_KEY = "0123456789abcdef"
_IV = "fedcba9876543210"


class _FakeDb:
    """Duck-typed AsyncSession stand-in — only .add()/.commit() are used."""

    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        pass


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeAsyncClient:
    """Records every POST and returns the next queued response."""

    calls: list[dict[str, Any]] = []
    responses: list[_FakeResponse] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def post(self, url: str, json: dict[str, Any], headers: dict[str, Any]) -> _FakeResponse:
        _FakeAsyncClient.calls.append({"url": url, "json": json, "headers": headers})
        return _FakeAsyncClient.responses.pop(0)


@pytest.fixture(autouse=True)
def _mfu_settings(monkeypatch: pytest.MonkeyPatch):
    from dhanradar.config import settings

    monkeypatch.setattr(settings, "MFU_UAT_ENABLED", True)
    monkeypatch.setattr(settings, "MFU_ENTITY_ID", "E1")
    monkeypatch.setattr(settings, "MFU_LOGIN_USER", "testuser")
    monkeypatch.setattr(settings, "MFU_LOGIN_PASSWORD", "testpass")
    monkeypatch.setattr(settings, "MFU_AES_KEY", _KEY)
    monkeypatch.setattr(settings, "MFU_AES_IV", _IV)
    monkeypatch.setattr(settings, "MFU_API_BASE_URL_UAT", "https://test.mfuonline.com")
    yield settings


@pytest.fixture
def fake_http(monkeypatch: pytest.MonkeyPatch):
    _FakeAsyncClient.calls = []
    _FakeAsyncClient.responses = []
    monkeypatch.setattr(mfu_client.httpx, "AsyncClient", _FakeAsyncClient)
    return _FakeAsyncClient


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------


def test_none_to_empty_recursive() -> None:
    assert _none_to_empty({"a": None, "b": {"c": None, "d": [1, None, "x"]}}) == {
        "a": "",
        "b": {"c": "", "d": [1, "", "x"]},
    }


def test_new_unique_id_len_and_uniqueness() -> None:
    ids = {new_unique_id() for _ in range(1000)}
    assert len(ids) == 1000
    for uid in list(ids)[:5]:
        assert len(uid) <= 50


def test_build_envelope_shape_and_no_nulls() -> None:
    envelope = build_envelope("TESTAPI", {"a": None, "b": "x"})
    header = envelope["reqHeader"]
    assert header["entityId"] == "E1"
    assert header["version"] == "1.00"
    assert header["apiType"] == "TESTAPI"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", header["reqTS"])
    datetime.strptime(header["reqTS"], "%Y-%m-%d %H:%M:%S")  # parses cleanly
    assert len(header["uniqueId"]) <= 50
    assert "data" in envelope["reqBody"]
    # decrypt round-trip proves None -> "" happened before encryption
    from dhanradar.mfu.crypto import decrypt

    decrypted = decrypt(envelope["reqBody"]["data"], _KEY, _IV)
    assert '"a":""' in decrypted or '"a": ""' in decrypted


def test_scrub_redacts_credentials_and_pan() -> None:
    scrubbed = _scrub(
        {
            "clientUser": "enc-user",
            "clientPwd": "enc-pwd",
            "access_token": "abc.def.ghi",
            "investor": {"pan": "ABCDE1234F", "mobile": "9999999999", "email": "a@b.com"},
            "note": "PAN in free text ABCDE1234F should be masked too",
        }
    )
    assert scrubbed["clientUser"] == "***"
    assert scrubbed["clientPwd"] == "***"
    assert scrubbed["access_token"] == "***"
    assert scrubbed["investor"]["pan"] == "***"
    assert scrubbed["investor"]["mobile"] == "***"
    assert scrubbed["investor"]["email"] == "***"
    assert "ABCDE1234F" not in scrubbed["note"]
    assert "*****" in scrubbed["note"]


# --------------------------------------------------------------------------
# base_url() guard
# --------------------------------------------------------------------------


def test_base_url_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from dhanradar.config import settings

    monkeypatch.setattr(settings, "MFU_UAT_ENABLED", False)
    with pytest.raises(MfuError) as exc_info:
        base_url()
    assert exc_info.value.error_code == "DISABLED"


def test_base_url_missing_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    from dhanradar.config import settings

    monkeypatch.setattr(settings, "MFU_AES_KEY", "")
    with pytest.raises(MfuError) as exc_info:
        base_url()
    assert exc_info.value.error_code == "NOT_CONFIGURED"


def test_base_url_wrong_host(monkeypatch: pytest.MonkeyPatch) -> None:
    from dhanradar.config import settings

    monkeypatch.setattr(settings, "MFU_API_BASE_URL_UAT", "https://evil.example.com")
    with pytest.raises(MfuError) as exc_info:
        base_url()
    assert exc_info.value.error_code == "NOT_UAT_HOST"


def test_base_url_http_scheme_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    from dhanradar.config import settings

    monkeypatch.setattr(settings, "MFU_API_BASE_URL_UAT", "http://test.mfuonline.com")
    with pytest.raises(MfuError) as exc_info:
        base_url()
    assert exc_info.value.error_code == "NOT_UAT_HOST"


def test_base_url_ok() -> None:
    assert base_url() == "https://test.mfuonline.com"


# --------------------------------------------------------------------------
# login()
# --------------------------------------------------------------------------


async def test_login_success_caches_token(fake_http, patch_redis) -> None:
    fake_http.responses = [
        _FakeResponse(200, {"access_token": "tok-123", "token_type": "Bearer", "expires_in": "24"})
    ]
    db = _FakeDb()
    token, ttl_s = await login(db)
    assert token == "tok-123"
    assert ttl_s == 24 * 3600 - 3600
    cached = await patch_redis.get(mfu_client._TOKEN_KEY)
    assert cached == "tok-123"
    assert len(db.added) == 1
    assert db.added[0].resp_flag == "S"
    assert db.added[0].error_code is None


async def test_login_failure_sets_cooldown_and_raises(fake_http, patch_redis) -> None:
    fake_http.responses = [
        _FakeResponse(
            400,
            {
                "errorRespData": {
                    "errorCode": "1",
                    "errorMsg": "General Exceptions while decrypt the text.",
                }
            },
        )
    ]
    db = _FakeDb()
    with pytest.raises(MfuError) as exc_info:
        await login(db)
    assert exc_info.value.error_code == "1"
    assert "decrypt" in exc_info.value.error_msg
    assert await patch_redis.get(mfu_client._COOLDOWN_KEY) is not None
    assert db.added[0].http_status == 400
    assert db.added[0].error_code == "1"


async def test_login_top_level_error_shape(fake_http, patch_redis) -> None:
    """Sometimes the error is {"errorCode": ..., "errorMsg": ...} at top level."""
    fake_http.responses = [
        _FakeResponse(401, {"errorCode": "2", "errorMsg": "Invalid credentials"})
    ]
    db = _FakeDb()
    with pytest.raises(MfuError) as exc_info:
        await login(db)
    assert exc_info.value.error_code == "2"
    assert exc_info.value.error_msg == "Invalid credentials"


async def test_cooldown_blocks_second_login_without_http_call(fake_http, patch_redis) -> None:
    fake_http.responses = [
        _FakeResponse(400, {"errorRespData": {"errorCode": "1", "errorMsg": "boom"}})
    ]
    db = _FakeDb()
    with pytest.raises(MfuError):
        await login(db)
    assert len(fake_http.calls) == 1

    # Second attempt must be refused WITHOUT another HTTP call.
    with pytest.raises(MfuError) as exc_info:
        await login(db)
    assert exc_info.value.error_code == "COOLDOWN"
    assert len(fake_http.calls) == 1  # unchanged — no HTTP call made


# --------------------------------------------------------------------------
# call() — decrypt-failure logging, token eviction, plaintext evidence
# --------------------------------------------------------------------------


async def _seed_token(patch_redis) -> None:
    """Pre-cache a token so call() -> get_token() skips login() entirely."""
    await patch_redis.set(mfu_client._TOKEN_KEY, "tok-cached", ex=3600)


async def test_call_garbage_resp_data_raises_decrypt_error_and_logs(fake_http, patch_redis) -> None:
    await _seed_token(patch_redis)
    fake_http.responses = [_FakeResponse(200, {"respData": "not-valid-base64-ciphertext!!"})]
    db = _FakeDb()
    with pytest.raises(MfuError) as exc_info:
        await call(db, "TESTAPI", "some/path", {"a": "b"})
    assert exc_info.value.error_code == "DECRYPT_ERROR"
    assert len(db.added) == 1
    assert db.added[0].error_code == "DECRYPT_ERROR"
    # error_msg is the exception CLASS NAME only — never leaks payload content.
    assert db.added[0].error_msg and " " not in db.added[0].error_msg


async def test_call_token_expired_error_evicts_cached_token(fake_http, patch_redis) -> None:
    await _seed_token(patch_redis)
    fake_http.responses = [
        _FakeResponse(
            401,
            {"errorRespData": {"errorCode": "100007", "errorMsg": "token expired"}},
        )
    ]
    db = _FakeDb()
    with pytest.raises(MfuError) as exc_info:
        await call(db, "TESTAPI", "some/path", {"a": "b"})
    assert exc_info.value.error_code == "100007"
    assert await patch_redis.get(mfu_client._TOKEN_KEY) is None


async def test_call_token_invalid_error_evicts_cached_token(fake_http, patch_redis) -> None:
    await _seed_token(patch_redis)
    fake_http.responses = [
        _FakeResponse(
            401,
            {"errorRespData": {"errorCode": "100006", "errorMsg": "token invalid"}},
        )
    ]
    db = _FakeDb()
    with pytest.raises(MfuError):
        await call(db, "TESTAPI", "some/path", {"a": "b"})
    assert await patch_redis.get(mfu_client._TOKEN_KEY) is None


async def test_call_other_error_code_does_not_evict_token(fake_http, patch_redis) -> None:
    await _seed_token(patch_redis)
    fake_http.responses = [
        _FakeResponse(400, {"errorRespData": {"errorCode": "999", "errorMsg": "unrelated"}})
    ]
    db = _FakeDb()
    with pytest.raises(MfuError):
        await call(db, "TESTAPI", "some/path", {"a": "b"})
    assert await patch_redis.get(mfu_client._TOKEN_KEY) == "tok-cached"


async def test_call_logs_plaintext_request_with_pii_masked(fake_http, patch_redis) -> None:
    await _seed_token(patch_redis)
    resp_plain = '{"respHeader": {"respFlag": "S"}, "respBody": {}}'
    resp_data_enc = encrypt(resp_plain, _KEY, _IV)
    fake_http.responses = [_FakeResponse(200, {"respData": resp_data_enc})]
    db = _FakeDb()
    body = {"investor": {"pan": "ABCDE1234F", "mobile": "9999999999"}, "amount": 100}

    result = await call(db, "TESTAPI", "some/path", body)

    assert result["respHeader"]["respFlag"] == "S"
    assert len(db.added) == 1
    logged = db.added[0].request_json
    # The logged body must be the PLAINTEXT field structure (masked), not the
    # single opaque "data" ciphertext field the wire envelope carries.
    assert "reqBody" in logged
    assert "investor" in logged["reqBody"]
    assert logged["reqBody"]["investor"]["pan"] == "***"
    assert logged["reqBody"]["investor"]["mobile"] == "***"
    assert logged["reqBody"]["amount"] == 100
    assert "data" not in logged["reqBody"]
