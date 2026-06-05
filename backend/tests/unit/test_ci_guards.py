"""Self-test for scripts/ci_guards.py advisory coverage (B13).

Runs the real guard script as a subprocess (exactly as CI invokes it) against a
temporary non-code asset planted in the frontend tree, proving that:

  * non-code label assets beyond the 3 hardcoded token files are scanned
    (the gap that let an advisory ``signal`` block ship in tokens.json), and
  * camelCase advisory keys (``strongBuy``) are caught, not only snake_case.

The fixture is written under ``frontend/`` and always removed in ``finally`` so
the working tree is left clean even if an assertion fails.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
GUARD = REPO_ROOT / "scripts" / "ci_guards.py"
FRONTEND = REPO_ROOT / "frontend"


def _run_guard() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GUARD)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


def test_repo_is_currently_clean() -> None:
    """Baseline: the committed tree must pass the guard (exit 0)."""
    result = _run_guard()
    assert result.returncode == 0, f"guard unexpectedly failing on clean tree:\n{result.stdout}"


@pytest.mark.parametrize(
    ("filename", "payload"),
    [
        # camelCase advisory key in a non-token .json asset (B13 asset walk).
        ("__ci_guard_selftest__.json", '{"strongBuy": "x"}\n'),
        # quoted advisory verb in a .css asset.
        ("__ci_guard_selftest__.css", '/* label: "buy" */\n'),
    ],
)
def test_advisory_in_noncode_asset_is_caught(filename: str, payload: str) -> None:
    fixture = FRONTEND / filename
    fixture.write_text(payload, encoding="utf-8")
    try:
        result = _run_guard()
        assert result.returncode == 1, (
            f"guard should FAIL on advisory verb in {filename}, but passed:\n{result.stdout}"
        )
        assert "advisory verb usage" in result.stdout
        assert filename in result.stdout
    finally:
        fixture.unlink(missing_ok=True)
