# DhanRadar — DevOps & Security Architecture

*Production deployment, observability, resilience, and security controls. Completes the architecture set (docs 03 backend · 04 data/AI · 05 frontend). Stack-aligned: FastAPI · PostgreSQL · Redis · Elasticsearch · Celery · Next.js, on Kubernetes.*

**Prepared by:** DevOps Architecture · Security Architecture · **Date:** June 2026 · **Status:** v1 for build

---

## 0. Topology

```
                          ┌── Cloudflare ──┐
   Users ───────TLS──────▶│ WAF · CDN · DNS│
                          │ DDoS · Bot mgmt│
                          └───────┬────────┘
                                  ▼
                       ┌──── Ingress (k8s) ────┐
                       │  nginx/Kong · mTLS     │
                       └───┬──────────┬─────────┘
                  ┌────────▼───┐  ┌───▼──────────┐
                  │ web (Next) │  │ api (FastAPI)│   (HPA-scaled pods)
                  └────────────┘  └───┬──────────┘
                                      │
                  ┌───────────┬───────┼────────┬──────────┐
                  ▼           ▼       ▼        ▼          ▼
            ┌─────────┐ ┌────────┐ ┌──────┐ ┌────────┐ ┌─────────┐
            │ Postgres│ │ Redis  │ │ ES   │ │ Celery │ │ Vector  │
            │ (HA,    │ │ (HA,   │ │(HA)  │ │ workers│ │ (pgvec) │
            │  PITR)  │ │ Sentinel)│      │ │ +beat  │ │         │
            └─────────┘ └────────┘ └──────┘ └────────┘ └─────────┘
   Managed where possible (RDS/CloudSQL · ElastiCache · managed ES).
   Secrets: Vault/KMS. Registry: signed images. GitOps: ArgoCD.
```

**Environments:** `dev` → `staging` (prod-like, anonymized data) → `prod`. Ephemeral **preview environments** per PR (Vercel for web; namespaced k8s for api). Infra is **Terraform** (state in remote backend, locked); app deploy is **GitOps (ArgoCD)** from Helm charts.

---

# PART 1 — DOCKER

**Principles:** small, reproducible, non-root, multi-stage, pinned.

### API (FastAPI) — multi-stage
```dockerfile
# ---- builder ----
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev -o requirements.txt \
 && pip wheel --no-cache-dir -w /wheels -r requirements.txt
# ---- runtime ----
FROM python:3.12-slim AS runtime
RUN addgroup --system app && adduser --system --ingroup app app
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY --chown=app:app . .
USER app                       # non-root
EXPOSE 8000
HEALTHCHECK CMD ["python","-m","app.health"]
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--workers","4"]
```

### Web (Next.js) — standalone output
```dockerfile
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
FROM node:20-slim AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build                     # next.config: output: 'standalone'
FROM node:20-slim AS runtime
RUN addgroup --system app && adduser --system --ingroup app app
WORKDIR /app
COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static ./.next/static
COPY --from=build --chown=app:app /app/public ./public
USER app
EXPOSE 3000
CMD ["node","server.js"]
```

**Image hygiene**
- Pinned base digests; `.dockerignore` (no secrets, no `.git`, no tests in runtime).
- Distroless/slim runtime; **non-root** user; read-only root filesystem at runtime (`securityContext`).
- **Trivy/Grype** scan in CI (fail on HIGH/CRITICAL); **SBOM** (Syft) generated and stored.
- Images **signed (cosign)**; cluster admits only signed images (Kyverno/OPA policy).
- Celery worker + beat are the **same API image** with different commands (no drift).

---

# PART 2 — CI/CD (GitHub Actions)

**Pipeline stages** (per service, path-filtered monorepo):

```
PR opened ─▶ ① Lint+Typecheck ─▶ ② Unit/Component ─▶ ③ Build image
          ─▶ ④ SAST (CodeQL) + Secret scan (gitleaks) + Dep scan (osv)
          ─▶ ⑤ Image scan (Trivy) + SBOM (Syft) + Sign (cosign)
          ─▶ ⑥ Preview env deploy ─▶ ⑦ e2e (Playwright) + Lighthouse/a11y budgets
          ─▶ ⑧ DAST (ZAP baseline) on preview
merge→main ─▶ push signed image ─▶ ArgoCD sync to STAGING (auto)
           ─▶ smoke + integration ─▶ manual approval gate
           ─▶ ArgoCD sync to PROD (progressive: canary → full)
```

