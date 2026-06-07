# DhanRadar — KVM4 Deploy Runbook

## 1. Scope & safety preamble

This runbook covers the DhanRadar application stack only.
The KVM4 host is **shared**: it also runs an unrelated SSH-lifeline cloudflared tunnel and
other project containers.
A wrong command can destroy the SSH lifeline or another tenant's data.

**Before you touch anything, read `docs/infra-notes.md` on the host.**
That file (never committed) contains the real hostnames, tunnel IDs, and secret values.
This file contains **placeholders only**.

### NEVER-TOUCH list (enforced by `scripts/deploy.sh`; never override)

- The host `/etc/cloudflared/config.yml` and the host `cloudflared` systemd service / binary.
  Those belong to the SSH lifeline tunnel — not DhanRadar.
  DhanRadar runs its own `dhanradar-cloudflared` **container**.
- Any container, volume, or config whose name starts with `etip_`, `roadmap`, or `trendsmap`.
- `pkill` / `killall` — these commands can kill your own SSH shell (known incident).
  Use only `docker compose -p dhanradar …` scoped operations.
- Bare `docker stop` / `docker rm` / `docker system prune` — always scope to the compose project.

### Human-gated deploy

Production deploy requires:

- No open Security or Compliance BLOCKER.
- B37 (DB backup / PITR) resolved — confirm before first production deploy.
- B38 (monitoring / alerting) resolved — confirm before first production deploy.
- Separate explicit human approval (the GitHub `production` environment is main-branch-gated).

---

## 2. Prerequisites

#### Access

- SSH to the box via the `intelwatch` alias (ProxyCommand over Cloudflare; there is no public `:22`).
  The real connection details live in `docs/infra-notes.md`.

#### On the KVM4 box

- Repo cloned at `<DHANRADAR-REPO-PATH>` (see `docs/infra-notes.md` for the actual path).
- `.env` present at the repo root and complete (see secret list in `docs/infra-notes.md`).
  Required keys include at minimum:
  `POSTGRES_PASSWORD`, `R2_*`, `OPENROUTER_API_KEY`, `RESEND_API_KEY`,
  `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`,
  `RAZORPAY_WEBHOOK_SECRET`, `ADMIN_USER_IDS`, and any `KITE_*` keys parked for the equities phase.
- Docker Engine and Docker Compose plugin installed and accessible as `docker compose`.
- Currently on the `main` branch (the GitHub `production` environment is main-branch-gated;
  deploying from any other branch is blocked by `scripts/deploy.sh`).

#### PostgreSQL extension availability (first deploy only)

Run this query before starting a cold deploy:

```sql
SELECT name, default_version, installed_version
FROM pg_available_extensions
WHERE name IN ('pg_cron', 'pg_partman');
```

Run it via:

```bash
docker compose -p dhanradar exec dhanradar-postgres \
  psql -U dhanradar -d dhanradar \
  -c "SELECT name, default_version, installed_version FROM pg_available_extensions WHERE name IN ('pg_cron','pg_partman');"
```

Both extensions must be available before the stack is started.
If either is missing, do not proceed — raise this with the KVM4 host administrator.

#### Cloudflared credentials file

The file `/etc/cloudflared-dhanradar/dhanradar.json` must exist on the KVM4 host.
It is **never committed to the repo**.
Without it the `dhanradar-cloudflared` container will fail to start.
See `docs/infra-notes.md` for how to provision it.

---

## 3. First deploy (cold start)

### 3.1 Clone and check out main

```bash
git clone <DHANRADAR-REPO-URL> <DHANRADAR-REPO-PATH>
cd <DHANRADAR-REPO-PATH>
git checkout main
```

### 3.2 Create .env

Copy the template and fill every value from `docs/infra-notes.md`.
Never commit `.env` — it is in `.gitignore`.

```bash
cp .env.example .env
# Edit .env with the real values from docs/infra-notes.md
```

### 3.3 Verify the cloudflared credentials file

```bash
ls -la /etc/cloudflared-dhanradar/dhanradar.json
```

If the file is absent, stop and provision it (see `docs/infra-notes.md`).

### 3.4 Cloudflared DNS / CNAME gotchas

Three known traps — all must be honoured:

- Always route DNS via the explicit tunnel UUID (`<DHANRADAR-TUNNEL-ID>` in
  `infra/cloudflared/config.yml`), never the tunnel name.
  Use `--overwrite-dns` when creating the CNAME so a stale record is replaced atomically.
