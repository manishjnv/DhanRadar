# Stage 2 — Execution Plan

**Status: APPROVED (rev. 2), 2026-06-05 — PC6 + PC7 cleared; Stage 2 execution authorized. No code is written by this document.**
**Date:** 2026-06-05
**Predecessors:** `REPOSITORY_ALIGNMENT_REPORT.md`, `CANONICAL_OPENAPI_ALIGNMENT.md`, `CANONICAL_DESIGN_SYSTEM_ALIGNMENT.md`, `RECOMMENDATION_ENGINE_ALIGNMENT.md`, `FINAL_SCORING_SPEC.md`, `MIGRATION_STRATEGY_FINAL.md`.
**Authority order (binding):** Architecture docs → Implementation Plan → existing code → docs/features → docs/ui-system → mockups.

**rev. 2 changes (review-applied):** API contract now Step 1 (before frontend scaffold / client generation); REC-D1/D2/D3 + PC4/PC5 marked resolved; `FINAL_SCORING_SPEC.md` added as the engine reference and approval gate for Step 8.

Stage 2 is the first stage that touches code. It is scoped to non-runtime-behavior-changing reconciliation first, then gated, additive build. Every security-adjacent step carries an adversarial sign-off. Nothing deploys to KVM4 without separate explicit approval.

---

## 1. Pre-conditions

| # | Pre-condition | State |
|---|---|---|
| PC1 / REC-D1 | Factor 5th axis = **Trend** (keep 5-axis; Growth nested in Trend) | **RESOLVED** (review) |
| REC-D2 | Confidence internal 0–1, ×100 display, launch band-only | **RESOLVED** (review) |
| REC-D3 | Risk-profile = architecture thresholds + states; UI questionnaire reused | **RESOLVED** (review) |
| PC4 | Stage 2 works on a **feature branch** (not `main`) | **APPROVED** |
| PC5 | No push / no deploy / no KVM4 change without separate approval | **APPROVED (standing)** |
| PC6 | **`FINAL_SCORING_SPEC.md` approved** before Step 8 (ranking_configs staging) | **APPROVED** (cleared by ADR-0019, 2026-06-05) |
| PC7 | This revised plan approved | **APPROVED** (operator, 2026-06-05) |

All pre-conditions are now resolved. **Stage 2 is unblocked**; execution begins at Step 1
(regenerate canonical `openapi.yaml`) on the `stage2/contract-reconciliation` feature branch.
PC4/PC5 still bind: no push/deploy/KVM4 change without separate explicit approval.

---

## 2. Execution sequence (reordered; dependencies noted)

### Step 1 — Regenerate canonical `openapi.yaml`  *(REPLACE spec; no runtime code)*

- Author `openapi.yaml` in-repo from `CANONICAL_OPENAPI_ALIGNMENT.md`: base `/api/v1`, cookie security scheme, RFC7807 components, **4-label non-advisory enum**, gated numerics, idempotency headers, `factors` key set = `quality/valuation/momentum/risk/trend` (now frozen per REC-D1).
- Validate the spec against the existing live endpoints (auth/health/webhook) so generated types match reality.
- **Why first:** the API contract must exist before frontend scaffolding and `gen:api` client generation.
- **Depends on:** PC7. **Routing:** Opus (contract correctness is judgment) + Sonnet for bulk path entry. **Effort:** M (1–1.5 days).
- **Risk:** medium — the spec is the contract; errors propagate. Mitigated by validating against live auth/health/webhook.

### Step 2 — Canonical token freeze + pipeline  *(non-load-bearing; no runtime behavior change)*

- Confirm `frontend/styles/tokens.json` completeness; add additive tokens (extra spacing stops, xs/xl shadow, focus ring) **under brand naming only** (Geist/warm).
- Build a single token-generation step emitting `tokens.json` + `tokens.css` + `tailwind.config.js` from one source (kills drift).
- **Depends on:** PC7. **Routing:** Tier-2/Sonnet mechanical; Opus diff-review. **Effort:** S (0.5 day).
- **Risk:** low. Token typo → visual diff caught in review.