### Example workflow (api)
```yaml
name: api-ci
on: { pull_request: { paths: ['api/**'] }, push: { branches: [main], paths: ['api/**'] } }
permissions: { contents: read, id-token: write, packages: write }  # OIDC, least-priv
concurrency: { group: api-${{ github.ref }}, cancel-in-progress: true }
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<pinned-sha>
      - uses: astral-sh/setup-uv@<pinned-sha>
      - run: uv sync --frozen
      - run: uv run ruff check . && uv run mypy app
      - run: uv run pytest --cov --cov-fail-under=80
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<pinned-sha>
      - uses: github/codeql-action/analyze@<pinned-sha>   # SAST
      - uses: gitleaks/gitleaks-action@<pinned-sha>        # secret scan
      - run: trivy fs --exit-code 1 --severity HIGH,CRITICAL .
  build:
    needs: [test, security]
    runs-on: ubuntu-latest
    steps:
      - uses: docker/build-push-action@<pinned-sha>
      - run: syft <image> -o spdx-json > sbom.json          # SBOM
      - run: cosign sign --yes <image>                       # sign (keyless OIDC)
```

**Controls baked in**
- **OIDC to cloud** — no long-lived cloud keys in GitHub; short-lived tokens via federation.
- **Pinned actions by SHA** (supply-chain), `permissions:` least-privilege, `concurrency` to cancel stale runs.
- **Branch protection** — required checks, ≥1 review (CODEOWNERS), signed commits, no force-push to `main`.
- **Migrations** — Alembic runs as a **pre-deploy Job** (expand/contract pattern; never destructive in one step), gated and reversible.
- **Rollback** — ArgoCD keeps history; one-click rollback to the last healthy revision; DB migrations are backward-compatible so app rollback is safe.

---

# PART 3 — DEPLOYMENT & PROGRESSIVE DELIVERY

- **Kubernetes** with Helm charts per service; **HPA** on CPU + RPS (api) and queue depth (Celery, via KEDA).
- **Progressive delivery (Argo Rollouts):** canary 10% → analysis (error rate, p95 latency, 5xx from Prometheus) → 50% → 100%; **auto-rollback** on metric breach.
- **Zero-downtime:** rolling updates, `readiness`/`liveness`/`startup` probes, `PodDisruptionBudget`, graceful shutdown (drain SIGTERM), connection-draining at ingress.
- **Resource governance:** requests/limits per pod, `LimitRange`/`ResourceQuota` per namespace, `PriorityClass` (api > workers > batch).
- **Config/secrets** mounted from Vault (CSI) / sealed-secrets — never baked into images.

---

# PART 4 — MONITORING & OBSERVABILITY

**Three pillars + one trace id everywhere.**

### Prometheus (metrics)
- App exposes `/metrics`: RED (Rate, Errors, Duration) per endpoint, Celery queue depth/latency, cache hit-rate, AI cost/tokens, DB pool, business KPIs (signups, conversions).
- **kube-prometheus-stack**; recording + alerting rules; **Alertmanager** → PagerDuty/Slack.
- **SLOs with burn-rate alerts:** API availability 99.9%, read p99 < 250ms, alert latency < 60s; multi-window burn-rate (fast + slow) to cut noise.

### Grafana (dashboards)
- Golden-signals per service, k8s cluster health, Postgres/Redis/ES, Celery queues, **AI-Ops** (latency/cost/quality/cache-hit), business funnel, and a **Data Source Monitor** (ingest freshness/lag).
- Dashboards as code (provisioned), versioned in git.

### Sentry (errors + tracing + RUM)
- Frontend (Next) + backend (FastAPI) + Celery; release-tagged, source-mapped; **performance tracing** + **session replay** (PII-scrubbed) on web; Core Web Vitals from real users.
- Alerts on new/regressed issues, spikes; linked to the deploy that introduced them.

### Logs & traces
- Structured JSON logs → Loki (or ELK); **OpenTelemetry** traces (gateway → service → DB/model) with one `request_id`; logs/traces/metrics correlated by that id.
- **Security telemetry:** authz-denial spikes, payment-failure spikes, **audit-write failures**, AI safety flags → dedicated alerts (feeds SIEM).

---

# PART 5 — CLOUDFLARE (edge & protection)

