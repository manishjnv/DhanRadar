# DhanRadar — Production Deploy Log (2026-06-08)

First production deploy to KVM4. **Result: LIVE at <https://dhanradar.com>.**
(No infra IDs / secrets in this file — the repo is public.)

## Outcome

- **Public:** `https://dhanradar.com/` → 200 (Next.js app, `<title>DhanRadar</title>`);
  `/api/v1/health` → 200 `{"status":"ok","db":"ok","redis":"ok"}`; anonymous `/api/v1/consent` → 401.
- **Stack:** 8 own containers via `docker compose -p dhanradar -f docker-compose.yml` (the prod
  compose only — never the dev override), **no host ports**, fronted by the dedicated `dhanradar`
  cloudflared **container** (4 QUIC connections to the CF Mumbai edge).
- **Schema:** Alembic `0001 → 0013` (single head, 72 tables) via `python -m alembic upgrade head`.
- **Compliance:** `ENV=production`; **DPDP consent enforcement live (B48)** — proven by signup→201
  then a consent-gated CAS upload **without** a grant → **403 `consent_required`** (plus the boot
  guard: the app would hard-crash on boot if consent were disabled under `ENV=production`).
- **Footprint:** ~630 MiB total (cap ~3 GB). **Shared-box impact: none** — etip containers all up,
  the host etip-ssh cloudflared lifeline `active`/untouched, zero host-port collisions.

## Sequence (Phase 1 internal → Phase 2 public, human-gated)

1. Synced box to canonical `main`; injected secrets into `/opt/dhanradar/.env` (generated
   `POSTGRES_PASSWORD` + RS256 JWT keypair from files so keys never hit argv; forced
   `ENV=production`, `COOKIE_SECURE=True`, `DPDP_CONSENT_ENFORCED=true`, `AI_FREE_MODELS`).
   `.env` is `chmod 600`, never committed.
2. Verified `pg_cron` present in the image (no Postgres crash-loop); built images.
3. Data tier up (fresh `dhanradar_pgdata` volume → guarded `01_init.sql` ran clean); migrations;
   app + workers up; internal validation; **paused for explicit human approval**.
4. On approval: started the cloudflared connector → public go-live; verified end-to-end from an
   independent network path.

## Five first-deploy blockers found & fixed (all merged to `main`, CI green, verified on box)

| # | Symptom | Root cause | Fix | PR |
|---|---------|-----------|-----|----|
| 1 | Postgres init aborts (exit 3), schemas never created | `timescaledb-ha:pg16` lacks `pg_partman`; bare `CREATE EXTENSION` aborts under ON_ERROR_STOP (the B55 CI fix only patched the CI sed-strip, not the prod init path) | per-extension `EXCEPTION WHEN OTHERS` guard in `01_init.sql`; CI now runs it verbatim | #29 |
| 2 | nextjs reachable by service name but healthcheck fails | standalone binds `$HOSTNAME` (Docker = container id) → container-IP only, not loopback | `HOSTNAME=0.0.0.0` | #30 |
| 3 | nextjs still unhealthy (blocks cloudflared `service_healthy` dep) | healthcheck used `localhost` → alpine resolves `::1` (IPv6) first; server is IPv4-only | healthcheck → `127.0.0.1` | #31 |
| 4 | celery-beat crash-loop | EACCES writing `./celerybeat-schedule` (non-root appuser, root-owned `/app`) | `--schedule=/tmp/celerybeat-schedule` | #30 |
| 5 | migrations: `ModuleNotFoundError: dhanradar` | package copied to `/app`, NOT pip-installed; bare `alembic` doesn't put CWD on `sys.path` (uvicorn does) | `python -m alembic …`; `deploy.sh` fixed | #30 |

**Box-provisioning fix (NOT in repo):** the cloudflared image runs as uid `65532`; the tunnel
credentials file was `0400 root:root` → permission denied. Fixed by `chown 65532:65532` the creds
file, keeping `0400` (no world-read on the shared box). Re-apply if the creds file is re-provisioned.

## Degraded / open (operator follow-ups — none launch-blocking)

- **B34** — R2 bucket India-residency not yet verified; audit archival + backups stay best-effort
  (skip if R2 unconfigured) until confirmed. Do not rely on the 7-yr archive until then.
- **`ADMIN_USER_IDS` unset** — admin endpoints fail-closed to 404 (safe). Set to enable admin.
- **pg_partman absent** — auto monthly-partition rollover off; the `ai_recommendation_audit` table
  and its DEFAULT partition exist (migration 0006), so writes work.
- **B38** — Sentry DSN/Prometheus scrape onto the shared `etip_prometheus` not yet wired.
- **B29** — first live NAV backfill not yet run, so funds return `insufficient_data` until seeded.

## Guardrails honored

Only `dhanradar-*` resources + `/etc/cloudflared-dhanradar/` touched. Never touched the host
`/etc/cloudflared/config.yml` / `cloudflared.service` (etip-ssh SSH lifeline), any etip/shared
container, or the host cloudflared binary. No `pkill`. No host ports. No secret value printed or
committed.