### Step 3 — Frontend scaffold: `src/` structure + dependency set + client gen  *(REPLACE skeleton)*

- Introduce `src/{app,features,components,lib,hooks,types}` inside `frontend/`; add the approved dependency set; wire ESLint import-isolation; add `gen:api` pointed at the **Step 1** `openapi.yaml`; generate the typed client (cookie auth, `credentials: 'include'`, base `/api/v1`).
- **Depends on:** Steps 1–2. **Routing:** Sonnet; Opus review. **Effort:** M (1 day).
- **Risk:** low-medium. Dependency drift; commit lockfile. No backend impact.

### Step 4 — Retokenize core components  *(MERGE; one compliance-relevant change)*

- Port `Button`, `Card`, `ScoreRing` from reference-impl, retokenized to Geist/warm (`blue→royal`, `ink-2→ink-secondary`, fonts→Geist, `ring-royal/40`).
- **ScoreRing:** render **confidence band, not raw numeric score** on ungated views (architecture "no numeric in DOM" + `FINAL_SCORING_SPEC.md` §7).
- **Depends on:** Steps 2–3. **Routing:** parallel Sonnet (one per component); Opus diff-review. **Effort:** M (1 day).
- **Risk:** medium — ScoreRing change is a compliance boundary; verify no numeric leaks to DOM.

### Step 5 — RFC7807 exception handler + request-id middleware  *(MERGE; security-adjacent surface)*

- Add a global problem+json handler + request-id middleware to the FastAPI app; migrate existing `detail` codes into the `type` taxonomy; keep cookie auth and webhook security logic untouched.
- **Depends on:** Step 1 (taxonomy). **Routing:** Sonnet implement; **Opus critique; `codex:rescue` adversarial sign-off before merge** (auth/error surface). **Effort:** M (1 day).
- **Risk:** medium. Adversarial pass on: no stack-trace/PII in `detail`; 401/402/403 semantics unchanged; webhook still 400-on-bad-sig; generic login error preserved (no enumeration).
- **Acceptance:** existing auth/webhook tests green; new tests assert problem+json shape + `request_id` + `X-Request-ID` header.

### Step 6 — `plans` catalog migration (backward-compatible)  *(MERGE; additive schema)*

- New Alembic migration: create `billing.plans`; add nullable `subscriptions.plan_id` FK alongside existing `plan` TEXT (transition). No drop of `plan`.
- **Depends on:** PC4. **Routing:** Sonnet; **Opus review; gated** (subscription/billing data). **Effort:** S-M (0.5–1 day).
- **Risk:** medium — migration on a payment-linked table. Reversible; tested on the override stack; no production run.
- **Acceptance:** `upgrade`/`downgrade` clean on local override stack; existing rows unaffected; webhook still writes `plan` (and `plan_id` when resolvable).

### Step 7 — `billing/*` endpoint shapes + webhook re-mount  *(MERGE; security-adjacent)*

- Add `GET /api/v1/billing/plans`, `POST /api/v1/billing/checkout` (Razorpay order, `Idempotency-Key`); re-mount the existing webhook at `/api/v1/billing/webhook` preserving verify-before-parse + dedup; keep `/subscriptions/webhook` alias one release.
- **Depends on:** Steps 1, 5, 6. **Routing:** Sonnet; **Opus critique; `codex:rescue` sign-off** (payment path). **Effort:** M (1 day).
- **Risk:** medium-high — payments. Idempotency + signature verification identical to the proven handler.
- **Acceptance:** webhook tests pass at both paths; checkout idempotency test; no double-charge path.

### Step 8 — `ranking_configs` v1 (config only, engine NOT built)  *(MERGE; spec→config)*

- Encode `FINAL_SCORING_SPEC.md` §3 v1 weights + normalization + confidence + risk numbers as a **versioned, declarative `ranking_configs` v1 record/file** — data, not engine logic. Seed a `rating_engine_changelog` entry. Mark "unactivated; pending backtest pass-gates + two-person methodology approval."
- **Depends on:** **PC6 (`FINAL_SCORING_SPEC.md` approved)**. **Routing:** Opus (compliance-sensitive). **Effort:** S (0.5 day).
- **Risk:** low (no execution). The engine itself is Implementation-Plan Phase 4.

