# Review Ledger — b38-metrics-network

- **Change:** `docker-compose.yml` — add external `dhanradar_metrics` bridge network; `dhanradar-fastapi` dual-homed (B38 Prometheus scrape path for the shared `etip_prometheus`).
- **Date:** 2026-06-11 · **Branch:** `feat/b38-metrics-scrape-network` · **Tier:** B (load-bearing `docker-compose*.yml`, shared-box infra, security-adjacent network isolation).
- **Builder:** main session (Fable 5). Reviewers are independent agents (not the builder).

## Design decision

`etip_prometheus` (on `etip_network`) must scrape `dhanradar-fastapi:8000/metrics`. Direct
`docker network connect` onto the app network was **rejected**: `dhanradar-redis` is
password-less inside the app network and holds refresh-token JTIs, so a co-tenant container
must never gain reach into it. Chosen design: a dedicated host-created external bridge
(`dhanradar_metrics`) joined only by fastapi; the scraper is attached to that bridge and can
reach nothing but fastapi `:8000`. `external: true` so `compose down` can never remove the
network out from under the attached scraper, and fresh-host deploys fail closed (clear error)
if the network was not pre-created.

## Deterministic gates

- `docker compose config` — valid.
- Secrets scan + TODO/FIXME grep on diff — 0 hits.
- Diff = 11 lines, comments + network declarations only; no service contract touched.
- Test suite: not affected by compose-only change; CI checks gate the PR (see PR checks).

## Security review (independent Sonnet adversarial takeover — codex:rescue unavailable on this account)

Vectors evaluated: dual-homed pivot/routing (OK — containers don't IP-forward between bridges);
full `:8000` surface exposure to the metrics network (CONCERN — acceptable residual: `/api/v1`
is JWT-gated, `/internal/v1` is token-gated fail-closed; mitigation = future scrape-token
dual-control); DNS alias spoofing (OK); compose lifecycle (OK — fail-closed if network absent);
public surface (unchanged); DPDP/SEBI (no new PII/cross-border flow).

**Verdict: ACCEPT-WITH-CONDITIONS**

1. Log the metrics-network `:8000` surface residual in `BLOCKERS.md` (done — B38 entry).
2. Document `docker network create dhanradar_metrics` as a fresh-host deploy prerequisite and
   the manual re-attach of `etip_prometheus` after any recreation of that container
   (done — `docs/infra-notes.md`, local-only).

## Compliance review

**Verdict: ACCEPT** — no new PII flow, no user-facing surface, no cross-border transfer, no
advisory surface; metrics payload carries route templates/method/status only.

## Sign-off

- Gates green · Security ACCEPT-WITH-CONDITIONS (conditions satisfied in-session) ·
  Compliance ACCEPT → **merge-eligible**.
- Deploy of this compose change to KVM4 executed under the standing VPS deploy authorization
  for `dhanradar-*` resources; `etip_prometheus` attach + scrape-config edit performed with
  backup + post-reload verification per the shared-box standing rules.
