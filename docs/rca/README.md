# DhanRadar — RCA Log (Root Cause Analysis)

Every bug fix gets an entry here. This is a standing rule: a fix is not "done" until its RCA is written. New entries go at the top (newest first). Keep each entry short and concrete — the goal is that a future session never re-hits the same trap.

## Entry template (copy this)

```
### YYYY-MM-DD — <short title>
- **Symptom:** what was observed (the failure as seen, not the guess).
- **Root cause:** the actual underlying reason, proven not assumed.
- **Fix:** what changed, with file:line references.
- **Prevention:** the guard added so this class of bug cannot recur (test, check, lint, doc rule, config).
- **Phase/area:** which phase or module.
```

## Log

### 2026-06-07 — ci_guards advisory scan false-positive: ARIA `role="switch"` flagged as an advisory verb

- **Symptom:** `scripts/ci_guards.py` failed (exit 1) on the notification preferences UI
  page, flagging `role="switch"` at two lines as "advisory verb usage (non-neg #2)". The
  prior session's "compliance greps clean" claim missed it because the page was untracked
  when that claim was made.
- **Root cause:** the advisory word set legitimately includes **`switch`** (the architecture's
  recommendation set has "switch funds"), and `_ADV_QUOTED` matches any `"switch"` quoted
  value. But `role="switch"` is the standard **ARIA accessibility role** used by every
  toggle/switch component — `switch` is the one advisory verb that collides with a valid HTML
  role. The guard could not tell the a11y attribute from an advisory label. Same
  over-/under-matching class as the earlier `ci_guards` tuning RCAs (B12/B13).
- **Fix:** added a negative lookbehind to `_ADV_QUOTED` —
  `(?<!role=)["']{_ADV_WORD}["']` (`scripts/ci_guards.py`) — so a quoted advisory word
  **immediately preceded by `role=`** is exempt, while a standalone advisory value like
  `"switch"` (not an ARIA role) is still caught. Verified: full guard now exits 0; the
  notification page passes.
- **Prevention:** `backend/tests/unit/test_ci_guards.py` gains two regression tests run as a
  subprocess against planted fixtures — `test_aria_role_switch_is_not_flagged` (asserts
  `role="switch"` is NOT flagged) and `test_standalone_switch_value_still_flagged` (asserts a
  bare advisory `"switch"` IS still caught, proving the lookbehind did not weaken detection).
- **Phase/area:** CI tooling / compliance net for non-negotiable #1 (advisory verbs). Found
  during the B20/B31 slice; not a field incident.

### 2026-06-06 — AI premium budget hard-cap was check-then-act → concurrent spillovers could overshoot the $9.50/day cap (B18)

- **Symptom:** found in the Phase-3 governance review (tracked as B18, not a field
  incident). `budget_guard` did `GET key` → compare to cap → `yield` → `INCRBYFLOAT`
  **after** the guarded call. Under concurrency, N premium Sonnet spillovers could all
  read `current < $9.50`, all pass the gate, all call, all increment — overshooting the
  hard money cap by up to (N−1) calls' cost. The free call-count cap had the same race.
- **Root cause:** a check-then-act (TOCTOU) sequence on a shared Redis counter — the read
  and the increment were separate round-trips with the network call in between, so the
  decision was made on a stale value. The same non-atomic-critical-key class as the
  refresh-rotation `GET`-then-`DELETE` RCA (2026-05-19), where the rule "any Redis
  check-then-act on a critical key must use an atomic primitive" was set but not yet
  applied to the budget counter.
- **Fix:** `budget_guard` reworked to **incr-then-rollback**
  (`backend/dhanradar/budget.py`): reserve the per-call amount up front with an atomic
  `INCRBYFLOAT`, admit only if the value that existed BEFORE our reservation was under the
  cap (so concurrent callers observe each other's reservations — at most one is admitted
  past the boundary, the irreducible single-call cost). On reject the reservation is
  released; on a failed call it is fully rolled back; on clean exit it is reconciled to the
  caller's actual recorded spend. Release/reconcile go through `_adjust_quietly` (swallows +
  logs a Redis error so it never masks the caller's real outcome; the daily EXPIREAT is the
  self-heal backstop). A warning fires when a premium call's actual cost exceeds the reserve
  (`_PREMIUM_RESERVE_USD = $0.20`), since the concurrency guarantee needs the reserve to be
  an upper bound. No Lua used — `INCRBYFLOAT` + `SET NX EXAT` are atomic and fakeredis-safe.