### Step 9 — CI workflow + grep guards  *(MERGE; infra, non-runtime)*

- Adapt UI-package GitHub Actions to `backend/`+`frontend/`, `dhanradar`: ruff + mypy(strict) + pytest; vitest + playwright + tsc; secrets scan; **grep guards** for non-negotiables (no bearer/Authorization-header auth in new code, no `elasticsearch`, no advisory `strong_buy|buy|hold|avoid` strings in API/enum code, no `/v1/` non-`/api` paths, no Manrope/Inter in canonical tokens).
- **Depends on:** Steps 1–5. **Routing:** Sonnet; Opus review. **Effort:** S-M (0.5–1 day).
- **Risk:** low. CI-only.

---

## 3. Dependency graph (rev. 2)

```
PC7 ─┬─> Step1 (OpenAPI) ─┬─> Step3 (FE scaffold+client) ─> Step4 (components)
     │                    ├─> Step5 (RFC7807, gate) ─┐
     │                    └─> Step9 (CI)             │
     ├─> Step2 (tokens) ──> Step3                    ├─> Step7 (billing, gate)
     └─> Step6 (plans mig, gate) ─────────────────────┘
PC6 ─> Step8 (ranking_configs)
```

Parallel tracks: API/contract {1→5→6→7} and frontend {2→3→4, +9} run concurrently after Step 1. Step 8 is independent once PC6 clears.

## 4. Risk areas (consolidated)

| Risk | Where | Mitigation |
|---|---|---|
| Spec/reality mismatch | Step 1 | validate generated types against live auth/health/webhook before FE consumes |
| Payment regression | Steps 6, 7 | reuse proven webhook logic; codex:rescue; idempotency tests; local-only |
| Auth error-semantics drift | Step 5 | codex:rescue; assert 401/402/403 + no enumeration unchanged |
| Numeric score leaking to DOM | Step 4 | explicit test: ungated payload/DOM has band only |
| Advisory terminology creeping back | all FE/contract | grep guard in CI (Step 9); relabel at source |
| Token drift re-emerging | Step 2 | single generation pipeline; retire competing sets (doc-state) |
| Migration irreversibility | Step 6 | additive nullable FK only; tested up+down; no prod run |

## 5. Estimated effort

- **API/contract track (Steps 1, 5–8):** ~4.5–5.5 days.
- **Frontend track (Steps 2–4, 9):** ~3–3.5 days.
- **Parallelized wall-clock:** ~5–6 working days, one operator + delegated Sonnet bursts.
- Tiering: mechanical retokenization/scaffold → Sonnet; contract + compliance + payment/auth judgment → Opus; adversarial gates → codex:rescue.

## 6. Required approvals

1. **PC7** — this revised plan — before any Stage 2 code. **APPROVED (operator, 2026-06-05).**
2. **PC6** — `FINAL_SCORING_SPEC.md` — before Step 8. **APPROVED (ADR-0019, 2026-06-05).**
3. **codex:rescue sign-off** on Steps 5 and 7 (auth/error + payment) — before those merge.
4. **Separate explicit approval** for any KVM4 deploy or GitHub push (Stage 2 is local feature-branch only).
5. **Two-person methodology gate** before any future activation of `ranking_configs` v1 (Step 8 only stages it).

## 7. Explicit non-goals for Stage 2

- No KVM4 deploy, no production migration, no cloudflared change.
- No scoring-engine implementation (Phase 4 territory; Step 8 only stages config from `FINAL_SCORING_SPEC.md`).
- No OTP activation (D2), no Elasticsearch (non-neg #3), no bearer-token auth (non-neg #4).
- No new domain modules beyond billing shape — MF/Stock/ETF/etc. remain SPEC, built in their architecture phases.

---

**End of Stage 1 deliverables (rev. 2). PC6 + PC7 APPROVED 2026-06-05 — Stage 2 begins at Step 1.**
</content>
