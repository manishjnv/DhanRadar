"""Guard against Alembic revision-id collisions in ``backend/alembic/versions/``.

Problem this solves
--------------------
On 2026-07-05, three concurrent Claude sessions working on this repo collided on
Alembic migration revision numbers TWICE within one hour:

1. PR #469 vs #470 — #470's migration file was silently lost during a git
   rebase (a builder saw ``alembic heads -> 0065`` and mistook another
   session's 0065 for their own, so their own untracked migration file
   vanished from the staged tree). The model columns shipped WITHOUT their
   DDL migration, causing ``asyncpg.UndefinedColumnError`` 500s on the public
   fund page for ~6 minutes in production, recovered by an emergency
   ``ALTER TABLE ... ADD COLUMN IF NOT EXISTS``.
2. PR #472 vs #473 — caught by the CI ``migrations`` job's own
   ``alembic upgrade head`` failing with "Multiple head revisions". This one
   did NOT reach prod because CI correctly went red and autodeploy only
   deploys on CI=success.

The existing convention ("check `alembic heads` against origin/main before
rebasing/merging") already exists but has proven insufficient — it failed
twice in one day because it depends on a human remembering to run it at
exactly the right moment against exactly the right ref. This script is the
structural, always-on replacement.

Check A vs Check B
-------------------
Check A (local graph integrity) — always runs, needs no network or git
access. It parses every migration file in ``backend/alembic/versions/``,
asserts every ``revision`` id is globally unique, and asserts the
revision -> down_revision graph has exactly one head. This is fast (<1s) and
safe to run on every local dev invocation (wired into
``scripts/ci_guards.py``).

Check B (PR-context freshness check) — only runs under ``--pr-check``, since
it needs network/git access. It fetches the LIVE current tip of
``origin/main`` and diffs the migration filenames this PR adds against what
already exists there. If a new migration's revision-number prefix already
exists on that freshly-fetched tip, that is exactly the missed case from both
incidents above: something merged into main after this branch diverged, and
this branch's migration now collides with it.

Why the merge-base is deliberately NOT used
--------------------------------------------
A collision only becomes real if ANOTHER migration merges into main AFTER
this branch already branched off. Comparing this PR's migrations against the
git merge-base (the commit where the branch diverged from main) will NOT
catch that: the merge-base is stale by definition, frozen at branch-off time,
and can never see anything that landed on main afterwards. Check B therefore
always compares against a freshly fetched ``origin/main`` (or an explicit
``--base-ref``), never a locally cached ref and never ``git merge-base``. See
the exact point this matters in ``fetch_base_ref``/``list_ref_migration_filenames``
below.

Main-branch CI's own ``alembic upgrade head`` step remains the backstop for
the last-mile merge-click race (two PRs merging within seconds of each
other) — this script closes the much larger and more common gap: a PR whose
migration collides with something that merged hours earlier, which this
script's Check B catches immediately in the PR's own CI run instead of at
merge time.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

# backend/scripts/check_migration_collisions.py -> repo root is 2 levels up
# from `backend/` (scripts -> backend -> repo root).
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
VERSIONS_DIR = BACKEND_DIR / "alembic" / "versions"
VERSIONS_DIR_RELATIVE = "backend/alembic/versions"

# This repo's migration filename convention (verified against the real files):
#   0068_mf_category_flows_scheme_type.py
#   0008a_mf_nav_monthly_agg.py       <- letter suffix used to linearize a
#                                        duplicate-number branch (see 0008a's
#                                        own docstring for precedent).
# Group 1 captures the leading numeric-prefix (with optional trailing letter),
# which by convention matches the file's `revision` value.
_FILENAME_RE = re.compile(r"^(\d+[a-z]?)_[A-Za-z0-9_]+\.py$")

_REVISION_RE = re.compile(r'^revision\s*(?::[^=\n]+)?=\s*["\']([^"\']+)["\']', re.MULTILINE)
_DOWN_REVISION_RE = re.compile(
    r'^down_revision\s*(?::[^=\n]+)?=\s*(None\b|["\']([^"\']+)["\'])', re.MULTILINE
)


@dataclass(frozen=True)
class Migration:
    """A single parsed Alembic migration file."""

    path: Path
    revision: str
    down_revision: str | None


def iter_migration_files(versions_dir: Path) -> list[Path]:
    """Return migration files in ``versions_dir`` matching this repo's naming convention.

    Skips ``__pycache__`` (not a file, so excluded naturally by the ``is_file``
    check), any file starting with ``_``, and any ``.py`` file that does not
    match the ``<number>[letter]_<name>.py`` pattern used throughout
    ``backend/alembic/versions/``.
    """
    if not versions_dir.exists():
        return []
    files: list[Path] = []
    for p in sorted(versions_dir.iterdir()):
        if not p.is_file() or p.suffix != ".py":
            continue
        if p.name.startswith("_"):
            continue
        if not _FILENAME_RE.match(p.name):
            continue
        files.append(p)
    return files


def parse_migration_file(path: Path) -> Migration:
    """Parse the ``revision`` and ``down_revision`` assignments out of one migration file.

    Uses regex over the raw source text (NOT ``importlib``/``ast``) — importing
    60+ migration modules has side effects, is slow, and can fail on
    dependencies unrelated to this check. Every migration file in this repo
    declares both assignments as simple module-level literals
    (``revision: str = "0068"``, ``down_revision: str | None = "0067"`` or
    ``= None``), so a line-anchored regex is sufficient and robust.
    """
    text = path.read_text(encoding="utf-8")

    rev_match = _REVISION_RE.search(text)
    if rev_match is None:
        raise ValueError(f'{path}: could not find a `revision = "..."` assignment')
    revision = rev_match.group(1)

    down_match = _DOWN_REVISION_RE.search(text)
    if down_match is None:
        raise ValueError(f"{path}: could not find a `down_revision = ...` assignment")
    down_revision = None if down_match.group(1) == "None" else down_match.group(2)

    return Migration(path=path, revision=revision, down_revision=down_revision)


def load_migrations(versions_dir: Path) -> list[Migration]:
    """Parse every migration file in ``versions_dir`` into a ``Migration``."""
    return [parse_migration_file(p) for p in iter_migration_files(versions_dir)]


def check_unique_revisions(migrations: Sequence[Migration]) -> list[str]:
    """Assert every migration's ``revision`` id is globally unique.

    Returns a list of human-readable failure messages (empty = pass). Does
    not raise, so callers can collect failures from multiple checks before
    reporting.
    """
    by_revision: dict[str, list[Migration]] = {}
    for m in migrations:
        by_revision.setdefault(m.revision, []).append(m)

    failures: list[str] = []
    for revision, group in sorted(by_revision.items()):
        if len(group) > 1:
            names = ", ".join(m.path.name for m in group)
            failures.append(
                f"Duplicate revision id {revision!r} declared by multiple migration files: "
                f"{names}. Every migration must have a globally unique `revision` value — "
                "renumber one of these."
            )
    return failures


def find_heads(migrations: Sequence[Migration]) -> list[Migration]:
    """Return the migrations that are nobody's ``down_revision`` (the graph's heads).

    A migration ``m`` is a head when no other migration declares
    ``down_revision == m.revision`` — i.e. nothing continues the chain past it.
    A single, linear chain has exactly one head (the tip/latest migration).
    """
    down_revisions = {m.down_revision for m in migrations if m.down_revision is not None}
    return [m for m in migrations if m.revision not in down_revisions]


def check_single_head(migrations: Sequence[Migration]) -> list[str]:
    """Assert the revision graph has exactly one head (no cycle, no branch).

    Returns a list of human-readable failure messages (empty = pass).
    """
    heads = find_heads(migrations)
    if len(heads) == 0:
        return [
            "No head revision found among migrations — the revision graph appears to "
            "contain a cycle (every revision is some other revision's down_revision). "
            "Check for a broken/circular down_revision chain."
        ]
    if len(heads) > 1:
        names = ", ".join(f"{m.revision!r} ({m.path.name})" for m in heads)
        return [
            f"Multiple head revisions found: {names}. Alembic requires exactly one head — "
            "renumber/rechain one of these migrations so it revises the other, or merge them."
        ]
    return []


def find_new_migration_collisions(
    new_filenames: Iterable[str], base_filenames: Iterable[str]
) -> list[tuple[str, str]]:
    """Find new migration filenames whose numeric prefix collides with a base-ref file.

    Pure comparison function — takes plain filename iterables so it is
    testable without invoking git. ``new_filenames`` are migration files that
    exist in the current working tree but NOT on the base ref (i.e. what this
    PR is adding); ``base_filenames`` are the migration files that exist on
    the freshly-fetched base ref tip. Returns ``(new_file, colliding_base_file)``
    pairs.
    """
    base_prefixes: dict[str, str] = {}
    for fname in base_filenames:
        m = _FILENAME_RE.match(fname)
        if m is not None:
            base_prefixes.setdefault(m.group(1), fname)

    collisions: list[tuple[str, str]] = []
    for fname in sorted(new_filenames):
        m = _FILENAME_RE.match(fname)
        if m is None:
            continue
        prefix = m.group(1)
        if prefix in base_prefixes:
            collisions.append((fname, base_prefixes[prefix]))
    return collisions


def fetch_base_ref(remote: str = "origin", branch: str = "main") -> None:
    """Fetch the LIVE tip of ``<remote>/<branch>`` fresh from the network right now.

    Deliberately a shallow, targeted fetch (``--depth=1``) — enough for
    ``git ls-tree`` to see the current tip's file list without a full history
    clone. This is NOT ``git merge-base`` and NOT a locally cached ref: this
    is precisely the distinction that caused both 2026-07-05 collisions (see
    module docstring) — a stale/cached view of main cannot see migrations
    that merged after this branch diverged.
    """
    subprocess.run(
        ["git", "fetch", remote, branch, "--depth=1"],
        cwd=REPO_ROOT,
        check=True,
    )


def list_ref_migration_filenames(
    ref: str, versions_dir_relative: str = VERSIONS_DIR_RELATIVE
) -> set[str]:
    """List migration filenames present in ``versions_dir_relative`` at ``ref``'s tip.

    ``ref`` must already point at a freshly fetched tip (e.g. ``origin/main``
    right after ``fetch_base_ref()``) — this function does not fetch itself,
    it only reads whatever ``ref`` currently resolves to. Callers must not
    pass a merge-base or other stale ref; see the module docstring for why.
    """
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref, "--", versions_dir_relative],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {Path(line).name for line in result.stdout.splitlines() if line.strip()}


def main(argv: list[str] | None = None) -> int:
    """Entry point: run Check A always, Check B under ``--pr-check``."""
    parser = argparse.ArgumentParser(
        description="Guard against Alembic revision-id collisions.",
    )
    parser.add_argument(
        "--pr-check",
        action="store_true",
        help=(
            "Also run Check B: compare this branch's new migration files against the "
            "freshly-fetched live tip of --base-ref, catching collisions with anything "
            "that merged into main after this branch diverged."
        ),
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Ref to compare against for Check B (default: origin/main).",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help=(
            "Skip the internal `git fetch` before Check B — use when the caller (e.g. a "
            "CI step) has already fetched a fresh --base-ref itself."
        ),
    )
    args = parser.parse_args(argv)

    failures: list[str] = []

    try:
        migrations = load_migrations(VERSIONS_DIR)
    except ValueError as exc:
        print(f"Migration collision check FAILED to parse migration files:\n  - {exc}")
        return 1

    failures.extend(check_unique_revisions(migrations))
    failures.extend(check_single_head(migrations))

    if args.pr_check:
        if not args.skip_fetch:
            try:
                fetch_base_ref()
            except subprocess.CalledProcessError as exc:
                print(f"Migration collision check FAILED to fetch base ref: {exc}")
                return 1
        try:
            base_files = list_ref_migration_filenames(args.base_ref)
        except subprocess.CalledProcessError as exc:
            print(
                f"Migration collision check FAILED to list migration files on "
                f"{args.base_ref!r}: {exc}"
            )
            return 1

        current_files = {m.path.name for m in migrations}
        new_files = current_files - base_files
        for new_name, base_name in find_new_migration_collisions(new_files, base_files):
            failures.append(
                f"New migration {new_name!r} collides with {base_name!r}, which already "
                f"exists on the live tip of {args.base_ref!r}. Someone else's migration "
                "merged into main after this branch diverged and claimed the same "
                "revision number — renumber your new migration to the next free prefix "
                "and rerun this check."
            )

    if failures:
        print("Migration collision check FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1

    suffix = " + Check B" if args.pr_check else ""
    print(f"Migration collision check passed ({len(migrations)} migration(s), Check A{suffix}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
