# DhanRadar — Project Operating Overlay (CLAUDE.md)

Project overlay to the global `~/.claude/CLAUDE.md`. **On conflict, this file wins.**
Load this in Phase 0 of every session.

## What DhanRadar is

SEBI-**educational** (never advisory) market-intelligence platform for Indian retail. MF-first
launch wedge (CAS upload → ≤60s labelled report); stocks/ETFs follow. Runs on **KVM4
shared-infra** via a dedicated `dhanradar` cloudflared tunnel, 8 own containers, ~3 GB cap.
Stack: FastAPI (`dhanradar` package) + Next.js (`frontend/`) + TimescaleDB + Redis + Celery.

## Authority order (binding — resolves every source-of-truth conflict)

For architecture / contracts / behaviour:
`DhanRadar_Architecture_Final.md` → `DhanRadar_Implementation_Plan.md` → existing code →
`docs/features/*`.

**For UI / visual design (founder rule 2026-06-19, binding):** `docs/ui-system/` is the **master UI
design and the FIRST source of truth** for every UI change and every new page/screen. The live
`frontend/` pages are the **older build**; bring them UP TO the ui-system master, don't treat them as
the design truth. Open ui-system FIRST for design intent:

- **Page mockups** — `docs/ui-system/brand/mockups/*.jsx` (landing, portfolio, screener, stock, app,
  mobile, charts) + `docs/ui-system/screens/*.md` (dashboard, fund-detail, portfolio, watchlist,
  settings, …). Use or improve the matching mockup to build a similar page.
- **Components / typography / color / buttons** — `docs/ui-system/components/*.md` (Button, Card,
  Input, Table, …) + the brand guide `docs/ui-system/brand/README.md`. Always reference these for
  type scale, font colour, and button variants.

ui-system is **already Geist/warm** (brand guide = Geist Sans + Geist Mono + Instrument Serif; palette
Deep Navy / Royal Blue `#1E5EFF` / Emerald / Cyan / Amber / Red) — it matches the stack lock, so there
is **no font/token conflict** to retokenize. Implement via the live token pipeline as the mechanism
(`frontend/styles/tokens.json` → `scripts/gen-tokens.mjs` → generated `src/styles/tokens.css` +
`tailwind.tokens.cjs`; never hand-edit generated files); if the live tokens drift from the brand
guide, reconcile toward the brand guide. Reuse `frontend/src/components/`.

**What still overrides ui-system (compliance, not design — always win):** the **Non-negotiables**
below, especially (1) the **SEBI advisory boundary** — the brand palette labels Emerald/Amber/Red as
"Buy/Hold/Sell"; **translate those to educational labels, never copy the advisory verbs** (RecommendationCard
likewise) — and (2) **no-numeric-in-DOM** — Chart/ScoreRing show a band, never a raw score.
Also ignore the ui-system **standalone-package build docs** (`docs/ui-system/docs/01–07`,
`contracts/`, `nextjs-blueprint/`, `claude-code/*-spec.md`, bootstrap guides) — they describe a
DIFFERENT stack/auth/API/DB; the real build is `backend/` + `frontend/` per the architecture.

## Read-first each session (Phase 0)

1. `docs/infra-notes.md` — verified facts + ❌ NEVER-TOUCH list + standing rules.
2. This file.
3. The canonical-doc map below, for the area you are touching.
4. `docs/rca/README.md` — before any debugging (known traps live there).
5. `docs/project-state/SESSION_STATE.md` + `BLOCKERS.md` — where we are, what is open.

## Canonical-doc map (which doc is truth for what)

