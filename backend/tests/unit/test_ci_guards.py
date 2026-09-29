"""Self-test for scripts/ci_guards.py advisory coverage (B13) and NullPool guard (SEV2).

Runs the real guard script as a subprocess (exactly as CI invokes it) against a
temporary non-code asset planted in the frontend tree, proving that:

  * non-code label assets beyond the 3 hardcoded token files are scanned
    (the gap that let an advisory ``signal`` block ship in tokens.json), and
  * camelCase advisory keys (``strongBuy``) are caught, not only snake_case.

Also tests Guard #6 (pooled-engine session outside db.py) by planting a fixture
Python file under ``backend/dhanradar/`` with ``async_sessionmaker(engine`` and
asserting the guard flags it (SEV2 prevention).

The fixture is written under its target tree and always removed in ``finally`` so
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
BACKEND_DHANRADAR = REPO_ROOT / "backend" / "dhanradar"


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


def test_aria_role_switch_is_not_flagged() -> None:
    """ARIA ``role="switch"`` is a legitimate accessibility attribute (used by every
    toggle component), not advisory copy — it must NOT trip the advisory scan.
    Regression: "switch" is in the recommendation verb set and collided with the
    HTML role before the lookbehind exemption."""
    fixture = FRONTEND / "__ci_guard_selftest_aria__.tsx"
    fixture.write_text('<button role="switch" aria-checked={true} />\n', encoding="utf-8")
    try:
        result = _run_guard()
        assert "__ci_guard_selftest_aria__" not in result.stdout, (
            f'ARIA role="switch" must NOT be flagged as advisory:\n{result.stdout}'
        )
    finally:
        fixture.unlink(missing_ok=True)


def test_standalone_switch_value_still_flagged() -> None:
    """Proof the ARIA lookbehind did NOT weaken detection: a standalone advisory
    ``"switch"`` label value (not preceded by ``role=``) is still caught."""
    fixture = FRONTEND / "__ci_guard_selftest_switch__.json"
    fixture.write_text('{"label": "switch"}\n', encoding="utf-8")
    try:
        result = _run_guard()
        assert result.returncode == 1, (
            f'guard must still flag a standalone advisory "switch":\n{result.stdout}'
        )
        assert "__ci_guard_selftest_switch__" in result.stdout
    finally:
        fixture.unlink(missing_ok=True)


def test_pooled_engine_session_outside_db_py_is_caught() -> None:
    """Guard #6 (SEV2 NullPool invariant): any file under backend/dhanradar/ other
    than db.py that contains ``async_sessionmaker(engine`` must be flagged.

    Regression: the original #69 fix migrated tasks/* but left service files
    open-coding their own pooled-engine sessions; Guard #6 ensures that pattern
    can never re-enter the tree undetected.
    """
    fixture = BACKEND_DHANRADAR / "__ci_guard_nullpool_test__.py"
    fixture.write_text(
        "from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker\n"
        "from dhanradar.db import engine\n"
        "SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)\n",
        encoding="utf-8",
    )
    try:
        result = _run_guard()
        assert result.returncode == 1, (
            "guard must FAIL when async_sessionmaker(engine) appears outside db.py, "
            f"but passed:\n{result.stdout}"
        )
        assert "SEV2 guard #6" in result.stdout
        assert "__ci_guard_nullpool_test__" in result.stdout
    finally:
        fixture.unlink(missing_ok=True)


def test_db_py_pooled_engine_not_flagged() -> None:
    """Guard #6 must NOT flag db.py itself — it is the one allowed owner of the
    pooled-engine binding."""
    # The committed db.py already contains async_sessionmaker(engine).
    # If the guard is clean on the real tree, this invariant holds.
    result = _run_guard()
    assert result.returncode == 0, (
        f"db.py's own async_sessionmaker(engine) must not be flagged:\n{result.stdout}"
    )


def test_mfu_importing_bse_is_caught() -> None:
    """Guard #11 (mfu/bse module isolation, non-neg #7): a file under
    backend/dhanradar/mfu/ that imports dhanradar.bse must be flagged."""
    fixture = BACKEND_DHANRADAR / "mfu" / "__ci_guard_isolation_test__.py"
    fixture.write_text("import dhanradar.bse\n", encoding="utf-8")
    try:
        result = _run_guard()
        assert result.returncode == 1, (
            f"guard must FAIL when mfu/ imports dhanradar.bse, but passed:\n{result.stdout}"
        )
        assert "mfu/bse module isolation" in result.stdout
    finally:
        fixture.unlink(missing_ok=True)


def test_bse_importing_mfu_is_caught() -> None:
    """Guard #11, reverse direction: bse/ must not import dhanradar.mfu."""
    fixture = BACKEND_DHANRADAR / "bse" / "__ci_guard_isolation_test__.py"
    fixture.write_text("import dhanradar.models.mfu\n", encoding="utf-8")
    try:
        result = _run_guard()
        assert result.returncode == 1, (
            f"guard must FAIL when bse/ imports dhanradar.models.mfu, but passed:\n{result.stdout}"
        )
        assert "mfu/bse module isolation" in result.stdout
    finally:
        fixture.unlink(missing_ok=True)


@pytest.mark.parametrize(
    "payload",
    [
        # from-package import: `from dhanradar import bse` — the old line
        # regex `^\s*(?:import|from) dhanradar\.` never matched this (no dot
        # right after "dhanradar").
        "from dhanradar import bse\n",
        # from-package import naming a submodule under dhanradar.models.
        "from dhanradar.models import bse\n",
        # importlib.import_module() with a literal target string.
        'import importlib\nimportlib.import_module("dhanradar.bse.service")\n',
        'from importlib import import_module\nimport_module("dhanradar.admin.bse_uat_router")\n',
    ],
)
def test_mfu_importing_bse_bypass_shapes_are_caught(payload: str) -> None:
    """Guard #11 AST rewrite: each of these previously slipped past the line
    regex (a line that never starts with `import dhanradar.` / `from dhanradar.`)."""
    fixture = BACKEND_DHANRADAR / "mfu" / "__ci_guard_isolation_bypass_test__.py"
    fixture.write_text(payload, encoding="utf-8")
    try:
        result = _run_guard()
        assert result.returncode == 1, (
            f"guard must FAIL on bypass shape {payload!r}, but passed:\n{result.stdout}"
        )
        assert "mfu/bse module isolation" in result.stdout
        assert "__ci_guard_isolation_bypass_test__" in result.stdout
    finally:
        fixture.unlink(missing_ok=True)


@pytest.mark.parametrize(
    "relative_import",
    [
        # `mfu_uat_router.py` lives in the SAME package (dhanradar.admin) as
        # bse_uat_router.py, so a relative import stays entirely invisible to
        # any check anchored on the literal string "dhanradar." — this is the
        # bypass shape the line regex could never catch regardless of pattern.
        "from . import bse_uat_router\n",
        "from .bse_uat_router import get_ucc\n",
    ],
)
def test_mfu_admin_router_relative_import_of_bse_is_caught(relative_import: str) -> None:
    """Guard #11 AST rewrite: a relative import resolves against the file's own
    package (dhanradar.admin), so it must be caught even though the string
    "dhanradar.bse" never appears in the source. Temporarily appends to the
    REAL admin/mfu_uat_router.py (the only admin-side file in the mfu scope)
    and always restores the original content, even on assertion failure."""
    target = BACKEND_DHANRADAR / "admin" / "mfu_uat_router.py"
    original = target.read_text(encoding="utf-8")
    try:
        target.write_text(original + "\n" + relative_import, encoding="utf-8")
        result = _run_guard()
        assert result.returncode == 1, (
            f"guard must FAIL on relative import {relative_import!r}, but passed:\n{result.stdout}"
        )
        assert "mfu/bse module isolation" in result.stdout
        assert "mfu_uat_router.py" in result.stdout
    finally:
        target.write_text(original, encoding="utf-8")


def test_docstring_naming_other_rail_is_not_flagged() -> None:
    """A docstring/comment that merely NAMES the other module (to document the
    isolation rule itself) must never trip the AST-based guard — only real
    import/call nodes count."""
    fixture = BACKEND_DHANRADAR / "mfu" / "__ci_guard_isolation_docstring_test__.py"
    fixture.write_text(
        '"""This module must never import dhanradar.bse or dhanradar.models.bse."""\n'
        "# see also: from dhanradar import bse (forbidden, do not do this)\n",
        encoding="utf-8",
    )
    try:
        result = _run_guard()
        assert result.returncode == 0, (
            f"a docstring/comment naming the other rail must NOT be flagged:\n{result.stdout}"
        )
    finally:
        fixture.unlink(missing_ok=True)
