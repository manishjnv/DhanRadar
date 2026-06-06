# DhanRadar — Repository Alignment Report

> **Resolved 2026-06-06:** the UI-package token conflict described below is closed. The Manrope/cool `design-system/`, `tokens/`, `reference-impl/`, and the `brand/` token mirror were deleted; canonical UI lives in `frontend/`, reference material in `docs/ui-system/` (see `docs/ui-system/README.md`).

**Date:** 2026-06-05
**Author:** Architecture review (read-only; no code changed)
**Scope reviewed:**
`docs/DhanRadar_Architecture_Final.md`, `docs/DhanRadar_Implementation_Plan.md`,
`backend/`, `frontend/`, `infra/`, `docker-compose.yml` (+`override`), and the
`docs/ui-system/` design+implementation package (contracts, design-system,
nextjs-blueprint, reference-impl, brand, tokens).

---

## 0. Executive summary

There are **three sources of truth in tension**, not two:

1. **Architecture of record** — `docs/DhanRadar_Architecture_Final.md` + `docs/DhanRadar_Implementation_Plan.md`. Self-declared "canonical architecture of record." The existing code was built to these.
2. **Existing implementation** — `backend/` (FastAPI `dhanradar` package, Phase-1/Phase-2 Auth slice), `frontend/` (Next.js skeleton), `infra/` + `docker-compose.yml` (8-container, cloudflared-only, KVM4 shared-infra).
3. **UI package** — `docs/ui-system/`, an independently produced complete design + contract kit with its **own** OpenAPI spec, SQL schema, stack assumptions, and design tokens.

Key finding: **the existing repo faithfully implements (1). The UI package (3) conflicts with BOTH (1) and (2)** on compliance framing, stack, auth transport, API base path, data model, and design tokens. The UI package is also **internally inconsistent** (its own `brand/` contradicts its own `design-system/`).

Most conflicts resolve in favour of the architecture-of-record + existing code. The UI package contributes real value that should be **harvested, not adopted wholesale**: RFC7807 errors, richer auth tables (sessions/otp/roles/audit), the screen/component/figma layer, and the Next.js feature-slice structure.

**One conflict is a hard blocker and must be resolved before any UI build:** the UI package's advisory `Signal` enum (`strong_buy / buy / hold / caution / avoid`) and DOM-exposed numeric score/fair-value **violate the architecture's non-negotiable SEBI educational boundary**, which is a legal constraint, not a style choice.

Legend for each conflict block:
- **Existing** — what the repo / architecture-of-record does today.
- **UI package** — what `docs/ui-system/` expects.
- **Source of truth** — recommended winner.
- **Resolution** — what to change (proposed; nothing done yet).

---

## 1. Architecture conflicts

### A1 — Product framing: educational vs advisory (HARD BLOCKER, legal)
- **Existing:** Architecture §A1/§A2/§B8 — DhanRadar is an **educational** platform. "No buy/sell/hold advice." Output vocabulary is *signal / probability / trend / risk / momentum*. Enforced in code (serializer disclaimer injection, schema rejection of advisory `recommendation_type`). The scoring engine's verb labels are **In-form / On-track / Off-track / Out-of-form** (§S2.2).
- **UI package:** `contracts/openapi.yaml` defines `Signal: strong_buy, buy, hold, caution, avoid`; `Score.signal` and `/recommendations?signal=` use it; the design language is "investment research / recommendations."
- **Source of truth:** **Architecture-of-record.** The educational boundary is a SEBI/regulatory constraint, not a preference.
- **Resolution:** Re-map the UI package's `Signal` enum to the non-advisory label set (In-form/On-track/Off-track/Out-of-form, or 🟢🟡🟠🔴). Rename "Recommendations" surfaces to "Signals/Picks (educational)." Treat every UI screen that says buy/sell as requiring relabel before build.

