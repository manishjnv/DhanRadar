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

### 2026-06-10 — B56 news: feed shows 2-year-old headlines + dead (404) links

- **Symptom:** the dashboard Market News widget shows stale 2024 items ("SEBI circular … March
  2024", "AMFI … April 2024", "RBI … April 2024" — rendered "792d ago" etc.) and the headline
  links 404. (SEV3 — degraded, user-visible trust issue; wedge unaffected.)
- **Root cause (design/data, not a code bug):** the `/news` feature shipped only the *admin-curated
  fallback* — a **hardcoded static list of 3 sample 2024 headlines** in `news/service.py:34-59`
  (`_CURATED_ITEMS`) with **fixed 2024 `published_at`** and **unverified placeholder URLs**. The
  beat task `tasks/news.py::refresh_market_news` re-upserts those same 3 rows every 30 min, so the
  feed never advances and never carries recent items. The PRIMARY live-source path (RSS / a real
  feed with feed-supplied dates + real URLs) was **never built** (no `rss/httpx/fetch` anywhere in
  `news/`). Reproduced: HEAD-checking the 3 URLs → SEBI **404**, AMFI **404**, RBI 200. So "old
  news" = frozen seed dates; "404 links" = placeholder URLs that were never liveness-checked.
- **Fix:** NOT YET APPLIED — tracked as a build task (see below). Corrective = replace the static
  seed with a real recent-news source (sanctioned RSS: RBI press / SEBI circulars / AMFI, or a
  vetted financial RSS) surfacing feed-supplied recent `published_at` + real item URLs.
- **Prevention (the class, not the instance):** (1) **URL liveness check at ingest** — HEAD each
  `canonical_url`, skip/deactivate non-200 so a dead link can never reach the UI; (2) **recency
  guard** — don't serve items older than N days and/or show an "as of" freshness label; (3)
  **staleness observability** — log/metric + alert when the newest served item is older than a
  threshold (today there is no signal that the feed has gone stale); (4) a regression test asserting
  served items are within the recency window and URLs were liveness-checked. Captured in memory
  [[news-feed-stale-hardcoded-seed]].
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
