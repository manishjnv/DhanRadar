"""
Unit tests for dhanradar.ops.r2_put.main.

No DB, no network — storage.put_object and sys.stdin are monkeypatched.
"""

from __future__ import annotations

import io
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stdin(data: bytes) -> io.BytesIO:
    """Return a BytesIO that mimics sys.stdin.buffer."""
    return io.BytesIO(data)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_uploads_stdin_bytes_to_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: non-empty stdin → put_object called once with correct args; returns 0."""
    from dhanradar.ops import r2_put
    from dhanradar import storage

    mock_put = MagicMock()
    monkeypatch.setattr(storage, "put_object", mock_put)

    payload = b"PGDMP\x00\x01\x02data"
    stdin = _make_stdin(payload)

    rc = r2_put.main(["r2_put", "backups/postgres/2026/06/07/test.dump"], _stdin=stdin)

    assert rc == 0
    mock_put.assert_called_once_with(
        "backups/postgres/2026/06/07/test.dump",
        payload,
        "application/octet-stream",
    )


def test_refuses_empty_backup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty stdin → put_object NOT called; returns 3."""
    from dhanradar.ops import r2_put
    from dhanradar import storage

    mock_put = MagicMock()
    monkeypatch.setattr(storage, "put_object", mock_put)

    stdin = _make_stdin(b"")

    rc = r2_put.main(["r2_put", "backups/postgres/2026/06/07/empty.dump"], _stdin=stdin)

    assert rc == 3
    mock_put.assert_not_called()


def test_missing_key_arg(monkeypatch: pytest.MonkeyPatch) -> None:
    """No key argument → returns 2; put_object not called."""
    from dhanradar.ops import r2_put
    from dhanradar import storage

    mock_put = MagicMock()
    monkeypatch.setattr(storage, "put_object", mock_put)

    rc = r2_put.main(["r2_put"])

    assert rc == 2
    mock_put.assert_not_called()


def test_storage_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """put_object raises StorageNotConfigured → returns 4."""
    from dhanradar.ops import r2_put
    from dhanradar import storage

    monkeypatch.setattr(
        storage,
        "put_object",
        MagicMock(side_effect=storage.StorageNotConfigured("R2 endpoint/credentials missing")),
    )

    stdin = _make_stdin(b"PGDMP some real data here")

    rc = r2_put.main(["r2_put", "backups/postgres/2026/06/07/unconfigured.dump"], _stdin=stdin)

    assert rc == 4


def test_unexpected_exception_returns_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """put_object raises an unexpected exception → returns 1."""
    from dhanradar.ops import r2_put
    from dhanradar import storage

    monkeypatch.setattr(
        storage,
        "put_object",
        MagicMock(side_effect=RuntimeError("network timeout")),
    )

    stdin = _make_stdin(b"PGDMP good data")

    rc = r2_put.main(["r2_put", "backups/postgres/2026/06/07/error.dump"], _stdin=stdin)

    assert rc == 1