- **DNS + proxied** origins; full-strict TLS to origin (mTLS via origin certs).
- **WAF** — OWASP managed ruleset + custom rules (block known bad patterns, geo/rate anomalies).
- **DDoS** — L3/4 + L7 protection; **rate limiting** at edge (volumetric) layered under app business limits.
- **Bot management** — challenge suspicious automation on auth/checkout/AI endpoints.
- **CDN cache** for marketing/static + ISR; cache-tag purge on content/score change.
- **Page/edge rules** — HSTS, security headers at edge, redirect/canonical enforcement; **Turnstile** on signup/login to deter abuse without harming UX.

---

# PART 6 — BACKUP STRATEGY

| Asset | Method | Frequency | Retention | Restore-tested |
|---|---|---|---|---|
| **Postgres** | Continuous WAL archiving (PITR) + nightly base | continuous / nightly | 35 days PITR, 12 monthly | quarterly drill |
| **Object store (reports/exports)** | versioned bucket + cross-region replication | continuous | per policy | spot-check |
| **Elasticsearch** | snapshot to object store | 6-hourly | 14 days | reindex from Postgres possible (source of truth) |
| **Redis** | AOF + periodic RDB (cache = rebuildable) | hourly | 3 days | n/a (rebuild) |
| **Vector store** | snapshot + re-embed pipeline | daily | 7 days | re-embed from source |
| **Secrets/Vault** | encrypted Vault snapshots | daily | 35 days | drill |
| **Infra state (Terraform)** | remote backend + versioning | per apply | indefinite | — |

- **3-2-1**: 3 copies, 2 media/locations, 1 off-site (cross-region). Backups **encrypted** (KMS), access-audited, **immutable (WORM)** for the audit log + financial records.
- ES and vector store are **derivable from Postgres** — backups are for speed, not correctness.

---

# PART 7 — DISASTER RECOVERY

- **Targets:** **RPO 5 min** (WAL archiving), **RTO 30 min** (API), 60 min full platform.
- **Tiers:** Postgres PITR/replica promotion is the critical path; ES/Redis/vector are rebuildable.
- **Multi-AZ** by default; **warm standby** in a second region (replicated Postgres, IaC-reproducible cluster) for region failure.
- **Runbooks** for: DB failover (promote replica), region failover (DNS cutover via Cloudflare), data-feed outage (serve last-good + lower confidence), payment-gateway outage (queue + retry), key compromise (rotate + revoke sessions).
- **Game days** — quarterly DR drill (restore from backup into an isolated env, validate, time it); chaos testing on staging (pod/node kills, dependency latency).
- **Graceful degradation:** if AI is down, the app still serves quant scores + cached explanations; if a feed is stale, confidence drops and a banner shows — the product never hard-fails on a dependency.

---

# PART 8 — SECRETS MANAGEMENT

- **Vault (or cloud KMS/Secrets Manager)** as the single store; apps fetch via **CSI driver / sidecar**, never from env files in images.
- **Dynamic secrets** for DB where supported (short-TTL credentials, auto-rotated); static secrets rotated on schedule + on incident.
- **Encryption:** envelope encryption (KMS-wrapped DEKs); TLS in transit; secrets never logged (log scrubbers + gitleaks in CI).
- **CI/CD:** OIDC federation → short-lived cloud tokens; no static cloud keys in GitHub; sealed-secrets/SOPS for any GitOps-stored config.
- **Scope & audit:** least-privilege policies per service identity (k8s ServiceAccount ↔ Vault role); every secret access is audited.

---

# PART 9 — RBAC (platform + product)

**Two planes:**
1. **Infra RBAC** — k8s RBAC (namespaced roles, no cluster-admin for humans), cloud IAM least-privilege, Vault policies per identity, ArgoCD project-scoped permissions. Human prod access is **break-glass** (time-boxed, approved, audited).
2. **Product RBAC** — `user · admin · ml_ops · support` (doc 03 Part G): route guards + plan entitlements + row-level tenancy; admin/AI-ops on a separate audited shell; **step-up auth** for destructive ops.

- **Separation of duties** — who deploys ≠ who approves; who can refund ≠ who can change score models.
- All privileged actions → **audit log** (hash-chained, doc 03 Part K).

---

# PART 10 — MFA

- **Users:** TOTP + WebAuthn/passkeys; SMS-OTP for phone verification (signup/login) with anti-fraud throttling; MFA **required** for high-risk actions (payment method change, broker link, data export).
- **Staff/admin:** **mandatory** WebAuthn (phishing-resistant) for the admin/AI-ops shells and all cloud/k8s/Vault access; no password-only path.
- **Step-up** — re-prompt MFA for sensitive operations even within an authenticated session (refund, suspend, model promote, delete account).
- **Recovery** — backup codes (hashed), audited recovery flow; device/session management UI with revoke-all.

