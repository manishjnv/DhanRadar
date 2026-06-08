# DhanRadar — LAUNCH RUNBOOK (KVM4 deploy)

Single ordered checklist to take `hardening/launch-gate-blockers` (PR #28) from a
CI-green branch to a verified production deploy on KVM4.

**How to read this:** every step is tagged either

- `[done-this-session]` — already completed by the build session; nothing for you to do
  except note it, **or**
- `[OPERATOR on KVM4]` — a human/infra action you must run yourself.

**Absolute guardrails (never violate — `docs/infra-notes.md`):**

- ❌ NEVER touch the host `/etc/cloudflared/config.yml` or the host `cloudflared` systemd
  service — that is the **etip-ssh** tunnel (`6e263591-…`), the box's SSH lifeline.
  DhanRadar uses its own pinned `dhanradar-cloudflared` **container**.
- ❌ NEVER touch any `etip_*` / `roadmap*` / `accessbridge*` / `ti-platform*` / `assessiq*` /
  `trendsmap*` / `dev-tunnel` container, volume, or config.
- ❌ NEVER upgrade the host `cloudflared` binary (2026.3.0).
- ❌ NEVER `pkill -f` / `killall` / bare `docker stop|rm|system prune` — scope every Docker op
  to `docker compose -p dhanradar -f docker-compose.yml …` (the scripts already do this).
- Cloudflared DNS routing, if ever needed: always use explicit tunnel **UUID** +
  `--overwrite-dns`; validate with `cloudflared tunnel --config FILE ingress validate`
  (global flag BEFORE the subcommand).

**Deploy gate (project `CLAUDE.md`):** a passing CI ledger is *merge-eligible, not
deploy-eligible*. Production needs: **no open Security/Compliance BLOCKER** + the **Phase-7 §5
adversarial gate logged** + **separate explicit human approval**. Honor it at Step 8.

---

## STEP 0 — Pre-flight: confirm CI is green on the head commit `[done-this-session]`

The build session fixed the three red checks and pushed `135ad63` to
`hardening/launch-gate-blockers`:

- **B54** (backend pytest, 5 failures) — consent grant/revoke `jsonb_set` double-encode fixed
  in `backend/dhanradar/consent/service.py`. Tier-B adversarial review: **ACCEPT** (no fail-open).
- **market_data** (backend pytest, 2 failures) — stale canned-stub unit tests for the now
  DB-backed `AMFINavProvider` replaced; DB happy-path covered by
  `tests/integration/test_mf_nav_scoring.py`.
- **B55** (migrations) — `pg_partman` stripped in the CI migrations job (like `pg_cron`); the one
  migration that uses it (`0006`) already guards behind `IF EXISTS … RAISE NOTICE`-skip.
  Production `infra/postgres/init/01_init.sql` keeps the strict `CREATE EXTENSION` (fail-loud).
- **B48** — new tests prove `ENV=production` forces consent enforcement.

`[OPERATOR]` Before merging, confirm the required checks are green on the head commit:

```bash
gh pr checks 28
# Expect: backend = pass, migrations = pass, frontend = pass, guards = pass.
# lint MAY show fail — it is continue-on-error (advisory, B40 ruff backlog). NOT a blocker.
```

PR: <https://github.com/manishjnv/DhanRadar/pull/28>

> If `backend` or `migrations` is not `pass`, STOP — do not proceed. Re-open the build session.

---

## STEP 1 — Merge PR #28 into `main` `[OPERATOR on KVM4 / GitHub]`

The merge is a **human approval on `main`** — never automated by the build session.

```bash
# The PR is currently a DRAFT (WIP). Mark it ready, then squash-merge:
gh pr ready 28
gh pr merge 28 --squash --subject "Launch-gate hardening (PR #28)"
# Confirm main now points at the merge commit:
gh api repos/manishjnv/DhanRadar/commits/main --jq '.sha[0:8]'
```

**Verification:** `gh pr view 28 --json state --jq .state` returns `MERGED`. The GitHub
`production` environment is main-gated, so deploy can only proceed from `main`.

---

## STEP 2 — Set production env: `ENV=production` + consent enforced `[OPERATOR on KVM4]`

On the KVM4 box, in the DhanRadar repo root, edit the production `.env` (NEVER commit it; the
repo is public). Required for the consent gate (B48):

```dotenv
ENV=production
# DPDP consent: do NOT ship a disable flag in production. EITHER omit the line
# (default is enforced) OR set it true. A `false` here will HARD-CRASH the app at boot.
DPDP_CONSENT_ENFORCED=true
```

**Why this is safe (B48, verified this session):** the config boot guard
(`backend/dhanradar/config.py` → `model_post_init`) refuses to start if
`DPDP_CONSENT_ENFORCED=false` in any env that is not `development`/`test`/`ci`. So even a leaked
dev kill-switch cannot silently disable consent on production. `consent_bypassed` is `False`
for `ENV=production` regardless of the flag. Proven by
`backend/tests/unit/test_b48_consent_prod_guard.py` (6 tests) +
`tests/integration/test_consent_writer.py::test_consent_gated_route_refuses_without_grant`.

Also set the other production secrets per `docs/infra-notes.md` / `.env.example` (DB password,
JWT keys, Razorpay live keys, Resend key, `INTERNAL_API_TOKEN`, R2 vars — see Steps 3 & 6).

**Verification (after the stack is up in Step 4):**

```bash
docker compose -p dhanradar exec dhanradar-fastapi printenv ENV
# → production
# Negative test: a consent-gated route refuses an un-granted user:
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://dhanradar.com/api/v1/mf/upload/cas
# → 401 (anonymous) ; a logged-in user without a grant → 403 consent_required.
```

---

## STEP 3 — Verify R2 archival bucket is India-resident (B34) `[OPERATOR on KVM4]`

The 7-year SEBI `ai_recommendation_audit` archive contains `user_id` (DPDP personal data). The
**only** approved cross-border control is India bucket residency (ADR-0022 — do NOT pseudonymize).

Full procedure: `docs/ops/b25-b34-infra-verification.md` (B34). Essentials:

1. In the Cloudflare dashboard → **R2 → <bucket> → Settings → Bucket details**, confirm
   **Jurisdiction = India (IN)**. Jurisdiction cannot be changed after creation — if it is not
   India, create a new bucket:

   ```bash
   curl -s -X POST "https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/r2/buckets" \
     -H "Authorization: Bearer <R2_API_TOKEN>" -H "Content-Type: application/json" \
     -d '{"name":"<BUCKET_NAME>","locationHint":"APAC","jurisdiction":"in"}'
   # Response must show "jurisdiction": "in".
   ```

2. Add the **7-year (84-month) lifecycle rule** on the bucket (dashboard → Object lifecycle
   rules, or API). The backup script does NOT manage long-term retention — the bucket does.
3. Set the archival R2 env vars (note these differ from the backup vars in Step 5):
   `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` (the
   India bucket), `R2_ENDPOINT_URL`.

**Verification (run after Step 4):**

```bash
docker compose -p dhanradar exec dhanradar-fastapi printenv R2_BUCKET_NAME   # matches India bucket
docker compose -p dhanradar exec dhanradar-celery-misc \
  celery -A dhanradar.celery_app call dhanradar.tasks.compliance.archive_audit_daily
# → "archive: N rows → r2://audit/YYYY/MM/DD.jsonl.gz"  (NOT "R2 unconfigured")
```

> Archival is best-effort: it logs a warning and skips if R2 is unset, so the stack is safe to
> deploy first and enable archival once residency is confirmed.

---

## STEP 4 — Deploy + migrations via `deploy.sh` (B36) `[OPERATOR on KVM4]`

`scripts/deploy.sh` (validated this session) scopes every Docker op to `-p dhanradar`, runs
migrations **pre-serve on the new image**, and gates on a smoke test. Run from the repo root on
the **`main`** checkout:

```bash
git fetch origin && git checkout main && git pull --ff-only origin main
bash scripts/deploy.sh deploy
```

What it does, in order (each must succeed or it aborts non-zero):

1. `docker compose -p dhanradar build`
2. brings up `dhanradar-postgres` + `dhanradar-redis`, waits for `healthy`
3. **`alembic upgrade head`** on the new image (pre-serve) — `compose run --rm -T dhanradar-fastapi`
4. `docker compose -p dhanradar up -d` (all 9 services)
5. waits for `dhanradar-fastapi` + `dhanradar-nextjs` healthy
6. smoke test: `GET http://localhost:8000/api/v1/health` must return 200, else **abort**

**Expected tail:** `Smoke test passed — API returned 200.` then `Deploy complete.` then a
per-service `state=running health=healthy` table.

**Migration reversibility (already proven in CI on the prod-like `timescaledb-ha:pg16` image):**
the `migrations` job runs `upgrade head → downgrade base → upgrade head` clean. Single head
(`alembic heads` returns exactly one). You do NOT need to run a downgrade on the live box.

**Verification:**

```bash
bash scripts/deploy.sh status         # all 9 services running + healthy
docker compose -p dhanradar run --rm dhanradar-fastapi alembic current   # one head, matches code
curl -s -o /dev/null -w "%{http_code}\n" https://dhanradar.com/api/v1/health   # 200
```

> First populate of MF NAV data (B29) so the wedge produces real labels — run AFTER the stack is
> healthy (these are operational, not part of deploy.sh):
>
> ```bash
> docker compose -p dhanradar exec dhanradar-celery-batch \
>   celery -A dhanradar.celery_app call dhanradar.tasks.mf.nav_backfill --args='[3]'
> # then confirm the daily fetch beat task is scheduled (Step 5 monitoring shows it running).
> ```

---

## STEP 5 — Backups + monitoring live (B37, B38) `[OPERATOR on KVM4]`

### 5a. Backups (B37) — `scripts/backup.sh`

Validated this session: `pg_dump -Fc` (size-sanity gated) + Redis BGSAVE/AOF → MANIFEST with
sha256 → upload to the **India** R2 backup bucket. Uses **distinct** env vars from archival:
`R2_BACKUP_BUCKET`, `R2_ENDPOINT` (+ `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`).

```bash
# One manual run to prove the path end-to-end:
bash scripts/backup.sh
# Expected tail: "=== Backup SUCCESS: stamp=… r2_dest=s3://<bucket>/<stamp>/ ==="

# Then schedule nightly (host cron — NOT the host cloudflared, NOT etip_*):
crontab -e
#   30 20 * * *  cd /path/to/DhanRadar && bash scripts/backup.sh >> /var/log/dhanradar-backup.log 2>&1
#   (20:30 UTC = 02:00 IST)
```

**Restore drill (do once before relying on backups):** restore the just-made backup into a
throwaway target and verify, per `docs/ops/backup-restore-runbook.md`. `restore.sh` is gated by
`CONFIRM_RESTORE=1`, verifies sha256 + rejects path-traversal artifact names.

### 5b. Monitoring (B38) — Sentry + Prometheus

App code is done (`init_sentry()` + a `/metrics` endpoint outside `/api/v1`, no bearer auth — by
design). Residual is infra wiring onto the shared `etip_prometheus` / `etip_grafana` stack
(read-only to us — add scrape config + alert rules; do not restart etip services destructively).

```bash
# Confirm the app exposes metrics from inside the network:
docker compose -p dhanradar exec dhanradar-fastapi \
  python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/metrics').status)"
# → 200
# Confirm SENTRY_DSN is set (errors will report):
docker compose -p dhanradar exec dhanradar-fastapi printenv SENTRY_DSN | wc -c   # > 1
```

Add a Prometheus scrape target for the dhanradar-fastapi `/metrics` endpoint and alert rules
(health down, audit-write-failure metric > 0). Verify the target shows **UP** in Prometheus and
a test alert routes to Grafana.

---

## STEP 6 — Internal numeric endpoint isolation / mTLS (B25) `[OPERATOR on KVM4]`

`/internal/v1/score/…` is mounted without `/api/v1` (cloudflared routes only `^/api/.*` to
FastAPI) and is fail-closed: `INTERNAL_API_TOKEN` unset → 503; wrong `X-Internal-Token` → 403
(`hmac.compare_digest`). Full procedure: `docs/ops/b25-b34-infra-verification.md` (B25).

```bash
# 1. Token set with real entropy (>32 chars):
docker compose -p dhanradar exec dhanradar-fastapi printenv INTERNAL_API_TOKEN | wc -c   # > 32
# 2. Not reachable from outside the tunnel (run from a laptop / off-box):
curl -s -o /dev/null -w "%{http_code}\n" https://dhanradar.com/internal/v1/score/equity/RELIANCE
#    → 404 (or 403/503). A 200 is a BLOCKER — stop.
# 3. Port 8000 NOT host-published:
docker compose -p dhanradar ps dhanradar-fastapi      # PORTS column empty / internal only
ss -tlnp | grep 8000                                  # no output
#    (Ensure the dev-only docker-compose.override.yml that publishes 8000 is NOT used in prod.)
```

mTLS / dedicated internal Docker network is the recommended hardening (not required at launch);
if applied, document the approach in `docs/infra-notes.md`.

---

## STEP 7 — Production smoke test `[OPERATOR on KVM4]`

```bash
# Public health:
curl -s -o /dev/null -w "%{http_code}\n" https://dhanradar.com/api/v1/health         # 200
# Auth posture (no bearer auth; cookie-based):
curl -s -o /dev/null -w "%{http_code}\n" https://dhanradar.com/api/v1/consent        # 401 not_authenticated
# Consent enforced (un-granted user is refused) — sanity that B48 is live:
#   sign up a throwaway account in the UI, do NOT grant, attempt a CAS upload → 403 consent_required.
# RFC7807 + request_id present on an error body:
curl -s https://dhanradar.com/api/v1/does-not-exist | grep -E 'request_id|type'
# Frontend renders (no numeric score in DOM — non-neg #2): load the report page, view source.
```

All green → proceed to the gate.

---

## STEP 8 — GO / NO-GO gate `[OPERATOR — human decision]`

**GO requires ALL of:**

- [ ] PR #28 merged to `main`; deploy ran from `main`; `alembic current` = single head.
- [ ] **No open Security/Compliance BLOCKER** (see `BLOCKERS.md`).
- [ ] **Phase-7 §5 adversarial panel logged** — `docs/project-state/reviews/phase7-predeploy-panel.md`
      (ACCEPT-WITH-CONDITIONS, no REJECT).
- [ ] B48 consent enforced in prod (Step 2 verified).
- [ ] B34 R2 bucket India-resident + 7-yr lifecycle (Step 3 verified).
- [ ] B25 internal endpoint not publicly reachable + token set (Step 6 verified).
- [ ] B37 backup ran + restore drill passed; nightly cron scheduled (Step 5a).
- [ ] B38 `/metrics` UP in Prometheus + Sentry DSN set + alerts route (Step 5b).
- [ ] B29 NAV backfill run — funds produce real labels, not `insufficient_data` (Step 4 note).
- [ ] **Separate explicit human approval** recorded.

**NO-GO if any box is unchecked.** A failing Step-6 curl returning 200, a non-India R2 bucket, or
an un-enforced consent gate are hard stops.

---

## ROLLBACK PLAN `[OPERATOR on KVM4]`

**Trigger:** smoke test fails, error rate spikes in Sentry/Prometheus, or a data-integrity issue
appears post-deploy.

**App-only rollback (safe, no schema change — migrations are additive so old code runs on the new
schema):**

```bash
git fetch origin
git checkout <previous-good-sha-or-tag>
bash scripts/deploy.sh deploy        # rebuilds + redeploys at the checked-out ref, re-smoke-tests
# (scripts/deploy.sh rollback <ref> prints the same guidance; it does NOT auto-downgrade schema.)
```

**Schema downgrade (DANGEROUS — only if a migration is the cause):** follow the MANUAL procedure
in `docs/ops/deploy-runbook.md` §6b. A **verified B37 backup must exist first**. Restore from
backup if data was lost:

```bash
CONFIRM_RESTORE=1 bash scripts/restore.sh <r2-backup-prefix>   # e.g. 20260608203000
# then: docker compose -p dhanradar run --rm dhanradar-fastapi alembic current  (verify head)
```

Never `pkill`, never bare `docker rm`, never touch host cloudflared/etip during a rollback.

---

## Session provenance

Prepared by the DEPLOY-READINESS session (2026-06-08). Code changes this session:
commit `135ad63` (B54 consent fix + B55 CI + B48 tests + market_data test repair). The session did
**not** ssh to KVM4, did **not** merge `main`, and did **not** mutate any infra or secret — every
`[OPERATOR on KVM4]` step above is left for the human deployer.