- **Prevention:** `backend/tests/unit/test_budget.py` (now 21) adds a real
  `asyncio.gather` race that admits **exactly one** caller from one reservation of headroom
  (this test FAILS against the old check-then-act code — a positive control), a
  release-on-reject test (counter never left inflated), and a Redis-failure-on-rollback
  test (original exception still propagates). The "atomic primitive for critical Redis
  keys" rule now has a second enforced instance. Independent adversarial review (Sonnet
  takeover — Codex companion lacked model entitlement) ACCEPT-WITH-CONDITIONS; all four
  conditions were applied in the same session before commit.
- **Phase/area:** Phase 3 / AI gateway — budget governor (B18). Load-bearing path;
  adversarial sign-off completed inline.

### 2026-06-06 — Navigation off the brand guideline: unicode-glyph icons + missing a11y (aria-current / focus ring)

- **Symptom:** UI-guideline audit of the nav (sidebar) against `docs/ui-system/brand/mockups/app.jsx`
  and `docs/ui-system/components/Sidebar.md`. The sidebar used unicode glyphs (`⊞ ↑ ◐ ◎`) as
  "icons" (off-system, inconsistent stroke/size; `◎`/`◐` are not real icons), had **no
  `aria-current="page"`** on the active item, **no focus-visible ring** on nav links, an
  `aria-label="Main navigation"` instead of the spec's `"Primary"`, and a bare wordmark with
  no logo mark / sub-label (the brand lockup is mark + "DhanRadar" + sub).
- **Root cause:** the shell was scaffolded with placeholder glyphs and minimal markup before
  the brand assets/icon system were wired; "renders a nav" was mistaken for "matches the
  nav guideline". Same config-vs-live gap class as the Geist-font RCA below — the tokens/
  assets existed (`public/brand/icon.svg`) but weren't used.
- **Fix:** `frontend/src/components/ui/AppShell.tsx` rebuilt to use the `lucide-react`
  line-icon set (LayoutDashboard / Upload / Compass / Settings), a single `NavLink` that sets
  `aria-current="page"` + a `focus-visible:ring-royal/40` ring, `aria-label="Primary"`, the
  `public/brand/icon.svg` mark + "Investor Console" sub-label, a "Workspace" section label,
  and Settings pinned to the footer (per the mockup). Public Mood header
  (`src/app/mood/page.tsx`) given the same logo mark; its empty-state `◐` glyph replaced with
  a lucide `Compass`.
- **Prevention:** icons come from one set (`lucide-react`) — no unicode glyphs in product
  chrome. Nav a11y checklist: active item carries `aria-current="page"`, links have a
  focus-visible ring. Recorded in the [[ui-follows-branding-guide]] memory: verify the LIVE
  screen against the brand mockup (icons, lockup, a11y), not just tokens. Deferred (future
  scope, logged not lost): topbar search/⌘K + market-indices ticker + theme toggle + avatar,
  the plan-aware Upgrade card, and the mobile bottom-tab/collapsed responsive variants.
- **Phase/area:** UI launch screens / app shell + navigation.

### 2026-06-06 — Brand font (Geist) specified in tokens but never loaded; Tailwind fontFamily hardcoded (token drift)

