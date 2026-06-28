"""
DhanRadar — stdin → R2 uploader (the upload half of ``scripts/backup-db.sh``).

Reads a compressed pg_dump from stdin so the dump streams directly from
``pg_dump`` inside the postgres container into R2 via the fastapi container's
existing ``storage.put_object`` — no temp file is written on the host.

Empty-dump guard
----------------
If the pipe produces 0 bytes (e.g. ``pg_dump`` failed and the shell's
``pipefail`` somehow did not propagate), this module refuses to upload and
exits non-zero.  A 0-byte object would silently overwrite a good backup with
an empty file; the guard makes a bad dump visible rather than hiding it.

Usage (invoked by backup-db.sh)::

    <pg_dump output> | python -m dhanradar.ops.r2_put <r2-key>

Exit codes
----------
0  — upload succeeded.
1  — unexpected exception during upload.
2  — missing key argument.
3  — stdin was empty; upload refused.
4  — R2 not configured (``StorageNotConfigured``).
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import IO


def main(argv: Sequence[str] | None = None, *, _stdin: IO[bytes] | None = None) -> int:
    """Upload stdin bytes to R2 under the given key.

    Parameters
    ----------
    argv:
        Argument vector (``sys.argv``-style, index 0 = program name).
        Defaults to ``sys.argv`` when ``None``.
    _stdin:
        Byte-stream to read from.  Defaults to ``sys.stdin.buffer``.
        Exists solely so unit tests can inject a ``BytesIO`` without
        monkeypatching ``sys.stdin`` globally.
    """
    if argv is None:
        argv = sys.argv

    if len(argv) < 2 or not argv[1]:
        print("error: usage: python -m dhanradar.ops.r2_put <r2-key>", file=sys.stderr)
        return 2

    key: str = argv[1]
    source: IO[bytes] = _stdin if _stdin is not None else sys.stdin.buffer

    data: bytes = source.read()

    if len(data) == 0:
        print(
            "error: refusing to upload empty backup — pg_dump produced 0 bytes; "
            "check pg_dump exit status and pipefail propagation",
            file=sys.stderr,
        )
        return 3

    from dhanradar import storage

    try:
        storage.put_object(key, data, "application/octet-stream")
    except storage.StorageNotConfigured as exc:
        print(f"error: R2 not configured — {exc}", file=sys.stderr)
        return 4
    except Exception as exc:  # noqa: BLE001 — surface all unexpected failures to the caller
        print(f"error: upload failed — {exc}", file=sys.stderr)
        return 1

    print(f"uploaded {len(data)} bytes -> {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
