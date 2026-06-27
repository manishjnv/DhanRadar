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

### 2026-06-28 — B81 PR-2: enabling RLS silently broke a per-request commit-then-read (caught in review)

- **Symptom:** PR-2 added FORCE RLS to `notify.notification_preferences`. `POST /notifications/preferences`
  would then return all-default (empty) prefs after **every** successful save — the write committed, but
  the confirming read returned 0 rows. (Caught by the independent reader-completeness review **before**
  merge, not in prod.)
- **Root cause:** `notifications/service.py::upsert_preferences` commits internally (line 200/208) and
  THEN calls `get_preferences` (line 210) to read back. The per-request `app.user_id` GUC is set with
  `SET LOCAL` (transaction-scoped) by `current_user_or_anonymous`; the internal commit **clears it**, so
  the post-commit SELECT ran with no GUC → the owner policy `user_id = NULLIF(current_setting(...),'')`
  evaluated `user_id = NULL` = FALSE → deny-all → 0 rows → the all-None defaults branch. Invisible
  before PR-2 (no RLS on the table) and invisible to the existing endpoint tests (they run through the
  owner/superuser session via `override_get_db`, which **bypasses RLS**).
- **Fix:** `await set_rls_user(db, user_id)` after the commit, before the `get_preferences` read
  (`notifications/service.py:210`) — re-establishes the owner GUC for the confirming read; a no-op on
  the BYPASSRLS admin engine. Same re-set-after-commit pattern already used in `auth.record_login` and
  the `cas_upload` activity write.
- **Prevention:**
  - **Rule — enabling RLS on a table breaks any per-request path that commits and then reads/writes that
    table again** (the request GUC is `SET LOCAL`, cleared by every commit). When adding a table to
    `RLS_ENFORCED`, grep its readers/writers for **commit-then-touch** in the same request, not just
    cross-user Celery/webhook readers. The multi-commit CAS path uses `rls_user_session` (re-applies the
    GUC on every `after_begin`) for exactly this reason; single request paths re-call `set_rls_user`.
  - Endpoint tests via `override_get_db` run as the **owner (RLS-bypassing)** session, so they will NOT
    catch this class — the dedicated app-role (`app_session`) RLS tests are the only gate. Don't claim an
    RLS-touching endpoint safe on the HTTP tests alone.
- **Phase/area:** Backend — B81 PR-2 RLS (signal/notify/auth/compliance) + the per-request GUC lifecycle.

### 2026-06-27 — B81 RLS (#395) auto-merged to main with a RED backend suite (`backend` is not a required check)

