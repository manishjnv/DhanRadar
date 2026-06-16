# Competitor Feature-Opportunity Plan — 2026-06-13

**Owner skill:** `DhanRadar-Competitor-Market-Research` · **Analyst:** Claude (orchestrator) ·
**Evidence stamp:** all competitor facts sourced live 2026-06-13; volatile facts must be
re-verified next quarterly review (Inv. 2–3).

## 0. How to read this (governance note — do not skip)

- This is a **gated opportunity backlog with verdicts**, not an implementation spec. Per the
  research-skill mandate, each item is a `Differentiate / Improve / Copy(table-stakes) /
  Ignore / Never-Build` verdict that passed (or failed) the value test. **No feature here is
  recommended "because a competitor has it"** (Inv. 1).
- **Pricing is LOCKED** by founder instruction (2026-06-13). Nothing in this plan changes tiers
  or prices; monetization stays the existing freemium + Founding Access (DhanRadar Plus) model.
- **Building any item routes through `DhanRadar-Engineering-Governance`** (doc → feature-spec →
  task → code) and the **owning module skill** (named per item). This doc is the upstream
  "is it worth building + how does it differentiate" gate, nothing further.
- **Build-state caveat:** items are tagged `NEW` / `EXTEND` against my best knowledge of the
  current repo. Confirm actual build-state via `DhanRadar-Project-Progress-Auditor` before
  scheduling — do not build what already exists.
- Compliance wording, the advisory boundary, and the label/IP question all **defer to
  `DhanRadar-SEBI-Compliance-Guardrail` + counsel** (Inv. 5). This skill does not rule on legality.

---

## 1. Executive read — the market converged; DhanRadar's water moved

Across all seven competitors (Value Research + the six below), one pattern dominates: **everyone is
racing to the same destination — import the portfolio → analyze it → tell the user what to do.**

- **Value Research** (heritage research house) became a SEBI RIA (Fund Advisor, buy/sell/hold).
- **PowerUp Money** (new entrant) is a SEBI RIA giving keep/pause/exit calls **on DhanRadar's exact
  label set**.
- **ET Money** pushes Genius (₹249/mo advisory, 76k paying subs, model portfolios).
- **Groww** is piloting Prime (guided MF) + GR1 AI co-pilot.
- **INDmoney** ships mIND AI + an official Claude MCP server.
- **Morningstar** has the deepest *explainability* (analyst People/Process/Parent write-ups) but
  it's gated, jargon-heavy, global-first, manual-entry, no CAS.
- **Tickertape** has the best consumer *screening UX* + the MMI hook, but thin MF explainability and
  no real AI.

**So what for DhanRadar's differentiation + moat.** The "give the answer" lane is now crowded and is
exactly the lane DhanRadar structurally will not enter. DhanRadar's defensible water is the **one
step everyone skips: the plain-language, grounded, cited, *educational* explanation of WHY a fund is
where it is — without telling the user what to do.** Three moats, ranked by durability:

1. **Explainability depth at retail scale, in plain language, non-advisory.** Morningstar proves
   depth sells; nobody delivers it cheaply, in plain English, on an imported CAS, without gating or
   jargon. This is the core Differentiate.
2. **A grounded, non-advisory AI research layer for MF.** Real AI in India-retail MF is nearly
   empty (Tickertape none, ET Money none, VR none, PowerUp roadmap-only; only INDmoney/Groww have
   shipped, both equity-skewed). DhanRadar already shipped the first gateway consumer (MF
   commentary) — extend it.
3. **The compliance boundary itself as a trust moat** — but only if it converts to a genuinely
   different, no-conflict, educational experience the user values (see the bear case, §6).

The labels are **not** a moat — they are now contested (PowerUp). The moat is the *explanation under
the label* and the *refusal to cross into advice*.

---

## 2. CRITICAL ESCALATION — PowerUp Money label collision (compliance · legal · brand)

**This is the single most important output of this review and needs a decision before further
public-surface work.**

