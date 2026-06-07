# Review — B36 deploy runbook + deploy script

## Gate ledger

**Tier:** infra/ops (load-bearing-adjacent — drives `docker-compose`/`cloudflared` on the SHARED
KVM4 box; blast radius includes an unrelated SSH-lifeline tunnel) · **Class:** major (first deploy
automation; safety-critical, runs as root on shared infra) · **Branch:** `ops/deploy-runbook-b36`
(off `main`) · **Date:** 2026-06-07.

**Artifacts:** `docs/ops/deploy-runbook.md` (new), `scripts/deploy.sh` (new),
`docs/project-state/BLOCKERS.md` (B36 → ADDRESSED).

| Gate | Required | Verdict | Reviewer/tier |
|---|---|---|---|
| Deterministic (bash -n + secret-leak scan + markdownlint) | always | PASS (syntax OK; no real IDs/secrets leaked; runbook MD clean) | machine |
| Architect | always | self-note (scoped `-p dhanradar`; mirrors compose + infra-notes; no infra mutation) | orchestrator (Opus) |
| Security (adversarial) | safety-critical infra | **ACCEPT-WITH-CONDITIONS** (8 scope-escape vectors; 2 low ergonomics conditions, applied) | Sonnet takeover (codex n/a) |

## Design

- **Runbook** (`docs/ops/deploy-runbook.md`): scope/safety preamble + NEVER-TOUCH list; prerequisites
  (SSH alias, `.env`, pg_cron/pg_partman availability, cloudflared cred file); first-deploy (cold)
  with the 3 cloudflared gotchas (explicit tunnel UUID + `--overwrite-dns`; global `--config` before
  the subcommand; `ingress validate` before start); update-deploy via `scripts/deploy.sh deploy`;
  migrations (pre-serve ordering + rationale); 2-path rollback (app-rollback preferred vs the
  DANGEROUS manual-only schema downgrade, B37-gated); post-deploy checklist (9 services, 3072M sum,
  B37/B38 open gates). Public-repo safe — placeholders only; real values → local `infra-notes.md`.
- **Script** (`scripts/deploy.sh`): `deploy`/`status`/`rollback`/`help`. Every docker op scoped
  `docker compose -p dhanradar -f docker-compose.yml`; no `pkill`/`killall`, no bare
  `docker stop`/`rm`/`prune`/`down -v`. `deploy` = build → data tier up + wait-healthy → `run --rm -T
  alembic upgrade head` (pre-serve) → full `up -d` → wait-healthy fastapi/nextjs → smoke-test
  `/api/v1/health` (abort non-200). `rollback <ref>` is app-only, refuses unless the tree is already
  at the ref, and NEVER calls `alembic downgrade`.

## Security (independent, adversarial — Sonnet takeover; codex unavailable) — ACCEPT-WITH-CONDITIONS

8 vectors (scope escape; host cloudflared / SSH lifeline; self-kill; data destruction; set -e /
pipefail correctness; rollback safety; preflight gaps; runbook copy-paste). **No scope-escape, no
host-service touch, no `pkill`, no data-destruction path, `alembic downgrade` unreachable from the
automated path, rollback fail-closed, preflight guards the wrong-dir case.** Conditions applied:

1. `wait_healthy` now tracks whether the container was ever seen and emits a distinct
   "container never started (build/up failed or Docker daemon down?)" abort instead of a silent
   timeout spin (`scripts/deploy.sh`).
2. Runbook §6a `cd <DHANRADAR-REPO-PATH>` before `git checkout` annotated (guard a wrong-repo
   checkout). (The `cd` was already present; comment strengthened.)

## Final status

**ACCEPT** (conditions applied). Merge-eligible. **REMAINING (validation):** the runbook + script are
UNTESTED against the live KVM4 box — a first real `deploy.sh` run is the validation step, and stays
gated on PC4/PC5 human approval + B37 (backups) + B38 (monitoring) before any production deploy.