- **Symptom:** every screen rendered in the system fallback font, not Geist. Found during the
  UI-guideline review (non-neg #8 = Geist/warm identity).
- **Root cause:** two layers. (a) `tokens.json`/`tokens.css` declared `font-family: 'Geist', …`
  but **no Geist webfont was ever bundled** — `layout.tsx` had only a commented `@font-face`
  placeholder, so the browser fell straight through to `ui-sans-serif`. (b) `scripts/gen-tokens.mjs`
  **hardcoded** the Tailwind `fontFamily` array instead of deriving it from `tokens.json`, so the
  "single source of truth" wasn't single — a font change in the source wouldn't reach Tailwind.
- **Fix:** self-hosted fonts via `next/font` in `src/app/layout.tsx` — Geist Sans + Mono from the
  official `geist` package, Instrument Serif from `next/font/google` — each exposing a CSS var
  (`--font-geist-sans`/`-mono`/`--font-instrument-serif`) referenced first in `tokens.json`
  `type.family`. `gen-tokens.mjs` now derives the Tailwind `fontFamily` from `tokens.json`
  (`famArr()`), so `tokens.css` + `tailwind.tokens.cjs` are both generated from one source.
- **Prevention:** added `npm run check:tokens` (`gen-tokens --check`) which fails if the committed
  generated files drift from `tokens.json`; **wired into CI** (`.github/workflows/ci.yml` — runs
  `check:tokens` instead of silently regenerating). Rule (in [[ui-follows-branding-guide]]):
  verify the brand RENDERS, not just that tokens are configured.
- **Phase/area:** UI launch screens / design-token pipeline + fonts.

### 2026-06-06 — App bricked on "Starting development mocks…": MSW gate had no failure path

- **Symptom:** the app hung forever on the "Starting development mocks…" loading screen
  (observed on `/mood`). Root server state was also corrupted (404 on every route) because a
  `next build` was running concurrently with `next dev` (see next entry).
- **Root cause:** `src/app/providers.tsx` did `initMocks().then(() => setReady(true))` with **no
  `.catch` and no timeout**. If `worker.start()` rejected or stalled (stale/"waiting" service
  worker from a prior session, integrity warning, transient SW lifecycle), the rejection was
  unhandled, `setReady(true)` never fired, and the whole app was trapped on the loader with no
  recovery — a single point of failure with no fallback.
- **Fix:** `providers.tsx` mock gate now `.catch`es (logs) and `.finally(setReady(true))`s, with a
  3s timeout backstop — the app renders even if the mock layer fails, and logs the error.
- **Prevention:** any "block the UI until X initialises" gate must fail OPEN (timeout + catch),
  never trap the user on an init step. App must never hang on the mock/dev-only layer.
- **Phase/area:** UI launch screens / dev mock layer.

### 2026-06-06 — Dev server 404'd every route: `next build` run concurrently with `next dev` corrupted `.next/`

- **Symptom:** the running dev server returned 404 for `/`, `/mood`, `/settings/notifications`,
  `/dashboard` (while still serving `public/` files like `/mockServiceWorker.js`); the browser
  showed a stale shell. A fresh dev server also failed to reach "Ready". Process list showed a
  `next build` (PID) running alongside two `next dev` servers.
- **Root cause:** `next build` and `next dev` both write to the same `frontend/.next/` directory;
  running them simultaneously corrupts the dev route manifest → all-route 404. Triggered by the
  "optional `npm run build`" testing suggestion being run while `npm run dev` was up.
- **Fix:** stop all frontend node processes, `Remove-Item -Recurse -Force frontend/.next`, start a
  single `npm run dev` (Ready in ~2s, all routes 200).
- **Prevention:** never run `next build` and `next dev` together (shared `.next/`). For a build
  sanity check, stop dev first. Test-steps guidance corrected to say so.
- **Phase/area:** UI launch screens / local dev environment.

### 2026-06-06 — CAS upload: PDF password captured in the UI but never sent to the backend

- **Symptom:** found in the UI launch-screens review (not a field incident). The CAS
  upload page (`frontend/src/app/(app)/mf/upload/page.tsx`) collects a "Password
  (optional)" field and tells users CAS PDFs are "usually password-protected", but
  `useUploadCas` built the `FormData` with only the `file` part — the password was held in
  React state and silently dropped. Any password-protected CAS (the common case) would
  parse-fail with no usable signal to the user.
- **Root cause:** the upload hook's `mutationFn` took a bare `File` and never threaded the
  password through, while the backend `POST /mf/upload/cas` has accepted an optional
  `password: Form()` since Phase 5 (`backend/dhanradar/mf/router.py:53`, stashed to a
  short-lived Redis key for the parser). The frontend contract drifted from the backend
  form contract — "field shown" was mistaken for "field wired", the same exists≠applied
  class as the auth rate-limiter RCA (2026-05-19).
- **Fix:** `useUploadCas` now takes `{ file, password? }` and appends `password` to the
  `FormData` only when set (`frontend/src/features/mf/api.ts`); the upload page passes
  `password || undefined` and now renders the field via the shared `Input` component
  instead of a hand-rolled `<input>`.
- **Prevention:** when a screen renders an input, the review checklist now asks "is this
  value actually in the request payload?" — a visible-but-unsent field is a silent
  data-loss bug. Longer-term, generating the FE request types from the backend OpenAPI
  (already on the Stage-2 dependency list) would make a dropped form field a type error.
- **Phase/area:** Phase 5 (MF) / UI launch screens.

### 2026-06-06 — Phase-7 §5: RequireConsent returned 403 to anonymous (fragile 401-before-403 contract) + container memory over budget

- **Symptom:** the Phase-7 §5 pre-deploy adversarial gate found (a) `RequireConsent`
  (the fail-closed DPDP consent gate) raised **403 consent_required** for an ANONYMOUS
  caller — relying on each route to add its own `is_anonymous → 401` check first (the MF
  route does; a future route adopting `Depends(RequireConsent(...))` directly would not),
  a fragile contract and a mild 401-vs-403 route-topology oracle; (b) the docker-compose
  memory limits summed to 3572M, over the architecture §A6 ~3 GB budget.
- **Root cause:** (a) the gate deferred the auth-ordering decision to its callers instead
  of being safe-by-default — the same fail-open-by-construction class as the ESLint matrix
  (B10) and the `/test` tier-gate-before-auth (Phase 6 RCA): a primitive that is only
  correct when every caller remembers to wrap it. (b) limits were set generously
  per-service at scaffold time without summing against the budget.
- **Fix:** (a) `RequireConsent.__call__` now raises **401 not_authenticated** for anonymous
  as its first operation, before any DB read (`backend/dhanradar/deps.py`); the 401-before-403
  ordering now holds without caller discipline. `UserContext.consented_purposes` annotated as
  an intentionally-unpopulated non-gate (fresh-DB read is the only consent path). (b) limits
  trimmed to exactly **3072M** (postgres 1024 / fastapi 512 / nextjs 448 / batch 256 /
  mood 192 / misc 192 / redis 256 / beat 64 / cloudflared 128) (`docker-compose.yml`).
- **Prevention:** rule — a security/consent gate primitive must be safe-by-default (deny in
  the correct order on its own), never correct-only-if-the-caller-guards-first; the same rule
  that produced the `/test` and ESLint fixes. `test_consent.py` asserts the 401 path; the
  remediation was re-verified by an independent adversarial pass (ACCEPT, no bypass). A
  compose memory-sum check is part of the Phase-7 constraint audit.
- **Phase/area:** Phase 7 / §5 pre-deploy adversarial gate + constraint audit (not a field
  incident).

### 2026-06-06 — Notification (Phase 6) review-found defects: tier-gate-before-auth 402-leak + Telegram HTML injection in text body

- **Symptom:** pre-merge governance review of the Phase-6 Notification module found
  (a) `POST /notifications/test` declared `Depends(RequireTier("pro"))`, which runs
  before the route body — so an **anonymous** caller received `402 upgrade_required`
  instead of `401 not_authenticated` (anonymous defaults to `tier="free"`, rank 1 <
  pro), leaking that the endpoint exists / is Pro-gated and contradicting the route's
  own "auth first" contract; (b) message templates HTML-escaped dynamic values
  (`scheme_name`, `report_url`) only in the email `html` part — but the `text` part is
  rendered by Telegram with `parse_mode=HTML`, so a crafted scheme name could inject
  markup into the delivered Telegram message.
- **Root cause:** (a) FastAPI resolves all `Depends` **before** the function body, so a
  body-level `_require_auth(user)` can never precede a dependency-level tier gate —
  `RequireTier` treats anonymous as `free` and 402s first by construction. (b) the two
  output parts (`text` for Telegram-HTML + email-plaintext, `html` for email) were
  escaped inconsistently — the `text` part's double duty as a Telegram-HTML payload was
  missed.
- **Fix:** (a) removed the `RequireTier` dependency from `/test`; the gate is now invoked
  in-body **after** the auth check — `_require_auth(user)` (401) then `await _pro_gate(user)`
  (402) (`backend/dhanradar/notifications/router.py`). (b) `scheme_name`/`report_url` are
  now `_esc`-escaped in the `text` body as well as the `html`
  (`backend/dhanradar/notifications/templates.py`). Also added a `^-?\d{1,20}$` pattern on
  `telegram_chat_id` to reject garbage at write time.
- **Prevention:** rule — when an endpoint must distinguish 401-then-402, the auth check
  must run **before** the tier gate, which means in-body (or an auth dependency ordered
  first), never relying on `RequireTier` to imply authentication. Rule — any value
  interpolated into a Telegram `parse_mode=HTML` payload is HTML and must be escaped, even
  when the same string is also an email plain-text part. Both are covered by the new unit
  tests (`tests/unit/test_notifications.py`) + the 402/401 integration cases.
- **Phase/area:** Phase 6 / Notification — pre-merge Security review (not a field incident).

### 2026-06-05 — DPDP gates fail-open: RequireConsent was a pass-through stub; deletion_requested_at unenforced (B3/B4)

- **Symptom:** `RequireConsent` (the per-purpose DPDP consent gate) always returned
  `None` — so the first data-processing route to adopt `Depends(RequireConsent("…"))`
  would have silently processed data for users who never consented (non-negotiable #10).
  Separately, `auth.users.deletion_requested_at` existed but nothing checked it, so a
  user who requested erasure could still log in.
- **Root cause:** both were deferred to "the later Consent module" and left as no-ops
  rather than fail-closed primitives — the same fail-open-by-default trap as the ESLint
  matrix (B10): a gate that defaults to *allow* is worse than no gate, because it reads
  as enforced.
- **Fix:** `RequireConsent` now validates the purpose against the canonical taxonomy
  (`mf_analytics|ai_insights|marketing|portfolio_sync|behavioral_nudges`) at construction
  and, on call, reads the grant FRESH from `users.dpdp_consents` (no cache, so a revoke is
  honoured immediately) — missing/false/anonymous → 403 `consent_required`
  (`backend/dhanradar/deps.py`). `authenticate_user` denies login for a deletion-pending
  account (403 `account_deletion_pending`, checked after password verify so it is not an
  enumeration oracle; `backend/dhanradar/auth/service.py`).
- **Prevention:** added `backend/tests/unit/test_consent.py` (11-row `_consent_granted`
  truth table + anonymous/granted/denied gate cases + the two login cases) — a future
  regression to fail-open trips the suite. Default-deny is the rule for every new gate.
- **Phase/area:** Phase 2 / Auth + DPDP enforcement primitives (B3/B4). The full Consent
  module (audit log, grant/revoke endpoints, CMP, erasure, cache+flush) remains a later
  slice; only the gate primitives were hardened here.

### 2026-06-05 — Feature import-isolation silently fail-open for new features; apiClient base-path strippable; ScoreRing triple a11y announce (B10)

- **Symptom:** post-merge Architect/UI review of the Stage-2 frontend found (a) `.eslintrc.json`
  enforced module isolation via a hand-enumerated N×N `import/no-restricted-paths` matrix listing
  only **7** features — but the repo had **9** feature folders, so `dashboard` and `mf` (the launch
  wedge) had **zero** cross-feature import enforcement; (b) `apiClient` derived `API_BASE` from
  `NEXT_PUBLIC_API_URL` with no check, so a misset value without `/api/v1` silently made every
  request miss the versioned base path (and the `(cond && val) ?? '/api/v1'` form returned the
  boolean `false` when `process` was undefined); (c) `ScoreRing` announced its name three times
  (`<figure aria-label>` + `role="img"` SVG + `sr-only` span).
- **Root cause:** the isolation rule was **enumerated, not generic** — adding a feature required
  hand-editing the matrix, which nobody did, so it failed open by construction. The apiClient
  trusted env input for a non-negotiable contract. The ScoreRing a11y model layered three naming
  mechanisms instead of one.
- **Fix:** (a) replaced the 42-zone matrix with a single generic `eslint-plugin-boundaries`
  `boundaries/dependencies` rule that classifies every `src/features/*` folder and forbids importing
  another feature's internals — auto-covers current and future features (`frontend/.eslintrc.json`);
  verified clean tree passes AND a planted `dashboard → mf/api` import is flagged. (b) `apiClient.ts`
  now throws at module load if `NEXT_PUBLIC_API_URL` is set but does not end with `/api/v1`, strips a
  trailing slash, and uses `||` (fixes the `false` fallback). (c) `ScoreRing.tsx` made the SVG
  decorative (`aria-hidden` + `focusable="false"`) and gives the figure a single accessible name via
  one sr-only `<figcaption>`.
- **Prevention:** isolation is now enforced by element-type, not by an enumerated list, so a new
  feature cannot quietly escape it. Base-path is fail-closed at startup. Boundaries rule has a
  positive-control verification recorded in the review trail.
- **Phase/area:** Stage 2 / frontend foundation (B10).

### 2026-06-05 — ci_guards advisory scan had residual coverage gaps after B12 (B13)

- **Symptom:** the B12 fix (above) hardcoded only **3** token files for the non-code advisory scan
  and skipped the **whole** `scoring/` dir; other `.json/.yaml/.css/.html` label assets were
  unscanned, and `_ADV_SKIP` matched bare `not`/`guard` substrings that could mask a real advisory
  verb sharing a line.
- **Root cause:** B12 closed the *known* leak (tokens.json) by enumerating the known files rather
  than scanning the asset *class*; the skip-list used over-broad tokens; the scoring skip was
  dir-wide, exempting any future engine code there.
- **Fix:** `scripts/ci_guards.py` now walks **all** `.json/.yaml/.yml/.css/.html` (+ config
  `.cjs/.js`) under `frontend/` and `backend/dhanradar/` (minus `node_modules/.next/__pycache__`);
  `_ADV_SKIP` dropped the bare `guard`/`not` tokens for anchored phrases (`must not|do not|cannot`,
  `guardrail`); the scoring skip narrowed from `"scoring" in p.parts` to `ranking_configs*` files
  only.
- **Prevention:** added `backend/tests/unit/test_ci_guards.py` — runs the real guard as a subprocess
  against planted advisory fixtures (camelCase key in a `.json`, quoted verb in a `.css`) and asserts
  it fails; plus a clean-tree baseline. The guard's own coverage is now regression-tested.
- **Phase/area:** CI tooling / compliance net for non-negotiable #1 (B13).

### 2026-06-05 — Advisory verbs in design tokens passed CI (guard never scanned token files + regex too narrow)

- **Symptom:** post-merge UI governance review found `frontend/styles/tokens.json` shipped a
  `signal` block with advisory labels `Strong Buy / Buy / Hold / Avoid` (+ numeric score-band
  cutoffs) and an `amber.role: "Warning, hold"` comment — on `main`, having passed CI. Violates
  non-negotiable #1 (no advisory vocabulary anywhere) and ties labels to numeric bands (vs
  `FINAL_SCORING_SPEC` §4.2 rule-table derivation).
- **Root cause (two compounding gaps):** (a) **Scope** — `scripts/ci_guards.py`'s advisory scan
  only covered `backend/dhanradar` + `frontend/src` with code extensions, so it **never scanned
  `frontend/styles/tokens.json`** at all (`frontend/styles` is outside `frontend/src`; `.json` is
  outside `CODE_EXT`). (b) **Pattern** — even where it scanned, the regex `\b(strong_buy|caution)\b`
  was **snake_case only**, missing the camelCase key `strongBuy` and the strings
  `"Strong Buy"/"Buy"/"Hold"/"Avoid"`. Either gap alone would have let the block through.
- **Fix:** removed the `signal` block from `tokens.json`; changed the amber role to
  "Warning / attention state"; re-ran `gen:tokens` (regenerated `src/styles/tokens.css` +
  `tailwind.tokens.cjs`); verified zero advisory verbs remain in tokens/generated files. The
  `ScoreRing` "NEVER: strong_buy|buy|hold|caution|avoid" string is a guardrail comment, not usage.
- **Prevention (DONE, B12):** `ci_guards.py` advisory detection broadened to camelCase / Title /
  spaced / quoted-label / object-key forms, **and the scan now includes the design-token files**
  (`frontend/styles/tokens.json` + generated `tokens.css`/`tailwind.tokens.cjs`) — closing both the
  scope and pattern gaps. Verified: the broadened guard catches all four old `signal` lines; prose /
  guardrail comments stay clean. Residual coverage gaps (scan all non-code assets, not 3 hardcoded;
  tighten the skip-list) tracked as **B13**.
- **Phase/area:** Stage 2 Steps 2-4 (frontend tokens) / post-merge governance review.

### 2026-05-19 — Auth slice: rate limiter built but unwired; refresh rotation non-atomic

- **Symptom:** found in pre-merge security review of the Phase-2 Auth slice (not a field incident). (a) `RateLimit` dependency existed in `ratelimit.py` but was attached to no route → `/auth/login` had no brute-force throttle. (b) `rotate_refresh_token` did `redis.get` then `redis.delete` → two concurrent uses of one refresh token could both succeed, defeating reuse detection.
- **Root cause:** (a) limiter authored as a reusable dependency but the wiring step was never done — "exists" was mistaken for "applied". (b) read-then-delete is not atomic; the reuse-detection invariant requires single-consumer semantics.
- **Fix:** (a) `Depends(_rl_login/_rl_signup/_rl_refresh/_rl_totp)` wired onto the auth endpoints, keyed by `CF-Connecting-IP` (XFF is client-spoofable behind the tunnel) — `auth/router.py`, `ratelimit.py:_get_client_ip`. (b) atomic `redis.getdel(key)` + owner-match assert — `auth/service.py rotate_refresh_token`. Plus adversarial-gate fixes: logout access-jti revocation, webhook event-id idempotency, exact-plan-id map, password `max_length`.
- **Prevention:** a security control is not "done" until it is wired to a route AND exercised by a test (e2e auth test owed before deploy — Phase 7 §5). Rule: any Redis check-then-act on an auth-critical key must use an atomic primitive (`GETDEL`/`SET NX`/Lua), never GET-then-DELETE. Both recorded in `docs/features/auth.md` "Known limitations".
- **Phase/area:** Phase 2 / Auth & Tiering.

### 2026-05-19 — Malformed table row in architecture doc (data being dropped)

- **Symptom:** markdownlint `MD056/table-column-count` at `docs/DhanRadar_Architecture_Final.md:234` — header had 3 columns, the row produced 6; "extra data will be missing" (the cell was being mis-rendered/truncated).
- **Root cause:** the cell contained literal `|` pipes inside an inline code span (`{ status: queued|processing|done|failed }`); markdown's table parser treats `|` as a column separator even inside backticks.
- **Fix:** escaped the pipes as `\|` in that cell — `docs/DhanRadar_Architecture_Final.md:234`.
- **Prevention:** repo `.markdownlint.json` keeps `MD056` enabled (only opinionated/cosmetic rules disabled), so genuinely broken tables keep failing the lint; pipes inside table cells must always be `\|`.
- **Phase/area:** Docs / markdown-lint pass.

### 2026-05-18 — Cloudflare tunnel CNAME mis-targeted to shared-ssh

- **Symptom:** after `cloudflared tunnel route dns dhanradar dhanradar.com`, the `dhanradar.com` DNS record pointed at tunnel `<SHARED-SSH-TUNNEL-ID>` (shared-ssh) instead of the new `dhanradar` tunnel `<DHANRADAR-TUNNEL-ID>`.
- **Root cause:** `cloudflared tunnel route dns <NAME> …` resolves the tunnel using the default `/etc/cloudflared/config.yml` (which is shared-ssh's), ignoring the name argument.
- **Fix:** corrected the DNS record to `<DHANRADAR-TUNNEL-ID>-….cfargotunnel.com` (Cloudflare DNS UI); verified HTTP/2 200 end-to-end.
- **Prevention:** plan + `infra-notes.md` now mandate explicit tunnel **UUID + `--overwrite-dns`** for `route dns`; never rely on the tunnel name when a default config exists.
- **Phase/area:** Phase 1 / Cloudflare tunnel setup.

### 2026-05-18 — pkill self-terminated the SSH session

- **Symptom:** a verification SSH command exited 255 with truncated output during cleanup.
- **Root cause:** `pkill -f "cloudflared-dhanradar/config.yml"` matched the SSH shell's own command line (the pattern appeared in the script text), killing the session.
- **Fix:** re-verified state with a self-safe method.
- **Prevention:** standing rule in plan/infra-notes — never `pkill -f <pattern>` where the pattern can appear in your own command line; enumerate with `pgrep -x cloudflared` and check `/proc/<pid>/cmdline` per pid.
- **Phase/area:** Phase 1 / process cleanup over SSH.
