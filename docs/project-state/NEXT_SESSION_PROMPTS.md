# DhanRadar — Next-Session Kickoff Prompts

Paste the relevant block into a **fresh** session to build the next functional slice. Order
follows `BLOCKERS.md` → **Build sequence (functionality-first)**. After an item lands, mark it
done here and promote the next one.

**Build order:** ~~B29~~ → ~~B42~~ → **B43 (next)** → AI MF commentary → PHASE 5M tiering → B35.
**Done:** B29 (`58db876`), B42 (`725e3eb`,`588a719`), B44 (`927f64f`,`4b40f83`).
**Rule:** build product + a minimum unit test per slice; PARK deploy/governance/billing/security
residuals until a pre-deploy phase (see the BLOCKERS build-sequence section).

---

## 1. B43 — Onboarding / risk-profile UI (NEXT)

```text
Execute B43 (onboarding / risk-profile UI) on branch hardening/launch-gate-blockers —
item 3 in the functionality-first build sequence (B29, B42, B44 are already ADDRESSED).

PHASE 0 — warm start (do this first, cheaply):
Spawn the warm-start subagent with focus "B43 onboarding / risk-profile UI + the
risk-profile<->score separation invariant". It should read: docs/infra-notes.md, the project
CLAUDE.md overlay, agent.md (UI/UX build rules), docs/DhanRadar_Architecture_Final.md
(Onboarding module + the rule that Onboarding is the SOLE writer of risk_profile),
docs/project-state/BLOCKERS.md (the "Build sequence" section + the B43 row), and the live
frontend/ token files. Return a one-page brief; I start from that. Do NOT read the whole
canon on Opus.

GOAL (one sentence): give a new user a path out of the null-risk cold-start — an onboarding
flow whose completion writes users.risk_profile (Onboarding is the sole writer), so the app
is usable from first login.

IMPORTANT — assess before building. First report what already exists: is there a backend
onboarding endpoint / risk_profile column / any partial onboarding screen? Confirm what
B29/B42/B44 left in place (responsive AppShell, consent modal). Then build only the gap —
do not rebuild working parts.

ACCEPTANCE (prove each, with output/test):
1. A user with null risk_profile is routed into the onboarding flow (cold-start path); a
   user who has completed it is not.
2. Completing onboarding writes users.risk_profile via the onboarding endpoint (the SOLE
   writer) and persists; re-login reflects it.
3. SEPARATION INVARIANT (non-negotiable #3): risk_profile is NOT read by the scoring engine.
   Keep the test-enforced risk<->score separation GREEN; if no such guard test exists, add one
   (grep/contract test that scoring never imports/reads risk_profile).

CONSTRAINTS:
- agent.md UI rules are binding. Use the LIVE frontend/ design tokens (Geist/warm) + existing
  src/components — NO ad-hoc styling. (Memory: canonical UI = live frontend/ tokens.)
- Non-negotiables hold: risk_profile NEVER feeds the score (#3); no numeric score/factor/
  fair-value in the DOM (#2); RFC7807 + request_id on the backend route.
- Functionality-first: build the slice + a MINIMUM test set — one happy-path (submit sets
  risk_profile) + the #3 separation guard. No deploy hardening, no governance audit, no extra
  docs churn this session.
- Tier classification: Tier-A UI, BUT it touches the risk_profile separation invariant — keep
  the Architect + the #3 separation check inline this session (it is a non-negotiable). No
  codex:rescue needed unless the scoring seam is modified.
- Routing: delegate the FE flow + the small backend risk_profile-write endpoint to a Sonnet
  subagent against this exact contract; Opus reviews the diff + verifies #3. Use noreply
  commit identity.

When done: update BLOCKERS.md B43 status (link the commit), one line in SESSION_STATE
next-action (-> AI MF commentary), and stop. Report: what already existed vs what you added,
acceptance proof incl. the #3 guard result, tests pass Y/N, next item.
```

---

## 2. AI MF commentary — first AI consumer (after B43)

Load-bearing (AI gateway) — this one keeps its full inline Tier-B review (Security via
`codex:rescue`, or the Sonnet-takeover fallback if codex is down; Compliance via Opus).

