# Review — stage2-steps2-4-frontend (post-merge)

## Gate ledger

**Tier:** A (frontend foundation: tokens, scaffold, components) · **Class:** major ·
**Scope:** Step 2 (token pipeline), Step 3 (`src/` scaffold + deps + client gen), Step 4
(retokenized Button/Card/ScoreRing) · **Diff:** merged in `9c0cf39` (PR #2) — reviewed post-merge ·
**Date:** 2026-06-05.

| Gate | Required by tier | Verdict | Reviewer/tier |
|---|---|---|---|
| Deterministic (CI guards + frontend build job) | always | PASS | machine |
| Architect | always | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |
| UI | tier A | ACCEPT-WITH-CONDITIONS → **BLOCKER fixed** | Sonnet (independent) |

**Final status:** ACCEPT-WITH-CONDITIONS — the UI BLOCKER was **fixed this session**; remaining
conditions tracked (B10).

## UI (independent) — found + fixed a real compliance BLOCKER

- [BLOCKER→**FIXED**] `frontend/styles/tokens.json` carried a `signal` block with advisory verbs
  (`strongBuy/buy/hold/avoid`) + score-band cutoffs, and an `amber.role: "Warning, hold"` comment.
  This violated non-negotiable #1 (advisory vocabulary anywhere) and tied labels to numeric bands
  (vs FINAL_SCORING_SPEC §4.2 rule-table derivation). **Fix:** removed the `signal` block; changed
  the amber role to "Warning / attention state"; re-ran `gen:tokens`; verified zero advisory verbs
  remain in tokens/generated files. RCA logged (`docs/rca/README.md` 2026-06-05).
- **PASS (compliance seam):** `ScoreRing` takes only `label`/`confidenceBand` props — no numeric
  score prop; renders the band word, not a percentage (no-numeric-in-DOM honoured). The advisory
  verbs in ScoreRing are a *guardrail comment* ("NEVER: …banned"), not usage.
- **PASS (tokens):** single-source pipeline (`tokens.json` → `tokens.css` + `tailwind.tokens.cjs`
  via `gen-tokens.mjs`); brand keys `royal`/`ink-secondary`; Geist fonts; no Manrope/Inter/cool
  hexes anywhere in the tree.
- [MAJOR→track] ScoreRing aria split model (`aria-hidden` SVG + `<figure aria-label>`) — tighten
  for AT. [MINOR] `bg-elev` not exposed in the Tailwind preset; `<figure>` without `<figcaption>`.
  → BLOCKERS B10.

## Architect (independent)

ACCEPT-WITH-CONDITIONS. PASS: feature-slice structure, `apiClient` cookie auth
(`credentials:'include'`, base `/api/v1`, no Authorization header), `gen:api` → Step-1
`openapi.yaml`, generated `src/types/api.ts` enums match (5-label `Label`, band-only
`ConfidenceBand`, `Score`/`ScorePublic` gating), approved dependency set, single-source token
pipeline.

- [BLOCKER→track] ESLint `import/no-restricted-paths` is a hand-enumerated N×N matrix that
  **fails open** when a new feature slice is added — must switch to a glob/`eslint-plugin-boundaries`
  rule before Steps add new slices (auth/billing/ai isolation at risk). → BLOCKERS B10.
- [MAJOR→track] `apiClient` `NEXT_PUBLIC_API_URL` can strip the `/api/v1` base path if misset —
  assert the suffix at startup or rename. → BLOCKERS B10.
- [MINOR] `tailwind.config.js` dead `./app/**` content glob (source is under `src/`).

## Orchestrator note

The token BLOCKER is exactly what the deterministic guard should have caught — `ci_guards.py`'s
advisory-verb regex (`strong_buy|caution`, snake_case) missed the camelCase/spaced verbs. Guard
strengthening tracked (B12) + RCA logged.