- **Finding (tier A, verified firsthand 2026-06-13):** PowerUp Money's "Power Rank" uses
  **In-form / On-track / Off-track / Out-of-form** — verbatim DhanRadar's `in_form / on_track /
  off_track / out_of_form` — and maps them to advice: *Off-track = "pause new investments,"
  Out-of-form = "exit this mutual fund."* They are a SEBI RIA (INA000019798). They were **first to
  market** with this label set (2024); DhanRadar is the later entrant.
- **Why it matters:**
  1. **Brand-confusion / copycat perception.** A well-funded, fast-growing competitor owns this
     vocabulary in the same market and category. DhanRadar risks *looking* like the imitator on its
     own signature element — the opposite of a differentiation moat.
  2. **Possible IP/trademark exposure (Inv. 14 — respect IP).** If PowerUp has filed any trademark
     on the label taxonomy or "Power Rank," DhanRadar's identical labels are a legal risk. **This
     must be checked by counsel.** I cannot and do not rule on it.
  3. **The compliance distinction is razor-thin to a user.** PowerUp's label says "exit"; DhanRadar's
     identical label must *never* say "exit" (Non-negotiable #1). Same words, opposite legal posture.
     That makes DhanRadar's non-advisory boundary harder to communicate, not easier, when the
     vocabulary is shared.
- **Routing (this skill does not decide it):**
  - → `DhanRadar-SEBI-Compliance-Guardrail` + **counsel**: (a) trademark/IP search on PowerUp's
    label set & "Power Rank"; (b) confirm DhanRadar's `out_of_form` surface copy carries **zero**
    exit/pause/keep action language.
  - → **Founder decision**: keep identical labels (accept the collision, lean on the
    non-advisory + explainability difference) **vs.** differentiate the *surface vocabulary* while
    keeping the underlying taxonomy/methodology. My strategic read: **differentiate the public label
    words** to escape the copycat frame, retain the internal taxonomy. But this is a brand+legal
    call above this skill's authority.
- **Do not treat as settled.** Until counsel + founder rule, flag any new public surface that
  renders the four labels.

---

## 3. Cross-competitor gap map (what nobody does well = the build targets)

| Capability | Who does it (dated, 2026-06-13) | Who does it *well* | The open gap = DhanRadar target |
|---|---|---|---|
| Plain-language **"why this label"** explanation | Morningstar (analyst write-ups, gated/jargon) | ~Morningstar only | Explainable why, free, plain-English, on imported CAS |
| **Grounded AI** MF assistant (non-advisory) | INDmoney mIND+MCP, Groww GR1 (equity-skewed) | Nobody for MF education | Cited, refuses-advice MF research assistant |
| **Portfolio overlap / X-ray** | Morningstar (manual, 10 funds), INDmoney (overlap), ET Money (breakdown) | Morningstar depth, INDmoney friction | Overlap/concentration *explained* on a CAS import |
| **Fund-label change alerts + the why** | PowerUp (rating-change alert), INDmoney INDsights | PowerUp (but as advice) | "Your fund's label changed — here's the education" |
| **Education fused with the tool** | Tickertape Learn, Morningstar, Groww Academy (funnel) | Tickertape loop | Educational report *is* the learn surface |
| **Market mood hook** | Tickertape MMI (™, equity sentiment) | Tickertape brand | Educational, explained "Mood Compass" (own IP) |
| **Low-friction import** | MF Central OTP (VR, Groww, Tickertape), PAN-consent (PowerUp, ET Money), AA/scrape (INDmoney) | Groww/PowerUp friction | CAS-first (privacy) **+** MF Central pull option |
| **Family/household view** | PowerUp, INDmoney, ET Money, VR | INDmoney breadth | Household CAS view, educational framing |

**Blue-ocean read:** the densest cluster of "everyone has a thin version, nobody has a deep
non-advisory educational version" is **explainability (why) + grounded AI + explained overlap**.
That is where DhanRadar should spend, because it deepens a moat rivals structurally can't follow
(advisory players can't be purely educational without abandoning their revenue model).

---

## 4. The gated feature backlog (verdicts + value tests + routing)

Value-test axes (Inv. 4): **U**ser · **B**usiness · **S**trategic · **C**ompliance · **Cx**
complexity · **D**efensibility · **M**onetization · **Su**stainability. Each item states the
verdict, why it's *independently* justified (never "they have it"), the moat, and the owning skill.

### TIER 1 — Differentiate (moat-deepening; build first)

**F1. Explainable "Why this label" layer — the educational reasoning under every fund label**
`EXTEND` · **Verdict: DIFFERENTIATE**
- **Evidence/gap:** Morningstar is the only one with real per-fund qualitative explanation, and it's
  gated, jargon-heavy, global-first, manual-entry [A, morningstar.in, 06-13]. PowerUp/Groww/ET Money
  ship a label or star with little or no plain-language *why* [A, 06-13]. The "why is my fund
  off-form" question is largely unanswered at India-retail scale.
- **What it is:** for each fund in the CAS report, a short, plain-English, **grounded + cited**
  explanation of what drives its label (consistency, downside protection, recent form, cost,
  category context) — framed as education, never as a recommendation. No numerics in DOM
  (Non-negotiable #2); label + band + *why*.
- **Value test:** U=High · S=High · C=core-positive (educational) · D=High (this is the moat) ·
  Cx=Med · M=High (the thing worth paying for) · Su=High. 
- **Justified by "they have it"? N** — justified because the *explanation* is the job competitors do
  badly and it's DhanRadar's defining promise, independent of any rival.
- **Moat:** explainability + scoring/AI IP + non-advisory trust. The single hardest thing for an
  advisory rival to copy without diluting their "just tell me" product.
- **Routing:** `DhanRadar-Scoring-Engine` + `DhanRadar-Explainable-AI-Enrichment` +
  `DhanRadar-SEBI-Compliance-Guardrail` (wording). Build via Engineering-Governance (Tier-C).

**F2. Grounded, non-advisory MF research assistant (conversational, cited, refuses advice)**
`EXTEND` · **Verdict: DIFFERENTIATE**
- **Evidence/gap:** real AI in India-retail MF is nearly empty — Tickertape none, ET Money "AI" is a
  quant model not AI, VR none, PowerUp roadmap-only; only INDmoney (mIND + Claude MCP) and Groww
  (GR1 beta) shipped, both **equity-skewed and advice-adjacent or guarded** [A/B, 06-13]. Morningstar
  "Mo" is not India-retail [B, 06-13].
- **What it is:** ask-anything assistant grounded on DhanRadar's own fund/portfolio data + education
  corpus, with citations, confidence, and a hard advice refusal (no buy/sell/hold/allocate). Extends
  the already-shipped MF commentary consumer.
- **Value test:** U=High · S=High · C=High-risk surface (must be airtight non-advisory) · D=High ·
  Cx=High · M=Med-High (Plus feature) · Su=High.
- **Justified by "they have it"? N** — justified by the open lane + DhanRadar's existing AI gateway,
  not by mimicking mIND/GR1; in fact DhanRadar's non-advisory framing is the *opposite* bet.
- **Moat:** grounded-AI IP + the governance/guardrail stack (most rivals can't ship advice-refusing
  AI because their product *is* advice).
- **Routing:** `DhanRadar-Explainable-AI-Enrichment` (lead) + `DhanRadar-SEBI-Compliance-Guardrail`.
  Tier-B/C, full inline review (load-bearing AI path).

**F3. Explained portfolio X-ray — overlap, concentration, category drift (on the CAS import)**
`NEW` · **Verdict: DIFFERENTIATE (built on table-stakes)**
- **Evidence/gap:** Morningstar X-ray is manual + capped at 10 funds [A, 06-13]; INDmoney added
  overlap June 2025 [A]; ET Money has a "breakdown"; Groww shows allocation only; PowerUp doesn't do
  overlap [A/C, 06-13]. Nobody delivers overlap/concentration as **plain-language education** on a
  full CAS.
- **What it is:** look-through overlap (same stocks across funds), concentration, category/cap drift
  vs the user's own mix — each rendered as an *explained* educational insight ("3 of your funds hold
  the same top-10; here's what overlap means"), not a rebalancing instruction.
- **Value test:** U=High · S=High · C=positive (educational) · D=Med-High · Cx=Med-High (needs fund
  holdings data) · M=Med · Su=High.
- **Justified by "they have it"? N** — the *educational explanation* of overlap is the differentiator;
  raw overlap alone would be parity.
- **Moat:** explainability + the MF-analytics data asset (holdings/constituents).
- **Routing:** `DhanRadar-Portfolio-Intelligence` + `DhanRadar-Mutual-Fund-Analytics` +
  `DhanRadar-Data-Ingestion-Normalization` (constituents are partly blocked — see BLOCKERS P2).
  Tier-A/C.

**F4. "Mood Compass" — educational market-sentiment hook (own IP, explained)**
`NEW` · **Verdict: DIFFERENTIATE (never Copy)**
- **Evidence/gap:** Tickertape's MMI is a proven free top-of-funnel hook (222k live users) but it's
  **trademarked**, equity-sentiment, and unexplained-as-education [A, tickertape.in/market-mood-index,
  06-13].
- **What it is:** DhanRadar's own, differently-named, **educational** sentiment/market-context
  surface that *teaches* what the signal means — never "Market Mood Index," never a buy/sell timing
  cue. Free, SEO/acquisition hook.
- **Value test:** U=Med-High · S=High (acquisition + brand) · C=positive if framed educational ·
  D=Med · Cx=Med · M=Low direct (funnel) · Su=Med.
- **Justified by "they have it"? N** — justified as an educational acquisition surface on DhanRadar's
  terms; explicitly *not* a copy of MMI (Inv. 14 trademark discipline).
- **Moat:** brand + educational framing; modest but a cheap top-of-funnel.
- **Routing:** `DhanRadar-Market-Mood-Trend` (owns this) + `DhanRadar-SEBI-Compliance-Guardrail`
  (timing-cue boundary) + `DhanRadar-Programmatic-SEO-Content` (acquisition).

### TIER 2 — Improve / table-stakes the wedge genuinely needs (value-tested, not parity-reflex)

**F5. MF Central pull as an import option (alongside CAS upload)**
`NEW` · **Verdict: COPY (table-stakes) — passes value test**
- **Evidence/gap:** VR, Groww, Tickertape (MF) all use MF Central OTP pull; PowerUp/ET Money use
  PAN-consent; CAS-PDF-first is rarer [A, 06-13]. CAS upload is a privacy-preserving differentiator,
  but OTP pull is materially lower friction for many users.
- **Why table-stakes (not reflex):** import friction is a genuine activation dealbreaker; offering
  **both** (CAS for privacy/offline, MF Central for speed) removes the friction objection without
  abandoning the privacy edge.
- **Value test:** U=High · S=Med · C=DPDP-sensitive (consent) · Cx=Med · D=Low (parity) · M=Low ·
  Su=Med. Verdict holds because absence is a real funnel leak.
- **Routing:** `DhanRadar-Data-Ingestion-Normalization` (lead) + consent/DPDP path. Tier-B (consent).

**F6. Fund-label-change monitoring + alerts (with the educational why)**
`NEW` · **Verdict: IMPROVE**
- **Evidence/gap:** PowerUp sends monthly rating-change alerts (as advice), INDmoney INDsights daily
  health, ET Money portfolio health [A, 06-13]. Retention-grade table-stakes — but everyone's
  version is either advice or a bare number.
- **What it is:** notify when a held fund's label changes, with the **educational explanation** of
  what changed and why — never "exit now."
- **Value test:** U=High (retention) · S=Med · C=must stay non-advisory · Cx=Med · D=Med (the *why*
  is the edge) · M=Med (Plus) · Su=High.
- **Justified by "they have it"? N** — justified by retention economics + the educational framing,
  not by PowerUp's alert.
- **Routing:** `DhanRadar-Portfolio-Intelligence` + notifications + `DhanRadar-SEBI-Compliance-Guardrail`.

**F7. Household / family CAS view**
`EXTEND/NEW` · **Verdict: COPY (table-stakes) — conditional pass**
- **Evidence/gap:** PowerUp, INDmoney, ET Money, VR all offer family/household views [A, 06-13]. The
  household JTBD (one person managing the family's MFs) is real for the CAS wedge.
- **Value test:** U=Med-High · S=Med · C=DPDP (multi-person consent — handle carefully) · Cx=Med ·
  D=Low · M=Med (Plus) · Su=Med. Passes for the family-CAS use case; gate on consent design.
- **Routing:** `DhanRadar-Portfolio-Intelligence` + DPDP consent. Tier-B (multi-party consent).

**F8. Educational learn-loop fused to the report (and to programmatic SEO)**
`EXTEND` · **Verdict: DIFFERENTIATE (cheap, on-brand)**
- **Evidence/gap:** Tickertape Learn ties education to the tool; Groww Academy is a funnel;
  Morningstar has depth [A/B, 06-13]. DhanRadar's labelled report *is* an educational surface —
  tighten the loop (each label/insight links to a plain-English explainer; explainers double as
  SEO/programmatic pages).
- **Value test:** U=High · S=High (SEO acquisition + activation) · C=core-positive · Cx=Low-Med ·
  D=Med · M=Low direct · Su=High.
- **Routing:** `DhanRadar-Programmatic-SEO-Content` + `DhanRadar-Onboarding-Activation`.

### TIER 3 — Watch / later (documented, not planned)

- **Goal/SIP calculators** (everyone has; SEO/education table-stakes) → `DhanRadar-Goal-Planning-Calculator`;
  verdict **Copy(table-stakes)/Improve** with educational framing — **verify if already built** before
  scheduling.
- **Corporate-action timeline** (INDmoney Feb 2026) → educational value, low urgency →
  `DhanRadar-Portfolio-Intelligence`.
- **Multi-asset / net-worth aggregation** (INDmoney's breadth) → **Ignore for now**: off the MF-first
  wedge, high complexity, DPDP/credential-scraping risk; revisit post-MF-launch only if the
  educational job demands it. Not a parity chase.

### NEVER-BUILD (advice-adjacent — permanent, Inv. 5)

These appear across competitors; they are **permanently barred** regardless of how many rivals ship
them. Wording/scope defers to `DhanRadar-SEBI-Compliance-Guardrail`.

- Buy/sell/hold/**keep/pause/exit** calls on funds (PowerUp, VR Fund Advisor, ET Money Genius).
- **Mapping any DhanRadar label to an action** (the PowerUp pattern) — `out_of_form` must never mean
  "exit." This is the sharpest line given §2.
- Model portfolios / rebalancing proposals (ET Money Genius, PowerUp Power Rebalancing, Smallcase).
- "Best funds to buy" curated pick lists framed as recommendations (Groww, VR).
- Performance/return promises or AUM-linked advice fees.

---

## 5. Priority sequence (moat × value, gated)

1. **§2 label/IP escalation** — resolve before any new public label surface (counsel + founder).
2. **F1 Explainable "why" layer** — the core moat; highest U×D.
3. **F2 Grounded non-advisory AI assistant** — open lane + extends shipped AI; Tier-B/C inline review.
4. **F3 Explained portfolio X-ray/overlap** — high user value; gated on constituents data (BLOCKERS P2).
5. **F5 MF Central import option** + **F6 label-change alerts** — activation + retention table-stakes.
6. **F8 learn-loop** + **F4 Mood Compass** — cheap acquisition/brand, run alongside.
7. **F7 family view** — when household demand is evidenced.
8. Tier 3 — documented, not planned.

Each step is **merge-eligible only after** Engineering-Governance + the tier's reviews + deterministic
gates; load-bearing items (F2 AI, F3/F5 ingestion+consent, F7 consent) keep full inline Tier-B/C
review in-session (no deferral).

---

## 6. Falsification / bear case (Inv. 8 — the honest disconfirming read)

- **The market's convergence on advice is disconfirming evidence.** Value Research (30-yr research
  house) *and* PowerUp (new RIA) *and* ET Money all concluded retail pays for **the answer**, not the
  explanation. DhanRadar refuses the answer. The non-advisory boundary may be a **monetization
  ceiling**, not only a moat.
- **PowerUp is the live test.** They took DhanRadar's labels, added advice, raised $19.1M, and grew
  fast. If users prefer "exit this fund" over "here's why it's off-form," DhanRadar's wedge is
  contested *and* out-monetized on the same vocabulary.
- **Rebuttal (also evidence-based, also testable):** advice monetizes but stays small/slow under
  fee-only RIA economics (VR ~₹24 Cr after 30 yrs; PowerUp ~5% paid conversion; ET Money Genius 76k
  subs). DhanRadar's freemium-educational + creator-trust funnel targets a larger top-of-funnel, and
  the explainability moat is harder to copy than a label. **But this is a hypothesis.**
- **What would falsify DhanRadar's advantage — the metric to watch:** repeat-use / retention of the
  educational report. If users complete the CAS report once, want a "what do I do," can't get it, and
  leave for PowerUp/Groww Prime/a distributor, the boundary is a ceiling. **Instrument
  activation→repeat-use before over-investing in F1/F2.**

---

## 7. Hand-offs & routing summary

- **Compliance / advisory boundary / label-IP** → `DhanRadar-SEBI-Compliance-Guardrail` + counsel
  (the §2 escalation is the priority).
- **Pricing** → no change (founder-locked); competitor pricing evidence held by
  `DhanRadar-Monetization-Pricing` if ever needed.
- **Build execution** → `DhanRadar-Engineering-Governance` (feature-spec per item) + owning module
  skills named above.
- **Build-state truth** → `DhanRadar-Project-Progress-Auditor` before scheduling any `EXTEND`/`NEW`.

## 8. Evidence appendix — competitor one-liners (sourced 2026-06-13)

- **Value Research** — research house → SEBI RIA (Fund Advisor ₹4,999/yr, buy/sell/hold); free
  ratings + MF-Central portfolio tracker; no real AI; 35L+ users, ~₹24 Cr rev. [A, valueresearchonline.com]
- **Tickertape** — Smallcase-owned analytics/screener; Scorecard (0–10, explainable), MMI™ hook,
  broker-link import, PRO ~₹200/mo; no real AI; RA-registered. [A, tickertape.in]
- **ET Money** — 360 ONE-owned MF super-app; Genius advisory (₹249/mo, 76k subs, model portfolios),
  Portfolio Health Check; SEBI RIA INA00006898; "AI" = quant model. [A/B, etmoney.com + TechCrunch]
- **Morningstar India** — research/ratings authority; Medalist (People/Process/Parent) + Instant
  X-ray (manual, 10 funds); "Mo" AI not India-retail; SEBI RA INH000008686. [A/B, morningstar.in]
- **INDmoney** — super-app aggregator (16+ asset classes), CAS+AA import, mIND AI + official Claude
  MCP; 2cr downloads; SEBI RIA+broker+DP. [A, indmoney.com]
- **Groww** — mass-market broker/distributor (27% NSE share, 39% direct-SIP inflows); CAS-via-MF-
  Central import+transact, Groww Prime (pilot), GR1 AI co-pilot (beta, equity); distributor, not RIA.
  [A/B, groww.in]
- **PowerUp Money** — SEBI RIA INA000019798; **In-form/On-track/Off-track/Out-of-form labels =
  advice** (keep/pause/exit); PAN-consent import, family view, ₹999–1,999/yr; $19.1M (Peak XV/Accel);
  ~500–800k users; AI roadmap-only. [A, powerup.money] — **see §2.**

---

*Self-validation (Inv. checklist): every competitor fact dated+sourced ✓ · no verdict justified by
"they have it" ✓ · advice-adjacent items → Never-Build ✓ · output is verdicts feeding a gated backlog,
not a parity list ✓ · competitors steelmanned + DhanRadar thesis falsified (§6) ✓ · opportunities
moat-ranked, hype discounted ✓ · ends at differentiation+moat ✓ · pricing untouched ✓ · nothing
fabricated, tier-D gaps flagged in source agents ✓ · IP respected (MMI™, PowerUp label escalation) ✓.*
