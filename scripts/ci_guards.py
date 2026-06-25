#!/usr/bin/env python3
"""
DhanRadar deterministic CI guards (non-negotiables + secret scan).

Fails (exit 1) if any guard is violated. Runs in CI and is safe to run locally
(`python scripts/ci_guards.py`). Scans application CODE only — docs/ and the
scoring config legitimately *mention* rejected patterns (as rejected), so they
are excluded to avoid false positives.

Guards:
  1. No Elasticsearch in code (non-negotiable #3 — Postgres FTS only).
  2. No bearer / Authorization-header auth value in code (non-neg #4 — cookies).
  3. No Manrope/Inter fonts in the generated token files (D1 — Geist only).
  4. No advisory verbs as usage in code (non-neg #2 — educational labels only).
  5. No obvious committed secrets.
  6. No pooled-engine session creation outside db.py (SEV2 NullPool invariant).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE_DIRS = [ROOT / "backend" / "dhanradar", ROOT / "frontend" / "src"]
CODE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".cjs", ".mjs"}

fails: list[str] = []


def code_files():
    for d in CODE_DIRS:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if not (p.is_file() and p.suffix in CODE_EXT):
                continue
            # Skip generated files (e.g. the openapi-typescript client) — they
            # may echo descriptions that mention rejected patterns as rejected.
            if p.name == "api.ts" and "types" in p.parts:
                continue
            yield p


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


# 1. Elasticsearch ----------------------------------------------------------
for p in code_files():
    if re.search(r"elasticsearch", read(p), re.I):
        fails.append(f"{p}: 'elasticsearch' in code (non-neg #3: Postgres FTS only)")

# 2. Bearer / Authorization-header auth -------------------------------------
for p in code_files():
    t = read(p)
    if re.search(r"Bearer\s+\$|Bearer \{|['\"]Bearer | Bearer ", t):
        # match the bearer scheme value, not a comment saying it's absent
        for i, line in enumerate(t.splitlines(), 1):
            if "Bearer " in line and not re.search(r"absent|no bearer|not |never|reject", line, re.I):
                fails.append(f"{p}:{i}: 'Bearer ' auth value (non-neg #4: cookie auth only)")

# 3. Manrope/Inter in generated token files ---------------------------------
TOKEN_FILES = [
    ROOT / "frontend" / "styles" / "tokens.json",
    ROOT / "frontend" / "tailwind.tokens.cjs",
    ROOT / "frontend" / "src" / "styles" / "tokens.css",
]
for p in TOKEN_FILES:
    if p.exists():
        t = read(p)
        if "Manrope" in t or re.search(r"['\"]Inter['\"]", t):
            fails.append(f"{p}: Manrope/Inter font token (D1: Geist/warm only)")

# 4. Advisory verbs as usage (non-neg #2) — educational labels only.
# Catches snake_case, camelCase, Title Case, spaced, quoted-label, and
# object-key forms. Also scans the design-token files (source + generated):
# they live outside frontend/src and are .json/.css (outside CODE_EXT), so the
# original code-only scan missed an advisory `signal` block shipped in
# tokens.json (see docs/rca/README.md 2026-06-05).
_ADV_HARD = re.compile(r"strong[\s_-]?(?:buy|sell)", re.I)  # never innocent
# Covers the architecture's full enumerated recommendation set (buy/sell/hold/
# switch) + the scoring label verbs. The RUNTIME advisory screen
# (ai_gateway/quality.py) carries a broader, domain-owned set; this static net
# guards SOURCE/label assets.
_ADV_WORD = r"(?:strong[\s_]?buy|strong[\s_]?sell|buy|sell|hold|switch|avoid|caution)"
# Negative lookbehind exempts the ARIA accessibility attribute role="switch" — a
# standard, non-advisory a11y role and the ONLY advisory verb that collides with a
# valid HTML role (used by every toggle/switch component). A standalone advisory
# value like "switch" NOT preceded by role= is still caught (verified in
# backend/tests/unit/test_ci_guards.py).
_ADV_QUOTED = re.compile(rf"""(?<!role=)["']{_ADV_WORD}["']""", re.I)  # quoted label value
_ADV_KEY = re.compile(
    r"""(?:^|[{,])\s*["']?(?:strongBuy|strongSell|buy|sell|hold|switch|avoid|caution)["']?\s*:""",
    re.I,
)  # advisory word as an object key
# _ADV_SKIP: lines that legitimately *name* an advisory verb in order to reject
# it (guardrail comments, prohibition copy). Kept deliberately narrow — the bare
# tokens `guard` and `not ` were removed because they co-occur with real advisory
# verbs on innocent-looking lines and would mask a true positive (B13). Negation
# is now matched only as anchored phrases, not any substring of "not".
_ADV_SKIP = re.compile(
    r"reject|never|banned|forbid|prohibit|disallow|advisory|non-advisory|"
    r"educational|guardrail|must not|do not|cannot|may not|no[\s-]?buy",
    re.I,
)

# Advisory scan covers application code PLUS all non-code label assets (B13):
# any .json/.yaml/.css/.html (and config .cjs/.js) under frontend/ and
# backend/dhanradar/ — not just the 3 hardcoded token files, which missed the
# class that shipped the advisory `signal` block in tokens.json.
ASSET_DIRS = [ROOT / "frontend", ROOT / "backend" / "dhanradar"]
ASSET_EXT = CODE_EXT | {".json", ".yaml", ".yml", ".css", ".html"}
ASSET_SKIP_DIRS = {"node_modules", ".next", "__pycache__", ".git", ".venv"}


def _advisory_scan_files():
    seen: set[Path] = set()
    for fp in code_files():
        seen.add(fp)
        yield fp
    for d in ASSET_DIRS:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if not (p.is_file() and p.suffix in ASSET_EXT):
                continue
            if set(p.relative_to(ROOT).parts) & ASSET_SKIP_DIRS:
                continue
            if p in seen:
                continue
            seen.add(p)
            yield p


for p in _advisory_scan_files():
    # ranking_configs files list the rejected verbs verbatim as the banned set;
    # narrowed from a whole-`scoring`-dir skip so engine code is still scanned (B13).
    if p.name.startswith("ranking_configs"):
        continue
    for i, line in enumerate(read(p).splitlines(), 1):
        if _ADV_SKIP.search(line):
            continue
        if _ADV_HARD.search(line) or _ADV_QUOTED.search(line) or _ADV_KEY.search(line):
            rel = p.relative_to(ROOT)
            fails.append(f"{rel}:{i}: advisory verb usage (non-neg #2: educational labels only)")

# 6. Pooled-engine session creation outside db.py (SEV2 NullPool invariant) ------
# Only db.py is allowed to bind `async_sessionmaker(engine, ...)` to the pooled
# QueuePool engine. Every other module must use TaskSessionLocal (backed by the
# NullPool task_engine) or receive a session via get_db / task_session. A module
# that creates its OWN async_sessionmaker(engine, ...) at call time drags the
# pooled engine into Celery asyncio.run() calls and reproduces the InterfaceError
# SEV2 (docs/rca/README.md 2026-06-10). The pattern `async_sessionmaker(engine`
# is the literal trigger — TaskSessionLocal/task_engine are explicitly exempted
# (they are fine; the guard does not flag them).
_DB_PY = ROOT / "backend" / "dhanradar" / "db.py"
for p in code_files():
    if p.resolve() == _DB_PY.resolve():
        continue  # db.py owns the pooled-engine binding — always allowed
    t = read(p)
    for i, line in enumerate(t.splitlines(), 1):
        # Flag any line that creates a session from the pooled `engine` directly.
        # Exempt the NullPool task_engine binding (it's always safe) and any
        # comment/string that merely references the pattern.
        if re.search(r"async_sessionmaker\(engine\b", line):
            rel = p.relative_to(ROOT)
            fails.append(
                f"{rel}:{i}: async_sessionmaker(engine) outside db.py "
                "(SEV2 guard #6 — use TaskSessionLocal instead)"
            )

# 5. Secret scan (scoped) ---------------------------------------------------
SECRET_RES = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ASIA[0-9A-Z]{16}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"xai-[A-Za-z0-9]{20,}"),
    re.compile(r"re_[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{30,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"""(password|secret|token|api_key)\s*[:=]\s*["'][^"']{12,}["']""", re.I),
]
SKIP_DIRS = {".git", "node_modules", ".next", "docs", "scripts", "__pycache__", ".venv"}
SKIP_SUFFIX = {".md", ".lock"}
for p in ROOT.rglob("*"):
    if not p.is_file():
        continue
    rel = p.relative_to(ROOT)
    if set(rel.parts) & SKIP_DIRS:
        continue
    if p.suffix in SKIP_SUFFIX or p.name in {"package-lock.json"}:
        continue
    if "tests" in rel.parts:  # test fixtures use deterministic fake creds
        continue
    t = read(p)
    for rgx in SECRET_RES:
        m = rgx.search(t)
        if m:
            fails.append(f"{rel}: possible secret matching /{rgx.pattern[:32]}.../")
            break

# 8. VerbLabel allowlist — approved label phrasings only (B58-f1) ----------
# The 5 phrasings below are the ONLY valid label values per the SEBI-educational
# boundary. If someone adds or renames a VerbLabel member, CI fails here.
_VERB_LABEL_APPROVED = {
    "in_form", "on_track", "off_track", "out_of_form", "insufficient_data"
}
_schemas_py = ROOT / "backend" / "dhanradar" / "scoring" / "engine" / "schemas.py"
if _schemas_py.exists():
    _in_verb_label = False
    _found_labels: set[str] = set()
    for _line in read(_schemas_py).splitlines():
        if "class VerbLabel" in _line:
            _in_verb_label = True
            continue
        if _in_verb_label:
            if _line.strip().startswith("class "):
                break  # next class — done
            _m = re.match(r"\s+(\w+)\s*=", _line)
            if _m:
                _found_labels.add(_m.group(1))
    _extra = _found_labels - _VERB_LABEL_APPROVED
    _missing = _VERB_LABEL_APPROVED - _found_labels
    if _extra:
        fails.append(
            f"scoring/engine/schemas.py: VerbLabel has unapproved label(s): {sorted(_extra)} "
            "(non-neg #1 — only approved phrasings allowed)"
        )
    if _missing:
        fails.append(
            f"scoring/engine/schemas.py: VerbLabel is missing expected label(s): {sorted(_missing)}"
        )
else:
    fails.append("scoring/engine/schemas.py not found — VerbLabel allowlist check skipped")

# 9. No-suppress UI guardrail (founder 2026-06-25) --------------------------
# A page/section/table/filter/button must NOT be deleted or hidden when its
# backend data is empty/missing — it must stay mounted and render a "no data"
# empty state. This flags the two dominant suppression signatures in the React
# UI:
#   (a) an emptiness guard that returns null:  if (x.length === 0) return null
#   (b) a whole section/card/table wrapped in a data-presence guard that removes
#       it:  {data && <SomethingSection ...   /   {items.length && <FooTable ...
# Purely cosmetic edits (color/typography/font/alignment/nav/breadcrumb) never
# match these patterns, so the allowed-exception work is never blocked.
# Escape hatch: put `no-suppress-ok: <reason>` in a comment on the same line (or
# the line directly above) for a genuinely-conditional, non-data case.
_NOSUP_RETURN_NULL = re.compile(
    r"if\s*\([^)]*(?:\.length\s*===\s*0|\.length\s*<\s*1|!\s*[\w.]+\.length)[^)]*\)\s*return\s+null",
)
_NOSUP_INLINE_GUARD = re.compile(
    r"\{\s*[\w.?]+\s*&&[^}]*<[A-Z]\w*(?:Section|Card|Table|Panel|Grid|Strip|Hero|Banner)\b",
)
_NOSUP_OK = re.compile(r"no-suppress-ok", re.I)
_UI_DIR = ROOT / "frontend" / "src"
# Pre-existing hits (helpers that return a null VALUE, internal/admin tools, and
# small sub-blocks) are grandfathered in this baseline so the gate enforces the
# rule GOING FORWARD — any NEW suppression fails the build. Triage/clear entries
# over time; never ADD to this file to silence a new customer-facing violation.
_NOSUP_BASELINE_FILE = ROOT / "scripts" / "no_suppress_baseline.txt"
_nosup_baseline: set[str] = set()
if _NOSUP_BASELINE_FILE.exists():
    for _bl in read(_NOSUP_BASELINE_FILE).splitlines():
        _bl = _bl.strip()
        if _bl and not _bl.startswith("#"):
            _nosup_baseline.add(_bl)
if _UI_DIR.exists():
    for p in _UI_DIR.rglob("*.tsx"):
        if p.name.endswith(".test.tsx"):
            continue
        lines = read(p).splitlines()
        rel = p.relative_to(ROOT).as_posix()  # forward slashes — stable across OS/CI
        for i, line in enumerate(lines, 1):
            if _NOSUP_OK.search(line):
                continue
            if i >= 2 and _NOSUP_OK.search(lines[i - 2]):
                continue
            if _NOSUP_RETURN_NULL.search(line) or _NOSUP_INLINE_GUARD.search(line):
                key = f"{rel}|{line.strip()}"  # line-text key — stable when lines move
                if key in _nosup_baseline:
                    continue  # grandfathered pre-existing case
                fails.append(
                    f"{rel}:{i}: UI suppressed on empty data — keep it mounted and render a "
                    "'no data' state (no-suppress rule). Add 'no-suppress-ok: <reason>' if "
                    "intentional, or grandfather it in scripts/no_suppress_baseline.txt."
                )

# Result --------------------------------------------------------------------
if fails:
    print("CI GUARDS FAILED:")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("CI guards passed: no non-negotiable violations or secrets found.")
