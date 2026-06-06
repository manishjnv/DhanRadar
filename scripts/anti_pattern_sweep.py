#!/usr/bin/env python3
"""
DhanRadar — Implementation-Plan §0.3 anti-pattern sweep (CI guard).

Fails (exit 1) if any §0.3 anti-pattern is reintroduced. Complements
`ci_guards.py` (non-negotiables + secrets); this script enforces the
*build-discipline* guards from the plan so Phase-7-style regressions are caught
in CI, not re-audited by hand each phase.

Scans application code only (`backend/dhanradar/**`, `frontend/src/**`); excludes
this file and `ci_guards.py` (which legitimately NAME these patterns as rejected),
plus generated/vendor dirs. A line that merely *rejects* a pattern in a comment is
skipped via a per-guard skip set.

Guard strength:
  * STRONG  — reliable textual signature, no known false positives.
  * HEURISTIC — narrow signature tuned to the current clean tree; catches the
    obvious reintroduction, may need widening over time.

Guards (Plan §0.3):
  1. `regex=` in a Pydantic Field        (must be `pattern=`)            STRONG
  2. `@app.on_event(`                     (must use lifespan)            STRONG
  3. closure-style `def require_tier/consent(` (must be a class)         HEURISTIC
  4. hardcoded `vendor/model:free` id     (must be env + verify-on-start) STRONG
  5. `sendgrid` import / "SendGrid"       (must be Resend)               STRONG
  6. OpenRouter 402 conflated with retry  (402 = balance, not rate-limit) HEURISTIC
  7. cross-module raw `INSERT INTO`       (must go via interface/event)   HEURISTIC
  8. Celery `beat_schedule` without `conf.timezone`                       STRONG
  9. `boto3.client("s3", ...)` without `region_name="auto"` (R2)          STRONG
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE_DIRS = [ROOT / "backend" / "dhanradar", ROOT / "frontend" / "src"]
CODE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".cjs", ".mjs"}
SKIP_DIRS = {"node_modules", ".next", "__pycache__", ".git", ".venv"}
# Files that legitimately reference the patterns (the guards themselves).
SKIP_FILES = {"anti_pattern_sweep.py", "ci_guards.py"}

fails: list[str] = []


def code_files():
    for d in CODE_DIRS:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if not (p.is_file() and p.suffix in CODE_EXT):
                continue
            if set(p.relative_to(ROOT).parts) & SKIP_DIRS:
                continue
            if p.name in SKIP_FILES:
                continue
            yield p


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def _scan(guard: str, pattern: re.Pattern, skip: re.Pattern | None = None) -> None:
    for p in code_files():
        for i, line in enumerate(read(p).splitlines(), 1):
            if skip is not None and skip.search(line):
                continue
            if pattern.search(line):
                fails.append(f"{p.relative_to(ROOT)}:{i}: §0.3 {guard}")


# 1. regex= in Pydantic Field (STRONG) — skip lines that also show the fix.
_scan(
    "regex= in Field (use pattern=)",
    re.compile(r"\bregex\s*="),
    re.compile(r"pattern\s*=|#.*regex|NOT regex|deprecat", re.I),
)

# 2. @app.on_event( decorator (STRONG) — the comment form is "@app.on_event)".
_scan(
    "@app.on_event (use lifespan)",
    re.compile(r"@\w+\.on_event\s*\("),
)

# 3. closure-style require_tier/consent factory (HEURISTIC) — the correct form is
#    a class `RequireTier`/`RequireConsent`; the alias is `require_tier = RequireTier`
#    (an assignment, not a def). Anchored at column 0 (module level): the real
#    anti-pattern is a top-level factory function, while the FORBIDDEN docstring
#    EXAMPLE in deps.py is indented, so this does not false-positive on the doc.
_scan(
    "closure-style def require_tier/consent (use a class)",
    re.compile(r"^(?:async\s+)?def\s+require_(?:tier|consent)\s*\("),
)

# 4. hardcoded vendor/model:free id (STRONG) — a quoted "<vendor>/<model>:free".
#    The Redis key "ai:budget:free:today" has no slash, so it does not match.
_scan(
    "hardcoded ':free' model id (set via env + verify-on-startup)",
    re.compile(r"""["'][\w.\-]+/[\w.\-]+:free\b"""),
)

# 5. sendgrid / SendGrid (STRONG) — skip the "NOT SendGrid"/Resend guardrail lines.
_scan(
    "sendgrid (use Resend)",
    re.compile(r"sendgrid", re.I),
    re.compile(r"not\s+sendgrid|resend|instead of", re.I),
)

# 6. 402 conflated with a retry/backoff (HEURISTIC) — 402 is a balance/credit error
#    and must NOT be retried like 429. Skip lines that explicitly say so.
_scan(
    "OpenRouter 402 treated as retryable (402 = balance, alert don't retry)",
    re.compile(r"\b402\b.*(retry|backoff|sleep)|(retry|backoff|sleep).*\b402\b", re.I),
    re.compile(r"never|not\s|distinct|balance|credit|alert|exhaust|429|#", re.I),
)

# 7. cross-module raw INSERT INTO (HEURISTIC) — the ORM never emits raw "INSERT
#    INTO"; a raw cross-schema write is the isolation breach (non-neg #7).
_scan(
    "raw 'INSERT INTO' (cross-module writes must use the interface/event)",
    re.compile(r"INSERT\s+INTO\s", re.I),
)

# 8. Celery beat_schedule without conf.timezone (STRONG) — file-scoped: any file
#    that sets a beat_schedule must also set conf.timezone.
for p in code_files():
    t = read(p)
    if re.search(r"\.conf\.beat_schedule|beat_schedule\s*=", t) and not re.search(
        r"\.conf\.timezone\s*=", t
    ):
        fails.append(f"{p.relative_to(ROOT)}: §0.3 beat_schedule without conf.timezone set")

# 9. boto3.client("s3", ...) without region_name="auto" (STRONG) — file-scoped.
for p in code_files():
    t = read(p)
    if re.search(r"""boto3\.client\(\s*["']s3["']""", t) and 'region_name="auto"' not in t and "region_name='auto'" not in t:
        fails.append(f"{p.relative_to(ROOT)}: §0.3 boto3 s3 client without region_name=\"auto\" (R2)")


if fails:
    print("ANTI-PATTERN SWEEP FAILED (Plan §0.3):")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("Anti-pattern sweep passed: no §0.3 anti-patterns found.")
