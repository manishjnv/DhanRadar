"""Unit tests for scripts/check_migration_collisions.py.

Imports the script's module-level functions directly (via
``importlib.util.spec_from_file_location``, since it's a standalone script in
``backend/scripts/``, not an installed package) and exercises Check A's pure
parsing/graph logic plus Check B's pure filename-comparison logic against
synthetic fixture files under ``tmp_path`` — no real Alembic imports, no git,
no network.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "backend" / "scripts" / "check_migration_collisions.py"


def _load_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("check_migration_collisions", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mc = _load_module()


def _write_migration(
    directory: Path, filename: str, revision: str, down_revision: str | None
) -> None:
    down_literal = "None" if down_revision is None else f'"{down_revision}"'
    directory.joinpath(filename).write_text(
        f'"""Fixture migration."""\n\n'
        f"from __future__ import annotations\n\n"
        f'revision: str = "{revision}"\n'
        f"down_revision: str | None = {down_literal}\n"
        f"branch_labels = None\n"
        f"depends_on = None\n\n"
        f"def upgrade() -> None:\n"
        f"    pass\n\n"
        f"def downgrade() -> None:\n"
        f"    pass\n",
        encoding="utf-8",
    )


class TestCheckAParsing:
    def test_unique_revisions_and_single_head_passes(self, tmp_path: Path) -> None:
        _write_migration(tmp_path, "0001_init.py", "0001", None)
        _write_migration(tmp_path, "0002_second.py", "0002", "0001")
        _write_migration(tmp_path, "0003_third.py", "0003", "0002")

        migrations = mc.load_migrations(tmp_path)
        assert len(migrations) == 3
        assert mc.check_unique_revisions(migrations) == []
        assert mc.check_single_head(migrations) == []

    def test_duplicate_revision_fails_naming_both_files(self, tmp_path: Path) -> None:
        _write_migration(tmp_path, "0001_init.py", "0001", None)
        _write_migration(tmp_path, "0002_second.py", "0002", "0001")
        _write_migration(tmp_path, "0002a_second_dupe.py", "0002", "0001")

        migrations = mc.load_migrations(tmp_path)
        failures = mc.check_unique_revisions(migrations)
        assert len(failures) == 1
        assert "0002" in failures[0]
        assert "0002_second.py" in failures[0]
        assert "0002a_second_dupe.py" in failures[0]

    def test_two_heads_fails_listing_both(self, tmp_path: Path) -> None:
        _write_migration(tmp_path, "0001_init.py", "0001", None)
        _write_migration(tmp_path, "0002_branch_a.py", "0002", "0001")
        _write_migration(tmp_path, "0003_branch_b.py", "0003", "0001")

        migrations = mc.load_migrations(tmp_path)
        failures = mc.check_single_head(migrations)
        assert len(failures) == 1
        assert "0002" in failures[0]
        assert "0003" in failures[0]
        assert "0002_branch_a.py" in failures[0]
        assert "0003_branch_b.py" in failures[0]

    def test_zero_heads_cycle_fails(self, tmp_path: Path) -> None:
        # Two revisions that each claim to revise the other -> no head exists.
        _write_migration(tmp_path, "0001_a.py", "0001", "0002")
        _write_migration(tmp_path, "0002_b.py", "0002", "0001")

        migrations = mc.load_migrations(tmp_path)
        failures = mc.check_single_head(migrations)
        assert len(failures) == 1
        assert "cycle" in failures[0].lower()

    def test_non_migration_files_are_skipped(self, tmp_path: Path) -> None:
        _write_migration(tmp_path, "0001_init.py", "0001", None)
        tmp_path.joinpath("__init__.py").write_text("", encoding="utf-8")
        tmp_path.joinpath("_helpers.py").write_text("revision = 'nope'\n", encoding="utf-8")
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        pycache.joinpath("0001_init.cpython-312.pyc").write_bytes(b"\x00")

        migrations = mc.load_migrations(tmp_path)
        assert [m.path.name for m in migrations] == ["0001_init.py"]


class TestCheckBComparison:
    def test_no_collision_when_prefixes_disjoint(self) -> None:
        new_files = {"0069_new_thing.py"}
        base_files = {"0067_mf_fund_events.py", "0068_mf_category_flows_scheme_type.py"}
        assert mc.find_new_migration_collisions(new_files, base_files) == []

    def test_collision_when_new_prefix_already_on_base_ref(self) -> None:
        new_files = {"0069_my_feature.py"}
        base_files = {"0068_mf_category_flows_scheme_type.py", "0069_someone_elses_feature.py"}
        collisions = mc.find_new_migration_collisions(new_files, base_files)
        assert collisions == [("0069_my_feature.py", "0069_someone_elses_feature.py")]

    def test_multiple_new_files_only_flags_actual_collisions(self) -> None:
        new_files = {"0069_ok.py", "0070_collides.py"}
        base_files = {"0068_x.py", "0070_already_there.py"}
        collisions = mc.find_new_migration_collisions(new_files, base_files)
        assert collisions == [("0070_collides.py", "0070_already_there.py")]


class TestRealRepoIntegration:
    def test_real_migrations_directory_currently_passes_both_checks(self) -> None:
        """Sanity check: this repo's real migration chain is clean right now (Check A only).

        Parses the real backend/alembic/versions/ directory exactly like Check A
        does — no alembic/DB imports, just file parsing — confirming the chain
        stays a single linear graph with globally-unique revision ids.
        """
        migrations = mc.load_migrations(mc.VERSIONS_DIR)
        assert len(migrations) > 0

        unique_failures = mc.check_unique_revisions(migrations)
        assert unique_failures == [], unique_failures

        head_failures = mc.check_single_head(migrations)
        assert head_failures == [], head_failures


def test_main_exits_zero_on_real_repo(capsys: pytest.CaptureFixture[str]) -> None:
    """Running main() (Check A only, no --pr-check) against the real repo passes."""
    exit_code = mc.main([])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "passed" in out
