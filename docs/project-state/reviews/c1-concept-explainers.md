# Review — c1-concept-explainers

## Gate ledger

**Tier:** A (+ inline Compliance — public advice-adjacent educational content) · **Class:** feature ·
**Scope:** C1 Concept-Explainer "Learn" library (GROWTH_BACKLOG Tier 1) — `concepts` schema
(migration 0017) + `dhanradar/concepts/` module + crawlable `/learn/concepts` SSR pages ·
**Diff:** PR #85 (`4295a51` backend, `c47f153` frontend, `d2ba570` docs) → squash-merged
`4e121e4` · **Date:** 2026-06-11.

| Gate | Required | Verdict | Reviewer/tier |
|---|---|---|---|
| Deterministic (ci_guards + pytest + tsc/eslint/vitest + migrations CI) | always | PASS | machine |
| Builder | always | done (Fable 5 builder session) | builder |
| Architect / lane | always | ACCEPT (post-rebase) | Sonnet (independent) |
| Compliance (inline — advice-adjacent public copy) | this change | **ACCEPT** | Opus (independent) |

## Compliance review (Opus, independent of builder) — ACCEPT

Per-rule results (full evidence in the review output, 2026-06-11):

1. No advice / no advisory framing — **PASS** (zero second-person framing; asset-allocation body
   explicitly defers personal suitability to SEBI-registered advisers).
2. No guarantees/projections; figures are labelled dated hypotheticals — **PASS** (`_ILLUS` label
   on every ₹ body; unit-test enforced).
3. No numeric score surface — **PASS** (N/A surface confirmed absent).
4. Disclosure + not-advice + disclaimer version on every response/page — **PASS**
   (`_Disclosed` mixin; `DisclosureBundle` on both pages; `DISCLAIMER_VERSION 2026-06-06.v1`;
   test-enforced FE + integration).
5. No advisory verbs as labels/enums/keys — **PASS** (ci_guards Guard #4 exit 0).
6. No "better option" nudges; direct-vs-regular descriptive; SIP no-assured-profit caveat —
   **PASS** (comparatives explicitly neutralised in copy).

NITs (non-blocking, left as-is by reviewer recommendation): "Consider two hypothetical funds…"
(volatility — rhetorical illustration-opener) and "best understood as a discipline mechanism"
(SIP — explanatory idiom, adjacent copy refuses to rank SIP vs lump-sum).

Earlier independent Sonnet pass (same session): copy/disclosures/figures CLEAN; its lane findings
were a two-dot-diff artifact vs advanced main, resolved by rebase (see
`three-dot merge-base diffs` rule).

## CI (PR #85)

backend PASS · frontend PASS · guards PASS · migrations PASS (0017 applied + downgraded cleanly) ·
lint advisory-red (pre-existing repo-wide; zero findings in C1 files).

## Deploy (2026-06-11, explicit human approval in-session)

KVM4 synced to `4e121e4` → `scripts/deploy.sh deploy` (build, pre-serve `alembic upgrade head`,
full stack up, smoke 200) → `python -m dhanradar.concepts.seed` (8 rows) → verified live:
`alembic current = 0017 (head)`; `GET /api/v1/learn/concepts` returns all 8 slugs + disclosure
bundle (`2026-06-06.v1`); detail 200 / bad slug RFC7807 404; SSR `/learn/concepts` +
`/learn/concepts/compounding` render with the not-advice line. All 9 services healthy.

**Final status:** ACCEPT — merged `4e121e4`, deployed and verified live on KVM4 2026-06-11.