- Architecture / module contracts → `docs/DhanRadar_Architecture_Final.md`
- Phase sequence / Allowed-APIs / anti-patterns → `docs/DhanRadar_Implementation_Plan.md`
- API contract (paths / auth / errors / enums) → `docs/project-state/CANONICAL_OPENAPI_ALIGNMENT.md`
- UI / visual design master — FIRST source of truth → `docs/ui-system/`: page mockups (`brand/mockups/*.jsx`, `screens/*.md`) + component/typography/colour/button specs (`components/*.md`, `brand/README.md`)
- Design tokens / implementation → `docs/project-state/CANONICAL_DESIGN_SYSTEM_ALIGNMENT.md` + live `frontend/` token files (Geist/warm; the mechanism that implements the ui-system master — already aligned, no Manrope/cool conflict)
- UI/UX build rules (creating screens/components) → `agent.md`
- Scoring / rating engine → `docs/project-state/FINAL_SCORING_SPEC.md`
- ui-system KEEP/MERGE/REPLACE/IGNORE → `docs/project-state/MIGRATION_STRATEGY_FINAL.md`
- Current stage plan → `docs/project-state/STAGE2_EXECUTION_PLAN.md`
- How work is governed & reviewed → `docs/project-state/AI_GOVERNANCE_MODEL.md`
- Major architectural decisions (ADR log) → `docs/project-state/ARCHITECTURE_DECISIONS.md`

## Non-negotiables (enforced in code + CI grep; violating any = BLOCKER)

1. **SEBI educational boundary** — no buy/sell/hold advice anywhere (enum, copy, AI output).
   Labels: `in_form/on_track/off_track/out_of_form/insufficient_data`. Advisory verbs
   (`strong_buy/buy/hold/caution/avoid`) are rejected. Label derives from the rule table, not a
   pure function of the score.
2. **No numeric in DOM** — public surface = label + confidence **band** only; numeric
   score / factor weights / fair-value never reach the client (numerics tier-gated server-side).
3. **Risk profile never feeds the score** (test-enforced separation; sole writer = Onboarding).
4. **Confidence band-only** at launch (`high/medium/low`); `< 0.30 → insufficient_data` (refuse).
5. **Auth = RS256 JWT in `__Host-` HttpOnly cookies**; refresh rotation + reuse detection
   (atomic `GETDEL`); **no bearer / Authorization-header auth**; rate-limit keyed by
   `CF-Connecting-IP`.
6. **Base path `/api/v1`**; RFC7807 errors + `request_id`; `Idempotency-Key` on mutating /
   payment routes; tier-gate = **402**.
7. **Module isolation** — interface-only coupling; no cross-module JOIN/INSERT; `scoring` must not
   import `billing`; schema-per-concern (no flat `public`).
8. **Stack locks** — no Elasticsearch (Postgres FTS + `pg_trgm`); TimescaleDB required; Resend
   (not SES/SendGrid); governed OpenRouter gateway (not a generic LLM client); Geist/warm tokens
   (not Manrope/cool).
9. **Disclosures + audit** — every score/label/AI surface renders the disclosure bundle +
   `NOT_ADVICE`, tied to the in-force disclaimer version in `ai_recommendation_audit`.
10. **DPDP consent** enforced on data-processing routes (`RequireConsent` is currently a stub —
    wire it before those routes go live; tracked in `BLOCKERS.md`).

## Load-bearing paths (no Sonnet/Haiku/Tier-2 code lands here without Opus line-by-line diff review + the tier's gates)

- `backend/**/auth/*`, session/JWT, `RequireTier` / `RequireConsent`
- payments / webhook (Razorpay verify-before-parse + event dedup)
- scoring / rating engine + `ranking_configs`
- AI gateway / prompt / classifier / budget governor
- consent / DPDP + `ai_recommendation_audit`
- Alembic migrations; `docker-compose*.yml`; cloudflared config; `infra/`

## Governance & approval gates (full model: `docs/project-state/AI_GOVERNANCE_MODEL.md`)

Claude Code acts as **Builder + Architect + Security + Compliance + UI + Product** reviewer. Which
reviews run is set by a **3-tier classification** (Builder + Architect Review are required in every
tier):

- **Tier A — Standard features:** Builder + Architect + **UI**.
- **Tier B — Security / Auth / Billing / AI / Compliance:** Builder + Architect + **Security**
  (`codex:rescue`, fail-closed) + **Compliance** (Opus).
- **Tier C — Scoring engine / Recommendation logic:** Builder + Architect + **Compliance**
  (Opus) and **Product**.

Rules: pick the highest-risk tier touched (C > B > A); add one cross-tier review if a surface from
another tier is clearly present (e.g. a Tier-C change that ships a screen adds UI; a Tier-A screen
showing a score/label/AI adds Compliance). Minor changes → Builder + Architect only (logged).
Reviewers are **independent agents**, never the builder instance; fan out in one parallel message.

