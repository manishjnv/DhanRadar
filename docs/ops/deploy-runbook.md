# Deploy Runbook — DhanRadar

Single-box deploy and rollback procedure for DhanRadar on KVM4 (docker compose stack).

> **NOTE:** Nothing in this runbook authorizes a production deploy. A deploy requires:
> explicit human **PC5 approval**, a merge to `main`, and a signed governance ledger entry
> per the AI Governance Model. This document describes the mechanics only.

---

## Prerequisites

- KVM4 host with Docker Engine and **Docker Compose v2** (`docker compose version`).
- Repo cloned at the target path and checked out to `main` (or the target SHA).
- **`.env` file present at repo root** containing all required secret keys. Required keys
  (names only — never store values here):
  - `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`
  - `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`
  - `OPENROUTER_API_KEY`, `AI_FREE_MODELS`
  - `SENTRY_DSN`, `NEXT_PUBLIC_SENTRY_DSN`
  - `CONSENT_KILL_SWITCH` (DPDP kill-switch; defaults enforced in code)
  - Any other keys required by `backend/core/config.py`
- Cloudflared credentials file already present on the host at
  `/etc/cloudflared-dhanradar/dhanradar.json` (never committed to the repo).
- The `.deploy/` directory is gitignored — it is created automatically by `deploy.sh`.

---

## Migration safety — tested upgrade/downgrade sequence

Before deploying to production, validate migrations on a **scratch database** (do not run
this against a live DB):

```bash
docker compose run --rm dhanradar-fastapi alembic upgrade head
docker compose run --rm dhanradar-fastapi alembic downgrade base
docker compose run --rm dhanradar-fastapi alembic upgrade head
```

A clean double-pass (upgrade → downgrade → upgrade) with no errors confirms both the
forward and reverse paths are sound.

CI (blocker B40) also runs `alembic upgrade head` against the TimescaleDB image on every
PR, catching migration regressions before they reach the host.

Migration history is **linear with a single head at revision 0009**. The historical
duplicate-0008 branch was resolved; `alembic heads` must return exactly one entry.

---

## Deploy

```bash
bash scripts/deploy.sh
```

The script is idempotent and safe to re-run. It performs these steps in order:

1. **Preconditions** — asserts it is running from the repo root, `.env` exists, and
   `docker compose` v2 is available.
2. **Record current state** — writes the current git SHA to `.deploy/last-good-sha` and
   the current alembic revision to `.deploy/last-good-alembic` (defaults to `base` if the
   stack is not yet up). Warns (but continues) if the working tree is dirty.
3. **`git pull --ff-only`** — pulls latest commits. Skipped automatically if HEAD is
   detached. Set `DEPLOY_SKIP_PULL=1` to skip explicitly.
4. **`docker compose build`** — rebuilds all images from source.
5. **`alembic upgrade head`** — runs pending migrations via a one-off container. Aborts
   the deploy (exit 1) on any migration failure; the DB is left at the pre-deploy revision.
6. **`docker compose up -d`** — starts / restarts all services.
7. **Health gate** — polls `docker inspect` health status for `dhanradar-fastapi` and
   `dhanradar-nextjs` every 5 seconds for up to 180 seconds. On timeout, prints the last 50
   log lines for the unhealthy service and exits 1.
8. **Success** — updates `.deploy/last-good-sha` to the new SHA and prints a summary.

### Environment variable

| Variable | Effect |
|---|---|
| `DEPLOY_SKIP_PULL=1` | Skip `git pull` (e.g. when SHA is already at target) |

---

## Rollback

```bash
bash scripts/rollback.sh [target-git-sha [target-alembic-rev]]
```

Without arguments, rolls back to the SHA and alembic revision recorded in `.deploy/`.
Both values can be overridden by positional arguments.

Steps performed:

1. **Preconditions** — same checks as deploy.
2. **Resolve targets** — reads `.deploy/last-good-sha` and `.deploy/last-good-alembic`,
   or uses the provided arguments.
3. **DB downgrade gate** — if the target alembic revision differs from the current one,
   the script prints a loud warning and **requires `CONFIRM_DB_DOWNGRADE=1`** before
   running `alembic downgrade <target-rev>`. Without it, the DB downgrade is skipped and
   only the code is rolled back (safe when the target code is schema-compatible).
4. **`git checkout <target-sha>`** — reverts the working tree to the target commit.
5. **`docker compose build && docker compose up -d`** — rebuilds and restarts the stack.
6. **Health gate** — same 180-second polling logic as deploy.
7. **Summary** — reports the code SHA rolled back to and whether the DB was downgraded.

### DB downgrade confirmation

```bash
CONFIRM_DB_DOWNGRADE=1 bash scripts/rollback.sh
```

> **Warning:** Alembic downgrade can be irreversible if the migration drops columns or
> tables. Review the migration file before setting `CONFIRM_DB_DOWNGRADE=1`.

---

## Health verification

### Service health status

```bash
docker compose ps
```

All services should show `(healthy)`. The compose file defines healthchecks for every
service; the deploy and rollback scripts gate on these statuses.

### In-network endpoint checks

Use `docker compose exec` or a one-off `run` to reach services over the internal Docker
network (no host ports are bound):

```bash
# FastAPI health
docker compose exec dhanradar-fastapi \
  curl -sf http://localhost:8000/api/v1/health

# Next.js reachability
docker compose exec dhanradar-nextjs \
  curl -sf http://localhost:3000/
```

### Public reachability

Public traffic reaches DhanRadar **exclusively via the cloudflared tunnel**. There are no
host port bindings on any service. Do not attempt to `curl` the host's IP directly —
verify the tunnel is connected via `docker compose logs dhanradar-cloudflared`.

---

## Constraints and gotchas

- **No host port bindings.** No service exposes a port on the host. All inter-service
  traffic is routed over the internal Docker network; external traffic comes through
  cloudflared only.
- **Cloudflared image is pinned to `2026.5.0`.** Do not change the image tag without an
  explicit architecture decision and governance sign-off.
- **Cloudflared credentials file is host-only.** `/etc/cloudflared-dhanradar/dhanradar.json`
  lives only on the KVM4 host and is never committed to the repository.
- **Secrets live in root `.env` only.** Never hard-code secret values in compose files,
  scripts, or application config. The `.env` file is gitignored.
- **~3 GB box memory cap.** KVM4 is a shared-infra host with approximately 3 GB RAM
  reserved for DhanRadar containers. Avoid building multiple large images in parallel if
  memory pressure causes OOM kills; build sequentially with `docker compose build
  <service>` if needed.
- **Migrations are run as a one-off container (`--rm`), not a dedicated service.** The
  Alembic config (`alembic.ini`) is at `backend/alembic.ini`, which is the WORKDIR of the
  `dhanradar-fastapi` image. The backend runs as non-root user `appuser` (uid 1001).
- **Single migration head.** `alembic heads` must always return exactly one revision
  (currently `0009`). A two-head state means a branch merge was done incorrectly; fix the
  migration history before deploying.