### A2 — Score/confidence exposure to the client
- **Existing:** Architecture §B1/§S3 — UI shows **verb label + one confidence word only**; "numeric score and factor weights are *not* in the DOM." Confidence is band-only "until calibrated."
- **UI package:** `Score` model returns `score (0–100)`, `factors {valuation,growth,quality,momentum,risk}`, `fair_value`, and integer `confidence` directly to the browser; screens render the numeric score ring (`reference-impl/components/charts/ScoreRing.tsx`).
- **Source of truth:** **Architecture-of-record** for the public/anonymous surface; this is part of the IP-protection + trust model.
- **Resolution:** Server must gate numeric internals. Public payloads: label + confidence band. Numeric score/factors/fair-value behind tier gate (and per §S, factor *weights* never shipped). Adapt `ScoreRing` to render a band, not a raw number, on ungated views.

### A3 — Factor taxonomy
- **Existing:** Architecture §S2 stock score axes = **Quality · Valuation · Momentum · Risk · Trend**.
- **UI package:** `Score.factors` = valuation, growth, quality, momentum, risk (**"growth" instead of "trend"**).
- **Source of truth:** **Architecture-of-record** (the engine computes these axes).
- **Resolution:** Align the `factors` object keys to the engine's actual axes before the score contract is frozen. Decide "growth" vs "trend" deliberately (one-word schema change, but it propagates to engine + UI).

