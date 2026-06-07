# DhanRadar — B25 / B34 Deploy-Time Infra Verification

The application code for B25 and B34 is complete. This document is the human and infra
verification procedure that must be run on the KVM4 box before those blockers can be
marked cleared at deploy time. Nothing here requires an application code change.

## How this maps to the deploy checklist

See `docs/project-state/DEPLOY_GATE_CHECKLIST.md`.
B25 maps to **Gate 4** (internal numeric endpoint network policy / mTLS).
B34 maps to **Gate 3** (R2 archival India-residency) and is also verified as part of
**Gate 6** (live-stack runtime proofs).

---

## B25 — Internal numeric endpoint isolation

### Code already in place

The internal score endpoint lives at `GET /internal/v1/score/{instrument_type}/{identifier}`.
It is mounted **without** the `/api/v1` prefix, which is the first layer of isolation
(the cloudflared ingress at `infra/cloudflared/config.yml` routes only `^/api/.*` to
FastAPI; anything else falls through to the catch-all `http_status:404` rule).

The second layer is a fail-closed shared-secret guard in
`backend/dhanradar/scoring/engine/router.py`, lines 33–41.
If `settings.INTERNAL_API_TOKEN` is unset, the guard raises HTTP 503 immediately — the
endpoint is disabled rather than open.
If the token is set but the caller's `X-Internal-Token` header does not match
(`hmac.compare_digest`), the guard raises HTTP 403.

### What must be verified at deploy

1. `INTERNAL_API_TOKEN` is set in production to a strong random secret (min 32 bytes of entropy).
2. The `/internal/v1/score` path is **not** reachable through the public cloudflared tunnel
   or any host-published port.
3. The FastAPI container does not expose port 8000 to the host in the production compose file
   (the `docker-compose.override.yml` that publishes port 8000 is dev-only and must not be
   used in production).
4. Ideally, network-level isolation limits access to the internal endpoint to only the
   containers that legitimately call it (Celery workers / internal services), using Docker
   network scoping or an explicit firewall rule on the KVM4 host.

### Verification steps

**Step 1 — Confirm the env token is set and non-empty.**

```bash
docker compose exec dhanradar-fastapi printenv INTERNAL_API_TOKEN | wc -c
# Must print a number > 32; if it prints 0 or 1, the token is missing.
```

**Step 2 — Confirm the endpoint is not reachable through the public tunnel.**

Run this from any machine outside the KVM4 private network (e.g. a laptop or a CI runner):

```bash
curl -s -o /dev/null -w "%{http_code}" \
  https://dhanradar.com/internal/v1/score/equity/RELIANCE
# Expected: 404 (caught by the cloudflared catch-all, never reaches FastAPI)
# A 503 or 403 is also acceptable proof the router is hit but guarded.
# A 200 is a BLOCKER — stop the deploy.
```

**Step 3 — Confirm port 8000 is not published to the host.**

```bash
docker compose ps dhanradar-fastapi
# The PORTS column must be empty or show only internal container ports (no 0.0.0.0:8000 mapping).
```

Also check from the host:

```bash
ss -tlnp | grep 8000
# Must print nothing. Any output means the port is host-exposed.
```

**Step 4 — Inspect the Docker network to confirm the FastAPI container is on the internal network.**

```bash
docker network inspect dhanradar_default \
  --format '{{range .Containers}}{{.Name}} {{end}}'
# The FastAPI container must appear. Only cloudflared and the services it proxies
# need network-level reach to port 8000; no external/host-facing bridge should exist.
```

**Step 5 — Optional mTLS / network-policy hardening (recommended, not required at launch).**

For a stronger guarantee, restrict traffic to `/internal/v1/*` at the Docker network level
so that only designated caller containers can open a connection. One approach: create a
dedicated internal Docker network, attach the FastAPI container and its callers to it, and
leave cloudflared off that network. Document the chosen approach in `docs/infra-notes.md`.

### Pass criteria

- `curl` from outside the tunnel returns 404 (or 503/403 — anything but 200).
- `ss -tlnp | grep 8000` returns no output on the KVM4 host.
- `INTERNAL_API_TOKEN` is set and has at least 32 characters of entropy.
- The endpoint returns 503 when called from inside the network without the correct token,
  and 200 with the correct token (confirm once, then treat the token as a secret).

---

## B34 — R2 archival India-residency

### Code already in place

The daily archival task `archive_audit_daily` is defined in
`backend/dhanradar/tasks/compliance.py`, lines 29–89.
It runs via Celery beat at 02:00 IST and exports the prior IST calendar day's
`ai_recommendation_audit` rows to R2 as gzip-JSONL under the key prefix `audit/YYYY/MM/DD.jsonl.gz`.

Two supporting items are also already complete:

- An audit-write-failure metric (`bump_audit_metric`, defined in
  `backend/dhanradar/compliance/service.py`) is emitted on the fire-and-forget audit-write
  failure path.
