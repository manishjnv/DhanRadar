# Gate ledger — b62-f1-chip-tint (PR #102)

**Change:** B62-f1 cosmetic bug fix — `WhatChangedPanel` change-kind chip tint. A 2-digit
hex-alpha suffix on an interpolated CSS `var()` token was an invalid color value (silently
dropped → chips rendered untinted). Fix: `color-mix(in srgb, <token> 13%, transparent)`
background / 33% border. Source-guard vitest added (jsdom drops both broken and fixed values at
render time, so only a source-level guard catches this class). `color-mix` approach credited to
superseded PR #86.

**Classification:** minor (cosmetic CSS bug fix, non-load-bearing) — Builder + Architect, logged.

## Deterministic gates (pre-review)

- vitest `WhatChangedPanel.test.tsx`: **21 passed / 21**. `tsc --noEmit` clean; scoped eslint
  clean; markdownlint clean (incl. drive-by fix of the pre-existing MD004 +-wrap in the RCA
  log). CI is the merge gate.

## Verdicts (independent agents; builder ≠ reviewer)

| Review | Agent | Verdict |
|---|---|---|
| Architect | Sonnet subagent | ACCEPT |

## Findings — disposition

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | NIT | `color-mix` correct vs relative-color syntax (worse Safari 16.x coverage) | informational |
| 2 | NIT | 13%/33% vs 0x22/0x55 = −0.33 pp — visually faithful | informational |
| 3 | MINOR | guard regex covers `${color}` only, not future interpolated tokens | accepted residual — scope-matched to the fix; consistent with `test_scoring_separation.py` precedent |
| 4 | NIT | RCA Fix line range said 116-121, actual 116-119 | fixed in this PR |

**Merge-eligible** once CI is green. Docs-only + cosmetic frontend; deploy via the standard gate.