### A4 — Launch surface / phasing
- **Existing:** Architecture §A5 is **MF-first** — the launch wedge is the mutual-fund CAS→60s report; stocks are Phase 2/3.
- **UI package:** Screen set and routes are **stock-centric** (dashboard top-scored stocks, screener, recommendations, fair-value); MF appears only as a generic `funds/{symbol}` detail page; there is no CAS-upload screen.
- **Source of truth:** **Architecture-of-record** for sequencing.
- **Resolution:** Build the UI package screens in architecture phase order (MF detail + CAS upload + 60s report first). Add the missing CAS-upload / job-status / MF-report screens (UI package's `agent.md` explicitly permits creating missing screens in-system).

---

## 2. Naming conflicts

### N1 — Top-level service directories
- **Existing:** `backend/` (FastAPI) and `frontend/` (Next.js). `docker-compose.yml` build contexts are `./backend` and `./frontend`; cloudflared ingress targets `dhanradar-fastapi` / `dhanradar-nextjs`.
- **UI package:** `nextjs-blueprint` + `GETTING_STARTED.md` + `project-config/docker-compose.yml` assume **`api/`** and **`web/`**.
- **Source of truth:** **Existing repo.** The names are wired into compose, the tunnel, and infra-notes.
- **Resolution:** Keep `backend/` + `frontend/`. When porting UI-package docs/configs, rewrite `api/`→`backend/`, `web/`→`frontend/`. Do **not** rename existing dirs.

### N2 — Python package/module name
- **Existing:** package module `dhanradar` (`dhanradar.main:app`, `dhanradar.celery_app`).
- **UI package:** project `dhanradar-api`, module **`app`** (`app.main:app`, `app.workers.celery_app`).
- **Source of truth:** **Existing repo** (`dhanradar`).
- **Resolution:** Ignore the UI package's `app.*` paths; keep `dhanradar.*`. Any UI-package backend snippet must be re-pathed.

### N3 — Frontend internal layout
- **Existing:** `frontend/app/...` at root, `frontend/styles/`, no `src/`. Bare skeleton.
- **UI package:** `src/app`, `src/features/{instrument,portfolio,watchlist,ai,billing,auth,news}`, `src/components`, `src/lib`, `src/hooks`, `src/types`, with ESLint `import/no-restricted-paths` feature isolation.
- **Source of truth:** **UI package** (this is a genuine improvement over the empty skeleton).
- **Resolution:** Adopt the UI package's `src/`-based feature-slice structure *inside* `frontend/`. This is additive (the skeleton has almost nothing to migrate).

### N4 — Tailwind color/token key names
- **Existing:** `frontend/tailwind.config.js` uses `royal`, `ink-secondary` (copied from `brand/`).
- **UI package:** `design-system/` + `reference-impl/` components use `blue`, `ink-2`; `Button.tsx` emits `bg-blue`, `text-bg`, `ink`, `positive`, `ring-blue/40`.
- **Source of truth:** **Decision required** (see D1) — the token key names follow whichever palette wins.
- **Resolution:** The built UI-package components will **not compile** against the existing config (`bg-blue` undefined; existing exposes `royal`). Either retokenize the components to the existing keys or switch the existing config. Blocked on D1.

### N5 — Postgres schema namespacing
- **Existing:** schema-per-concern — `auth.users`, `auth.subscriptions` (migration `0001`, `infra/postgres/init/01_init.sql` creates the `auth` schema). Architecture §B5 mandates "separate schema per concern."
- **UI package:** `contracts/schema.sql` is **flat `public`** (all tables unqualified).
- **Source of truth:** **Existing repo + architecture** (schema-per-concern is an explicit decoupling invariant).
- **Resolution:** When importing UI-package tables, assign each to its module schema (auth/billing/instruments/portfolio/…); do not adopt the flat public layout.

---

## 3. Stack conflicts

### S1 — Search engine: Elasticsearch (dropped) vs Postgres FTS
- **Existing:** Architecture §B5 explicitly **drops Elasticsearch** (v2.3): full-text/typeahead via Postgres `GIN tsvector` + `pg_trgm`. No ES container; KVM4 RAM budget assumes none.
- **UI package:** requires **Elasticsearch 8.14** — a compose service, `screener/stocks` "Elasticsearch-backed," `elasticsearch>=8` dep, `ELASTICSEARCH_URL` env.
- **Source of truth:** **Architecture-of-record** (no ES).
- **Resolution:** Drop ES from the UI package. Re-implement the screener/search on Postgres FTS + `pg_trgm`. Remove the ES dep/env/service. (ES on KVM4 would also break the ~3 GB container budget.)

### S2 — Database image: TimescaleDB vs plain Postgres
- **Existing:** `timescale/timescaledb-ha:pg16` (+`pg_cron`). Architecture needs hypertables (`mf_nav_history`, `etf_price_history`).
- **UI package:** plain `postgres:16`; `schema.sql` marks timescaledb "optional."
- **Source of truth:** **Existing repo + architecture** (TimescaleDB required).
- **Resolution:** Keep `timescale/timescaledb-ha:pg16`. Ignore the UI package's plain-pg compose.

### S3 — Email provider: Resend vs AWS SES
- **Existing:** Implementation Plan §0.1#1 mandates **Resend** (SendGrid retired); `config.py` has `RESEND_API_KEY`; Phase-6 gate verified Resend.
- **UI package:** `.env.example` uses **`SES_REGION`** (AWS SES) + `OTP_SMS_PROVIDER_KEY`.
- **Source of truth:** **Architecture-of-record** (Resend, already verified live).
- **Resolution:** Map SES→Resend in any UI-package config. (OTP-SMS provider is a new, legitimate need — see A-API/data OTP flow; decide a provider separately.)

### S4 — LLM access: governed OpenRouter vs generic LLM endpoint
- **Existing:** Architecture §B3 — `OpenRouterGateway`, free-pool round-robin → Sonnet spillover, `budget_guard()` hard/soft caps; `config.py` has `OPENROUTER_API_KEY`; `budget.py` exists.
- **UI package:** generic `LLM_API_KEY` + `LLM_BASE_URL`; no budget/spillover governance.
- **Source of truth:** **Architecture-of-record** (the budget governor is a cost-survival constraint).
- **Resolution:** Keep OpenRouter + budget governor. The UI package's AI screens consume the governed gateway; generic LLM env vars are insufficient and should be replaced.

### S5 — Frontend dependency baseline
- **Existing:** `frontend/package.json` = `next` + `react` + `react-dom` only (skeleton).
- **UI package:** TanStack Query 5, Zustand 4, React Hook Form 7, Zod, Radix UI, CVA, tailwind-merge, sonner, next-pwa, openapi-typescript, vitest, playwright, msw, eslint-jsx-a11y.
- **Source of truth:** **UI package** (the skeleton is intentionally empty).
- **Resolution:** Adopt the UI package's dependency set when the frontend build starts. This is a gap-fill, not a true conflict. (Note: the UI package uses Radix directly, not shadcn npm — consistent with architecture §B1 "shadcn vendored, not npm-linked.")

---

## 4. API conflicts

### P1 — Base path: `/api/v1` vs `/v1` (routing-breaking)
- **Existing:** FastAPI mounts everything under **`/api/v1`** (`main.py`). cloudflared ingress routes **`^/api/.*`** to FastAPI; anything else goes to Next.js.
- **UI package:** OpenAPI server `https://api.dhanradar.com/v1`, base **`/v1`**; frontend `NEXT_PUBLIC_API_URL=…/v1`; generated client calls `/v1/...`.
- **Source of truth:** **Existing repo** (`/api/v1` — the tunnel won't even route bare `/v1`).
- **Resolution:** Rewrite the OpenAPI `servers`/paths to `/api/v1` before running `gen:api`, OR set the generated client base to `/api/v1`. Critical to fix before the frontend talks to the backend.

### P2 — Auth transport: HttpOnly cookies vs Bearer header (security-adjacent)
- **Existing:** RS256 JWT in **`__Host-access` / `__Host-refresh` HttpOnly cookies**; JS never reads the token; refresh = cookie rotation + reuse detection (`auth/router.py`, `auth/security.py`).
- **UI package:** OpenAPI `bearerAuth` (HTTP `Authorization: Bearer`), `/auth/token/refresh` with a `TokenRefreshRequest` **body**.
- **Source of truth:** **Existing repo** (cookie model is implemented and security-reviewed; HttpOnly cookies are the stronger XSS posture).
- **Resolution:** Update the OpenAPI security scheme to cookie auth; drop the bearer/refresh-body shape. The frontend api-client must send `credentials: 'include'`, not an Authorization header. **This change touches auth → requires the adversarial sign-off gate before any related code lands.**

### P3 — Signup flow: password-immediate vs OTP-first
- **Existing:** `/api/v1/auth/signup` (password) returns cookies immediately + 201; 2FA is optional TOTP (`/auth/totp/*`).
- **UI package:** `/auth/signup` → **202 "OTP sent"**, then `/auth/otp/verify` → tokens; `otp_codes` table; `OTP_SMS_PROVIDER_KEY`.
- **Source of truth:** **Decision required** (see D2). Existing is the implemented flow; OTP-first is a product choice with a cost (SMS provider).
- **Resolution:** If OTP-first is wanted, it's an *additive* phase on top of existing auth (the `otp_codes` table from the UI package is reusable). If not, drop the OTP screens. Either way, keep existing cookie issuance. Security-adjacent → gated.

### P4 — Billing vs subscriptions naming + webhook path
- **Existing:** `/api/v1/subscriptions/webhook` (Razorpay, signature-verified before JSON parse, event dedup).
- **UI package:** `/v1/billing/*` (`/billing/plans`, `/billing/checkout`, `/billing/webhook`).
- **Source of truth:** **Mixed** — keep the existing webhook implementation; adopt the UI package's richer `billing/*` surface (plans/checkout) as new endpoints.
- **Resolution:** Standardise on one prefix (recommend `billing/` for the public surface, keep the existing webhook handler logic, mounted at the chosen path). Don't duplicate webhook receivers.

### P5 — Error format: FastAPI default vs RFC7807
- **Existing:** `HTTPException(detail="code_string")` → `{"detail":"invalid_credentials"}`. Not RFC7807.
- **UI package:** RFC7807 Problem+JSON (`type, title, status, detail, request_id`) + a full error catalog and React-Query mapping.
- **Source of truth:** **UI package** (RFC7807 is a real improvement; adopt it).
- **Resolution:** Add a global exception handler that renders RFC7807 and a stable `type` taxonomy + `request_id`. Migrate existing `detail` codes into the catalog. This is the main place the UI package should win on the API side.

### P6 — Tier-gate status code (AGREEMENT — record it)
- **Existing:** 402 on gated route (architecture §B2).
- **UI package:** `402 upgrade_required` (contextual paywall, not an error).
- **Source of truth:** Both agree. No change. Keep 402; adopt the UI package's "paywall, not error card" UX treatment.

---

## 5. Data model conflicts

### D-DM1 — Authorization model: tier enum vs roles + plans tables
- **Existing:** single `auth.users.tier` enum (`anonymous/free/pro/pro_plus/founder_lifetime`); subscription-derived; DPDP fields (`dpdp_consent_version`, `dpdp_consents JSONB`, `deletion_requested_at`) + TOTP (`totp_secret`, `totp_verified`) on the user row. Matches architecture Global §2 exactly.
- **UI package:** `roles` + `user_roles` (`user/admin/ml_ops/support`) + `plans` + `subscriptions.plan_id` FK + `usage_counters`; user row has `phone`, `full_name`, `status`, `email_verified` but **no** DPDP/TOTP fields.
- **Source of truth:** **Existing + architecture** for the tier enum and the DPDP/TOTP fields (those are compliance-mandated). **UI package** for the additive concepts (admin RBAC roles, `plans` catalog, `usage_counters` for quotas).
- **Resolution:** Keep `users.tier` + DPDP/TOTP. **Merge in** UI-package tables that fill real gaps: `roles`/`user_roles` (for admin/ml_ops surfaces — architecture Global §9), `plans`, `usage_counters` (quota metering for AI limits). Add `phone`/`full_name`/`status`/`email_verified` to `users` only if the OTP/profile product decision (D2) needs them.

### D-DM2 — Column naming drift on shared tables
- **Existing:** `users.hashed_password`; `subscriptions.razorpay_subscription_id`, `subscriptions.plan` (TEXT).
- **UI package:** `users.password_hash`; `subscriptions.gateway_sub_id`, `subscriptions.plan_id` (FK).
- **Source of truth:** **Existing repo** (already migrated + in code).
- **Resolution:** Keep existing column names. If a `plans` catalog is adopted (D-DM1), evolve `subscriptions.plan` TEXT → `plan_id` FK via a migration — but that's a deliberate schema change, not a rename to match the UI package.

### D-DM3 — Instrument modeling: unified table vs module-isolated tables
- **Existing/architecture:** per-module tables (`mf_funds`, `etf_metadata`, `stocks`), each in its own schema; **no shared mutable tables across modules** (decoupling invariant §B5). Time-series in TimescaleDB hypertables (`mf_nav_history`, `etf_price_history`).
- **UI package:** one unified `instruments` table (`type` enum stock/fund/etf) + `instrument_prices` + a single flat `scores` table.
- **Source of truth:** **Architecture-of-record** (module isolation is a core invariant; a shared `instruments` table is exactly the anti-pattern it forbids).
- **Resolution:** Keep module-isolated tables. The UI package's unified `instruments`/`scores` can serve as the *read-model/contract shape* the API returns (a serializer view over module tables), but not the physical schema.

### D-DM4 — Score storage shape
- **Existing/architecture §S:** engine output `{unified_score, confidence_band, verb_label, valid_until, eval_seq}` + per-type tables (`stock_picks`, `user_fund_scores`) with hysteresis/eval_seq governance.
- **UI package:** flat `scores(instrument_id, as_of, model_version, score, signal, factors, fair_value, confidence)` with the advisory `signal` enum.
- **Source of truth:** **Architecture-of-record.**
- **Resolution:** Use the engine's governed tables. Map them to the UI package's `Score` response shape at the serializer (relabeling `signal`, gating numerics per A1/A2).

### D-DM5 — Genuinely useful UI-package tables to harvest (not conflicts)
- `sessions` (jti, revoked_at) — formalises refresh-token revocation the existing code does in Redis only.
- `otp_codes` — needed if D2 chooses OTP.
- `audit_log` (hash-chained `prev_hash`/`hash`) — complements architecture's `ai_recommendation_audit`; the chaining is a nice tamper-evidence add.
- `watchlists`/`watchlist_items`, `alert_rules`/`alert_events`, `ai_conversations`/`ai_messages`, `corporate_actions`, `ingest_runs` — align with architecture modules; adopt (schema-qualified) when those modules are built.
- **Resolution:** Treat as additive, schema-qualified, built per architecture phase. No conflict.

---

## 6. Infrastructure conflicts

### I1 — Compose topology + exposure model
- **Existing:** 8 internal containers, **no host port bindings**, cloudflared tunnel as sole ingress; local testing via `docker-compose.override.yml` (publishes ports, `COOKIE_SECURE=False`). Targets KVM4 shared-infra; reuses `shared_prometheus`/`shared_grafana`.
- **UI package:** 6-service compose with **published host ports** (5432/6379/9200/8000/3000), no tunnel, includes Elasticsearch, generic greenfield host.
- **Source of truth:** **Existing repo** (the KVM4 model + tunnel are load-bearing and security-relevant).
- **Resolution:** Keep the existing compose + override. Mine the UI package's compose only for service-config ideas; do not adopt its port-publishing or ES service.

### I2 — CI/CD
- **Existing:** none yet (no workflow in repo).
- **UI package:** `project-config/github-actions-ci.yml`.
- **Source of truth:** **UI package** (gap-fill).
- **Resolution:** Adapt the UI package's CI workflow to the `backend/`+`frontend/` layout, `dhanradar` package, ruff/mypy/pytest + vitest/playwright. Additive.

### I3 — Observability stack
- **Existing/architecture:** reuse shared `shared_prometheus` + `shared_grafana` on KVM4; Sentry DSN.
- **UI package:** `opentelemetry-sdk` in pyproject; `/observability` docs assume own dashboards.
- **Source of truth:** **Architecture-of-record** (reuse shared Prom/Grafana).
- **Resolution:** OpenTelemetry instrumentation is fine to add, but export to the reused Prometheus; don't stand up a parallel stack on KVM4.

---

## 7. Design-system conflicts

### G0 — The UI package contradicts itself (root cause)
- `docs/ui-system/brand/` = **Geist Sans/Mono + Instrument Serif**, **warm palette** (`royal #1E5EFF`, `emerald #00B386`, `amber #F5A623`, `red #E5484D`), token key `royal`, `ink-secondary`. README declares branding **"LOCKED."**
- `docs/ui-system/design-system/` + `docs/ui-system/tokens/` + `figma/` + `reference-impl/` = **Manrope/Inter + JetBrains Mono**, **cool palette** (`blue #2563EB`, `emerald #10B981`, `amber #F59E0B`, `red #EF4444`), token key `blue`, `ink-2`.
- Both use the `--dr-*` CSS-var prefix, so they *look* unified but resolve to different fonts/hexes.
- **This is the upstream cause of every design conflict below.**

### G1 — Existing frontend tracks the Geist/warm "brand", components expect Manrope/cool "design-system"
- **Existing:** `frontend/styles/tokens.json`, `frontend/src/styles/tokens.css`, `frontend/tailwind.config.js` are **exact copies of `brand/`** (Geist, warm, `royal`/`ink-secondary`). Architecture/implementation-plan rule #3 + project memory point UI work at the canonical `frontend/` tokens (Geist); the former `docs/brand/` guide now lives at `docs/ui-system/brand/`.
- **UI package:** the buildable components (`reference-impl/components/ui/Button.tsx`, `ScoreRing.tsx`), the Figma handoff, and all `/screens` specs assume **design-system** (Manrope, cool, `blue`/`ink-2`/`positive`). They won't compile or render correctly against the existing config.
- **Source of truth:** **Decision required (D1).** Branding is declared "locked" to Geist/warm AND the repo already adopted it AND memory enforces it — that argues Geist/warm wins. But the entire component/figma/screen layer is authored in Manrope/cool.
- **Resolution (recommended, pending D1):** Pick **brand (Geist + warm) as the single token source of truth**, delete/retire `design-system/` + `tokens/` as duplicates, and **retokenize the UI-package components/screens** to brand keys (`blue→royal` or rename brand's `royal→blue`; `ink-2→ink-secondary`; swap Manrope/Inter→Geist; map cool hexes→warm). Alternatively, if the Manrope/cool direction is actually preferred, formally update `brand/` + the repo tokens to match and re-sign the "locked" branding. **Do not ship both.**

### G2 — Token key + scale divergence
- **Existing/brand:** color key `royal`; text `ink-secondary`; spacing 8 stops (1–16); radius sm4/md8/lg12/xl14/2xl18; shadows sm/md/lg.
- **UI package design-system:** color key `blue` (+50/600/700 shades); text `ink-2`; spacing 13 stops (0–32); radius sm6/…/2xl20; shadows xs/sm/md/lg/xl + ring.
- **Source of truth:** follows D1.
- **Resolution:** Unify on the winner's key names + scales; regenerate `frontend/tailwind.config.js`, `tokens.css`, `tokens.json` from the single source. The component focus-ring `ring-blue/40` requires the color key to expose an opacity-capable value — verify after unifying.

---

## 8. Where the existing repo and UI package already agree (no action)

- Postgres 16, Redis 7, Celery, FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2.
- Next.js 14 + React 18; Radix-based (vendored shadcn, not npm).
- UUID primary keys, snake_case columns, JWT **RS256**.
- Razorpay for payments; **402** for tier upgrade; Idempotency-Key on mutating/payment endpoints.
- `NEXT_PUBLIC_*` env convention; access≈15 min / refresh token TTL.

---

## 9. Decisions required from you (block parts of the resolution)

- **D1 — Design tokens:** Geist + warm (brand, currently in repo + "locked") **vs** Manrope/Inter + cool (the UI package's component/figma layer). One must win; the other gets retokenized. *Recommended: Geist/warm, retokenize the components.*
- **D2 — Signup:** keep password-immediate (implemented) **vs** add OTP-first (UI package; needs an SMS provider + user-table fields). *Recommended: keep existing for MVP; OTP as a later additive phase.*
- **D3 — Adopt RFC7807 errors now or later** (recommended: now — it's cheap and the catalog already exists).
- **D4 — `plans` catalog table** (move `subscriptions.plan` TEXT → `plan_id` FK) now or defer to billing phase.

---

## 10. Conflict index (quick reference)

- A1 product framing (BLOCKER) · A2 score exposure · A3 factor taxonomy · A4 launch phasing
- N1 dirs · N2 py package · N3 frontend layout · N4 tailwind keys · N5 db schema namespacing
- S1 elasticsearch · S2 timescaledb · S3 resend/ses · S4 openrouter/llm · S5 fe deps
- P1 base path (routing-breaking) · P2 cookie/bearer (security) · P3 signup/otp · P4 billing/subscriptions · P5 rfc7807 · P6 402 (agree)
- D-DM1 tier/roles · D-DM2 column names · D-DM3 instrument modeling · D-DM4 score storage · D-DM5 harvest tables
- I1 compose/exposure · I2 ci · I3 observability
- G0 ui-package self-contradiction · G1 brand vs design-system · G2 token keys/scale

**Source-of-truth tally:** Architecture-of-record/existing wins most (A1–A4, N1/N2/N5, S1–S4, P1/P2/P4-impl, D-DM1-3/4, I1/I3). UI package wins where it fills gaps (N3, S5, P5, I2, D-DM5). Genuine forks needing your call: D1 (design), D2 (signup).

---

*End of report. No code modified. Migration strategy proposed separately for approval.*
</content>
</invoke>
