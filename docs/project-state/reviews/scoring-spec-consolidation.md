# Review — scoring-spec-consolidation

## Gate ledger

**Tier:** C (Scoring engine / Recommendation logic) · **Class:** major (sole-source-of-truth
declaration for the scoring spec) · **Diff:** uncommitted on `stage2/contract-reconciliation`,
2026-06-05.

| Gate | Required by tier? | Verdict | Reviewer/tier | Conditions open? |
|---|---|---|---|---|
| Deterministic (markdownlint) | always | PASS (after `--fix`) | machine | no |
| Architect | always | ACCEPT | Sonnet (independent agent) | no |
| Compliance | tier C | ACCEPT-WITH-CONDITIONS → **resolved** | Opus (independent agent) | no (MAJOR fixed) |
| Product | tier C | **N/A-with-reason** | — | n/a — documentation authority block; no behavioral, user-facing, or edge-case surface introduced |

**Final status:** COMPLETE — merge-eligible.
**Human operator sign-off:** approved by operator (this session), 2026-06-05.
**Deploy-eligible?:** n/a — documentation only, no runtime change, no deploy.

## Builder summary

**Builder agent/tier:** Opus (scoring is an Opus-tier path).
**What changed (documentation only):**

- Added `## 0. Authority & scope` to `FINAL_SCORING_SPEC.md` declaring it the **sole source of
  truth** for the rating/scoring engine (factor/weight/confidence/risk/label/threshold/governance
  models), superseding `RECOMMENDATION_ENGINE_ALIGNMENT.md`, `docs/ui-system/recommendation-engine/*`,
  and `docs/ui-system/contracts/score-model.md`; architecture §S kept as the originating authority.
- Added **ADR-0019 — Scoring Engine Authority** to `ARCHITECTURE_DECISIONS.md` (+ index row).
- Added a "superseded by FINAL_SCORING_SPEC.md" pointer to `RECOMMENDATION_ENGINE_ALIGNMENT.md`.
- Marked **scoring governance COMPLETE** in `SESSION_STATE.md` (clears PC6).

**Non-negotiables touched:** #2 (SEBI labels / no-numeric-in-DOM) — framing only, no rule change.
**No FINAL scoring content (factors, weights, confidence, risk, labels, thresholds, governance)
was altered.** Numeric weights remain PROPOSED v1.
**Deterministic gate:** `markdownlint-cli2 --fix` run across all touched docs → clean.
**Deferred → BLOCKERS.md:** B6 (two-person methodology gate) unchanged — non-blocking until
production activation.

## Architect review (Sonnet, independent)

**VERDICT: ACCEPT.** Authority order respected (§0 keeps architecture §S as originating authority;
elaborates, does not override). Conflict rule coherent and asymmetric in the correct direction.
Supersession claims internally consistent; no dangling references. No architectural drift —
"sole source of truth" scoped only to the scoring domain.

- [MINOR] ADR-0019 referenced `contracts/score-model.md` without the `docs/ui-system/` prefix used
  in §0 — **fixed** (path aligned in ADR-0019 body).
- [NIT] `RECOMMENDATION_ENGINE_ALIGNMENT.md:3` still says "for all engineering purposes" vs §0's
  "for ALL purposes" — left as-is (the controlling §0 + ADR-0019 are unambiguous; the line-3 header
  edit was previously declined by the operator).

## Compliance review (Opus, independent)

**VERDICT: ACCEPT-WITH-CONDITIONS → conditions resolved.** Every SEBI non-negotiable preserved:
non-advisory labels intact (advisory verbs appear only as the rejected set); no-numeric-in-DOM
intact; confidence floor + band-only intact; risk-profile exclusion intact (§6.2 hard rule, two
constructs that never mix); §0/ADR subordinate to architecture §S hard rules.

- [MAJOR] Naming — §0 and ADR-0019 called it the "recommendation engine"; "recommendation" is the
  exact term SEBI advisory regulation hinges on and a regulator could cite a leaked internal doc.
  **Fixed:** renamed to "rating/scoring engine" throughout `FINAL_SCORING_SPEC.md` §0 and ADR-0019;
  the legacy term is now scoped to one provenance sentence stating it is **retired** and that
  DhanRadar issues no recommendations. (Fix applied verbatim per the reviewer's prescription;
  re-review waived — the change is the reviewer's own recommended text.)
- [NIT] §0 "ALL purposes" vs line-3 "engineering purposes" — same as the Architect NIT; line-3 edit
  was declined by the operator, §0/ADR control.

**Outcome:** the Compliance MAJOR is closed; no open conditions remain.