- The `cloudflared tunnel ingress validate` command requires the global `--config FILE` flag
  **before** the subcommand, not after:

  ```bash
  # CORRECT
  cloudflared --config infra/cloudflared/config.yml tunnel ingress validate

  # WRONG (silently reads the wrong file)
  cloudflared tunnel ingress validate --config infra/cloudflared/config.yml
  ```

- Validate the ingress before starting the container to catch a malformed config early:

  ```bash
  docker run --rm \
    -v "$(pwd)/infra/cloudflared/config.yml:/etc/cloudflared/config.yml:ro" \
    cloudflare/cloudflared:2026.5.0 \
    --config /etc/cloudflared/config.yml tunnel ingress validate
  ```

### 3.5 Build images and bring up the data tier

```bash
docker compose -p dhanradar -f docker-compose.yml build

docker compose -p dhanradar -f docker-compose.yml up -d \
  dhanradar-postgres dhanradar-redis
```

Wait until both services report `healthy`:

```bash
docker compose -p dhanradar -f docker-compose.yml ps
```

Postgres has a 30 s start period; Redis is faster.
Do not proceed until both are `healthy`.

### 3.6 Run migrations on the new image (pre-serve)

Migrations must run **before** the app starts serving traffic.
This prevents the running app from operating against an old schema.

```bash
docker compose -p dhanradar -f docker-compose.yml \
  run --rm dhanradar-fastapi alembic upgrade head
```

Confirm the output ends with `Running upgrade … -> head` and exits `0`.
See §5 for details and for checking the current revision.

### 3.7 Bring up the rest of the stack

```bash
docker compose -p dhanradar -f docker-compose.yml up -d
```

This starts `dhanradar-fastapi`, `dhanradar-nextjs`, all four Celery services,
and `dhanradar-cloudflared`.
`cloudflared` depends on both `fastapi` and `nextjs` being `healthy` (see `docker-compose.yml`);
expect 40–60 s before the tunnel is live.

### 3.8 Verify health

```bash
docker compose -p dhanradar -f docker-compose.yml ps
```

All 9 services must be `running` (healthy where applicable):
`dhanradar-postgres`, `dhanradar-redis`, `dhanradar-fastapi`, `dhanradar-nextjs`,
`dhanradar-celery-batch`, `dhanradar-celery-mood`, `dhanradar-celery-misc`,
`dhanradar-celery-beat`, `dhanradar-cloudflared`.

### 3.9 End-to-end smoke test

```bash
# API health (inside the docker network)
docker compose -p dhanradar -f docker-compose.yml exec dhanradar-fastapi \
  python -c "import urllib.request,sys; r=urllib.request.urlopen('http://localhost:8000/api/v1/health'); sys.exit(0 if r.status==200 else 1)" \
  && echo "API OK"

# Public ingress
curl -sS -o /dev/null -w "%{http_code}" https://dhanradar.com/api/v1/health
# Expected: 200

curl -sS -o /dev/null -w "%{http_code}" https://dhanradar.com/
# Expected: 200
```

---

## 4. Update deploy (the common path)

This is the path for every routine code update.

```bash
ssh intelwatch
cd <DHANRADAR-REPO-PATH>
git pull                    # must be on main; pull latest
bash scripts/deploy.sh deploy
```

The script:

1. Runs preflight checks (repo-root guard, `.env` guard, branch warn).
2. Builds fresh images (`docker compose build`).
3. Brings up the data tier and waits for healthy.
4. Runs `alembic upgrade head` on the new image before serving traffic.
5. Brings up the full stack.
6. Waits for `dhanradar-fastapi` and `dhanradar-nextjs` to be healthy.
7. Smoke-tests `/api/v1/health` (aborts on failure).
8. Prints the final `status` summary.

Expected output ends with:

```text
[deploy] Smoke test passed — API returned 200.
[deploy] Deploy complete.
```

Followed by the output of `docker compose -p dhanradar ps`.

---

## 5. Migrations

### Running migrations

Pre-serve (recommended via `deploy.sh`):

```bash
docker compose -p dhanradar -f docker-compose.yml \
  run --rm dhanradar-fastapi alembic upgrade head
```

Against a running container (post-deploy, for emergency patches):

