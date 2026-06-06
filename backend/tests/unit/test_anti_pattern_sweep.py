"""Self-test for scripts/anti_pattern_sweep.py + scripts/check_compose_memory.py.

Runs the real guard scripts as subprocesses (exactly as CI invokes them):
  * the committed tree must PASS both (exit 0);
  * a planted §0.3 anti-pattern under backend/dhanradar/ must FAIL the sweep.

Fixtures are always removed in ``finally`` so the working tree is left clean.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SWEEP = REPO_ROOT / "scripts" / "anti_pattern_sweep.py"
MEMCHK = REPO_ROOT / "scripts" / "check_compose_memory.py"
PKG = REPO_ROOT / "backend" / "dhanradar"


def _run(script: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script)], cwd=str(REPO_ROOT), capture_output=True, text=True
    )


def test_clean_tree_passes_sweep() -> None:
    result = _run(SWEEP)
    assert result.returncode == 0, f"sweep failing on clean tree:\n{result.stdout}"


def test_clean_tree_passes_memory_budget() -> None:
    result = _run(MEMCHK)
    assert result.returncode == 0, f"memory budget failing on clean tree:\n{result.stdout}"


@pytest.mark.parametrize(
    ("payload", "needle"),
    [
        ("from pydantic import Field\nx = Field(regex='a')\n", "regex="),
        ("import sendgrid\n", "sendgrid"),
        ('m = "deepseek/deepseek-v4-flash:free"\n', ":free"),
        ("def require_tier(tier):\n    def dep():\n        return None\n    return dep\n", "require_tier"),
    ],
)
def test_planted_antipattern_is_caught(payload: str, needle: str) -> None:
    fixture = PKG / "__antipattern_selftest__.py"
    fixture.write_text(payload, encoding="utf-8")
    try:
        result = _run(SWEEP)
        assert result.returncode == 1, (
            f"sweep should FAIL on planted '{needle}', but passed:\n{result.stdout}"
        )
        assert "__antipattern_selftest__.py" in result.stdout
    finally:
        fixture.unlink(missing_ok=True)
