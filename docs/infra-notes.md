# DhanRadar — Infra Notes (verified facts — read before ANY infra/Phase-1 work)

Last verified: **2026-05-18**. No secrets in this file (names/IDs/paths only).

## 📋 Standing documentation rules (apply to EVERY phase and fix)
- **RCA on every bug fix.** A fix is not done until an entry is appended to `docs/rca/README.md` (symptom, root cause, fix with file:line, prevention, date). Read the existing log before debugging — known traps are recorded there.
- **Feature doc per module.** Every module has `docs/features/<module>.md`, created when the module is built and updated whenever it changes, following the template in `docs/features/README.md`. A phase is not complete until the affected module's feature doc reflects the as-built reality and its changelog is updated.
- **UI follows the branding guide.** Any UI work must use the design tokens (`frontend/tailwind.config.js`, `frontend/app/tokens.css`, `frontend/styles/tokens.json`) and match the design system in `docs/brand/` (README + `docs/brand/mockups/`). No ad-hoc colours, spacing, typography, or off-system components.
- Treat all three as part of "done" in every phase's verification, not optional.

## Deployment target — KVM4 (shared-infra reuse model)
- **SSH:** alias `intelwatch` (Cloudflare-tunnel `ProxyCommand`; **no public :22**). Host `srv1536443`, user `root`. Ubuntu 24.04.4, 4 vCPU, 16 GB (~9.9 GB free), Docker 29.3.1, Python 3.12, Node 22. Shared box (~32 containers: `etip_*`/intelwatch, dev-tunnel, trendsmap, etc.).
- **Model:** DhanRadar runs ~8 *own* containers (own TimescaleDB Postgres, own Redis `noeviction`, fastapi, nextjs, celery-batch/mood/misc, celery-beat) + **reuses** the box, the Cloudflare tunnel daemon, and `etip_prometheus`/`etip_grafana`. ~3 GB capped, ~6 GB headroom.

## ❌ NEVER TOUCH (blast radius / SSH lifeline)
- `/etc/cloudflared/config.yml` + systemd `cloudflared.service` → that is the **`etip-ssh` tunnel `6e263591-9abd-446b-a980-aab7a84a0b44`** carrying `ssh.intelwatch.in` (**our SSH lifeline**) + `ti.intelwatch.in`. Currently pid 178455. Config sha16 `78d0636b64c354c3`.
- Any `etip_*` / `roadmap*` / `accessbridge*` / `ti-platform*` / `assessiq*` / `trendsmap*` / `dev-tunnel` container, volume, or config (incl. `etip_postgres`, `etip_redis`, `etip_nginx`).
- Host `cloudflared` binary (2026.3.0) — **do not upgrade** (etip-ssh depends on it). DhanRadar uses a pinned cloudflared **container**.
- Pre-existing CF User token "Cloudflare Agent Token - 2026-04-23" (Admin Read-only) — not ours.

## DhanRadar Cloudflare Tunnel (dedicated, isolated) — ✅ DONE & verified
- Tunnel name `dhanradar`, **ID `df2c5ae4-4d21-4052-83d4-12cbabbcd551`**.
- Isolated artifacts: cert `/etc/cloudflared-dhanradar/cert.pem` (account `Manishjnvk@gmail.com`), creds `/etc/cloudflared-dhanradar/dhanradar.json`, config dir `/etc/cloudflared-dhanradar/`.
- DNS: `dhanradar.com` **proxied CNAME → `df2c5ae4-….cfargotunnel.com`**. Verified end-to-end **HTTP/2 200**.
- Phase-1 runtime: cloudflared **container** `cloudflare/cloudflared:2026.5.0` in the DhanRadar compose stack, on the `dhanradar` docker net, mounting `dhanradar.json` + a config.yml ingress: `dhanradar.com` path `^/api/.*` → `dhanradar-fastapi:8000`, default → `dhanradar-nextjs:3000`, then `- service: http_status:404`.
- **Gotchas (cost a remediation; baked into the plan):**
  - `cloudflared tunnel route dns <NAME> …` resolves the tunnel via the *default* `/etc/cloudflared/config.yml` (= etip-ssh) and mis-targets the CNAME. **Always use explicit UUID + `--overwrite-dns`.**
  - `ingress validate` syntax: `cloudflared tunnel --config FILE ingress validate` (global flag *before* the subcommand).
  - Never `pkill -f <pattern>` where the pattern can appear in your own command line (it self-killed the SSH shell once). Use `pgrep -x cloudflared` + `/proc/<pid>/cmdline` check; kill only the pid whose cmdline has `/etc/cloudflared-dhanradar/config.yml`.

