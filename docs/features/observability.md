# Feature — Observability (Prometheus + Sentry)

**Status:** Prometheus scrape live in prod; Sentry pending `SENTRY_DSN` · **Phase:** B38 ·
**Last updated:** 2026-06-11

## Purpose & scope

Two-channel observability for the DhanRadar FastAPI service:

- **Prometheus `/metrics`** — request-level counters/histograms (method, route template,
  status); scraped by the co-tenant `etip_prometheus` stack.
- **Sentry** — exception capture for unhandled errors; DPDP-safe (PII scrubbed before
  transmission; no-op without `SENTRY_DSN`).

Celery workers are NOT covered by Sentry at this stage (only `main.py` calls
`init_sentry()`). See residuals.

## App contract

**File:** `backend/dhanradar/observability.py` (commit `efc6556`, 2026-06-07)

### PrometheusMiddleware + `/metrics` endpoint

- `PrometheusMiddleware` is added to the FastAPI app in `backend/dhanradar/main.py` via
  `add_middleware`. It records `method`, `route_template`, and `status_code` labels only —
  no raw paths or user IDs (bounded cardinality, no PII).
- The `/metrics` endpoint is mounted **outside** `/api/v1` (not on the public ingress path).
  It is unauthenticated by design; access control is delegated to the Docker network layer
  (see infra wiring). Non-neg #5 (no bearer auth) is satisfied because `/metrics` is not an
  API route.
- 24 DB-free unit tests cover the middleware labels, cardinality bounds, and the absence of
  raw path/ID leakage.

### `init_sentry()` + DPDP scrubber

- Called once at startup in `main.py`; is a no-op when `SENTRY_DSN` is absent.
- Config: `send_default_pii=False`, traces off.
- `before_send` scrubber strips: cookies; `Authorization`/`Cookie`/`X-Internal-Token`
  headers (both dict and list form); request body; `query_string`; `REMOTE_ADDR` from the
  server env; all breadcrumbs; the user object.
- Config field: `settings.SENTRY_DSN` (`config.py`); placeholder on line 55 of
  `.env.example`. To activate: set `SENTRY_DSN=<dsn>` in `/opt/dhanradar/.env` on KVM4,
  then restart `dhanradar-fastapi`.

## Infra wiring (B38, 2026-06-11)

### Metrics network design

`docker-compose.yml` (PR #93, `adf73de`) adds an **external** bridge network
`dhanradar_metrics`. Only `dhanradar-fastapi` joins it. `dhanradar-redis` is deliberately
excluded: Redis is password-less on the app network (it stores refresh-token JTIs) and the
co-tenant `etip_prometheus` scraper must never have a path to it. The dedicated bridge
limits the scraper to `fastapi:8000` only.

Host-side setup (imperative — not in compose, must be re-run if `etip_prometheus` is
recreated):

```bash
docker network create dhanradar_metrics
docker network connect dhanradar_metrics etip_prometheus
```

Fastapi is dual-homed (`dhanradar_dhanradar` app network + `dhanradar_metrics`);
its metrics-net IP is `172.20.0.2`.

### Prometheus scrape job

Appended to `/opt/intelwatch/docker/prometheus/prometheus.yml` on KVM4 (backup at
`prometheus.yml.bak-b38-20260611`; `promtool check config` passed; reloaded via the
Prometheus lifecycle endpoint — no container restart):

```yaml
- job_name: dhanradar
  scrape_interval: 15s
  metrics_path: /metrics
  static_configs:
    - targets:
        - dhanradar-fastapi:8000
      labels:
        env: production
        app: dhanradar
```

### Grafana alert rules (staged, not applied)

Two alert rules are staged but not yet applied to the co-tenant Grafana:

- **target-down** — fires after 2 m when `up{job="dhanradar"} == 0`.
- **p99 > 500 ms** — fires after 5 m when the 0.99 quantile latency exceeds 500 ms.

Public repo file: `infra/observability/grafana-alerts-dhanradar.yaml` (contains placeholder
`<PROM_DS_UID>`). A UID-filled copy lives at `/tmp/dhanradar-alerts.yaml` on the box.

**Operator action to apply:** copy the UID-filled file into
`/opt/intelwatch/docker/grafana/provisioning/alerting/` and restart `etip_grafana`.

## Verification (2026-06-11)

- Before wiring: 24 Prometheus targets up. After: 25 targets up; all etip targets
  unaffected.
- `up{job="dhanradar"}` returns 1.
- Public surface unchanged: `https://dhanradar.com/metrics` → 404 (ingress blocks it);
  `/api/v1/health` → 200.
- Review ledger: `docs/project-state/reviews/b38-metrics-network.md`
  (deterministic gates green; Sonnet adversarial Security ACCEPT-WITH-CONDITIONS,
  conditions closed; Compliance ACCEPT).

## Residuals & roadmap

| # | Item | Priority |
|---|---|---|
| a | Any container on `dhanradar_metrics` reaches fastapi's full `:8000` surface. Future hardening: non-Authorization scrape token + dual-control. | Low |
| b | `etip_prometheus` network attach is imperative — lost on container recreate. Must re-run `docker network connect dhanradar_metrics etip_prometheus`. | Operational |
| c | Audit-write-failure + AI-budget alerts not wirable from `/metrics` (counters in Redis). Need an exporter or `/metrics` gauges. | Low |
| d | Celery workers never call `init_sentry()` — worker exceptions will not reach Sentry. | Low |

## Changelog

- 2026-06-11 — B38 infra wired (PR #93 `adf73de`): `dhanradar_metrics` bridge,
  Prometheus scrape job, alert rules staged. Deployed `27685cb`. Sonnet adversarial
  Tier-B ACCEPT-WITH-CONDITIONS (conditions closed). Compliance ACCEPT.
- 2026-06-07 — App-side code built (`efc6556`): `PrometheusMiddleware`, `/metrics`
  endpoint, `init_sentry()` DPDP-safe scrubber. 24 unit tests. Adversarial review
  ACCEPT-WITH-CONDITIONS (4 PII-leak conditions fixed).
