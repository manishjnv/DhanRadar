# Gate ledger — b60-transparency-mount

**Change:** Mount the existing `TransparencyPanel` (B60/PU2, merged #80, Opus compliance gate
ACCEPT) on `/portfolio/[portfolioId]/intelligence`. New `features/transparency/` hook + section
wrapper mirroring the B62-f2 pattern; page mount; test extension; `queryKeys` factory entry.

**Classification:** Tier A (UI / standard feature; non-load-bearing path). Builder + Architect +
UI run inline. Compliance: no new compliance surface — the wrapper renders no copy of its own;
the panel's surfaces passed the Opus compliance gate in PR #80 pre-merge.

## Deterministic gates (pre-review)

- vitest `PortfolioIntelligence.test.tsx`: **31 passed / 31** (re-run by orchestrator after
  conditions, not builder-claimed).
- `tsc --noEmit`: clean. Scoped eslint: clean (repo-wide `boundaries` legacy-selector warning
  pre-existing). CI is the merge gate.

## Verdicts (independent agents; builder ≠ reviewer)

| Review | Agent | Verdict |
|---|---|---|
| Architect | Sonnet subagent | ACCEPT-WITH-CONDITIONS |
| UI | Sonnet subagent | ACCEPT-WITH-CONDITIONS |

## Conditions — all applied before commit

| # | From | Condition | Resolution |
|---|---|---|---|
| 1 | Architect MAJOR | inline query key bypasses `queryKeys` factory | `queryKeys.portfolio.transparency` added (`lib/queryKeys.ts`); hook uses it |
| 2 | UI MAJOR | shell h2 margin 4px (panel's subtitle-tight value) cramps skeleton/error states | shell heading margin → 16px, mirroring the WhatChanged shell; comment documents the deliberate divergence |
| 3 | Architect NIT (taken) | error-state tests missing the h2-invariant assertion | assertion added to BOTH the TransparencySection and WhatChangedSection error cases |

## Accepted residuals (logged, not fixed)

- No `refusal != null` case at section level — covered by `TransparencyPanel.test.tsx` unit
  suite (PU2 path); section suite mirrors the reference pattern's scope.
- `text-status-error` class has no token registration repo-wide (pre-existing in all four
  section wrappers) — token-system fix tracked separately, not this PR.
- `isLoading` not destructured: loading and idle states share the same shell (harmless at this
  route; `enabled: !!portfolioId`).
- Skeleton container lacks `aria-busy` (same omission in the reference pattern).

**Merge-eligible** once CI is green (CI is the gate, not local runs). Deploy-eligible only via
the standard deploy gate (separate human approval).