```bash
docker compose -p dhanradar -f docker-compose.yml \
  exec -T dhanradar-fastapi alembic upgrade head
```

### Checking the current revision

```bash
docker compose -p dhanradar -f docker-compose.yml \
  exec -T dhanradar-fastapi alembic current
```

### Why migrations run pre-serve

DhanRadar's migrations are **additive and backward-compatible** (new columns are nullable or have
defaults; no destructive drops in the forward path).
This makes pre-serve safe: the old code can run against the new schema without errors.
The reverse — running the new code against the old schema — is not guaranteed safe.
Therefore: **new image builds first, migrations run, then the app serves**.

---

## 6. Rollback

### 6a. App rollback (preferred)

Use this when the new code has a bug but the schema is still compatible.
Because DhanRadar migrations are additive, the old code runs fine against the new schema.

```bash
ssh intelwatch
cd <DHANRADAR-REPO-PATH>       # always cd to the repo root first — never git checkout in a foreign dir
git checkout <PRIOR-GIT-REF>   # e.g. the previous release tag or commit SHA
bash scripts/deploy.sh deploy
```

`scripts/deploy.sh rollback <ref>` is also available.
It prints a safety warning, confirms the ref, and calls the deploy flow.
See §6b below for when NOT to use it.

### 6b. Schema downgrade (DANGEROUS — manual only)

Only attempt a schema downgrade when:

- The forward migration introduced a breaking schema change (rare; the project convention is
  additive migrations).
- B37 (DB backup) is confirmed to exist and has been verified restorable.
- A human operator explicitly confirms the downgrade revision in writing.

**Never run `alembic downgrade` automatically.** The `deploy.sh rollback` subcommand does
**not** invoke `alembic downgrade`.

Manual procedure (confirm each step before running):

```bash
# 1. Check available revisions
docker compose -p dhanradar -f docker-compose.yml \
  exec -T dhanradar-fastapi alembic history --verbose

# 2. Stop the app services (leave postgres + redis running)
docker compose -p dhanradar -f docker-compose.yml stop \
  dhanradar-fastapi dhanradar-nextjs \
  dhanradar-celery-batch dhanradar-celery-mood \
  dhanradar-celery-misc dhanradar-celery-beat \
  dhanradar-cloudflared

# 3. Run the downgrade (replace <TARGET-REV> with the confirmed revision ID)
docker compose -p dhanradar -f docker-compose.yml \
  run --rm dhanradar-fastapi alembic downgrade <TARGET-REV>

# 4. Check out the matching app code
git checkout <MATCHING-GIT-REF>

# 5. Redeploy the old image
bash scripts/deploy.sh deploy
```

A schema downgrade can **drop columns or tables and destroy data permanently**.
Ensure B37 backups exist and are verified before starting.

---

## 7. Post-deploy checklist

Run through each item after every deploy before declaring success.

- All 9 services show `running` (healthy) in `docker compose -p dhanradar ps`:
  `dhanradar-postgres` · `dhanradar-redis` · `dhanradar-fastapi` · `dhanradar-nextjs` ·
  `dhanradar-celery-batch` · `dhanradar-celery-mood` · `dhanradar-celery-misc` ·
  `dhanradar-celery-beat` · `dhanradar-cloudflared`.
- `https://dhanradar.com/api/v1/health` returns HTTP 200.
- `https://dhanradar.com/` returns HTTP 200 (Next.js serving).
- No container exceeds its memory limit; the sum across all 9 services stays at or below 3072 MB
  (1024 + 256 + 512 + 448 + 256 + 192 + 192 + 64 + 128 = 3072).
- **Three cloudflared gotchas re-checked** (§3.4 above):
  tunnel UUID in config, `--overwrite-dns` for CNAME, global `--config` before subcommand.
- **B37 (DB backup) is OPEN** — nightly `pg_dump` to India-resident storage is not yet in place.
  Do not proceed to a production deploy until B37 is resolved.
- **B38 (monitoring / alerting) is OPEN** — Sentry `init` is not called and there is no
  `/metrics` endpoint. Do not proceed to a production deploy until B38 is resolved.

---

## 8. Pointer to real values

Real hostnames, tunnel IDs, credential file paths, and secret values are in `docs/infra-notes.md`
on the KVM4 host.
That file is never committed to this repo.
This runbook is public and contains placeholders only.