- A `reconcile_audit_disclaimers` beat task (scheduled at 02:30 IST) cross-checks
  all served `disclaimer_version` values against the registered disclaimers table.

The archival is **best-effort and gracefully skipped** when R2 is not configured
(`storage.StorageNotConfigured` → warning log, rows remain in Postgres). This means the
task is safe to deploy before R2 is configured; it will simply log a warning each night.

### What must be verified at deploy

The archive contains `user_id` (DPDP personal data) and constitutes the 7-year SEBI
`ai_recommendation_audit` record of serving per ADR-0022.

**Do not pseudonymize the archive.** ADR-0022 requires user-identifiable records; the
only approved control for cross-border PII is bucket data residency in India.

Before enabling archival in production:

1. The R2 bucket must be confirmed as India-resident (Cloudflare jurisdiction: India or
   a Cloudflare region that stores data exclusively in India).
2. The env flag that enables R2 must be set **only after** the residency is confirmed.

### Verification steps

**Step 1 — Confirm the R2 bucket's jurisdiction in the Cloudflare dashboard.**

In the Cloudflare dashboard, navigate to:
`R2 Object Storage → <your bucket> → Settings → Bucket details`.

Check the **Location** or **Jurisdiction** field. It must show **India (APAC / IN)**.
If the bucket was created without a location hint it defaults to the nearest Cloudflare
data centre, which may not be India. You cannot change a bucket's jurisdiction after
creation; a new bucket must be created with the correct jurisdiction.

To create a bucket with India jurisdiction via the Cloudflare API:

```bash
curl -s -X POST "https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/r2/buckets" \
  -H "Authorization: Bearer <R2_API_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"name": "<BUCKET_NAME>", "locationHint": "APAC", "jurisdiction": "in"}'
# "jurisdiction": "in" pins the bucket to India.
# Verify the response shows "location": "APAC" and "jurisdiction": "in".
```

**Step 2 — Confirm the bucket name matches the env var on the box.**

```bash
docker compose exec dhanradar-fastapi printenv R2_BUCKET_NAME
# Note the name, then confirm it matches the India-resident bucket in the dashboard.
```

**Step 3 — Enable archival only after Step 1 and Step 2 pass.**

Set the R2 credentials in the production environment:

```bash
# These must all be set before archival becomes active:
#   R2_ACCOUNT_ID   — Cloudflare account ID
#   R2_ACCESS_KEY_ID
#   R2_SECRET_ACCESS_KEY
#   R2_BUCKET_NAME  — must be the India-resident bucket confirmed in Step 1
#   R2_ENDPOINT_URL — e.g. https://<ACCOUNT_ID>.r2.cloudflarestorage.com
```

**Step 4 — Trigger a dry-run manually to confirm the task can reach R2 and write.**

```bash
docker compose exec dhanradar-celery \
  celery -A dhanradar.celery_app call \
  dhanradar.tasks.compliance.archive_audit_daily
# Inspect the return value and celery logs.
# Expected on a day with audit rows: "archive: N rows → r2://audit/YYYY/MM/DD.jsonl.gz"
# Expected with no rows yet:         "archive: 0 rows for YYYY-MM-DD (nothing to do)"
# A "R2 unconfigured" result means the env vars are not set (go back to Step 3).
```

**Step 5 — Verify the object appears in the R2 bucket with the correct key prefix.**

In the Cloudflare dashboard under R2, browse the bucket and confirm the `audit/` prefix
contains the expected object. Alternatively:

```bash
aws s3 ls s3://<BUCKET_NAME>/audit/ \
  --endpoint-url https://<ACCOUNT_ID>.r2.cloudflarestorage.com \
  --no-sign-request
# (Use the R2-compatible AWS CLI. Requires R2 credentials in the env or ~/.aws/credentials.)
```

### Pass criteria

- Cloudflare dashboard shows the R2 bucket jurisdiction is India (not auto-assigned).
- `R2_BUCKET_NAME` on the box matches the confirmed India-resident bucket.
- A manual task invocation returns a success string (not "R2 unconfigured").
- An object is visible under the `audit/` prefix in the bucket.

---

## Sign-off

The deployer must confirm each item before enabling the relevant feature in production.

- [ ] `INTERNAL_API_TOKEN` is set to a strong secret on the production box.
- [ ] `/internal/v1/score` is not reachable from the public internet (curl test passes, port 8000 not host-published).
- [ ] R2 bucket jurisdiction is confirmed as India in the Cloudflare dashboard.
- [ ] R2 credentials are set on the box and point to the India-resident bucket.
- [ ] A manual `archive_audit_daily` invocation returns success before the beat schedule is relied upon.
- [ ] Both items are marked cleared in `docs/project-state/DEPLOY_GATE_CHECKLIST.md` (B25 under Gate 4, B34 under Gate 3 and Gate 6).
