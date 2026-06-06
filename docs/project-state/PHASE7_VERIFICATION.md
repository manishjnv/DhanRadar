# DhanRadar — Phase 7 Verification & Hardening report

**Date:** 2026-06-06 · **Branch:** `phase7/verification-hardening` · **Base:** `main` (post #13, `7f2fc5e`)

Phase 7 is a verification gate, not a build phase: it proves the shipped system
(Phases 1–6) against the architecture, sweeps for anti-patterns, audits the launch
constraints, and runs the §5 pre-deploy adversarial gate. Method: five independent
auditor agents (2 Haiku sweeps, 2 Sonnet coverage, 1 Sonnet adversarial), Opus
synthesis + remediation.

**Headline:** the launch-critical path (anon → CAS upload → ≤60s labelled report →
notification delivery) is implemented and correct. Anti-pattern sweep is CLEAN.
The §5 adversarial gate is **ACCEPT-WITH-CONDITIONS** (no BLOCKER). Cheap hardening
landed in-branch; the remaining conditions are pre-existing, tracked deploy gates.

**Important framing:** the architecture describes the FULL platform (≈14 modules).
The build sequence ships it in phases. "Missing" endpoints/events/beat-tasks found
below belong to modules **not yet in the build sequence** (Compliance Audit, Mood
Compass, Alert/Digest, Behavioral Nudge, Gamification, Onboarding, Admin, Stock,
Portfolio, Search). They are catalogued here as future-phase scope, **not Phase-7
defects**. Phase-7 §2 asks whether the interfaces Phases 1–6 were meant to deliver
are delivered — they are.

---

## §1 — Anti-pattern grep sweep (Plan §0.3) — CLEAN (9/9)

All nine §0.3 guards pass with zero real violations (only benign guardrail comments
that *name* a pattern in order to reject it):

1. `regex=` in Pydantic Field → none (uses `pattern=`). 2. `@app.on_event` → none
(lifespan). 3. closure-style parameterized deps → none (`RequireTier`/`RequireConsent`
are `__init__`/`__call__` classes). 4. hardcoded `:free` model id → none (free pool is
env-set, `config.py` `AI_FREE_MODELS`). 5. `sendgrid` → none (Resend only). 6. OpenRouter
402-as-retry → correct (402 → `CreditExhaustedError`, distinct from 429). 7. cross-module
JOIN/INSERT → none (every `.join` is `os.path.join`; FKs to `auth.users` only). 8. Celery
beat without timezone → timezone set (`Asia/Kolkata`, `enable_utc=False`). 9. `boto3.client`
without `region_name="auto"` → the sole R2 client passes it (`storage.py`).

The deterministic `scripts/ci_guards.py` independently enforces a subset (Elasticsearch,
bearer auth, Manrope, advisory verbs, secrets) on every PR/commit.

---

## §2 — Coverage matrix (architecture interface vs shipped)

Per-module, phase-scoped verdict. "Future-phase" = the gap is a module not yet in the
build sequence.

| Module | Phase-scoped verdict | Notes |
|---|---|---|
| Auth & Tiering | COVERED | signup/login/logout/refresh/me/TOTP + tier gate shipped + hardened. Future: JWKS rotation endpoint; the standalone Consent module (grant/revoke/CMP/erasure) — the `RequireConsent` *gate primitive* is shipped + hardened. |
| Billing / Subscriptions | COVERED | webhook (verify-before-parse + dedup + tier flush) + plans + checkout (Idempotency-Key) shipped. Deploy gate: `EXACT_PLAN_TIERS`/`razorpay_plan_id` data-seeding (B2/B7/B8). |
| Mutual Fund | COVERED (Phase-5 scope) | CAS → parse → score → ≤60s report pipeline shipped. Future-phase: 5 of 8 full-contract REST endpoints (fund/nav-history/portfolio/overlap/refresh), the event emissions, and 4 beat tasks belong to the broader MF + data-pipeline build (B29 NAV). |
| Notification | COVERED (Phase-6 scope) | prefs + `/test` + drain + Telegram/Resend + share-card shipped. Future: WhatsApp (Y2); event consumers (upstream Mood/Alert/Nudge not built). Deploy gate: B31 cross-border consent. |
| Rating/Scoring Engine | COVERED + hardened | 5-axis collapse, rule-table label, hysteresis, confidence floor, governance (churn/distribution/two-person), `to_public()` numeric strip, internal token-gated endpoint — all present + invariant-tested. Future: MF/ETF sub-factor catalog (data pipeline), admin batch-approval endpoint + `rating_engine_changelog` table (Admin/Compliance modules). |
| Market Data Adapter | FRAMEWORK COVERED | adapter + circuit breaker + YAML ladders + event contracts shipped; all 8 provider rungs are intentional stubs (B29 + unsigned vendor agreements). Expected. |
| AI/LLM Gateway | COVERED + hardened | OpenRouter round-robin, 429-rotate, 402-distinct, quality+advisory screen, Sonnet spillover, 3-strike skip, budget guard (free 1000/day, premium $0.50 soft / $9.50 hard, crash-safe EXPIREAT). Future: Prometheus/Grafana metric emit (Observability module). |
| Cross-cutting (health, RFC7807, request-id, gates, Celery) | COVERED + hardened | problem+json with reserved-member guard, CRLF-safe request-id (pure ASGI), tier/consent gates, three queues + IST beat. Future beat jobs (audit archive, score recompute, erasure, SIP-streak, signal-health, risk nudge) belong to unbuilt modules. |

**Coupling note:** MF→Scoring currently uses a synchronous public-interface call
(`scoring_bridge.score_fund`) rather than the `scoring.result.published` event bus
(the event *dataclasses* exist; the bus/consumer infra is a later slice). This is
interface coupling (not reaching into internals) and was accepted at Phase 4; the
event-bus migration is a future-phase item, noted not blocking.

---

## §3 — Constraint audit (Plan Phase 7 §4)

| Constraint | Status | Evidence / action |
|---|---|---|
| Secrets only from env / GitHub Secrets | PASS | `config.py` reads every secret from env (pydantic-settings); no hardcoded literal; secret-scan clean. |
| Celery beat timezone + AI budget cap enforced | PASS | `Asia/Kolkata`/`enable_utc=False`; `budget_guard()` raises **before** the external call at the gateway layer; debits only on clean exit; daily reset via atomic `SET NX EXAT`. |
| Container memory ≤ ~3 GB (§A6 budget) | **PASS (fixed this phase)** | was 3572M → trimmed to **exactly 3072M** (postgres 1024 / fastapi 512 / nextjs 448 / batch 256 / mood 192 / misc 192 / redis 256 / beat 64 / cloudflared 128). Well under the box's ~6 GB headroom; limits can rise within headroom if a worker OOMs. |
| DPDP consent on data-processing routes | PARTIAL → tracked | MF `/upload/cas` gated `mf_analytics` (✓). Notification deliver seam ungated cross-border = **B31** (deploy gate). All auth/billing/health routes correctly non-consent-class. |
| `ai_recommendation_audit` partition + write | FAIL → tracked | table/migration does not exist; no writes. `disclaimer_version` is carried on `PublicScore` + stamped into the notification footer, but the audit-row persistence (7-yr, partitioned) is owed = **B26** (the Compliance Audit module). Top deploy blocker. |

**Runtime-only constraints (NOT verifiable locally — deploy-time checks):** live
end-to-end hop proof (needs the deployed stack; no local PG/Redis/casparser, B1),
NIC NTP sync on KVM4, `ai_recommendation_audit` R2 archival working, and the measured
container-memory sum on the box. These move to the deploy checklist (§5).

---

## §4 — Adversarial pre-deploy gate (Plan §5) — ACCEPT-WITH-CONDITIONS

Independent adversarial review of the four security-adjacent surfaces (Auth/Tiering,
Consent/DPDP, Rating-Engine governance, AI path). **No BLOCKER.** Verdict
ACCEPT-WITH-CONDITIONS.

**Fixed in-branch (Phase-7 hardening):**

- **[MAJOR] `RequireConsent` returned 403 to anonymous** — a fragile "caller must add
  auth first" contract + 401-vs-403 oracle. **Fixed:** the gate now raises **401
  not_authenticated** for anonymous as its first operation (safe-by-default), before any
  DB read (`deps.py`). Re-verified by an independent adversarial pass — ACCEPT, no bypass,
  all denial paths otherwise unchanged. Test updated. RCA logged.
- **[MINOR] `UserContext.consented_purposes` was an unused fail-open trap** — documented
  in code that it is intentionally unpopulated and `RequireConsent`'s fresh-DB read is the
  ONLY valid consent decision (`deps.py`).

**Accepted (defensible as-built) or already tracked:**

- **[MAJOR] `/internal/v1/score` serves raw numerics** — by design (its purpose is internal
  tier-gated numeric reads); mounted off the public `^/api/.*` ingress + fail-closed
  `X-Internal-Token` (constant-time). Defense-in-depth on the network boundary is **B25**
  (network/mTLS deploy gate). No redesign.
- **[MAJOR] AI budget check-then-increment race** — concurrent calls can burst past the cap
  by ≤ N-1 (free pool is count-bounded; premium financial exposure bounded to one Sonnet
  burst). Already **B18** (needs Redis Lua/WATCH). Safe under the single-worker beat today.
- **[MINOR] advisory screen misses "recommend"** — deliberately NOT added here: the forced
  AI disclaimer text contains "recommendation", so a naive add would self-flag every AI
  output. Folded into **B23** (versioned, domain-signed advisory taxonomy with the
  disclaimer-interaction check).
- **[MINOR] auth/session hygiene** — login rate-limit TOCTOU; tier cache not flushed at the
  point erasure SETS `deletion_requested_at`; `logout_user` relies on the caller also
  revoking the access jti; `messages` has no `system`-role guard; `INCRBYFLOAT` sub-cent
  drift. Bundled as **B33** (low; none exploitable as-shipped). JWT alg whitelist is correct
  (no alg:none/HS confusion); GETDEL refresh rotation + reuse detection sound; cookies are
  `__Host-` HttpOnly Secure, no bearer fallback.

**Confirmed-sound (no finding):** JWT RS256-only alg whitelist; refresh GETDEL atomicity +
reuse detection; `__Host-` cookie scope; label-derived-from-rule-table (not score);
`to_public()` numeric strip; confidence<0.30→refuse; >5% churn fail-closed hold; risk_profile
excluded from scoring inputs; 402≠429 handling.

---

## §5 — Deploy-gate checklist (merge-eligible ≠ deploy-eligible)

A passing verification is **merge-eligible**. KVM4 deploy additionally needs, per the
project deploy gate + PC4/PC5:

- [ ] **B26** — `ai_recommendation_audit` table (partitioned, 7-yr) + caller writes at the
      MF-report and notification-deliver seams (the Compliance Audit module). **Top blocker.**
- [ ] **B31** — cross-border DPDP consent gate at the notification deliver seam (channels
      token-gated off until wired + Compliance-verified).
- [ ] **B6 / B28** — scoring-engine activation gates (backtest pass-gates + two-person
      methodology gate) before any `ranking_configs` version is activated / any numeric is
      authoritative. Engine ships `activated:false` / `provisional_model`.
- [ ] **B18** — make the AI budget counter atomic before multi-worker scale.
- [ ] **B2 / B7 / B8** — Razorpay plan-id + total_count + EXACT_PLAN_TIERS data-seeding
      before billing charges (code fails safe 503 until then).
- [ ] **Runtime proofs on the deployed stack:** live end-to-end hop trace (anon → CAS →
      report → label change → Telegram alert); NIC NTP synced; `ai_recommendation_audit` R2
      archival working; measured container-memory sum ≤ budget; AI budget force-exhaust →
      402/skip not overspend.
- [ ] Honor the ❌ NEVER-TOUCH list + the 3 cloudflared gotchas (`infra-notes.md`).
- [ ] **Separate explicit human approval** (PC4/PC5); the GitHub `production` env is
      main-branch-gated.

---

## Ledger

Deterministic gates: 212 unit pass (consent test updated), integration collect (63),
ci_guards 0, F-lint 0, markdownlint 0, compose YAML valid + memory sum = 3072M.
Adversarial: §5 gate ACCEPT-WITH-CONDITIONS; the one in-branch security fix re-verified
ACCEPT by an independent pass. New blocker **B33** (auth/session hygiene, low). No new
merge BLOCKER. Not deploy-eligible (checklist above).
