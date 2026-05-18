# DhanRadar

AI-powered Indian mutual fund & stock radar. The backend is a FastAPI/Celery Python service; the frontend is Next.js 14 App Router. All services run behind a Cloudflare Tunnel — there are no public-facing host port bindings.

---

## Overview

DhanRadar aggregates NAV data, news sentiment, portfolio analytics, and AI-driven scoring for Indian mutual funds, ETFs, and stocks. Phase 1 stands up the infrastructure skeleton (Postgres + TimescaleDB, Redis, FastAPI, Celery, Next.js, cloudflared). Feature phases build on top of it.

Architecture and implementation plan: see `docs/`.

---

## Local Development

### Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- A `.env` file at the project root (copy `.env.example` and fill in real values)

### Bring the stack up

```bash
cp .env.example .env
# Edit .env — set POSTGRES_PASSWORD at minimum
docker compose up --build
```

Expected result: **9 containers** all reach healthy status. The cloudflared container will fail to connect to Cloudflare until the KVM4 credentials file exists, but all other services should be healthy.

### Verify the API health endpoint (container-internal, not host-exposed)

```bash
docker compose exec dhanradar-fastapi \
  python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/v1/health').read())"
```

Expected: `{"status":"ok","db":"ok","redis":"ok"}`

### Logs

```bash
docker compose logs -f dhanradar-fastapi
docker compose logs -f dhanradar-celery-batch
```

---

## Documentation

| File | Purpose |
|---|---|
| `docs/DhanRadar_Architecture_Final.md` | Full system architecture |
| `docs/DhanRadar_Implementation_Plan.md` | Phase-by-phase implementation plan |
| `docs/infra-notes.md` | KVM4 shared-infra notes, credentials, gotchas |

---

## KVM4 Deploy Notes

### Shared-infra reuse

DhanRadar runs on the same KVM4 host as the existing `etip` stack. The host's cloudflared binary (version 2026.3.0) and the `etip-ssh` tunnel are **shared infrastructure** — do not touch them. DhanRadar uses its **own dedicated tunnel** provisioned separately.

### Dedicated tunnel

- Tunnel ID: `df2c5ae4-4d21-4052-83d4-12cbabbcd551`
- Credentials file: `/etc/cloudflared-dhanradar/dhanradar.json` (KVM4 only, never committed)
- Config: `./infra/cloudflared/config.yml` (committed, read-only bind-mount)

### 3 cloudflared gotchas

**Gotcha 1 — `tunnel route dns` resolves via the default config, not the DhanRadar config.**
The host's `/etc/cloudflared/config.yml` points at the `etip-ssh` tunnel. Running
`cloudflared tunnel route dns <name> <hostname>` without an explicit config path will
route DNS for the *wrong* tunnel. Always use:

```bash
cloudflared tunnel --config /etc/cloudflared-dhanradar/config.yml \
  route dns df2c5ae4-4d21-4052-83d4-12cbabbcd551 dhanradar.com \
  --overwrite-dns
```

Or pass the UUID directly with `--overwrite-dns`.

**Gotcha 2 — `ingress validate` global flag order matters.**
The `--config` flag is a *global* flag and must come **before** the subcommand:

```bash
# CORRECT
cloudflared --config /etc/cloudflared-dhanradar/config.yml ingress validate

# WRONG — silently reads the default config
cloudflared ingress validate --config /etc/cloudflared-dhanradar/config.yml
```

**Gotcha 3 — never `pkill -f` a pattern that matches your own shell.**
`pkill -f cloudflared` will also kill any shell whose command line contains "cloudflared"
(e.g., the SSH session running the command). Instead:

```bash
# Enumerate PIDs safely
pgrep -x cloudflared
# Inspect each before killing
cat /proc/<pid>/cmdline | tr '\0' ' '
# Then kill the specific PID
kill <pid>
```

### NEVER TOUCH — Shared-infra items (do not modify, restart, or delete)

> **The following items belong to the etip stack and must not be touched:**
>
> - Tunnel `6e263591-...` (`etip-ssh`)
> - Host file `/etc/cloudflared/config.yml`
> - Systemd service `cloudflared.service`
> - Any container whose name starts with `etip_`
> - Host cloudflared binary at version `2026.3.0` — do not upgrade it

Modifying any of these will break the etip SSH reverse tunnel and cut off remote access to KVM4.
