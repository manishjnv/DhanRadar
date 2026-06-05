# Review — Phase 4: Rating/Scoring Engine v1 (branch `phase4/rating-scoring-engine`)

## Gate ledger

**Tier:** C (scoring/recommendation engine — the IP core) · **Class:** major · **Base:** `main`
(post #10) · **Commits:** `69756e1` (engine) + condition fixes (this turn) · **Date:** 2026-06-06.

| Gate | Required by tier | Verdict | Reviewer |
|---|---|---|---|
| Deterministic (ci_guards + unit pytest + py_compile + markdownlint) | always | PASS (133 unit) | machine |
| Architect | always | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |
| Compliance | tier C | ACCEPT-WITH-CONDITIONS (no BLOCKER) | Opus (independent of builder) |
| Product | tier C | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |

**Final status:** ACCEPT-WITH-CONDITIONS — no merge BLOCKER. The core SEBI invariants are
structurally enforced + test-covered (label≠score, no-numeric-public, risk-profile excluded,
floor→refuse, disclosure/NOT_ADVICE). Cheap conditions fixed in-branch; spec/deploy-level items
tracked (B24–B28). Merge-eligible; NOT deploy/activation-eligible (B6 + B28 + PC4/PC5).

## Conditions fixed this turn

- **[Architect F1/F2] Config completeness** — `EngineConfig.validate()` now also rejects a config
  missing any `Axis` weight or any expected `confidence_weights` key (catches runtime-fatal config
  errors at load, not under traffic).
- **[Compliance/Architect] Engine honors `activated`** — when `activated:false` (current v1), every
  result is tagged `provisional_model` so no downstream consumer mistakes a draft numeric for
  authoritative (B28; ties to B6).
- **[Compliance] `disclaimer_version`** — now carried on `ScoringResult` + `PublicScore` (audit
  linkage groundwork, non-neg #9); the audit-row write stays the caller's job (B26).
- **[Architect F3 / Compliance a] Internal endpoint defense-in-depth** — `/internal/v1/score` now
  requires a fail-closed `X-Internal-Token` (disabled if unset) on top of the network topology
  control; full network/mTLS policy is a deploy gate (B25).
- **[Product #3] Refusal context** — `prior_label` threaded through hysteresis → `ScoringResult`/
  `PublicScore` so a surface can say "previously <x>, now insufficient data".
- **[Product #5] Confidence on sparse inputs** — `factor_agreement` returns NEUTRAL 0.5 (not 1.0)
  for <2 present axes, so a one-axis instrument doesn't get an inflated agreement contribution.
- **[Architect F4] nit** — removed a pointless list comprehension in `composite()`.

## Confirmed sound (reviewers)

Label derived from the rule table only (`derive_label` takes no score; band cross-check is a logged
flag, never an override) — proven by `test_label_not_a_function_of_score`. Public projection carries
NO numeric; numeric confined to the internal result + the now-token-guarded `/internal/v1`. No
`user`/`risk_profile` input. Floor→refuse emits no numeric. Only non-advisory labels. Disclosure +
NOT_ADVICE on every path incl. refusal. Churn>5% fail-closed hold; distribution-collapse hold;
two-person gate enforced at activation. Module isolation (no auth/billing/market_data/ai_gateway
imports). Hysteresis 2-eval state machine correct; eval_seq monotonic; refusals publish immediately.

## Tracked residuals (BLOCKERS) — NOT in this PR

- **B24** label-precedence (manager_change/structural_concern veto vs recency window) — spec/
  architecture-owner decision (methodology change → two-person gate). Implemented as a documented
  fail-safe caution veto.
- **B25** internal numeric endpoint full network/mTLS policy (token guard added) — deploy gate.
- **B26** `ai_recommendation_audit` row write `(label, model_used, disclaimer_version)` at serve
  time — caller/later phase. **B27** canonical signal-name taxonomy for `contributing/contradicting`.
- **B28** full activation pipeline (backtest pass-gates + calibration + two-person) before any
  numeric is authoritative — ties to B6; `provisional_model` tag added now.
- MINORs: band-edge ±2 smoothing buffer (v1.1); `valid_for_seconds` should be set low/0 on the
  on-demand CAS path; high-confidence guard counts `contributing` strings (documented).
