# Review — Phase 3: Market Data Adapter + AI/LLM Gateway (branch `phase3/market-data-ai-gateway`)

## Gate ledger

**Tier:** B (AI/LLM Gateway = load-bearing / AI-classifier / compliance) + A (Market Data Adapter,
infra) · **Class:** major · **Base:** `main` (post #9) · **Commits:** `917e5ef` (Market Data §B4),
`3cd2fef` (AI Gateway §B3), plus condition fixes (this turn) · **Date:** 2026-06-06.

| Gate | Required by tier | Verdict | Reviewer |
|---|---|---|---|
| Deterministic (ci_guards + unit pytest + py_compile) | always | PASS (112 unit) | machine |
| Architect | always | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |
| Security (adversarial) | tier B | REVISE → conditions fixed | Sonnet (independent; codex:rescue substitute, fallback ladder) |
| Compliance | tier B | ACCEPT-WITH-CONDITIONS (1 BLOCKER → fixed) | Opus (independent of builder) |

**Final status:** ACCEPT-WITH-CONDITIONS — the two consensus BLOCKERs + the cheap MAJORs were fixed
this turn; the heavier items are tracked (B18–B23). Merge-eligible after the fixes; NOT deploy-eligible
(PC4/PC5 + the B20 cross-border deploy gate).

## BLOCKERs — fixed this turn

- **[Security + Compliance] Advisory reject-list under-inclusive** (`ai_gateway/quality.py`). The core
  set (buy/sell/hold/switch/avoid/caution/strong*) let the most common Indian-market advisory verbs
  through. **Fix:** expanded to add `accumulate`, `book profit(s)`, `book gain(s)`, `take profit(s)`,
  `square off`, `go long`, `overweight`, `underweight`, `top pick`, `buy the dip`; per-term regression
  tests added. Deliberately EXCLUDED ultra-broad/neutral words (`invest`, `add`, `enter`, `reduce`,
  `trim`, `exit` [`exit load` is a core MF term], `redeem`/`subscribe`, `outperform`/`underperform`)
  to avoid wrecking descriptive output — documented in-code; full taxonomy + domain sign-off tracked
  (B23). `switch` added to the static `ci_guards.py` net (it lacked it); the "twin" over-claim softened.
- **[Security] High-stakes unbounded premium loop + free counter never debits** (`ai_gateway/gateway.py`).
  **Fix:** (a) the free counter now debits **every served call** (valid or not), closing the
  under-count vector; (b) the high-stakes Sonnet-spillover path is now bounded by the SAME
  3-strike-per-(ticker,day) skip, so a persistently-bad ticker cannot loop premium spend.

## MAJORs — fixed this turn

- **[Architect] Non-atomic budget key init** → `set(key, 0, exat=midnight, nx=True)` (one round-trip;
  closes the no-TTL crash window) (`budget.py`).
- **[Security] Premium soft cap never observed** → `logger.warning` when premium spend crosses $0.50
  (`budget.py`).
- **[Security] `model_copy` could strip the SEBI disclaimer** → `AIOutputBase.model_copy` overridden to
  re-force the disclaimer (`schemas.py`).
- **[Security] Empty `choices` → unhandled IndexError** → treated as a malformed response (quality
  failure), not a 500 (`gateway.py`).
- **[Architect] All-circuit-open ladder raised with empty diagnostics** → `AllProvidersFailedError`
  now carries `skipped` (open-circuit) providers (`market_data/exceptions.py`, `adapter.py`).
- **[Architect] missing test** → added `AllFreeModelsFailedError` (all-429) test.

## Confirmed sound (reviewers)

402 vs 429 separation (CreditExhaustedError never retried, both free + spillover paths); disclaimer
non-strippable via `object.__setattr__` + `model_validate`; `_iter_text` traverses all nested str
fields; premium debited even when Sonnet output later fails validation; circuit-breaker state machine;
module isolation (no auth/billing/scoring imports); no hardcoded `:free`; no raw prompt/secret logging;
band/numeric separation clean; evidence floor (≥2; >0.7⇒≥3) matches §B3/§S.

## Tracked residuals (BLOCKERS) — NOT in this PR

- **B18** premium hard-cap TOCTOU race (atomic Redis needed). **B19** in-process circuit breaker
  (distributed before scale). **B20** cross-border + `RequireConsent` at the AI call site (DPDP deploy
  gate — consuming-module PRs, Compliance-verified). **B21** `ai_recommendation_audit` write + return
  `model_used`. **B22** `confidence<0.30 → refuse` enforced upstream. **B23** advisory taxonomy →
  versioned, domain-expert-signed asset kept in sync with ci_guards. Plus MINOR: `DataRequest.params`
  is a mutable dict under `frozen=True` (document/`Mapping`), stub providers pending vendor keys/AA partner.