**Review cadence (pre-launch, `AI_GOVERNANCE_MODEL.md` §3.2):** the tier's reviewer ceremony is
**batched, not per-session**. Per session: **Builder + Architect only** — build features, move the
MF-first wedge forward. The full tier panel (Security/Compliance/UI/Product) runs as **one
end-of-phase / pre-deploy audit pass** folded into the Phase-7 §5 gate. **Hard exception:** any
change touching a **load-bearing path** (list above) keeps its **full inline Tier-B/C review in the
same session it lands** — Security/Compliance sign-off there is never deferred. Deterministic gates
(tests · secrets · anti-pattern grep · ruff/mypy/tsc) run **per commit** regardless. A deferred
change is logged `NOT-COMPLETE (reviews batched to phase audit)` and is merge-eligible as WIP only,
never deploy-eligible until the batched pass clears it.

**Pre-launch build-first posture (founder 2026-06-14 — binding).** The pre-launch bottleneck is
review/doc **ceremony**, not the gates. Default for non-load-bearing work: **build → run the
automated gates → ship** — no per-change review doc, no reviewer panel, and no heavy session-exit
write-up for routine UI / reporting / copy / dev-tooling diffs. The only mandatory inline checks
there are the **deterministic gates** plus the **two hard compliance gates** (the **SEBI advisory
boundary** and the **scoring two-person gate**). Recent "nothing ships to the UI" was caused by
dormant flags, source-blocked data, and backend-only work — **not** by approvals. Keep docs for
decisions worth re-reading, not as a tax on every diff.

**Development-phase skill suspension (binding until pre-launch audit).** Do NOT
auto-invoke `DhanRadar-Engineering-Governance` during routine development sessions. Only invoke it
when explicitly requested by name, when touching a load-bearing path (auth / scoring / payments /
AI-classifier / migrations), or when a new score/label/AI surface is being introduced. For all other
work — UI, reporting, copy, data-pipeline, dev-tooling — skip the Engineering-Governance gatekeeper
and go straight to: automated deterministic gates + the two hard compliance gates below.
The full reviewer panels (`DhanRadar-Explainable-AI-Enrichment` red-team,
`DhanRadar-SEBI-Compliance-Guardrail` independent review, `DhanRadar-Feature-Competitiveness-Reviewer`)
are deferred to the end-of-phase audit pass, not per-session. `DhanRadar-Project-Progress-Auditor`
and `DhanRadar-Scoring-Engine` remain on-demand only (invoke only when explicitly requested).

**A change is complete only when** the deterministic gates are green, the tier's required reviews
pass (ACCEPT / ACCEPT-WITH-CONDITIONS), and the gate ledger is signed off. **The per-change review
file** `docs/project-state/reviews/<change-id>.md` **is required only for load-bearing / Tier-B/C
changes** (and anything that introduces a new score / label / AI surface); routine non-load-bearing
work needs only the gates above.

**Scoring-engine two-person methodology gate** (`approved_by ≠ created_by`) is **documented but
non-blocking** at this stage — it is a production-readiness gate enforced before any
`ranking_configs` version is *activated* in production. Tracked in `BLOCKERS.md` (B6).

## Deterministic gates (must be green BEFORE any reviewer spends tokens)

Executed tests · secrets scan · anti-pattern grep (Plan §0.3) · IGNORE-list grep (no
bearer/ES/OTP-first/Manrope/bare-`/v1`/advisory-verb) · ruff/mypy/tsc. Target: wired as CI + a
`PreToolUse` git-commit hook.

## Deploy gate

A passing ledger is **merge-eligible, not deploy-eligible**. KVM4 deploy needs: no open
Security/Compliance BLOCKER + the Phase-7 §5 adversarial gate logged + **separate explicit human
approval**. Honor the ❌ NEVER-TOUCH list and the 3 cloudflared gotchas (`infra-notes.md`). The
GitHub `production` env is main-branch-gated.

## Routing & telemetry (overlay to the global playbook)