---

# PART 11 — API SECURITY

- **AuthN/Z** — RS256 JWT (15-min) + rotating refresh, scoped API keys (Premium); validated at gateway + app (doc 03 F/G).
- **Transport** — TLS 1.3, HSTS, mTLS origin↔ingress.
- **Input/Output** — Pydantic validation, parameterized queries, output DTOs strip premium/PII; strict CORS allowlist; CSRF for cookie auth.
- **Rate limiting** — multi-tier Redis token-bucket + edge limits (doc 03 L); cost-aware AI limits.
- **Idempotency** — `Idempotency-Key` on all mutating/payment endpoints.
- **Webhooks** — HMAC-signature verified (Razorpay), replay-protected (event-id idempotency), source-IP allowlist.
- **SSRF/abuse** — outbound allowlist for broker/feed/LLM calls; no user-controlled URLs fetched server-side.
- **Versioning & deprecation** — `/v1`; documented sunset policy; backward-compatible changes preferred.

---

# PART 12 — OWASP CONTROLS (Top 10 mapping)

| OWASP risk | Control |
|---|---|
| **A01 Broken Access Control** | RBAC + plan entitlements + **row-level tenancy** (+ Postgres RLS backstop); deny-by-default; audited admin |
| **A02 Cryptographic Failures** | TLS 1.3, KMS-wrapped at-rest encryption, argon2id passwords, no secrets in logs |
| **A03 Injection** | Pydantic validation, parameterized SQL, output encoding, prompt-injection filter on AI |
| **A04 Insecure Design** | threat-modeled flows; the **scores table is read-only to all but the scoring worker** (structural integrity); abuse cases in design review |
| **A05 Security Misconfiguration** | hardened images (non-root, read-only FS), CIS-benchmarked k8s, security headers, no default creds, IaC-reviewed |
| **A06 Vulnerable Components** | SCA (osv/Dependabot), Trivy image scan, SBOM, pinned deps, patch SLA |
| **A07 Identity & Auth Failures** | MFA, rotating refresh + reuse detection, lockout/throttle, secure session mgmt |
| **A08 Software & Data Integrity** | signed images (cosign) + admission policy, pinned CI actions, SBOM, GitOps with signed commits |
| **A09 Logging & Monitoring Failures** | structured logs, hash-chained audit, SIEM, alerting on authz/payment/audit-write anomalies |
| **A10 SSRF** | outbound allowlist, no user-supplied fetch URLs, metadata-endpoint blocking |

**Program-level:** secure-SDLC (threat modeling, security review on sensitive PRs), annual pen-test + bug bounty, dependency patch SLAs, security training, and **DPDP/GDPR** compliance (consent, data export, right-to-erasure with audit-preserved soft-delete).

---

## Addendum — Observability (see /observability)
Full SRE observability architecture added: three pillars (Prometheus metrics, Loki logs, OpenTelemetry traces) + Sentry, correlated by request_id/trace_id; a KPI taxonomy (business, product, AI, recommendation, notification, subscription, cost); five audience dashboards (Executive, Product, Engineering, AI Operations, Support) provisioned as code; an SLO-burn-rate alerting framework with a catalog + runbook links; and a full SLA/SLO spec with error-budget policy. See /observability.

## Appendix — production readiness checklist

- [ ] Non-root, signed, scanned images; admission policy enforced
- [ ] Helm + ArgoCD GitOps; canary + auto-rollback wired
- [ ] HPA/KEDA scaling; PDB, probes, graceful shutdown
- [ ] Prometheus SLOs + burn-rate alerts; Grafana dashboards as code; Sentry releases
- [ ] Cloudflare WAF/DDoS/bot + Turnstile on auth/checkout
- [ ] PITR backups + quarterly restore drill; warm standby region
- [ ] Vault secrets via CSI; OIDC to cloud; no static keys
- [ ] MFA mandatory for staff; step-up for sensitive user actions
- [ ] OWASP Top-10 controls verified; pen-test booked
- [ ] DR runbooks + game day scheduled

*Completes the architecture set: 01 strategy · 02 IA · 03 backend · 04 data/AI · 05 frontend · 06 devops/security. The platform is specified end-to-end — product through production.*
