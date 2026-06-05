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
            if p.is_file() and p.suffix in CODE_EXT:
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

# 4. Advisory verbs as usage (exclude scoring config + rejection comments) ---
ADV = re.compile(r"\b(strong_buy|caution)\b")
for p in code_files():
    if "scoring" in p.parts:  # ranking_configs lists the rejected verbs
        continue
    for i, line in enumerate(read(p).splitlines(), 1):
        if ADV.search(line) and not re.search(
            r"reject|never|banned|not |advisory|forbid|no buy", line, re.I
        ):
            fails.append(f"{p}:{i}: advisory verb usage (non-neg #2: educational labels only)")

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

# Result --------------------------------------------------------------------
if fails:
    print("CI GUARDS FAILED:")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("CI guards passed: no non-negotiable violations or secrets found.")