The global `~/.claude/CLAUDE.md` routing matrix applies. This overlay tightens two things the
DhanRadar session footers have been getting wrong:

- **`reworked: Y` means any Opus correction that changed a subagent's output** — not just a full
  rebuild or a P3→P4 bounce. If Opus re-typed prose, flipped a type's ownership, fixed a contract
  detail, or rewrote more than a trivial line of what a Sonnet/Haiku/Tier-2/Tier-4 agent produced,
  the per-delegation telemetry line is **`reworked: Y (<one-line why>)`**. A run is `reworked: N`
  only when Opus shipped the agent's output essentially as-returned. Honest `Y`s are the whole
  point — they are how the matrix gets retuned; a footer of all-`N` carries no signal.
- **Cheap-tier doc drafting is the default, not the exception.** Session-state updates, RCA
  entries, feature-doc prose, ADR bodies, and commit messages are **drafted by Tier-4 free-chain
  (`or.mjs free-chain`) or a Sonnet subagent, then reviewed/edited by Opus** — never typed on Opus
  from scratch. A `PreToolUse(Write|Edit)` nudge fires on doc/governance paths as a reminder. The
  one-shot drafting exemption (≤~30 lines already in Opus's hot cache) still applies for tiny edits.
- **Activate Tier-2 (paid OpenRouter `dsf`/`grok-code`) for non-load-bearing batches.** It has been
  dormant; the $2/day cap is unused headroom. Route reporting queries, dev-only tooling, Storybook,
  and scratch scripts there with Opus review. Same data-privacy rules as Tier-4 (assume logged; no
  PII/credentials/prompt-skills/proprietary logic). **Never** Tier-2/Tier-4 in a load-bearing path.
- **Delegate the Phase-0 warm start; don't read the canon on Opus.** Carried context is re-billed
  every turn, so the bigger long-session cost is what Opus *ingests*, not what it types. Spawn the
  **`warm-start` subagent** (`.claude/agents/warm-start.md`) with the task focus; it reads the
  read-first docs + the area-specific canonical doc and returns a one-page brief (where we are ·
  binding blockers · the rules that bind this task · load-bearing paths in reach · known traps ·
  next action · read-next pointers). Opus starts from the brief and opens a full doc only for the
  specific seam it touches. Lean on the claude-mem digest / `mem-search` for "where are we" rather
  than re-reading whole docs. Judgment still lives on Opus — warm-start is orientation, not review.
- **Isolate token-heavy skill/tool payloads in a subagent.** Skills that dump large schemas into
  context (e.g. `update-config`'s full settings schema), big MCP tool schemas, doc-discovery, or
  "read N files for one fact" run **inside a Sonnet/Haiku subagent that returns only the answer** —
  the bulk never enters the Opus context. This is distinct from the output-token rules: it cuts
  *ingestion*, which is re-billed on every subsequent turn until `/clear`. Pair with the standing
  rule to `/clear` and reload from `SESSION_STATE.md` past ~60 tool calls — a fresh Opus on a lean
  context both reasons better and costs less than a drifting one on a bloated one.

## Standing rules (part of "done" every phase)

- **RCA** on every bug fix → `docs/rca/README.md` (symptom/cause/fix-with-file:line/prevention).
- **Feature doc** per module → `docs/features/<module>.md`, kept as-built.
- **ADR** for every major architectural decision → `docs/project-state/ARCHITECTURE_DECISIONS.md`.
- **UI** uses the live `frontend/` design tokens (Geist/warm) per `agent.md`; no ad-hoc styling.
- **Reply format** — simple-sentence pointers under: Implemented · Pending · Not implemented ·
  Action for you · Dependencies · Issues · Deviations · Agent/model usage & % · Improvements.
  No dense tables.
- **Session exit** — update `SESSION_STATE.md` (status + open blockers + agent-utilization &
  routing-telemetry footer) and `BLOCKERS.md`.
- All docs pass `markdownlint` (`.markdownlint.json`).

## Git push — email privacy

First and every commit uses the noreply pattern (committer + author =
`257227540+manishjnv@users.noreply.github.com`); never `git config` around it. The one-shot amend
pattern is in the global `~/.claude/CLAUDE.md`.