```text
Execute "AI MF commentary" (the first AI-gateway consumer) on branch
hardening/launch-gate-blockers — item 5 in the functionality-first build sequence
(B29/B42/B44/B43 done).

PHASE 0 — warm start (do this first, cheaply):
Spawn the warm-start subagent with focus "first AI consumer = MF report portfolio commentary;
the B20/B21/B22 call-site gates". It should read: docs/infra-notes.md, the project CLAUDE.md
overlay, docs/features/ai-gateway.md, docs/DhanRadar_Architecture_Final.md (B3 AI gateway + S
AIOutputBase contract), docs/project-state/BLOCKERS.md (B20, B21, B22 rows + the build
sequence), and DhanRadar_Implementation_Plan.md PHASE 5M. Return a one-page brief.

GOAL (one sentence): the MF report produces governed AI portfolio commentary via
OpenRouterGateway.complete(), wiring the three call-site gates that were left for the first
consumer — so the gateway finally has a real consumer.

IMPORTANT — assess before building. complete() is built and unconsumed; B20/B21/B22 infra is
built (default-deny consent flag, ai_recommendation_audit table, ai_low_confidence_log table)
and only the CALL SITE remains. First report exactly what each of B20/B21/B22 still needs at
the call site, then wire only that.

ACCEPTANCE (prove each, with a test):
1. MF report generation calls the gateway and returns educational portfolio commentary that
   passes the QualityValidator (>=2 contributing signals; no advisory verbs).
2. B20 (cross-border consent): the call site calls assert_consent(user_id, "cross_border_ai",
   db) and passes cross_border_consent_verified=True; a user WITHOUT the grant is refused
   BEFORE any payload reaches complete() (test the deny path).
3. B21 (audit): the served commentary writes ai_recommendation_audit with (label, model_used,
   in-force disclaimer_version); complete() returns model_used to the caller.
4. B22 (confidence floor, non-neg #4): confidence < 0.30 -> insufficient_data / refuse, and
   log_low_confidence(...) is written at the sub-0.30 seam.
5. Budget: the call is metered by the budget governor (free pool first; premium spillover
   stays within cap) — a forced over-budget state skips/refuses, never overspends.

CONSTRAINTS:
- Non-negotiables: SEBI educational only — no buy/sell/hold (enum + copy + AI output); the
  disclosure bundle + NOT_ADVICE render with the commentary, tied to the in-force disclaimer
  version; no numeric score/factor/fair-value in the DOM.
- Module isolation: the consumer calls the gateway via its interface; gateway stays
  module-isolated (no billing/scoring imports leaking in).
- Decouple from tiering: build the commentary so it CAN be tier-gated later (PHASE 5M makes it
  a DhanRadar Plus feature + one-time taster) — do NOT build the tier gate here; that is item 6.
- LOAD-BEARING (AI gateway + consent + compliance audit): full inline Tier-B review this
  session — Security adversarial sign-off (codex:rescue; Sonnet-takeover fallback if codex is
  down) + Compliance (Opus). Log the verdict in reviews/<change-id>.md.
- Functionality-first otherwise: minimum tests per acceptance item; no deploy hardening.
- Routing: Sonnet builds the call-site wiring against this contract; Opus reviews + runs the
  Tier-B gate. Use noreply commit identity.

When done: update BLOCKERS.md B20/B21/B22 rows (link the commit) + the build-sequence item,
one line in SESSION_STATE next-action (-> PHASE 5M tiering), and stop. Report: what infra
existed vs what you wired, acceptance proof incl. the deny-path + confidence-floor tests, the
Tier-B verdict, tests pass Y/N, next item.
```

---

## 3. PHASE 5M tiering — freemium + Founding Access (after AI commentary)

Load-bearing (billing/tiering) — keeps inline Tier-B review. Compose the full prompt when
reached, using the same template and the PHASE 5M contract in
`DhanRadar_Implementation_Plan.md`. Core scope:

- Add per-user `pro_access_until` (timestamp) + `pro_access_reason`
  (`founding` / `triggered_trial` / `subscription`); `RequireTier` grants Plus when
  `now < pro_access_until` OR an active subscription exists (downgrade is automatic by
  timestamp — no gateway, no revoke job).
- Gate the Plus features (tracking history, auto re-score, alerts, multiple portfolios, AI
  commentary beyond the one-time taster) behind `RequireTier` -> 402; Free stays ungated.
- Founding Access: pre-go-live signups get Plus free until billing go-live + 30-day grace.
- Keep `create_checkout` inert (B7/B8 503 fail-safe) — billing go-live stays a data-only flip.
- Min tests: `pro_access_until` future -> Plus; expired -> Free 402; founding flag sets the
  window.

---

## 4. B35 — Mood Compass data + embed (fast-follow)

After the MF wedge. Scope: real Market Data Adapter signals so `GET /market/mood` returns a
snapshot (not 404), the `/market/mood/embed` creator widget, a structured `data_unavailable`
200, human display labels for factor evidence, and the `mood.snapshot.published` event. See the
B35 row in `BLOCKERS.md` for the full gap list. Compose the prompt when reached.

---

## Maintenance

After each slice lands: strike it through in the build-order line at the top, move "(NEXT)" to
the following item, and (if not already) write its full prompt here from the template. Keep this
file as the single grab-and-go source so the next session never has to re-derive scope.