- **Symptom:** B81 PR-1 (#395, RLS on the 8 mf.* tables) was opened with auto-merge armed. The live-PG `backend` job FAILED (7 RLS-induced test regressions), but the PR **auto-merged to main anyway** at the pre-fix commit — main's backend suite went red. The fix (set_rls_user in the B80 app-role tests + patch `admin_task_session` in the rewired-task unit tests) had been pushed to the branch, but only AFTER the merge had already fired.
- **Root cause:** TWO things. (1) **`backend` is not a required status check** on the branch-protection rule — only `guards`/`migrations` gate the merge — so `gh pr merge --auto` fired the moment those (plus the path-filtered `frontend`) were green, regardless of `backend`/`lint` (both intentionally advisory/`continue-on-error`). All four prior load-bearing PRs (#390/#392/#393/#394) had `backend` pass *before* the merge, so this gap was invisible until a PR's `backend` genuinely failed. (2) The 7 regressions themselves: enabling FORCE RLS on a table breaks every test that reads/writes it without an `app.user_id` GUC — the B80 app-role tests (UPDATE/DELETE matched 0 rows → the append-only trigger never fired → "DID NOT RAISE"; INSERT hit `WITH CHECK`), and unit tests that `patch("dhanradar.db.TaskSessionLocal")` for the 5 Celery tasks B81 rewired to `admin_task_session` (the patch no longer intercepted → real connection, no test data).
- **Fix:** fix-forward — cherry-picked the test fixes onto main as #396 and **merged it MANUALLY only after confirming `backend` was green** (4m2s). `test_app_role_least_priv` now calls `set_rls_user(app_session, owner_id)` before each app-role op on an RLS table (re-set after each rollback — SET LOCAL resets); `test_mf_module`/`test_mf_tracking`/`test_mf_alerts` patch `admin_task_session` instead of `TaskSessionLocal`. Backend green on main again.
- **Prevention:**
  - **Make `backend` (and `migrations`) REQUIRED status checks** on the `main` branch-protection rule, so `--auto` can never merge a red test suite. Until that's set, **do not arm auto-merge for a backend-touching PR — wait for `backend` green, then `gh pr merge` manually.** (Founder action: flip the branch-protection setting; tracked in BLOCKERS.)
  - **Enabling RLS on a table is a breaking change for every test that touches it without a GUC** — when adding a table to `RLS_ENFORCED`, grep its ORM model + raw-SQL readers across `tests/` and either set the GUC (per-user) or patch the bypass session (the rewired Celery tasks). The live-PG `backend` job is the only gate that catches this — never claim an RLS PR done on local py_compile/ruff alone.
- **Phase/area:** Backend — B81 RLS (#395) + the CI required-check gap.

### 2026-06-27 — B80 de-superuser shipped (#393) granting the WRONG schema set → a latent prod outage on activation

- **Symptom:** the B80 PR (#393, merged) de-superusered the runtime DB role to `dhanradar_app` and passed CI (the 6 least-priv tests + the real-Postgres `migrations` job were all green). An independent post-merge review found that migration `0051`'s grant list (and the `01_init.sql` grant lists) granted the **aspirational** 17-schema architecture list, NOT the schemas migrations actually create. **7 real schemas the app/Celery write — `audit`, `billing`, `bse`, `concepts`, `education`, `notify` (typo'd `notif`), `signal` — got ZERO grants** (~11 phantom schemas granted instead). Nothing broke yet only because the runtime app password was unset, so `config.database_url` silently fell back to the owner/superuser. The moment a deploy set `DHANRADAR_APP_DB_PASSWORD` and switched to `dhanradar_app`, **every query into those 7 schemas would `permission denied` → prod outage** — and the fail-open fallback would have masked it as "running fine (as superuser)."
- **Root cause:** the grant list was **copied from the aspirational schema list in `01_init.sql`** (17 forward-looking module schemas, incl. a `notif`/`notify` typo) instead of being derived from the schemas migrations actually create (13). CI did not catch it: the `migrations` job ran the grants successfully because `01_init.sql` pre-creates the phantom schemas as empty stubs (so granting on them doesn't error), and the `backend` pytest job's least-priv tests used **conftest's** (correct) grant list and only exercised the `mf` schema — so neither job ever queried the 7 missing schemas **as `dhanradar_app`**. The fail-open fallback (unset password → superuser) hid the gap on every environment that hadn't set the password.
- **Fix:** centralized the real schema set in `backend/dhanradar/db_schemas.py::APP_SCHEMAS` (the 13, verified via `CREATE SCHEMA` across `alembic/versions/` + every model `__table_args__`). New follow-up migration `0052_app_db_role_grants_real_schemas.py` GRANTs `dhanradar_app` on all 13 (USAGE + DML + sequences + EXECUTE + future-table `ALTER DEFAULT`), each guarded by `to_regnamespace`, and **REVOKEs UPDATE/DELETE on the append-only audit ledger** (`audit.*` + `compliance.ai_recommendation_audit`) so the least-privilege role can write+read but never mutate audit (SEBI 7-yr / DPDP). `01_init.sql` grant lists replaced with a guarded DO-loop over the 13. `config.py model_post_init` now **fail-closed**: outside dev/test/ci an unset `DHANRADAR_APP_DB_PASSWORD` raises at boot (mirrors the B48 consent kill-switch) instead of silently reverting to superuser. `conftest` hard-sets the test password (an empty env defeated `setdefault` → false-green) and derives its grant block from `APP_SCHEMAS`.
- **Prevention:**
  - **The regression test that would have caught it** (`test_app_role_can_read_every_app_schema`): as `dhanradar_app`, SELECT a table in **every** schema that has tables, and assert `APP_SCHEMAS == the schemas that actually have tables`. This fails loudly for any ungranted schema or list drift (incl. a `notif`/`notify` typo). Plus a `NOBYPASSRLS` assertion and an audit-immutability (`has_table_privilege`) assertion.
  - **One source of truth for the schema list** (`db_schemas.APP_SCHEMAS`) that the migration (inlined, comment-synced), `01_init.sql` (comment-synced) and the conftest/test (imported) all reference — no more copying an aspirational list.
  - **Fail-closed, not fail-open, for a security posture:** a missing security credential must refuse to boot in prod, never silently downgrade with only a WARN. A fail-open fallback hides exactly the misconfiguration it should surface.
  - **A security change isn't proven by "CI green" when CI exercises a different code path than prod** — the least-priv role must be tested against the *real* schema set, not a fixture subset.
- **Phase/area:** Backend — DB role hardening (B80), `dhanradar_app` grants + migrations + `config.py` boot guard.

### 2026-06-27 — Calculator hub hero search + quick-category chips were inert (shipped as preview, never wired)

- **Symptom:** on `/calculators`, the hero **search box** and the **quick-category chips** directly under it (Mutual Fund / Tax / Retirement / Goal Planning / Loan / General Finance) did nothing — typing didn't filter, clicking a chip only re-coloured it. Confusing because the category **cards** lower down (S3) and the **filter chips** (S4) *did* work, so the page looked half-functional.
- **Root cause:** the hub (`CalculatorHub.tsx`, PR #350) shipped as a **pure-UI preview** and the `Hero` primitive was never wired. `Hero` (`frontend/src/components/calculators/ui.tsx`) rendered a static `<input>` with a literal `// inert placeholder — search wired later` comment (no `value`/`onChange`) and chips that only set a **local** `active` index for highlight — the selection never lifted to the hub's `filter` state. A later pass (RCA 2026-06-26) wired the S3 cards + S4 chips, but **missed `Hero`** precisely because it's a separate component holding its *own* local state, so the hub's working `filter` never reached it. tsc/lint/guards were all green the whole time — an inert-but-rendered control is invisible to every deterministic gate.
- **Fix:** made `Hero` controlled — added `searchValue` / `onSearchChange` / `onSearchSubmit` / `onSelectCat` / `activeCat` props; the input lives in a `<form role="search">` (Enter jumps to results) and chips call `onSelectCat` and highlight from `activeCat` (`frontend/src/components/calculators/ui.tsx`). `CalculatorHub` added a `query` state + `matchesQuery`; a search spans **all** calculators and overrides the chip filter, scrolls to the results on the first keystroke, and updates the count/empty-state; hero chips reuse `selectCategory` (which clears any active query) (`frontend/src/components/calculators/CalculatorHub.tsx`). PR #385.
- **Prevention:**
  - **A control that renders but does nothing is as misleading as a hidden one** — the no-suppress rule's cousin. When a section ships as "pure-UI preview", every inert interactive control must carry a visible `// TODO: wire` marker and be listed in the page's follow-up, so a later "wire it up" pass cannot silently miss one.
  - **Lifting smell:** a child component (here `Hero`) owning local state for a control whose *result* belongs to the parent (the hub's filter) is the bug shape — lift the state to the parent and pass handlers down. When wiring interactivity, audit **every** sub-component of the page, not just the obviously-interactive ones.
  - **Cheap grep before declaring an interactive page done:** look for inert inputs (a `placeholder=` with no `value=`/`onChange=`) and tell-tale comments (`wired later`, `visual only`, `inert`). The deterministic gates (tsc/lint/guards) will not catch a dead control.
- **Phase/area:** Frontend — Calculator Hub (`/calculators`) hero search + quick-category chips.

### 2026-06-25 — Portfolio V1 hydration mismatch (#418 → #422): SVG `<title>` rendered empty on server, filled on client

- **Symptom:** the just-deployed `/mf/portfolio` (Portfolio Command Center V1) threw React **#418** (hydration failed) → **#422** (Suspense boundary switched to client rendering) in production, at every viewport. The sister page `/mf/leaderboard` — same `MaybeShell` + `Suspense` + flat-route pattern — was clean. The page still rendered correctly (React recovered by client-rendering the boundary), so it was non-breaking but a real quality regression. Did **not** reproduce in local `next dev`.
- **Root cause:** the allocation **`Donut`** primitive (`frontend/src/components/mf/portfolio/ui.tsx`) rendered an SVG tooltip `<title>{a.name}: {a.pct}%</title>` inside each `<path>`. **React 18 treats `<title>` as hoistable document metadata**, so its *server* renderer emitted `<title></title>` (empty) while the *client* hydrated it as an SVG title with text (`<title>Equity: 96.5%</title>`) — a text-content mismatch on every arc, which fails hydration for the enclosing Suspense boundary. Why it was invisible locally: **`next dev` gates rendering behind MSW** ("Starting development mocks…"), so dev never SSRs the dashboard content (7.4 KB shell, fully client-rendered) — no SSR/CSR pair to mismatch. Prod has no MSW gate, fully SSRs (133 KB), so the mismatch only surfaces in a production build. Leaderboard has no `Donut`/`<title>`, which is exactly why it was clean.
- **Fix:** removed the `<title>` child from the donut `<path>` elements (`frontend/src/components/mf/portfolio/ui.tsx:91-96`). Zero functional/visual loss — the donut `<svg>` is already `aria-hidden="true"` (so the title gave no accessibility value) and the allocation name/percent are shown in the legend and rows beside the chart. Diagnosis was a normalized prod **SSR-HTML vs client-DOM** diff (strip comments/whitespace, sort attributes, convert hex/8-digit-hex→rgb(a), decode HTML entities) to isolate the one genuine divergence from browser cosmetics.
- **Prevention:**
  - **Never put `<title>` (or `<meta>`/`<link>`/document-`<title>`) inside an SVG that React renders** — React 18 metadata-hoists it and you get an SSR-empty/CSR-filled hydration mismatch. Use a sibling visible label or a wrapping element's `aria-label`/`role="img"` for SVG accessibility instead. (Decorative charts should stay `aria-hidden`.)
  - **`next dev` will NOT reveal hydration bugs on MSW-gated client pages** — dev serves a mock-loading shell and client-renders, so SSR/CSR never pair up. To repro a prod-only hydration error, diff the prod **SSR HTML (curl)** against the prod **client DOM (Playwright `outerHTML`)** after normalizing away browser cosmetics (attribute order, hex↔rgb(a), entity encoding, style-prop order); the first surviving diff is the real mismatch.
  - **A new page that imports a NEW shared primitive (here `Donut`) needs a quick prod-build hydration check**, not just `tsc`/guards (which are both green here) — the deterministic gates do not catch SSR/CSR divergence.
- **Phase/area:** Frontend — Portfolio Command Center V1 (`/mf/portfolio`), shared `Donut` primitive.

### 2026-06-23 — Admin AI dashboard + cost pages 500: budget snapshot called `.decode()` on a `str` Redis value

- **Symptom:** `GET /admin/ai` ("Could not load AI dashboard") and `GET /admin/ai/cost` ("Could not load cost data") both returned 500 in prod. Logs: `AttributeError("'str' object has no attribute 'decode'")`, unhandled, on every request to those two routes. Every OTHER admin AI-Ops page (versions / prompts / eval / safety / feedback) returned 200. Surfaced while testing the just-shipped latency PR (#325).
- **Root cause:** a **pre-existing latent bug** in the budget governor, NOT the latency PR. The shared Redis client is built with `decode_responses=True` (`backend/dhanradar/redis_client.py:66`), so `redis.get()` returns `str` in production. But `compute_budget_state` (`backend/dhanradar/budget.py:373-374`) did `free_raw.decode()` / `premium_raw.decode()`, assuming `bytes`. It only crashes when the budget keys are *populated* (truthy) — `ai:budget:free:today="0"`, `ai:budget:premium:today="0.0014…"` (both non-empty `str` once `budget_guard` has run that day) → `"0".decode()` → AttributeError. The unit tests passed only `bytes` literals (`b"10"`), matching the wrong `bytes | None` annotation, so CI stayed green while prod broke. The two crashing pages are the *only* callers of `compute_budget_state` (via `_read_budget_snapshot`), and the budget snapshot is computed *before* the page's other metrics — so the whole page 500s. The latency PR was innocent: it only ADDED a `read_latency_window` call that sits after the budget snapshot (and correctly uses `int()`/`float()` on `str`, not `.decode()`).
- **Fix:** new `_decode_counter(raw)` helper (`backend/dhanradar/budget.py`) normalises `bytes | str | None` → numeric `str` (`raw.decode() if isinstance(raw, bytes) else str(raw)`, None/empty → `"0"`), mirroring the guard already present at `get_effective_caps` (line ~181). `compute_budget_state` now calls it for both counters; signature widened to `bytes | str | None`. Read-only display path — the enforcement path (`budget_guard`, cap logic, spend accounting) is untouched (Tier-B confirmed).
- **Prevention:**
  - **Redis returns `str`, not `bytes`, everywhere in this codebase** (`decode_responses=True`). Never call `.decode()` on a `redis.get()` result without an `isinstance(raw, bytes)` guard. Grep `\.decode\(\)` near any `redis.get` when touching Redis-reading code.
  - **Regression tests added** that pass the *prod* type (`str`): `test_compute_budget_state_accepts_str_values_from_decode_responses` + `test_compute_budget_state_str_and_bytes_agree` (`backend/tests/unit/test_budget_caps_override.py`) — both fail on the pre-fix code. **Lesson: a unit test that feeds the type the test harness invents (`bytes`) instead of the type prod actually produces (`str`) is a false-green** — exercise the real client's return type.
  - **When a function's type annotation says `bytes` but the real caller is a `decode_responses=True` client, the annotation is the lie, not the data.**
- **Phase/area:** Admin AI-Ops console / budget governor read path (surfaced by Phase-3 PR-1 #325).

### 2026-06-23 — Admin "user activity not logged": field wired in the backend but invisible in the detail UI

- **Symptom:** the founder repeatedly reported that the admin Users page showed no user activity ("not logged / not updated"), even after `last_login_at` tracking shipped. The data WAS being recorded — `auth.users.last_login_at` was stamped on every genuine login (verified: real stamps in prod) — but it never appeared where they looked.
- **Root cause:** TWO compounding gaps, neither a data-pipeline bug. (1) **Wired one surface, not all:** PR #319 added `last_login_at` and rendered it in the user-LIST table, but the user-DETAIL view hardcoded `"Last Login: —"` with a stale *"not yet tracked"* tooltip, and `UserDetailResponse` did not even include the field — so in detail the value was always a dash regardless of the data. (2) **No-backfill + persistent sessions:** `last_login_at` (and later `user_activity_log`) is NULL until a user's first *fresh* login after the column was added; an admin browsing on a still-valid session never re-authenticates, so the feed reads empty — which presents as "not logged" when it is actually "no new event yet."
- **Fix:** PR #320 added `last_login_at` to `UserDetailResponse` (`backend/dhanradar/admin/users_schemas.py`) + populated it in `get_user_detail` (`backend/dhanradar/admin/users_router.py`) + bound the detail field to the real value in `frontend/src/app/admin/users/page.tsx` (was a hardcoded `—`). Follow-ups made activity visible from real usage: PR #321 added the `auth.user_activity_log` events table + per-user "Activity" + a global "Recent Activity" feed; PR #323 logged CAS uploads as activity events too (so the feed fills without waiting on rare logins).
- **Prevention:**
  - **When wiring a new backend field, surface it on EVERY view that shows it (list AND detail) and confirm the response SCHEMA includes it** — don't wire one surface and assume the rest. A grep for the field name across the frontend + each `*Response` schema is the cheap check.
  - **Observational, no-backfill fields are NULL until their first triggering event.** Communicate "needs a fresh login/action to populate; empty ≠ broken" in the UI copy and to the operator, so an empty feed isn't read as a failure.
  - **Two traps caught in review this session (recorded so they don't recur — neither shipped):** (a) **FastAPI route ordering** — a literal route (`GET /users/activity`) MUST be declared BEFORE a `/{param}` route (`/users/{user_id}`) or FastAPI matches the literal as the path param and the route is shadowed/unreachable. (b) **UUID path params** — parse the path string to `UUID(...)` (→ 404 on failure) BEFORE querying a `uuid` column; a raw malformed string otherwise raises a Postgres `invalid input syntax for type uuid` (500) instead of a clean 404.
- **Phase/area:** Admin Users / user-activity surfacing (PRs #319–#323).

### 2026-06-22 — Compose memory-budget guard left red on main: mem-limit bump didn't update its own CI cap

- **Symptom:** the `guards` CI job was failing on `main` from PR #315 (2026-06-22) until it was caught a few hours later while pushing PR #317. `scripts/check_compose_memory.py` exited 1: `COMPOSE MEMORY BUDGET FAILED: 3328M > 3200M`. It went unnoticed because the `guards` job was red behind the habitually-red (advisory) `lint` job, and neither blocks merge.
- **Root cause:** PR #315 raised `dhanradar-celery-mood`'s `deploy.resources.limits.memory` 192M→384M (a founder-approved, OOM-RCA-backed fix), taking the total compose footprint to 3328M — over the 3200M cap hard-coded in `scripts/check_compose_memory.py` (`CAP_MB`). The `guards` CI job runs **three** scripts (`ci_guards.py`, `anti_pattern_sweep.py`, `check_compose_memory.py`); when making #315 I verified the live deploy succeeded but ran only an ad-hoc check, not `check_compose_memory.py`, so the cap regression shipped. #315 merged anyway because `guards` is **not a required/blocking check** on `main` (same advisory posture as `lint`), so a real budget-guard regression sat red, masked by the always-red lint.
- **Fix:** raised `CAP_MB` 3200→3456 in `scripts/check_compose_memory.py` (committed on the #317 branch → merged `b8a38fa`), with a note mirroring the 3072→3200 (#269) precedent — the script's own docstring sanctions a deliberate, noted raise. 3328M stays well inside the KVM4 box's ~6 GB headroom. `guards` is green again on the post-merge run.
- **Prevention:** (1) **Any change to a `docker-compose.yml` `mem_limit`/`memory` value must run `scripts/check_compose_memory.py` AND update `CAP_MB` in the same commit** — the cap travels with the budget. (2) **Lesson — the `guards` CI job runs three scripts, not just `ci_guards.py`; running only `ci_guards.py` locally gives false confidence.** Run all three (`ci_guards.py` · `anti_pattern_sweep.py` · `check_compose_memory.py`) before pushing a load-bearing/infra change. (3) **Deeper (flagged for founder):** because `guards` is non-required, a genuine deterministic regression (budget / secret / anti-pattern) can sit red unnoticed behind the always-red `lint`. `guards` is fast (~10 s) and deterministic — making it a **required** status check would convert this class of silent regression into a hard merge block.
- **Phase/area:** CI / infra — compose memory-budget guard; follows the 2026-06-22 mood-worker OOM RCA (the bump that triggered it).

### 2026-06-22 — Mood worker OOM-killed on the first full (Upstox-enriched) snapshot — silent non-persist

- **Symptom:** after activating the Upstox token in prod (mood worker on KVM4), a triggered `compute_mood_snapshot` fetched everything correctly — log showed `upstox_analytics: fetched 3/3 signals` then `mood signals: normalised 10/10 macro signals` — but **no row appeared** in `mood.market_mood`; the public `/api/v1/market/mood` kept serving the prior 12:25 snapshot (8 inputs, no Upstox). The worker log then carried `Task handler raised error: WorkerLostError('Worker exited prematurely: signal 9 (SIGKILL) Job: 0.')`.
- **Root cause:** the `dhanradar-celery-mood` container memory limit was `192M` (`docker-compose.yml` `deploy.resources.limits.memory`), idling at ~118 MiB. Activating Upstox added two new memory costs to the snapshot pipeline: (1) the PCR expiry resolver fetches `/v2/option/contract` (~1,800 Nifty contracts, a multi-MB JSON buffered + parsed by `_parse_expiries`, `backend/dhanradar/market_data/providers/upstox.py`); (2) crossing the `commentary_allowed` gate (≥7 signals) for the first time, so `compute_and_store` now also runs the AI commentary generator + news-sentiment gateway calls. The combined peak crossed 192 MiB → the kernel OOM-killer SIGKILLed the worker mid-`compute_and_store`, before the DB write, so the snapshot silently did not persist. Same failure class as the 2026-06-19 128M trim RCA — this worker has a history of living at its memory edge.
- **Fix:** bumped `dhanradar-celery-mood` memory `192M → 384M` (`docker-compose.yml`, PR #315 → `049ae93`), redeployed. Re-triggered snapshot succeeded: `mood: neutral (11/11 inputs, ok)` in 143 s, worker peaked **203 MiB / 384 MiB** (no OOM), row persisted (`2026-06-22 16:50:21`, 11 inputs), and the public API now serves the FII/DII/PCR drivers. Total dhanradar budget 3136→3328 M, well within the ~8 GiB box headroom.
- **Prevention:** (1) the compose comment now documents the 192M→384M bump + the two reasons (contract parse + commentary path), so a future memory trim sees the cost. (2) **Lesson — a `WorkerLostError SIGKILL` mid-task means OOM, not a code fault; check the container `mem_limit` vs `docker stats` peak before debugging logic.** (3) **Lesson — adding any signal that triggers a previously-dormant heavy path (here, AI commentary at the ≥7-signal gate) changes the worker's memory envelope even if the new signal's data is tiny.** (4) Follow-up improvement (not done): cache the resolved expiry in Redis (TTL ~12 h) so the large `/option/contract` fetch isn't repeated every run.
- **Phase/area:** Market Mood / Upstox activation / celery-mood worker sizing (infra).

### 2026-06-22 — Upstox PCR silently absent — provisional Thursday-expiry guess (NSE Nifty weekly moved to Tuesday)

- **Symptom:** the first live Upstox smoke-test returned only **2/3** macro signals — `fii_flows` and `dii_flows` came back, but `put_call_ratio` was always absent, with no error (it failed soft as designed).
- **Root cause:** `/v2/market/pcr` requires a real, currently-listed option `expiry`; given a non-existent expiry it returns **HTTP 200 with `data: null`** (not a 4xx), which `_parse_pcr` correctly reads as "no signal". The provisional resolver `_nearest_weekly_expiry` (`backend/dhanradar/market_data/providers/upstox.py`) guessed the next **Thursday** — Nifty weekly options' historical expiry day. NSE has since moved the Nifty weekly expiry to **Tuesday**, so the guessed date (`2026-06-25`) was not a live expiry; the real nearest was `2026-06-23` (Tuesday). Confirmed live by querying `/v2/option/contract` and replaying PCR against each real expiry — only the real ones returned data.
- **Fix:** replaced the weekday guess with a real expiry lookup (PR #296 → merged `7de522c`). New helpers in `backend/dhanradar/market_data/providers/upstox.py`: `_parse_expiries` (distinct sorted expiries from `/v2/option/contract`), `_nearest_expiry` (pure; nearest ISO date on/after today — ISO strings sort chronologically), `_fetch_nearest_expiry` (live lookup, fail-soft None). `fetch()` now resolves the expiry and **skips the `/pcr` call entirely** when none resolves (PCR fails soft; FII/DII unaffected). Live result after fix: **3/3** signals, PCR `0.876`.
- **Prevention:** (1) the exchange's own contract list is now the source of truth for the expiry — robust to the Thursday→Tuesday shift and to holiday-shifted expiries; no hard-coded weekday remains. (2) Fixture-based unit tests added in `backend/tests/unit/test_mood_upstox.py`: `_parse_expiries`/`_nearest_expiry` edge cases + a "no expiry resolves → `/pcr` not called, FII/DII still returned" case (no live network in committed tests). (3) **Lesson — a vendor endpoint returning `200 + data:null` for a bad parameter is indistinguishable from "no data" at the parse layer; validate such params against the vendor's own list, don't guess.**
- **Phase/area:** Market Mood / Upstox Analytics provider (PCR).

### 2026-06-21 — Integration of 8 parallel branches surfaced 2 regressions single-branch gates missed

- **Symptom:** each of 8 feature branches passed its own gates, but merging them into one integration branch failed two checks: (1) `ci_guards` flagged `market_data/providers/upstox.py:70` `'Bearer ' auth value (non-neg #4)`; (2) `pytest tests/unit/test_mood_golive.py` raised `ValidationError: snapshot_at Input should be a valid string` (a `MagicMock`).
- **Root cause:** (1) the Upstox branch's gates ran ruff/mypy/pytest but **not** `ci_guards`, so the outbound third-party `f"Bearer {token}"` header was never scanned against the inbound-cookie-auth guard (non-neg #4). (2) The relative-time branch made `get_latest` call `row.snapshot_time.isoformat()`; `test_mood_golive`'s `_make_row` mock (from a different, older branch) never set `snapshot_time`, so it was an auto-`MagicMock` whose `.isoformat()` returned a non-string. Neither defect is reachable until the two branches coexist — single-branch CI is blind to it.
- **Fix:** (1) routed the outbound header through an `_AUTH_SCHEME = "Bearer"` constant so no literal `"Bearer "` appears in source (mirrors `notifications/channels.py`'s Resend header) — `market_data/providers/upstox.py:67-70`. (2) `_make_row` now sets `row.snapshot_time` to a real tz-aware datetime — `tests/unit/test_mood_golive.py:32`.
- **Prevention:** when shipping N parallel branches that touch shared files, **always merge to one integration branch and run the FULL gate suite (incl. `ci_guards` + cross-module pytest) before deploy** — per-branch green is necessary, not sufficient. Run `ci_guards` on every backend branch that adds an HTTP client; outbound third-party `Authorization` headers must use a scheme constant, never a literal `"Bearer "`.
- **Phase/area:** Mood Phase 2 integration / deploy gating.

### 2026-06-21 — Sharpe/Sortino exploded to ±10⁶ on near-flat NAV funds

- **Symptom:** post-deploy spot-check of the new `mf_fund_metrics` risk columns (PR #282) found ~32 funds with `|sharpe_ratio| > 1000`, the worst at **−1,375,258**; some `sortino_ratio` near −1300. All 36 unit tests were green.
- **Root cause:** Sharpe = `(ann_ret − Rf)/vol`. For near-constant NAV series (stale/placeholder AMFI data, annualised vol ≈ `5e-6`) the denominator collapses toward zero and the ratio explodes. The implemented `vol == 0` guard only caught the *exact*-zero degenerate case, not the near-zero neighbourhood. The synthetic unit-test NAV series never had near-zero volatility, so the suite missed it — only real production data exercised the path.
- **Fix:** generalised the zero-vol guard to a minimum-meaningful-volatility floor `_MIN_MEANINGFUL_VOL = 0.0005` (0.05% annualised) in `backend/dhanradar/mf/risk.py:46` — below it, Sharpe **and** Sortino are withheld (NULL) while the measured `volatility_pct` is still stored. Targets the cause (vol → 0), not the symptom (large |Sharpe|), so legitimate low-vol funds keep a real Sharpe. PR #283. Re-ran `mf_metrics_refresh` on KVM4: explosions 32 → 0, Sharpe range now −119…+4.92, ~128 near-flat funds correctly NULL'd.
- **Prevention:** (1) +2 unit tests in `test_mf_risk.py` (microscopic-vol → ratios None + vol stored; real low-vol fund → Sharpe kept and bounded); (2) standing practice — **range-check computed financial metrics against real prod data**, not just hand-picked unit inputs, before claiming done (the live `celery call mf_metrics_refresh` + min/max SQL is what caught it); (3) MF-analytics §20 codified in code comments — fail toward *withholding* a number, never emit a garbage rate.
- **Phase/area:** Phase 5 / MF risk-adjusted analytics (B74).

### 2026-06-20 — main red: compose memory budget 3136M > 3072M after celery-mood OOM fix

- **Symptom:** every PR + `main` itself failed CI on two jobs — `guards` (`scripts/check_compose_memory.py`) and `backend` (`tests/unit/test_anti_pattern_sweep.py::test_clean_tree_passes_memory_budget`) — both with `COMPOSE MEMORY BUDGET FAILED: 3136M > 3072M (§A6 ~3 GB target)`. The push immediately before was green.
- **Root cause:** PR #269 restored `dhanradar-celery-mood` `deploy.resources.limits.memory` 128M → 192M because 128M OOM-killed the worker on every mood snapshot. That legitimate +64M pushed the sum of the 9 service limits to exactly 3136M, 64M over the `check_compose_memory.py` `CAP_MB = 3072` discipline gate. The gate was working as designed; the cap simply hadn't been moved to match the OOM-proven footprint, so it red-lined all of CI.
- **Fix:** raised `CAP_MB` 3072 → 3200 in `scripts/check_compose_memory.py:24` (with an inline note citing #269), keeping celery-mood at the OOM-safe 192M. 3200M (3.125 GB) stays within the §A6 ~3 GB band and far inside the KVM4 box's ~6 GB headroom. Did **not** trim another worker — these limits are tuned close to real usage (celery-mood at 128M *was* OOM-killed), so blind trimming would likely just move the OOM. Script now exits 0 (`3136M < 3200M`).
- **Prevention:** when a `deploy.resources.limits.memory` change is made for an OOM fix, update `CAP_MB` in the same PR (the gate and the footprint must move together). The cap is a discipline gate, not a hard ceiling — the box has ~6 GB; raise it deliberately with a note + RCA, never silently.
- **Phase/area:** Infra / docker-compose memory budget (CI deterministic gate).

### 2026-06-20 — celery-mood OOM: macro breadth did a live yfinance fetch on cache miss

- **Symptom:** `compute_mood_snapshot` SIGKILL'd the `dhanradar-celery-mood` worker on off-hours runs even after the 128M→192M bump — `WorkerLostError: Worker exited prematurely: signal 9 (SIGKILL)`, no Python traceback, `yfinance` `TzCache` log lines immediately before the kill. Mood snapshots had not persisted since 2026-06-16. (`docker State.OOMKilled=false` because a worker *child* pid, not the container init, was memcg-killed — inspect the kernel `oom-kill` log, not just the docker flag.)
- **Root cause:** `YahooMacroProvider._fetch_breadth_ratio` (added PR #247) read the `signal:breadth:last` Redis cache first, but on a miss fell back to a LIVE ~50-ticker NIFTY-50 `yfinance.download` (pandas) inside the 192M mood worker. The cache is pre-warmed only during market hours (`market_data_refresh`, TTL 3600s), so any off-hours / cache-expired run triggered the heavy download → memory spike → OOM. A provider running in the memory-tight mood worker should never do the heavy fetch.
- **Fix:** PR #272 made `_fetch_breadth_ratio` **cache-only** — reads `signal:breadth:last`, returns `None` on miss/error (breadth omitted → graceful 6/11 degraded), never a live fetch. The heavy NIFTY-50 download stays solely in the `market_data_refresh` pre-warm task. Removed the now-unused `asyncio` import + `_TTL_BREADTH_SEC`. Verified on prod: warm cache → `mood: ... (7/11 inputs, ok)` persisted; empty cache → `6/11, degraded`, worker `restarts=0`, no SIGKILL.
- **Prevention:** code that runs in a memory-capped worker (celery-mood = 192M) must be a pure cache consumer — never run a pandas/yfinance bulk download there; the heavy fetch belongs to a dedicated pre-warm task sized for it. When wiring "cache-first with live fallback," ask *which worker the fallback executes in* and whether its cgroup limit survives the spike. Verify a data-pipeline fix on BOTH the warm-cache and cache-miss paths (the miss path is the dangerous one).
- **Phase/area:** Mood Compass / market-data ingestion (celery-mood worker memory).

### 2026-06-19 — Admin Phase 6: AMFI scheme-master ingested 0 rows (wrong delimiter assumption; test masked it)

- **Symptom:** post-deploy, the `mf_scheme_master_refresh` task ran to `status=success` but wrote **0 rows** (`0 written, 0 failed`) against the live AMFI feed — a false-healthy source. Unit tests were green (27 passed).
- **Root cause:** the builder assumed AMFI `DownloadSchemeData_Po.aspx?mf=0` is **semicolon**-delimited with 11 columns (copied from the `NAVAll.txt` shape). The live feed is **comma**-delimited with **10** columns, and the final field concatenates the Growth + Reinvest ISINs with **no separator** (`INF…157INF…CE5`). `parse_scheme_master` split on `;`, got 1 field/line, found no ISIN, skipped every row. The unit test passed only because its fixture was *also* hand-written in the wrong semicolon format — the test validated the assumption, not reality (no real-feed sample was ever captured).
- **Fix:** rewrote `parse_scheme_master` for the real format — comma split, numeric-`Code` data-row detection, trailing columns anchored from the **right** (so a comma inside a scheme name can't shift the ISIN/date columns), and ISINs extracted via `re.findall(r"INF[A-Z0-9]{9}")` on the concatenated blob (1 token → growth only; 2 → growth+reinvest). `backend/dhanradar/market_data/amfi_scheme_master.py`. Rewrote the test fixtures to the verified live format + added a comma-in-name robustness test. Verified live: fetch returns 16,244 lines and the parser yields rows.
- **Prevention:** a parser fixture MUST be a captured sample of the **real** source, never hand-authored to match the parser's assumption — otherwise the test green-lights the bug. For any new ingestion source, the acceptance gate is **`records_written > 0` against the live feed**, not just `status=success` (a 0-row success is a false-healthy and should be treated as a failure). Capture a byte sample of every new feed before writing the parser.
- **Phase/area:** Admin Console Phase 6 / data ingestion (AMFI scheme master).

### 2026-06-15 — Broken main: partial squash merge across two PRs touching one file + auto-merge racing a failing required check

- **Symptom:** after PR #185 (Fund Explorer v2) squash-merged, `main` failed `tsc`/`frontend` CI with 8 `TS2741` errors — `page.tsx` and the `SortHeader` call sites passed no `sortDir`, but `FundExplorerTableProps` + the `SortHeader` signature still *required* it.
- **Root cause:** two concurrent PRs touched `FundExplorerTable.tsx`. PR #184 (sortable-column-indicators) *added* `sortDir`; my PR #185 *removed* it. Because #184 squash-merged into `main` first, GitHub's squash of #185 applied only the half of my diff that still differed from the new base — it took the call-site removals but dropped the type-definition removals (the definitions matched #184's just-merged content at the hunk level). Result: a self-inconsistent file. `gh pr merge --auto` then merged #185 despite the `frontend` check being red (auto-merge raced / `frontend` not enforced as a hard gate at that moment).
- **Fix:** hotfix PR #186 (`fix/fund-explorer-sortdir-cleanup`, commit `f035bc4` → merged `4680db5`) removed `sortDir` from the `SortHeader` signature and `FundExplorerTableProps` so the definitions match the call sites. `tsc --noEmit` clean on merged `main`; redeployed fastapi+nextjs to KVM4.
- **Prevention:** (1) after any squash merge of a PR that shared a file with another recently-merged PR, sync `main` and run `tsc` before declaring done — squash diffs are computed against the *post-merge* base, not your branch base, so partial application is possible. (2) Never trust `--auto` to honor a red required check during a race; confirm `gh pr checks` is green (or `mergeStateStatus=CLEAN`) on the *final* merge, and verify the merged `main` builds. (3) When two sessions edit the same component, rebase one onto the other before merging rather than letting both squash independently.
- **Phase/area:** Frontend / Fund Explorer v2 / concurrent-session merge hygiene.

### 2026-06-13 — B66-f1: AMFI category carry-forward poisoned by an AMC-name line with parens ("IDF")

- **Symptom:** on its first prod run, the freshly-deployed B66 taxonomy validation layer WARNed
  that 2,572 funds carried category `IDF` and 2,046 `Income`. 2,572 is impossible for real
  Infrastructure Debt Funds (India has a handful); the `IDF`-tagged funds were actually
  close-ended FMPs (Nippon/Reliance/Kotak/SBI/ICICI Fixed Maturity / Fixed Horizon plans).
- **Root cause:** `parse_navall_with_category` (`backend/dhanradar/market_data/amfi.py`) treated
  ANY non-data line containing both "(" and ")" as a scheme-type section header and carried its
  inner-paren text forward as `category`. The live AMFI NAVAll.txt contains the AMC-name line
  `IL&FS Mutual Fund (IDF)` inside the "Close Ended Schemes(Income)" section; the parser read
  "(IDF)" as a header and mis-tagged every subsequent fund `IDF` until the next real header.
  `category` is the exact-string peer-cohort key (`mf/cohort.py`), so those funds cohorted as a
  bogus 2,572-member "IDF" group instead of with their real peers.
- **Fix:** require the text before "(" to end with "Schemes" before treating a line as a header
  (`amfi.py` `parse_navall_with_category`). The real headers — "Open Ended Schemes(…)",
  "Close Ended Schemes(…)", "Interval Fund Schemes(…)" — all end in "Schemes"; an AMC name never
  does. Ex-`IDF` funds now inherit their real section category ("Income"). Deployed; the next
  `nav_daily_fetch` drift log confirms `IDF` drops to ~0.
- **Prevention:** `TestParseNavallWithCategory` in `test_amfi.py` — a regression fixture with the
  exact `IL&FS Mutual Fund (IDF)` poison line asserting funds keep the section category, plus the
  "Schemes"-prefix-required and space-before-paren cases. The B66 taxonomy validation layer is the
  standing detector: any future such drift WARNs in the nightly `nav_daily_fetch` log.
- **Phase/area:** MF data ingestion (AMFI parser) → scoring cohort key. Surfaced by B66.

### 2026-06-12 — B65: CAMS CAS XIRR null — casparser sign convention not normalised at the parse boundary

- **Symptom:** CAMS CAS report shows `xirr_pct: null` despite the statement carrying full
  transaction history. Observed by the founder during the 2026-06-12 E2E (CAMS
  `docs/cas_cams.pdf`: 11 funds, value ₹94,767, invested ₹91,812, xirr null). CDSL CAS
  xirr-null is by design (no txn history) — this is a separate, distinct bug.
- **Root cause:** `parse_cas` (`backend/dhanradar/mf/cas.py`) did not normalise casparser's
  statement sign convention to the investor convention its own `ParsedTxn` contract and the
  `snapshot.xirr()` consumer require. casparser 1.0.1 (`parsers/cams_detailed.py:316-358`
  `_apply_balance_sign_fix`) delivers CAMS amounts in statement convention — purchases are
  POSITIVE (sign follows units). The investor convention requires purchases to be negative
  outflows. Without normalisation, an all-purchase portfolio produces all-positive cash flows;
  `snapshot.xirr()` (`backend/dhanradar/mf/snapshot.py:76-82`) guards against all-same-sign
  flows (a degenerate XIRR input) and returns None. Two contributing factors: (1) the unit
  fixture `test_mf_module.py:29` fed `amount: -4000.0` for a purchase, encoding the
  developer's assumed convention rather than real casparser output — CI stayed green because
  the injectable-reader design isolated tests from the real library's semantics; (2) the worker
  task logged neither txn counts nor the XIRR outcome, so the null was only surfaced by
  founder eyeball.
- **Fix:** per-type sign normalisation at the parse boundary in `backend/dhanradar/mf/cas.py`.
  `_TXN_INFLOW_AS_PRINTED` = DIVIDEND_PAYOUT kept as printed; `_TXN_FLOW_EXCLUDED` =
  DIVIDEND_REINVEST / SEGREGATION / STT_TAX / STAMP_DUTY_TAX / TDS_TAX / MISC / UNKNOWN
  excluded from cash flows; everything else (purchases, redemptions, switches) is negated so
  purchases become outflows and redemptions become inflows; reversal pairs self-cancel; switch
  pairs cancel at portfolio level. Handles both casparser 1.0 enum members and 0.7.x plain-string
  types via `getattr(.value)`. Branch: `fix/b65-cams-xirr-sign`.
- **Prevention:** 7 regression tests including the exact bug repro
  (`test_b65_all_purchase_portfolio_xirr_computable`) and a `(str, Enum)` type fake that fails
  a `str()`-based implementation; fixtures migrated to realistic statement convention.
  Observability closed: `cas.parse` logs excluded txn counts; the worker logs
  `mf.snapshot.built {funds, cashflows, xirr_computed}` per report build (boolean flag only —
  DPDP log discipline, no per-user financial values). 790 unit tests green; integration in CI.
- **Phase/area:** Phase 5 MF module — CAS pipeline / XIRR computation (B65).

### 2026-06-12 — B62-f1: chip tint invisible — hex-alpha suffix on a CSS var() is invalid CSS

- **Symptom:** "What Changed" panel change-kind chips rendered with no background or border tint
  in every browser; chip text color still applied, so the chips looked like plain text.
- **Root cause:** `WhatChangedPanel.tsx` built the tint by appending a 2-digit hex alpha suffix to
  an interpolated design-token color — but the token is a CSS `var()` reference, and `var()`
  followed by hex digits is an invalid CSS color value, so browsers silently dropped both the
  background and border declarations.
- **Fix:** `frontend/src/components/changes/WhatChangedPanel.tsx:116-119` — tint via
  `color-mix(in srgb, <token> 13%, transparent)` (border at 33%), which keeps the `var()` valid.
- **Prevention:** source-level vitest guard in `WhatChangedPanel.test.tsx` asserts no hex-alpha
  suffix is appended to the interpolated color and that `color-mix` is present. jsdom cannot catch
  this at render time — its CSS parser drops both the broken and the fixed value.
- **Phase/area:** frontend / What Changed explainability (Plan Group 2, B62).

### 2026-06-12 — restore.sh lacked TimescaleDB pre/post-restore wrappers (latent restore-failure bug)

- **Symptom:** latent — never bit in production. Found during B37 drill implementation when
  reviewing the restore path against TimescaleDB docs. A plain `pg_restore` on a TimescaleDB
  database without `timescaledb_pre_restore()` / `timescaledb_post_restore()` wrappers causes
  hypertable chunk catalog restore failures and leaves the database with
  `timescaledb.restoring=on` (unusable until `post_restore` is called manually).
- **Root cause:** `restore.sh` was written with a vanilla `pg_restore` call. The
  `timescaledb_pre_restore` / `timescaledb_post_restore` wrapper requirement is specific to
  TimescaleDB and is not part of the standard `pg_restore` documentation; it was not added
  when the script was first written.
- **Fix:** `scripts/restore.sh` lines 210–229 — `timescaledb_pre_restore()` is called before
  `pg_restore`; `timescaledb_post_restore()` runs unconditionally after (even when `pg_restore`
  exits non-zero) so the database is never left in restoring mode. `scripts/restore-drill.sh`
  lines 178–193 uses the same sequence. The 2026-06-12 restore drill ran both wrappers with
  `--exit-on-error` clean (PASS).
- **Prevention:** the quarterly restore drill exercises the real restore path end-to-end,
  including the TimescaleDB wrappers — a regression here would surface as a drill FAIL before
  it could affect production. Record is in `docs/ops/restore-drill-log.md`.
- **Phase/area:** infra / B37 backup-restore — `scripts/restore.sh`, `scripts/restore-drill.sh`.

### 2026-06-12 — MANIFEST alembic_rev always recorded as "unavailable"

- **Symptom:** every backup MANIFEST generated before 2026-06-12 recorded
  `alembic_rev=unavailable`. The field appeared to run successfully (no error logged) but
  produced no revision string.
- **Root cause:** `backup.sh` ran bare `alembic current` inside `docker compose run`. The
  `alembic` console script does not add the working directory (`/app`) to `sys.path`, so
  `env.py`'s `from dhanradar import ...` import raised `ModuleNotFoundError` on every
  invocation. The error was silently swallowed by `2>/dev/null` and the fallback
  `|| echo "unavailable"` fired, making every MANIFEST look like it succeeded.
- **Fix:** `scripts/backup.sh` line 147 — changed to `python -m alembic current`. The
  `-m` invocation adds CWD to `sys.path`, matching the pattern already used in `deploy.sh`.
  The 2026-06-12 drill restored the last pre-fix backup (stamp `20260612171924`, MANIFEST
  still saying `unavailable`); the restored alembic revision was verified directly instead
  (`0018`). MANIFESTs record the real revision from the next nightly run onward.
- **Prevention:** the quarterly restore drill verifies the restored alembic revision against
  a known head, which catches any future MANIFEST field failures. The fix mirrors the
  standing rule from the 2026-06-08 first-deploy RCA: always invoke Python entry points
  as `python -m <tool>` in containerised environments where CWD must be importable.
- **Phase/area:** infra / B37 backup MANIFEST — `scripts/backup.sh` line 147.

### 2026-06-11 — Every 2nd+ CAS upload in a worker child fails: Redis singleton bound to a closed event loop

- **Symptom:** CAMS E2E upload failed instantly (`internal_error`, progress 0) with
  `RuntimeError: Event loop is closed` at `cas_pipeline_start`, while the CDSL upload that ran
  FIRST in the same prefork child succeeded (`done`). Job 62923c49, worker child shared with the
  successful f4aee869.
- **Root cause (proven):** `redis_client.get_redis()` cached ONE module-level async client.
  Celery tasks each run under their own `asyncio.run()` loop: task #1 created the client bound to
  loop #1, `asyncio.run` closed loop #1 on exit, and task #2's first Redis call on the cached
  client raised "Event loop is closed". Same cross-loop-global class as the SEV2 asyncpg
  NullPool RCA (2026-06-10) — Redis was the remaining global. Masked historically because
  OOM-kills/deploys kept recycling worker children, so most tasks ran as the FIRST in a child.
- **Fix:** `redis_client.py` — the cache is now loop-aware: a new running loop gets a fresh
  client; the same loop (the entire web tier) reuses the cached one; no-loop callers keep
  legacy behaviour. Stale clients' dead sockets are abandoned to TCP cleanup (bounded: one per
  task loop).
- **Prevention:** regression test `test_redis_client_loop.py` (new-loop → new client, same-loop
  → same client); standing review rule extended: ANY module-level async resource (engine,
  client, pool) must be loop-aware or per-task — grep for module singletons when a Celery task
  touches a new async dependency.
- **Phase/area:** infra / redis_client / Celery task plumbing.

### 2026-06-11 — Shared-checkout co-edit: concurrent session's in-flight hunk silently carried into PR #93

- **Symptom:** PR #93's first CI run failed on two jobs (`guards` + `backend`): the compose
  memory budget guard reported a total of 3584 M, exceeding the 3072 M cap. The diff that
  was reviewed and intended contained only an 11-line network change to `docker-compose.yml`
  with no memory edits. No memory change appeared in the pre-commit `git diff` scan.
- **Root cause:** a concurrent session working on the same shared checkout (`E:\code\DhanRadar`)
  had edited `docker-compose.yml` in the working tree (celery-batch limit raised 256 M → 768 M
  as their B63 OOM fix) BETWEEN the pre-commit `git diff` gate and the `git add` + `git commit`
  step. The `git add docker-compose.yml` picked up the full working-tree file — including their
  un-staged hunk — and the commit silently carried both changes. The `git diff` gate ran clean
  because the concurrent edits were not yet staged at that moment; `git diff --staged` was not
  run immediately before `git commit`, so the final staged content was never verified.
- **Fix:** branch (`feat/b38-metrics-scrape-network`) rebuilt in an isolated git worktree
  (`E:\code\DhanRadar-wt-b38`) containing only the intended 11-line compose hunk; commit
  amended `490d026` → `1dd3e56`, force-pushed with lease; CI green on the rebuilt branch;
  squash-merged to main as `adf73de` (PR #93).
- **Prevention:** (a) always run `git diff --staged` IMMEDIATELY before `git commit` on a
  shared checkout and compare the staged hunks against the intended change — a gap between
  `git add` and `git commit` is enough for a concurrent session to contaminate the index;
  (b) prefer doing branch work in a dedicated git worktree (`git worktree add`) whenever
  another session is known to be active on the same checkout — isolation is free and
  eliminates the contamination vector by construction.
- **Phase/area:** infra / git workflow — shared checkout + concurrent sessions.

### 2026-06-11 — SEV1: production database destroyed on postgres container recreate (PGDATA volume-path mismatch)

- **Symptom:** `auth.users` and `alembic_version` "do not exist" on prod minutes after an
  `ADMIN_USER_IDS` env change + `docker compose up -d dhanradar-fastapi`. Postgres logs show
  full `initdb` ran. All production data (2 users, consents, portfolios, CAS holdings, score
  history, 2.03M-row NAV history, ~2 days of `ai_recommendation_audit`/`audit.*` rows, the
  scoring v1 activation registry row) was gone. No backup existed (B37 never run live).
- **Root cause (proven):** `docker-compose.yml` mounted the named volume at
  `/var/lib/postgresql/data` (vanilla-postgres path), but `timescale/timescaledb-ha` keeps
  `PGDATA=/home/postgres/pgdata/data` (verified via container env). The named volume was
  empty since 2026-06-08; ALL data lived in the container's **writable layer**, and the image
  declares no VOLUME for that path (verified: no anonymous pg volume exists; redis's anonymous
  `/data` volume DID survive the same recreate). The env-file change marked
  postgres/redis as config-changed dependencies, so `up -d dhanradar-fastapi` recreated them;
  removing the old postgres container deleted the writable layer = the database. Every prior
  deploy "survived" only because postgres was never recreated — an unenforced invariant.
  Contributing: the operator command piped through `tail -2`, truncating the compose output
  lines that showed postgres/redis being recreated; obs 5712 (2026-06-07) had flagged the same
  bug class for redis (anonymous `/data`) and was never actioned.
- **Fix:** `docker-compose.yml` — pg volume now mounts at `/home/postgres/pgdata` (parent
  of PGDATA, per timescaledb-ha docs); redis gains named `dhanradar_redis_data:/data`.
  Recovery: fresh DB rebuilt via `01_init.sql` + alembic `0001→0017` + seeds (education,
  concepts) + `nav_backfill` re-run + scoring v1 re-activation (same gated script; the original
  human approval stands); founder must re-signup (new user UUID → `ADMIN_USER_IDS` updated again).
- **Prevention:** (1) the volume-path fix itself — recreates now preserve data by
  construction; (2) `scripts/deploy.sh` fresh-DB tripwire — aborts before migrating when
  `alembic_version` is missing unless `DHANRADAR_ALLOW_FRESH_DB=1` (catches silent
  volume-loss before it is papered over); (3) B37 backups escalated from "deploy-gate owed"
  to URGENT — this incident is exactly the loss a nightly `pg_dump` would have bounded to 24h;
  (4) standing rule: never pipe deploy/compose output through `tail`/`head` — read it whole.
- **Phase/area:** infra / docker-compose / deploy.

### 2026-06-11 — MF report data quality: four live-report defects (B61 + parse + UI) — PR #81

- **Symptom:** a live CAS report (post-deploy, 2026-06-11) exhibited four distinct problems:
  (1) every fund labelled `insufficient_data`; (2) "Invested" showed ₹0 for several funds;
  (3) stray `▯` (U+0002 STX) characters appeared in scheme names; (4) the report timestamp
  rendered as a raw ISO string (`2026-06-11T03:11:...`) rather than a human-readable time.
- **Root cause — (1) insufficient\_data was a data-timing/pipeline issue, not a scoring bug.**
  The engine emits a real label (`on_track` minimum) whenever signals are present
  (`scoring/engine/labels.py:41`); `insufficient_data` only fires at `engine.py:134`
  (`unified is None`). Two upstream gaps combined: scores were written before NAV was populated,
  AND `mf_funds` was empty (0 rows) so `_compute_cohort` returned `{}` (no category-relative
  signals). The empty `mf_funds` traced directly to B61 — `nav_daily_fetch` was failing on every
  run (CardinalityViolationError), so the task that populates `mf_funds` never completed.
  Stale scores needed a re-score after the pipeline fix, not a code change in the engine.
- **Root cause — (2) invested ₹0 (data):** CDSL holdings with no transaction history carry no
  cost basis; `valuation.cost` is `None` → `invested_amount` is null in the API response. The
  frontend rendered null as `₹0` instead of a neutral placeholder.
- **Root cause — (3) scheme-name control chars (data/parse):** `casparser` emits raw ASCII
  control characters (U+0002 STX) in scheme names for certain CDSL entries. `cas.py` passed
  names through without sanitization, so the characters reached the DB and the UI.
- **Root cause — (4) raw ISO timestamp (frontend):** the report page rendered the
  `generated_at` field from the API response verbatim without formatting.
- **Fix (PR #81, `e8d8463`, deployed 2026-06-11):**
  1. `backend/dhanradar/tasks/mf.py` — dedup `_navrows_to_nav_upserts` (keep last-seen per
     `(isin, nav_date)`) and `_navrows_to_fund_upserts` (keep last-seen per `isin`), closing B61
     and unblocking `mf_funds` population so the engine receives real cohort signals.
  2. `backend/dhanradar/mf/cas.py` — new `_clean_text` helper strips ASCII control characters
     (U+0000–U+001F except tab/LF/CR) from scheme names at parse time.
  3. `frontend/src/app/(app)/mf/report/[jobId]/page.tsx` — `formatIstDateTime` renders
     `generated_at` as a readable IST string; null `invested_amount` renders "—" not ₹0.
  4. `frontend/src/features/mf/api.ts` and `types.ts` — `invested_amount` typed as
     `number | null`; display helpers added.
- **Verification:** deployed to KVM4; `nav_daily_fetch` succeeded immediately ("14,041 navs,
  14,037 funds"); `mf_funds` went from 0 → 14,037; an empirical re-score of the user's 6 held
  ISINs returned real labels (`on_track`/`off_track`/`in_form`, cohort populated, confidence
  ~0.59–0.67) — zero `insufficient_data`.
- **Prevention:** 7 new unit tests: 3 dedup tests for the upsert helpers
  (duplicate `(isin, nav_date)` → single output row); 4 `_clean_text` sanitization tests
  (STX stripped, printable chars preserved, empty string, None-safe). Standing lesson: a
  "labels look wrong" symptom can be entirely upstream data — scores written before their NAV
  and category inputs exist, plus a silently-failing ingestion task leaving `mf_funds` empty.
  Always verify the pipeline (task logs, `mf_funds` row count) before suspecting the scoring
  engine; stale scores need a re-score, not a code change.
- **Follow-ups (deferred):** IDCW/dividend-plan cross-variant ISIN NAV fallback (one fund type
  can still be `insufficient_data` if only its growth/reinvest variant carries NAV);
  folio-level aggregation for invested amount.
- **Phase/area:** Phase 5 MF report — data quality (parse + scoring data pipeline + UI).

### 2026-06-11 — Daily NAV refresh has never worked: duplicate (isin, nav_date) pairs abort bulk upsert (B61)

- **Symptom:** `nav_daily_fetch` triggered manually on prod (post-PR #74 deploy verification)
  returns HTTP 200 from AMFI (~14,208 rows), but the bulk upsert fails immediately with
  `asyncpg.exceptions.CardinalityViolationError: ON CONFLICT DO UPDATE command cannot affect
  row a second time` → task returns `"nav_daily_fetch: failed"`, 0 rows written.
  The daily beat has been running since launch and silently failing every time.
  This is DISTINCT from the asyncpg InterfaceError fixed in PR #74 — the task now successfully
  reaches AMFI (PR #74 confirmed working), but dies at the upsert stage.
- **Root cause (data/ingestion):** `_navrows_to_nav_upserts` in `backend/dhanradar/tasks/mf.py`
  (~lines 81–107) keys each row on `isin_growth or isin_reinvest`. AMFI NAVAll.txt lists both
  the growth and reinvest variants of the same fund scheme, which collapse to the same ISIN.
  Both variants appear in a single batch → two rows with identical `(isin, nav_date)` enter the
  same `INSERT … ON CONFLICT DO UPDATE` statement → Postgres rejects any single statement that
  would update the same physical row twice. `_navrows_to_fund_upserts` (~lines 109–126) has the
  same gap (keyed on `isin` alone). Found during post-deploy verification of PR #74.
- **Fix (PR #81, `e8d8463`):** deduplicate parsed rows before the upsert, keeping last-seen per
  `(isin, nav_date)` in `_navrows_to_nav_upserts` and last-seen per `isin` in
  `_navrows_to_fund_upserts`. Verified in prod: `nav_daily_fetch` now writes 14,041 NAV rows and
  14,037 fund rows; `mf_funds` went 0 → 14,037.
- **Prevention:** 3 dedup unit tests feeding duplicate `(isin, nav_date)` rows and asserting one
  deduped output row; post-fix prod smoke trigger of `nav_daily_fetch` confirmed non-zero rows.
- **Phase/area:** MF data ingestion — `backend/dhanradar/tasks/mf.py`
  (`_navrows_to_nav_upserts`, `_navrows_to_fund_upserts`). Closes B61.

### 2026-06-10 — SEV2 NullPool migration completion: CAS jobs stuck in `queued` forever + empty-NAV blocker

- **Symptom:** eCAS upload stalls — CAS jobs created with `status='queued'` and never advance.
  UI spins on "Analysing…" indefinitely. Live prod reproduce confirmed: job failed 342 ms after
  creation, `error_message` was NULL, job orphaned in `queued`. The `news` Celery task on the same
  worker also hit the same error. PR #69 (`670bc1a`) had attempted a partial fix (NullPool
  `task_engine` / `TaskSessionLocal`) but the task-aware service files were missed and prod was
  never deployed with even that partial fix.
- **Root cause (code — async DB connection lifecycle):** the pooled SQLAlchemy async engine,
  reused across Celery `asyncio.run()` event loops, hands the next task an asyncpg connection
  bound to a dead (previous-loop) event loop → `asyncpg InterfaceError: cannot perform
  operation: another operation is in progress`. The failure handler `_mark_failed` used the same
  poisoned pooled engine and also raised, so the job was never marked failed and was orphaned in
  `queued`. PR #69 added `task_engine` / `TaskSessionLocal` (NullPool) and migrated
  `tasks/mf.py`, `tasks/news.py`, `tasks/misc.py` — but the call sites inside the service files
  reachable from those tasks still used the pooled engine:
  `compliance/service.py` (`record_served_label`, `log_low_confidence`),
  `audit/service.py` (3 writers), `mood/service.py` (`_persist`),
  `tasks/compliance.py`.
- **Fix (PR #74, `42c96db`):**
  1. **NullPool migration completed** — all service-file call sites ported to `TaskSessionLocal`:
     `backend/dhanradar/compliance/service.py` (lines ~35, ~70),
     `backend/dhanradar/audit/service.py` (3 writers),
     `backend/dhanradar/mood/service.py` (`_persist`),
     `backend/dhanradar/tasks/compliance.py`.
  2. **CI guard added** — `scripts/ci_guards.py` Guard #6 bans `async_sessionmaker(engine`
     outside `db.py`; regression tests in `tests/unit/test_ci_guards.py` prevent recurrence.
  3. **Stuck-job reaper** — new Celery beat task `reap_stuck_cas_jobs` (every 5 min) marks any
     `queued`/`parsing`/`scoring` job older than 10 min as `failed='stuck_timeout'` and clears
     its dedup key (`backend/dhanradar/tasks/mf.py`).
  4. **Frontend timeout** — CAS status poll now times out after 150 s and renders a re-upload
     prompt instead of spinning forever (`frontend/src/features/mf/`).
  5. **Test-coupling repair** — 3 `test_audit_ledger.py` integration tests injected the DB error
     at the old pooled `engine`; patched to inject at `TaskSessionLocal`
     (`backend/tests/integration/test_audit_ledger.py`).
  6. **Prod remediation** — the 2 orphaned jobs were cleared; `nav_backfill` (docker run -m 2g,
     one-off) populated `mf.mf_nav_history` with 2,027,380 rows / 9,401 funds
     (2023-06-11 → 2026-06-10), resolving the long-standing empty-NAV / B29 deploy-gate blocker.
     Likely cause of prior empty NAV: migrations #67–#74 catching prod up to head recreated
     `mf_nav_history` and dropped the 2026-06-08 backfill.
- **Prevention:** (1) CI Guard #6 (`scripts/ci_guards.py`) — static ban on
  `async_sessionmaker(engine` outside `db.py`; fires on every CI run and pre-commit hook.
  (2) Stuck-job reaper as a safety net — even if a future regression orphans a job it will
  surface as `failed='stuck_timeout'` within 10 min rather than spinning forever.
  (3) Standing rule: **all Celery task DB access MUST use `TaskSessionLocal` (NullPool) —
  never the pooled `async_engine`.** Captured here and in `docs/features/mf.md`.
- **Phase/area:** SEV2 / Celery async DB lifecycle — `backend/dhanradar/tasks/`,
  `compliance/service.py`, `audit/service.py`, `mood/service.py`. Deploy: KVM4 `42c96db`.

### 2026-06-10 — B56 news: feed shows 2-year-old headlines + dead (404) links

- **Symptom:** the dashboard Market News widget shows stale 2024 items ("SEBI circular … March
  2024", "AMFI … April 2024", "RBI … April 2024" — rendered "792d ago" etc.) and the headline
  links 404. (SEV3 — degraded, user-visible trust issue; wedge unaffected.)
- **Root cause (design/data):** `news/service.py` shipped only a hardcoded static list of 3 sample
  2024 headlines (`_CURATED_ITEMS`) with fixed 2024 `published_at` and unverified placeholder URLs.
  `tasks/news.py::refresh_market_news` re-upserted those same 3 rows every 30 min, so the feed never
  advanced. The primary live-source path (RSS fetch) was never built. HEAD-checking the 3 URLs:
  SEBI → 404, AMFI → 404, RBI → 200 (but date frozen at 2024).
- **Fix:** `0b91826` (`fix/b56-live-news-rss`). New `news/rss.py` — sanctioned-feed registry (RBI
  press releases + notifications; ToS confirmed live 2026-06-10 from rbi.org.in/Scripts/rss.aspx);
  httpx async fetch + feedparser; per-item HEAD liveness check (non-2xx → skip). `list_news` gains
  `published_at >= now − NEWS_MAX_AGE_DAYS` recency filter + staleness WARNING log. `tasks/news.py`
  calls `fetch_and_upsert_rss_news` first; falls back to curated seed when RSS returns 0 items. No
  DB migration (schema unchanged; `is_active` + `provenance_source` already present in 0016).
  Config: `NEWS_MAX_AGE_DAYS=30`, `NEWS_STALENESS_WARN_HOURS=24`. Closes B56-f5.
- **Prevention:** (1) URL liveness HEAD check at ingest — dead links can never reach the UI;
  (2) recency guard (`NEWS_MAX_AGE_DAYS`) — old items dropped from `list_news`; (3) staleness
  observability — WARNING log when newest served item > `NEWS_STALENESS_WARN_HOURS` old; (4)
  regression tests in `test_news_rss.py` (8) + `test_news_service.py` (recency/staleness/rss-dedup) +
  `test_news.py` integration recency test.
- **Phase/area:** B56 / `backend/dhanradar/news/`.

### 2026-06-10 — G8: CI frontend build failed (`fetch failed / ECONNREFUSED`) on new SSR pages

- **Symptom:** the `frontend` CI job (`next build`, mocks-off) failed with
  `TypeError: fetch failed … ECONNREFUSED` after adding the G8 `/learn/tax` Server-Component
  pages. Backend unit + integration + migrations all passed; only the FE build broke.
- **Root cause:** App-Router pages are **statically prerendered at build by default**. The new
  `/learn/tax`, `/learn/tax/[slug]`, and `/learn/tax/calendar` pages are async Server Components
  that `fetch()` the backend API during render — so Next.js ran those fetches at build time, when
  no backend is reachable, and a failed fetch during static generation fails the whole build. (The
  existing `/mood` page never hit this because it is `'use client'` — fetched in the browser, not
  at build.)
- **Fix:** `export const dynamic = 'force-dynamic'` on all three pages
  (`frontend/src/app/learn/tax/{page,[slug]/page,calendar/page}.tsx`) → rendered per-request (SSR),
  never prerendered → no build-time fetch. Crawlers still receive fully server-rendered HTML (SEO
  intact). Verified `next build` marks them `ƒ (Dynamic)`. (`5e3dbf4`)
- **Prevention:** any NEW server-rendered page that fetches a runtime API must set
  `export const dynamic = 'force-dynamic'` (or be otherwise excluded from static generation), or
  the mocks-off `next build` CI job will fail with ECONNREFUSED. Captured in memory
  [[ssr-page-build-time-fetch-econnrefused]].

### 2026-06-09 — B58: every fund receives only `on_track` or `insufficient_data` — differentiating labels never emitted

- **Symptom:** every mutual fund a user uploaded received an identical label — either `on_track`
  (NAV present) or `insufficient_data` (no NAV). The labels `in_form`, `off_track`, and
  `out_of_form` were never emitted. The "explainable, differentiated labels" product value
  proposition was inert. Found by the 2026-06-09 progress audit, filed as B58.
- **Root cause:** the category-relative inputs to the deterministic rule table
  (`outperform_1y`, `outperform_3y`, `underperform_12m`, `drawdown_controlled`,
  `sustained_underperformance`) defaulted to `False` in `FundSignals` and were never set.
  No peer-cohort benchmark query existed — `dhanradar/mf/signals.py` only computed
  own-series momentum/risk axes. With all category-relative booleans `False`, the rule table
  in `dhanradar/scoring/engine/labels.py` could only fall through to `on_track`.
- **Fix:** added a peer-cohort benchmark computed from existing AMFI NAV data (no new external
  source, no migration). New pure module `dhanradar/mf/cohort.py` builds a per-category MEDIAN
  benchmark (1Y/3Y return + max-drawdown) over same-category funds and compares each fund
  (must beat/trail the median by > 2.0 pp). `dhanradar/mf/signals.py:long_horizon_stats`
  computes the 1Y/3Y/drawdown inputs; `compute_fund_signals` gained a `category_relative`
  param. `dhanradar/tasks/mf.py:_compute_cohort` loads peer NAV (≥1200-day history) and is
  wired at both scoring call sites (CAS report + monthly rescore). `out_of_form` remains
  intentionally unreachable — it requires a `structural_concern` fundamentals signal not yet
  ingested.
- **Prevention:** `tests/unit/test_mf_cohort.py` asserts real label flips to `in_form` and
  `off_track` (not just "a label exists"), plus a regression test confirming the no-benchmark
  path still yields `on_track`. Thresholds are tagged `provisional_model` pending the B6/B28
  activation gate. Lesson: boolean inputs with default `False` that feed a rule table will
  silently produce the base case forever — stub inputs must either assert a live writer or
  be guarded by a test that exercises the non-default branch.
- **Phase/area:** Phase 5 / MF scoring — category-relative labelling (Tier-C scoring engine).

### 2026-06-09 — Market Mood never shows: NSE macro endpoints 403-block the prod server → 0 snapshots ever stored

- **Symptom:** the public `/mood` page is permanently "Market mood is being computed". `mood.market_mood`
  has 0 rows; a manual `compute_mood_snapshot` returns `mood: skipped (all inputs missing)`.
- **Root cause:** the only macro provider (`NseMacroProvider`) fetches NSE public JSON endpoints, which
  **403 from datacenter IPs** (confirmed: warmup + every endpoint returns HTTP 403, 0 cookies, from the
  KVM4 box). With all 11 signals None, `compute_mood` returns None and `compute_and_store` stores
  **nothing** — so `get_latest` has no row and the API serves `data_unavailable` forever. The
  "always serve the last snapshot + twice-daily background refresh" was already built; it just never had
  a snapshot to serve.
- **Fix:** new `YahooMacroProvider` (`backend/dhanradar/market_data/providers/yahoo.py`) sourcing 6
  signals from Yahoo Finance's public chart API — server-reachable (verified HTTP 200): nifty_trend
  (^NSEI %), india_vix (^INDIAVIX), global_indices (^GSPC %), us_bond_10y (^TNX), oil_brent (BZ=F),
  usd_inr (INR=X %). Four new normalizers added to `mood/signals.py` (+ wired into `_NORMALIZERS`).
  Ladder `MACRO_SIGNAL` → `["yahoo_macro","nse_macro"]` (Yahoo primary, NSE fallback);
  `tasks/mood.py` registers both. 6 signals (weight 0.57, <7 inputs) → a real **degraded / medium**
  regime, not the all-missing skip. Adversarial review (Sonnet) MUST-FIX applied: an empty Yahoo result
  now raises `ProviderError` so the ladder falls through instead of recording a false success (which
  would silently re-create this bug).
- **Prevention:** `backend/tests/unit/test_mood_yahoo.py` pins the normalizers, the raw→signal
  derivation, the empty-result `ProviderError`, and that 6 signals yield a real medium regime. Lesson:
  a provider that returns an empty-but-valid payload must signal failure, or a degraded source masks a
  total outage. Compliance verified by review: no numeric leak (#2), refuse floor preserved (#4),
  no advisory copy (#1).
- **Phase/area:** Mood Compass — market-data sourcing (public educational surface).

### 2026-06-09 — CAS re-upload bounces to a done job whose report expired → /report 404 ("same error from mobile")

- **Symptom:** user re-uploads the same CAS (from mobile) and the report page shows "Could not load
  report" forever. Prod evidence: `POST /mf/upload/cas → 202`, `…/status → 200 (done)`, then
  `GET /mf/report/{job} → 404` repeated. The `mf_cas_job` row was `status=done`, `progress_pct=100`,
  empty `error_message` — so the job genuinely succeeded; only the report fetch 404s.
- **Root cause:** a **TTL mismatch**, not a parse failure. The Redis dedup key lives
  `_DEDUP_TTL = 24h` (`mf/service.py:24`) but the assembled report cache only `_REPORT_TTL = 2h`
  (`mf/service.py:26`). The prior dedup fix (#35) short-circuited a re-upload whenever the prior job
  `status == "done"` — but did **not** check the report still exists. In the 22h gap after the 2h
  report cache expires (job at 03:08 → re-upload at 05:51, evidence), a re-upload hits the still-live
  dedup key, returns the old done `job_id`, and `cas_report` then raises `404 report_expired`
  (`mf/router.py:333`) because the cache is gone. This is the *same* "re-upload → dead job" class the
  #35 fix targeted, re-triggered by **cache expiry** instead of job failure. "From mobile" was
  incidental (re-upload simply happened after the 2h window). Frontend was already correct — it
  navigates to the POST response's `job_id` (`upload/page.tsx:33`).
- **Fix:** the dedup short-circuit now requires the report to be **retrievable**, not just the job
  done. New `service.can_return_existing(redis, prior_status, job_id)` returns True only when
  `prior_status == "done"` AND `redis.exists("mf:report:{job_id}")` (`mf/service.py`); the upload
  route calls it and, on False, drops the stale dedup key and reprocesses the freshly-uploaded bytes
  (`mf/router.py:253-264`). A done-but-expired job now self-heals exactly like a failed one.
- **Prevention:** unit test `test_can_return_existing_requires_done_and_cached_report`
  (`tests/unit/test_mf_module.py`) pins the rule: done + cached → dedup; done + expired → reprocess;
  non-done → reprocess. Standing invariant: **dedup may only short-circuit to a still-serveable
  report** — never tie a 24h dedup key to a 2h cache without checking the cache. (Residual, separate:
  a bookmarked `/report/{job}` revisited after 2h with no re-upload still 404s; frontend could prompt
  re-upload on `report_expired` — noted, not fixed here.)
- **Phase/area:** Phase 5 / MF CAS upload + dedup.

### 2026-06-09 — Onboarding/risk-profile page shows twice (post-submit bounce back to /onboarding)

- **Symptom:** a new user completes the 5-question risk quiz, but the "Set your risk profile" page
  appears a **second** time and sticks there instead of landing on the dashboard.
- **Root cause:** two compounding defects. (a) **Refetch race:** `useSubmitRiskQuiz` only
  `invalidateQueries(auth.me)` on success and discarded the response's `risk_profile`; the page's
  `onComplete` then `router.replace('/dashboard')` runs immediately, so `AuthGuard` on `/dashboard`
  reads the **stale** cached `risk_profile: null` (the invalidated refetch is still in flight) and
  bounces the user back to `/onboarding`. (b) **Missing guard:** `AuthGuard` only redirected *to*
  `/onboarding` when `risk_profile == null`; it never redirected a **completed** user *away* from
  `/onboarding` — despite the onboarding page's own comment claiming it did — so once bounced there
  the user was stuck re-seeing the quiz.
- **Fix:** (a) `useSubmitRiskQuiz` now `setQueryData(auth.me, …risk_profile)` from the (authoritative,
  normalised) response **before** invalidating — mirrors `useLogin`/`useSignup` — so the guard sees
  the set profile synchronously and never bounces (`frontend/src/features/onboarding/api.ts`).
  (b) `AuthGuard` redirects a `risk_profile != null` user sitting on `/onboarding` → `/dashboard`,
  with a matching render guard (`frontend/src/features/auth/AuthGuard.tsx`).
- **Prevention:** `AuthGuard.cold-start.test.tsx` gains "redirects a COMPLETED user away from
  /onboarding". Lesson: a mutation whose result drives a routing guard must SEED the guard's cache
  from the response, not just invalidate — an in-flight refetch serves stale data to a synchronous
  redirect.
- **Phase/area:** Onboarding cold-start gate + AuthGuard routing, frontend.

### 2026-06-09 — CAS upload always fails (`parse_failed`): casparser pinned `>=0.7.0` pulled breaking 1.0

- **Symptom:** every CAS upload ends on the report page with "We couldn't process this statement".
  `dhanradar-celery-batch` logs: `parse_cas_job[...] received` → `CAS parse failed job=<id>` →
  `succeeded in 0.59s: 'failed: parse_failed'`. The celery task itself runs (the earlier
  task-registration + shared-volume fixes worked); the parse is what fails, fast and consistently.
- **Root cause:** `backend/requirements.txt` pinned `casparser>=0.7.0`; the worker image built with
  **casparser 1.0.0**, a breaking major bump. (a) `read_cas_pdf(..., output="dict")` now returns a
  typed `CASData` **pydantic model**, not a plain dict — but `parse_cas` walks dict-shaped output
  (`raw.get("folios")`), and a model has no `.get()` → every *successful* parse would 500
  (`internal_error`). (b) The user's specific upload failed earlier still, inside `read_cas_pdf`
  itself (→ `parse_failed`), and the underlying casparser exception was **swallowed** — `parse_cas`
  wrapped it as a bare `CasParseError` and `tasks/mf.py` logged only "CAS parse failed" with no
  reason, making it undiagnosable.
- **Fix:** (a) `parse_cas` normalises a pydantic-model reader result to a dict via `model_dump()`
  before the walk — the 1.0 model field names line up 1:1 with the 0.7 dict keys, so it is a drop-in
  that works on both majors — `backend/dhanradar/mf/cas.py`. (b) the `CasParseError` wrap now carries
  the original casparser exception class (`IncorrectPasswordError` / `HeaderParseError` / …) in its
  message, and `tasks/mf.py` logs `reason=%s` server-side (never to the client; no PII/password) so
  the real failure mode is visible — `backend/dhanradar/mf/cas.py`, `backend/dhanradar/tasks/mf.py:142`.
- **Prevention:** `test_parse_cas_normalises_pydantic_model_output` locks in the model→dict path
  (`backend/tests/unit/test_mf_module.py`). Dependency lesson: a `>=X` floor on a load-bearing
  parser silently absorbs the next breaking major — opaque `except`-and-mark-failed paths must log
  the underlying reason or the failure is undiagnosable in prod.
- **Phase/area:** Phase 5 MF module — CAS pipeline (Tier-C). NOTE: the *user's* `parse_failed`
  (the `read_cas_pdf` throw) is now logged but its exact cause is confirmed on the next re-upload.

### 2026-06-09 — Public `/mood` page crash (blank "client-side exception") on an out-of-enum regime

- **Symptom:** `https://dhanradar.com/mood` rendered "Application error: a client-side exception has
  occurred" (blank page) after hydration. HTTP 200 on the shell, so it passed a naive curl check.
- **Root cause:** the backend returns `regime:"data_unavailable"` / `data_quality:"unavailable"`
  when no snapshot has been computed. `data_unavailable` is outside the frontend `Regime` enum, so in
  `MoodGauge` `REGIME_DISPLAY[regime]` was `undefined` and line ~223 called
  `displayWord.toUpperCase()` → uncaught `TypeError` → the whole page died via the Next.js error
  boundary. Latent contract gap, triggered by the current no-snapshot data state (not the disclaimer
  deploy — `MoodGauge` was unchanged by it).
- **Fix:** added `data_unavailable` to the `Regime` enum + all lookup maps and made every regime
  lookup fail-safe (`?? fallback`) so any out-of-enum value degrades to the muted "insufficient"
  presentation instead of throwing (`frontend/src/components/mood/MoodGauge.tsx`); the page now shows
  the existing "being computed" empty state when `data_quality === "unavailable"`
  (`frontend/src/app/mood/page.tsx`); `DataQuality` gained `'unavailable'`
  (`frontend/src/features/mood/types.ts`). Shipped in PR #39.
- **Prevention:** `frontend/src/components/mood/MoodGauge.test.tsx` asserts no-throw on known +
  sentinel + arbitrary-unknown regimes. Lesson: a compliance-critical render component must never be
  able to crash the page on an unexpected enum value; lookups into `Record<Enum, …>` need a fallback.
- **Phase/area:** Mood module (public surface), frontend.

### 2026-06-09 — Celery workers OOM-crash-looping (concurrency=4 vs cgroup limit) + fastapi logs not JSON (uvicorn bypass), both found on the P1 deploy

- **Symptom:** post-deploy check of the live box (per the "read logs before fixing" rule) showed
  `dhanradar-celery-mood` + `-misc` in `Restarting (137)` with `OOMKilled=true` and 20+ restarts
  (`-beat` also churning); `dmesg` had repeated `CONSTRAINT_MEMCG … Killed process … task=celery`.
  Separately, `docker logs dhanradar-fastapi` was uvicorn's PLAIN text (`INFO: … "GET /health"`),
  NOT the structured JSON the P1 change emits on `celery-batch` — so fastapi-tier logs were neither
  JSON nor redacted.
- **Root cause:** (a) Celery prefork `--concurrency` defaults to the vCPU count (4); 4 child
  processes × per-child RSS exceeded the worker containers' cgroup memory limits (mood/misc 192M,
  beat 64M) → memcg OOM-kill → restart loop. Pre-existing, surfaced under image growth. (b) uvicorn
  installs its own `uvicorn`/`uvicorn.access`/`uvicorn.error` loggers with `propagate=False` + their
  own handlers at server boot, so they bypass the root JSON handler `configure_logging()` installs.
- **Fix:** (a) pin `--concurrency=1` on the batch/mood/misc worker commands — `docker-compose.yml`
  (one worker per low-volume queue fits the limit; no memory-limit change, so the compose-memory CI
  guard stays green). (b) in `configure_logging()`, after configuring, clear the uvicorn/gunicorn
  loggers' handlers and set `propagate=True` so their lines flow through the root ProcessorFormatter
  (JSON + redaction) — `backend/dhanradar/core/logging.py`.
- **Prevention:** test `test_uvicorn_loggers_rerouted_to_root` asserts the uvicorn loggers propagate
  with no own handlers; the standing "read logs before fixing" memory ([[check-logs-before-fixing]])
  is what surfaced both on the box. Follow-up DONE: `--concurrency=1` stabilised mood/misc, but
  `-beat` (no `--concurrency` knob) kept OOMing at 64M (~88 MiB needed) — raised beat 64M→128M,
  funded by trimming the now-lean mood+misc 192M→128M each (compose total 3008M, within the 3072M
  cap; guard green).
- **Phase/area:** B57 P1 logging / deploy + Celery worker config.

### 2026-06-08 — P1 logging adversarial review: raw user_id in two log messages + Celery contextvar leak on revoke

- **Symptom:** found by the independent Sonnet adversarial review of the P1 logging change
  (B57) before any commit — not a field incident. Two MUST-FIX findings: (M1) `tasks/mf.py`
  and `billing/service.py` each called `logging.warning`/`logger.error` with a raw user UUID
  %-interpolated into the message string, bypassing the key-based redaction rules. (M2)
  `celery_app.py` had `task_prerun` binding `request_id` + `user_ref` into contextvars and
  `task_postrun` / `task_failure` clearing them, but `task_revoked` had no clear — a revoked
  task left its contextvars bound, so the next task picked up on the same worker thread could
  log under the wrong `user_ref` / `request_id`.
- **Root cause:** (M1) The value-based regex in `_redaction_processor` catches known patterns
  (JWT, PAN, mobile, email, API keys) but a plain UUID4 has no distinct pattern — UUID regex
  was deliberately omitted so `job_id` stays visible. %-interpolation into a message string
  means the value appears as an unstructured substring of the `event` field; the key-based
  hash rule (`user_id` → sha256[:16]) never fires because the key is `event`, not `user_id`.
  (M2) The `task_revoked` signal path was not listed alongside `task_postrun` and
  `task_failure` when the contextvar clear was written — an omission, not a design choice.
- **Fix:** (M1) `backend/dhanradar/tasks/mf.py` — replaced
  `_slog.warning("...", user_id)` with `_slog.warning("...", user_ref=hash_user_ref(uid))`.
  `backend/dhanradar/billing/service.py` — replaced
  `logger.error("...", str(user_id))` with `logger.error("...", hash_user_ref(str(user_id)))`.
  (M2) `backend/dhanradar/celery_app.py` — added `@task_revoked.connect` handler that calls
  `structlog.contextvars.clear_contextvars()`, mirroring the `task_postrun` and
  `task_failure` handlers.
- **Prevention:** never %-interpolate a user id or any PII into a log message string — always
  pass a hashed `user_ref=hash_user_ref(uid)` as a structured keyword argument so the
  key-based redaction rule fires. Every `task_prerun` contextvar bind must be matched by a
  clear on ALL exit signals: `task_postrun`, `task_failure`, AND `task_revoked`. The
  redaction filter is test-enforced (`backend/tests/test_logging_redaction.py`, 16 tests) but
  cannot protect against values that bypass the key rules via message-string interpolation —
  the "never %-interpolate PII" rule is the only guard for that class.
- **Phase/area:** B57 P1 logging — load-bearing middleware + Celery signal wiring; caught at
  Tier-B adversarial review, not a field incident.

### 2026-06-08 — CAS re-upload bounced to a dead job (dedup returned a non-`done` job)

- **Symptom:** after the pipeline was fixed, re-uploading the same eCAS "did nothing" — the UI returned to the old, failed job and spun. The upload POST returned 202 but the status poll was for the OLD job id.
- **Root cause:** the SHA-256 upload dedup (`mf/router.py` :: `upload_cas`) returned ANY existing job for the content hash via `service.dedup_lookup` (Redis `mf:cas:dedup:{user}:{pf}:{hash}` → job_id), regardless of that job's status. The user's first upload had recorded job `4dd2d997`; every re-upload of the same file deduped straight back to it — even after it was marked `failed`. Re-uploading is exactly the retry path, so returning the dead job is the bug.
- **Fix:** only short-circuit to a job that actually `done` — `backend/dhanradar/mf/router.py` now `db.get(MfCasJob, existing)` and returns the dedup only when `status == "done"`; otherwise it calls the new `service.dedup_clear(...)` and falls through to create a fresh job. Unblocked the live user by deleting the stale Redis dedup keys. Unit test `test_dedup_clear_removes_record_so_reupload_reprocesses`.
- **Prevention:** a dedup/idempotency cache must key on a SUCCESSFUL terminal state, never "an attempt happened". Any "return the existing X" path needs to check that X is actually usable. (Mirrors the consent-writer lesson: validate the stored value, don't trust its presence.)
- **Phase/area:** Post-launch / MF CAS upload dedup.

### 2026-06-08 — Core MF wedge non-functional in prod: Celery task-discard, CAS file not shared, NAV-backfill OOM, frontend↔backend contract drift

- **Symptom:** an uploaded CAS hung forever on "Analysing your portfolio…". Reported live after go-live.
- **Root cause (four distinct bugs in the one flow):**
  1. **Workers registered ZERO tasks.** `celery_app.autodiscover_tasks(["dhanradar.tasks"])` resolves to the non-existent module `dhanradar.tasks.tasks` (package + default `related_name="tasks"`) and `tasks/__init__.py` is empty, so every worker imported no task modules. Every enqueued message (CAS, NAV, notify, mood, archival) was received as an *unregistered task* and silently discarded → the job row never advanced past `queued`.
  2. **CAS file not shared.** The API writes the PDF to `/tmp/dhanradar_cas` in the fastapi container; the worker read it in ITS container (no shared mount) → file-not-found even once registered.
  3. **NAV backfill OOM.** `nav_backfill` parses a 90-day all-funds AMFI window (tens of MB) — over the 256 MB celery-batch limit → `SIGKILL`/`WorkerLostError`; `mf_nav_history` stayed empty, so every fund scored `insufficient_data`.
  4. **Frontend↔backend contract drift.** The MF report UI was built against MSW mocks and never integrated: it polled `/mf/upload/cas/{id}/status` (backend had deviated to `/cas/{id}/status` → 404, infinite spinner), fetched the report at the wrong URL, mapped status `failed`→never-terminal, and expected a different (mock) report shape.
- **Fix:** (1) explicit `include=[the 5 task modules]` on `Celery()` + regression test (`test_celery_task_registration`) — `backend/dhanradar/celery_app.py` (PR #33). (2) shared named volume `dhanradar_cas_tmp` on fastapi + celery-batch; Dockerfile pre-creates the dir owned by appuser — `docker-compose.yml`, `backend/Dockerfile` (PR #33). (3) run the multi-year backfill as a one-off container with `-m 2g` (the 256 MB worker is right for steady-state per-portfolio scoring); 2.12M rows / 8841 funds populated, funds now score `on_track` etc. (4) backend status route → canonical `/upload/cas/{job_id}/status`; frontend `api.ts` adapters map the real backend wire shapes → the page contract + map status values — `backend/dhanradar/mf/router.py`, `frontend/src/features/mf/api.ts`, `types.ts` (PR #34). Plus: gated `archive_audit_daily` behind `AUDIT_ARCHIVE_ENABLED` (default off, DPDP residency) since the box is Mumbai-resident.
- **Prevention:** CI must exercise a real worker round-trip (enqueue→consume), not just call task functions directly — that gap hid (1) and (4) through green CI. Keep the `include=[...]` list in sync with `dhanradar/tasks/` (the regression test enforces it). A frontend built against MSW mocks needs at least one integration test (or a generated client from the backend OpenAPI) so contract drift fails CI, not production. Heavy one-off bootstrap jobs (`nav_backfill`) must run with their own memory budget, not on the steady worker. Multi-container file hand-offs need a shared volume by design — never rely on a per-container `/tmp`.
- **Phase/area:** Post-launch / MF report wedge (CAS→labelled report) end-to-end integration.

### 2026-06-08 — First KVM4 production deploy: five environment-gap blockers (init, nextjs ×2, beat, alembic) + cloudflared creds perms

- **Symptom:** the first real deploy surfaced five issues that local/CI runs had not: (1) `dhanradar-postgres` would crash-loop on first init; (2) `dhanradar-nextjs` reachable by service name but marked `unhealthy`; (3) still `unhealthy` after the bind fix; (4) `dhanradar-celery-beat` crash-loop; (5) `alembic upgrade head` → `ModuleNotFoundError: dhanradar`; and at go-live, cloudflared `permission denied` reading its credentials.
- **Root cause:** (1) `timescaledb-ha:pg16` lacks `pg_partman`; `01_init.sql`'s bare `CREATE EXTENSION` aborts under the entrypoint's ON_ERROR_STOP (the B55 fix had only patched the CI sed-strip, not the prod init path that runs via `docker-entrypoint-initdb.d`). (2) Next.js standalone binds `$HOSTNAME`, which Docker sets to the container id → it listens on the container IP only, not loopback. (3) the healthcheck used `localhost`, which alpine resolves to `::1` (IPv6) first, but the server is IPv4 `0.0.0.0` only → ECONNREFUSED. (4) celery beat's `PersistentScheduler` writes `./celerybeat-schedule` in root-owned `/app` as non-root `appuser` → EACCES. (5) the `dhanradar` package is COPYed to `/app` but never `pip install`ed; uvicorn imports it because uvicorn injects CWD onto `sys.path`, but bare `alembic` (a console script) does not. (creds) the cloudflared image runs as uid `65532`; the creds file was `0400 root:root`.
- **Fix:** (1) per-extension `EXCEPTION WHEN OTHERS` guard in `infra/postgres/init/01_init.sql`; CI runs it verbatim now (PR #29). (2) `HOSTNAME=0.0.0.0` on the nextjs service (PR #30). (3) healthcheck → `http://127.0.0.1:3000/` (PR #31). (4) `--schedule=/tmp/celerybeat-schedule` (PR #30). (5) `python -m alembic` in `deploy.sh` + at deploy time (PR #30). (creds) `chown 65532:65532` the creds file, keep `0400` (box-provisioning, not in the public repo).
- **Prevention:** the prod init path must be exercised verbatim in CI (now done) — a CI-only workaround (sed-strip) hid a prod-init abort for both `pg_cron` and `pg_partman`. For containerised Python apps not installed as a package, always invoke entry points as `python -m <tool>` so CWD is importable. For Next.js standalone in Docker: set `HOSTNAME=0.0.0.0` and probe `127.0.0.1` (never `localhost`) in healthchecks. Non-root images need writable paths for any tool that persists state (`/tmp` or a named volume). A bind-mounted secret must be readable by the container's runtime uid — provision its owner, do not loosen to world-read on a shared box. Recorded in `docs/ops/DEPLOY_LOG_2026-06-08.md`.
- **Phase/area:** Production deploy / KVM4 first bring-up.

### 2026-06-08 — Consent grant/revoke stored a double-encoded JSON string scalar → every grant read back as not-granted (B54)

- **Symptom:** CI `backend` job red — 5 `test_consent_writer` integration tests failed: a grant returned `consents.mf_analytics == false`, the raw `dpdp_consents` value was not a dict after grant/revoke, and siblings appeared clobbered. Only reproduced in CI (integration tests need a live Postgres; local `pytest` skips them), so B44's "tests pass" missed it.
- **Root cause:** `apply_consent_change` built `payload_json = json.dumps(payload)` and wrote `cast(payload_json, JSONB)`. The cast bound the *string* through SQLAlchemy's JSONB bind type, whose serializer ran `json.dumps` a SECOND time — storing a JSONB *string* scalar (`"{\"granted\": true …}"`) instead of an object. The canonical reader `_consent_granted` requires `isinstance(value, dict) and value.get("granted") is True`; a string fails `isinstance(dict)` → fail-CLOSED (not-granted) for every purpose. (Fail-closed, so not a security breach — but it makes consent unusable.)
- **Fix:** pass the dict so the JSONB bind type serialises exactly once — `cast(payload, JSONB)`; removed the now-unused `payload_json`/`import json` — `backend/dhanradar/consent/service.py:57,72`. Proven before the fix via a DB-free SQL-compilation diagnostic (the bound param was a str pre-fix, a dict post-fix). Tier-B adversarial review (Sonnet takeover, codex n/a — account lacks any Codex model entitlement) ACCEPT: no fail-open path across 6 vectors.
- **Prevention:** never `json.dumps(...)` a value that is then bound through a JSONB/JSON column or `cast(..., JSONB)` — the type's bind processor already serialises; pre-serialising double-encodes. Integration tests for any JSONB writer must assert the RAW column shape (`isinstance(dict)`, key truthiness), not just the API echo, and must run in CI against Postgres (the `create_all`/SQLite-ish local path does not exercise `jsonb_set`). Related: CI is the authoritative gate, not local `pytest`.
- **Phase/area:** Pre-deploy launch-gate / Consent (B44/B48) writer.

### 2026-06-08 — Consent writer idempotency key shared across grant+revoke (review-found fail-open) + 0-row UPDATE false audit (B44)

- **Symptom:** found in inline Opus review + the Tier-B Sonnet adversarial takeover (codex n/a)
  BEFORE any commit — two defects in the B44 consent writer draft: (1) the Redis idempotency key
  `consent:idem:{uid}:{key}` was not scoped by operation, so reusing one key value for a grant then
  a revoke made the revoke look like a replay → silently skipped → consent stayed granted while the
  caller received HTTP 200 (fail-open: user believes they revoked; the gate still passes them).
  (2) a grant/revoke for a user whose row was deleted mid-session (DPDP-erasure race) matched 0 rows
  on the `UPDATE` but still committed an audit row — a false forensic record of a consent change
  that never happened.
- **Root cause:** (1) the idempotency key was namespaced only by `uid` + client key, with no
  operation dimension — same dedup-without-full-scope class as the auth refresh `GETDEL` RCA
  (2026-05-19). (2) `result.rowcount` was not checked after the `UPDATE`; the audit append is only
  meaningful if the data write actually changed a row.
- **Fix:** (1) key namespaced per action — `consent:idem:grant:{uid}:{key}` /
  `consent:idem:revoke:{uid}:{key}` (`backend/dhanradar/consent/router.py`). (2) `rowcount == 0` →
  `await db.rollback()` + raise 401 `user_not_found` before any audit row is added
  (`backend/dhanradar/consent/service.py`). Both applied before the first commit (`927f64f`).
- **Prevention:** regression tests `test_same_idempotency_key_across_grant_then_revoke_still_revokes`
  and `test_grant_for_deleted_user_fails_closed_no_audit`
  (`backend/tests/integration/test_consent_writer.py`). Rule: an idempotency key that deduplicates
  mutating operations MUST include the operation name in its namespace; a data write and its audit
  append must be gated on `rowcount > 0`.
- **Phase/area:** B44 consent writer (load-bearing) — caught at inline Tier-B review, not a field
  incident.

### 2026-06-07 — Duplicate alembic revision `0008` silently broke `alembic upgrade head` (B36)

- **Symptom:** `alembic heads` warned `Revision 0008 is present more than once` and `alembic history`
  errored `FAILED: Requested revision 0009 overlaps with other requested revisions 0008`. A real
  deploy would have had no resolvable single head — `alembic upgrade head` is ambiguous/unrunnable.
  Caught while building the B36 deploy runbook, not in the field (the stack has never been deployed).
- **Root cause:** two migrations both declared `revision = "0008"` with `down_revision = "0007"` —
  `0008_admin_compliance_tables.py` and `0008_mf_nav_monthly_agg.py` (B29, landed in a separate
  slice). `0009` then set `down_revision = "0008"`, which no longer named a unique parent. The two
  0008s were authored in different sessions/PRs that each picked the next integer independently;
  nothing rejected the collision because the local test DB builds tables from ORM metadata
  (`create_all`), never runs the migration chain (B40), so CI never exercised `upgrade head`.
- **Fix:** linearized the chain — renumbered the independent mf_nav migration to `revision = "0008a"`,
  `down_revision = "0008"` (file renamed `0008a_mf_nav_monthly_agg.py`), and repointed
  `0009_engine_activation_unique.py` `down_revision` to `"0008a"`. Order is safe: 0009's real
  dependency (`compliance.rating_engine_changelog`, created in admin 0008) stays upstream; mf_nav is
  an independent `mf` schema continuous aggregate. Verified `alembic heads` → single `0009` and
  `alembic history` resolves linearly. No production DB was stamped (pre-launch), so renumbering is
  free. (`7035400`)
- **Prevention:** B40 will run `alembic upgrade head` against the real TimescaleDB image in CI — that
  turns this exact failure (duplicate/branched revision) into a red CI check instead of a deploy-time
  surprise. Rule for authors: when adding a migration, run `alembic heads` and confirm a **single**
  head before committing; never reuse an integer another in-flight branch may have taken.
- **Phase/area:** Alembic migration chain (load-bearing) / B36 deploy gate.

### 2026-06-07 — Integration test awaited a SYNC `AsyncSession.expire_all()` — passed local collect, failed first CI run (B26-admin)

- **Symptom:** the B26-admin PR (#22) backend CI job failed: `test_create_then_activate_disclaimer`
  raised `TypeError: object NoneType can't be used in 'await' expression` at
  `tests/integration/test_admin.py:185`. 411 passed, 1 failed. Found by CI before merge (not a
  field incident).
- **Root cause:** the test wrote `await db_session.expire_all()`. `AsyncSession.expire_all()` is a
  **synchronous** method (returns `None`), so `await None` raises `TypeError`. The bug survived local
  checks because the integration suite is only ever **collected** locally (no local Postgres, B1) and
  first **executes** in CI — `--collect-only` imports and parses the test but never runs the awaited
  expression. Same exists≠executed class as the "field shown ≠ field wired" RCAs, applied to tests.
- **Fix:** `db_session.expire_all()` (no `await`) with an inline note "sync on AsyncSession — must
  NOT be awaited" (`tests/integration/test_admin.py`). Scanned the slice's test + code for sibling
  awaited-sync calls (`expire(_all)`/`expunge`/`add`/`put_object`) — none (the only `await
  redis.expire` is the genuinely-async Redis client).
- **Prevention:** rule — a new integration test that only collects locally is UNVERIFIED until the
  CI backend job runs it; treat the first CI run as the real gate and read its result before merging
  (do not merge over a pending/failed backend check). Sync vs async on `AsyncSession`: `execute`,
  `scalar(s)`, `commit`, `rollback`, `flush`, `get` are async (await); `add`, `add_all`, `expire`,
  `expire_all`, `expunge` are sync (never await).
- **Phase/area:** B26-admin endpoints / integration test harness. Caught at the PR-#22 CI gate.

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

### 2026-06-22 — Mood news-sentiment signal chronically absent (starved by MF-only filter)

- **Symptom:** the 11th mood signal `news_sentiment` was almost never present; the mood engine ran at ≤7/11, and the signal showed "Awaiting data" on the /mood page despite GDELT working.
- **Root cause:** GDELT's query is already India-market-scoped (returns Moneycontrol "Sensex up 400 pts, Nifty above 24,100" etc.), but every article was then re-filtered through `news.rss._is_mf_relevant`, an **MF-only gate** (MF + monetary-policy keywords). Broad equity-market headlines matched neither and were dropped. Only ~3 thin, mostly-US headlines survived per 48h → the AI tone read landed below the 0.30 confidence floor → signal withheld (`mood/news_sentiment.py`).
- **Fix:** added `_MARKET_KEYWORDS` (distinctive equity-market terms; short ambiguous tokens + trade-action words excluded) → category `market`; the gate now keeps broad market headlines. Surfaced on the public news feed too (founder decision). `backend/dhanradar/news/rss.py` (PR #301, main `bf4d020`). Headline-metadata-only; gateway advisory screen + confidence floor still gate the score (no-impute intact). Tier-B compliance review ACCEPT — both hard gates clean.
- **Prevention:** a source-relevance filter NARROWER than the fetch query silently discards intended data — when a query is already scoped, don't re-filter on a different (stricter) axis. Verified the deployed gate keeps real Sensex/Nifty/FII headlines and still drops banking noise. Residual: GDELT 429s intermittently under manual hammering (rare under normal cadence); ingested headlines persist 48h so a single good call seeds the pool.
- **Phase/area:** Market Mood / news-sentiment signal.