## Cloudflare R2 — ✅ DONE & verified (rotated)
- Account id `468b124baae458fb4a8406c829d1e1c9`. S3 endpoint `https://468b124baae458fb4a8406c829d1e1c9.r2.cloudflarestorage.com` (account-level; bucket passed separately). boto3 needs `region_name="auto"`.
- Bucket **`dhanradar-prod`** (Standard, APAC, Public Access OFF).
- Token: Account API token `dhanradar-prod-rw` (Object Read & Write, scoped to `dhanradar-prod`). **First token was exposed in transcript → deleted/rotated 2026-05-18; old key confirmed revoked; new key verified `R2 OK`.** Lesson: never paste secrets/terminal dumps; report results in words.

## Email — Resend (NOT SendGrid — its free tier ended 2025-05-27)
- `dhanradar.com` added in Resend (Tokyo / ap-northeast-1). DNS in CF as **DNS-only (never proxy MX/SPF/DKIM/DMARC)**, verified resolving. `RESEND_API_KEY` = an `re_…` *sending* key (Resend → API Keys), in GitHub prod env secrets.

## GitHub
- Repo **`manishjnv/DhanRadar`** (capital D, R), **private**, empty (no commits yet).
- Actions secrets: **environment `production`**, deployment-branch policy = **`main` only**, 7 env secrets: `R2_ACCOUNT_ID R2_ENDPOINT R2_BUCKET R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY OPENROUTER_API_KEY RESEND_API_KEY`. Repo-level secrets empty. **`deploy.yml` job MUST declare `environment: production`** or it can't read them; non-deploy CI (lint/test/security) gets none — add repo-level only for PR-time scanners (e.g. `SNYK_TOKEN`).
- **Git email privacy:** pushes whose author OR committer email is `manishjnvk@live.com` are rejected. First + every commit must use noreply:
  `GIT_COMMITTER_EMAIL="257227540+manishjnv@users.noreply.github.com" GIT_COMMITTER_NAME="Manish Kumar" git commit --author="Manish Kumar <257227540+manishjnv@users.noreply.github.com>" …` — do **not** `git config` around it.

## Local dev box
- `e:\code\DhanRadar` (Windows; PowerShell + bash + Python 3.14 + boto3). Becomes the repo root in Phase 1.
- `.gitignore` created (`.env`, `.env.*`, `*.pem`, `*credentials*.json`, std Python/Node/Docker/OS). `.env` holds the rotated R2 keys locally (gitignored). Architecture/plan docs live here; commit them under `/docs` in the Phase-1 scaffold.

## OpenRouter
- API key set; **$10 credit purchased → 1,000 req/day free pool** (402 = balance/credit, 429 = rate-limit; treat differently).
- Verify free model ids live at `openrouter.ai/models` before hardcoding. Confirmed-live: `meta-llama/llama-3.3-70b-instruct:free`, `qwen/qwen-2.5-72b-instruct:free`. `deepseek/deepseek-chat-v3:free` may be deprecated → likely `deepseek/deepseek-v4-flash:free`. Sonnet spillover = `anthropic/claude-sonnet-4.6` (paid).

## Status: ALL Phase-1 prerequisites cleared (2026-05-18)
Cloudflare zone+NS · dedicated CF tunnel (verified) · Resend DNS · OpenRouter $10 · R2 (rotated, verified) · GitHub repo + `production` env (main-gated, 7 secrets) · KVM4 access · `.gitignore`. Long-lead items still in parallel (non-blocking): Razorpay, AA/FIU, MF Central, legal entity, SEBI positioning, NIC NTP on KVM4, DPDP consent-purpose list.
