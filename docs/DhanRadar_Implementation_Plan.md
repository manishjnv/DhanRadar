# DhanRadar — Phased Implementation Plan (Greenfield)

**Spec of record:** `e:\code\DhanRadar\DhanRadar_Architecture_Final.md` (all module/schema/interface detail lives there; this plan sequences and grounds it in verified external APIs).
**Build model:** each phase is self-contained, executable in a fresh chat context, references the architecture doc by section + the Allowed-APIs block below. **Frame every task as "copy the documented pattern," never "invent what should exist."**
**Invariants carried from the architecture doc (every phase must honor):** interface-only coupling (REST contract or named event), no shared mutable Postgres tables across modules, acyclic DAG build order, v2.3 cost ceiling (≤ ₹1,090/mo infra; AI free-pool → Sonnet spillover, hard $9.50/day), SEBI educational boundary + DPDP + CERT-In enforced in code.

---

## PHASE 0 — Allowed APIs & Anti-Patterns (READ FIRST, every phase)

Consolidated from official-doc discovery (sources cited). **Do not call any API not on this list without re-running discovery.**

### 0.1 Corrections to the architecture doc (authoritative — override the doc where they conflict)

| # | Architecture doc says | Reality (sourced) | Action |
|---|---|---|---|
| 1 | Email via "SendGrid free tier (100/day)" | SendGrid permanent free tier **retired 2025-05-27**; new accounts get 60-day trial then paid | **Use Resend** (`pip install resend`, 3,000/mo + 100/day permanent free) — src: resend.com/docs/send-with-python, twilio.com changelog. Brevo (300/day) is fallback. |
| 2 | Free model `deepseek/deepseek-chat-v3:free` | May be deprecated; current list shows `deepseek/deepseek-v4-flash:free` (1M ctx) | Add a startup check hitting `https://openrouter.ai/models`; never hardcode a free id without verifying it resolves. Keep `meta-llama/llama-3.3-70b-instruct:free`, `qwen/qwen-2.5-72b-instruct:free` as confirmed-live. |
| 3 | OpenRouter 1,000 req/day free | 50/day **without** $10 credit; 1,000/day **only after** purchasing $10; balance < 0 → HTTP **402** (not 429) | P0 task: buy the $10 OpenRouter credit before any AI phase; treat 402 as "balance/credit" distinct from 429 "rate limit". |

### 0.2 Allowed APIs (exact, copy-ready)

**OpenRouter** (src: openrouter.ai/docs) — `POST https://openrouter.ai/api/v1/chat/completions`; headers `Authorization: Bearer <key>`, `HTTP-Referer`, `X-Title`; body `{model|models, messages[], temperature, max_completion_tokens, response_format:{type:"json_object"}, stream}`; response `choices[0].message.content`, `usage`, `finish_reason`; error `{error:{code,message}}`; **429** = rate limit (per-day), **402** = balance. OpenAI-compatible client: `OpenAI(api_key=..., base_url="https://openrouter.ai/api/v1", default_headers={...})` → `client.chat.completions.create(...)`; catch `openai.RateLimitError` (429) and `openai.APIStatusError` (covers 402). Sonnet spillover model id: `anthropic/claude-sonnet-4.6` (paid $3/$15 per M). `models:[free, paid]` array does automatic fallback.

**Pydantic v2** (src: pydantic.dev) — `from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError, ValidationInfo`. Use `Field(ge=, le=, gt=, lt=, min_length=, max_length=, pattern=)` — **`pattern=` not `regex=`**. `@field_validator('f', mode='after') @classmethod def v(cls, value, info: ValidationInfo)` — `info.data` holds only fields declared **earlier** in class body. `@model_validator(mode='after') def v(self) -> Self: ... return self`. `ValidationError.errors()` → list of `{type, loc(tuple), msg, input, ctx, url}`.

**FastAPI** (src: fastapi.tiangolo.com) — parameterized dependency = **class with `__init__`+`__call__`**, pass the *instance* to `Depends()` (this is exactly how `require_tier("pro")`, `require_consent("purpose")` from the architecture doc must be implemented — NOT a closure). `HTTPException(status_code=402, detail=..., headers=...)`. Startup via `@asynccontextmanager lifespan` (NOT deprecated `@app.on_event`). Modular: `APIRouter(prefix=, tags=, dependencies=[Depends(...)])` + `app.include_router(router, prefix="/api/v1")`.

**Celery** (src: docs.celeryq.dev) — `Celery("dhanradar", broker="redis://...:6379/0", backend="redis://...")`; `@app.task(bind=True, autoretry_for=(...), retry_backoff=True, retry_backoff_max=600, retry_jitter=True, max_retries=...)`; `self.retry(exc=, countdown=)`; `app.conf.task_routes = {"mod.task":"queue"}`; `app.conf.beat_schedule = {name:{task,schedule:crontab(hour=,minute=,day_of_week=),args}}`; **always set `app.conf.timezone`**; worker `celery -A dhanradar worker -Q batch` / `-Q mood` / `-Q misc`; beat `celery -A dhanradar beat`. NOTE architecture doc beat times are **IST**; Celery runs UTC unless `timezone="Asia/Kolkata"` set — set it, or convert (e.g. NAV 23:30 IST = 18:00 UTC).

**Postgres 16 + TimescaleDB** (src: postgresql.org/docs/16, tigerdata.com docs) — `SELECT create_hypertable('mf_nav_history','nav_date', chunk_time_interval => INTERVAL '1 month');` (old interface, valid ≤2.18; **version-sensitive** — if TimescaleDB ≥2.13 prefer `CREATE TABLE ... WITH (tsdb.chunk_interval=...)`, verify at install). Continuous aggregate: `CREATE MATERIALIZED VIEW v WITH (timescaledb.continuous) AS SELECT time_bucket(INTERVAL '1 month', nav_date) ... GROUP BY ...` + `add_continuous_aggregate_policy(v, start_offset, end_offset, schedule_interval)`. Generated FTS col: `ADD COLUMN search_vec tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(...))) STORED` + `CREATE INDEX ... USING GIN(search_vec)`; query `@@ websearch_to_tsquery('english', q)`. `pg_trgm`: `CREATE EXTENSION pg_trgm; CREATE INDEX ... USING GIN(name gin_trgm_ops);` op `%` / `<->`. `pgvector`: `CREATE EXTENSION vector; col vector(11); CREATE INDEX USING ivfflat (v vector_cosine_ops) WITH (lists=...);` op `<=>`. `pg_partman`: `CREATE EXTENSION pg_partman; SELECT partman.create_parent(p_parent_table=>'public.ai_recommendation_audit', p_control=>'served_at', p_interval=>'1 month', p_premake=>4);` + `CALL partman.run_maintenance_proc();` via pg_cron.

**SQLAlchemy 2.x async** — `create_async_engine("postgresql+asyncpg://user:pass@host:5432/db", pool_size=, max_overflow=)`; `async_sessionmaker(engine, expire_on_commit=False)`; FastAPI yield-dependency `async def get_db() -> AsyncGenerator[AsyncSession,None]`.

**Docker Compose v2** — `deploy.resources.limits.memory: 512M` + `cpus:"0.50"` (preferred over legacy `mem_limit`); `depends_on: {postgres: {condition: service_healthy}}`; `healthcheck:{test:["CMD-SHELL","pg_isready -U postgres"], interval:10s, retries:5, start_period:30s}`.

**casparser** (src: github.com/codereverser/casparser) — `pip install casparser`; `casparser.read_cas_pdf(file_path, password)` → `{statement_period, file_type:CAMS|KARVY, cas_type, investor_info, folios:[{folio, amc, schemes:[{scheme, isin, amfi, valuation:{date,nav,value,cost}, transactions:[...]}]}]}`. Supports CAMS + KFintech; NOT NSDL/CDSL equity CAS.

**AMFI NAV — daily** (src: portal.amfiindia.com, live-verified 2026-05-17, re-verified 2026-06-07) — `GET https://portal.amfiindia.com/spages/NAVAll.txt`, **semicolon-delimited, 6 fields**, header `Scheme Code;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date`, date fmt `DD-Mon-YYYY`, `-` for missing ISIN, category-header + AMC-name + blank lines interspersed (skip lines not matching the 6-field split), updated ~21:00–22:00 IST business days (architecture doc's 23:30 IST NAV beat is safely after).

**AMFI NAV — historical** (src: portal.amfiindia.com, **added + live-verified 2026-06-07**, ADR-0025) — `GET https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?frmdt=DD-Mon-YYYY&todt=DD-Mon-YYYY` (no `mf`/`tp` params needed → returns all schemes for the window). **Semicolon-delimited but 8 fields in a DIFFERENT column order** vs NAVAll: `Scheme Code;Scheme Name;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Repurchase Price;Sale Price;Date` (Repurchase/Sale ignored). AMFI caps each request to ~3 months, so a multi-year backfill must loop over non-overlapping windows. The two layouts require **separate parsers** (`parse_navall` 6-field / `parse_nav_history` 8-field — `backend/dhanradar/market_data/amfi.py`). This is the canonical, India-resident backfill source for the 1Y/3Y return signals (B29); no third-party NAV vendor is introduced.

**Telegram Bot API** (src: core.telegram.org/bots/api) — `POST https://api.telegram.org/bot<TOKEN>/sendMessage` `{chat_id, text, parse_mode:"HTML"}`; `/sendPhoto` `{chat_id, photo|file, caption}`; channel push via `@channelusername` or numeric id, bot must be channel admin.

**Razorpay** (src: razorpay.com/docs) — `pip install razorpay`; `razorpay.Client(auth=(KEY_ID,KEY_SECRET))`; `client.plan.create({period,interval,item:{name,amount(paise),currency}})`; `client.subscription.create({plan_id,total_count,customer_notify})`; webhook header `X-Razorpay-Signature`, verify `client.utility.verify_webhook_signature(raw_body_bytes, signature, webhook_secret)` (raises on mismatch — do NOT json-parse before verifying).

**Cloudflare R2** (src: developers.cloudflare.com/r2) — `boto3.client("s3", endpoint_url="https://<ACCOUNT_ID>.r2.cloudflarestorage.com", aws_access_key_id=, aws_secret_access_key=, region_name="auto")`; R2-specific S3 token (not the CF account token); `upload_file`, `generate_presigned_url`.

**Account Aggregator** (src: docs.setu.co) — **integration-partner, deep spec deferred**: FIU registration (Sahamati / Setu FIU-as-service) required; consent UI is RBI-prescribed and cannot be skinned; flow = `POST /consents` → redirect user to AA approval → webhook → data-fetch as structured JSON. Plan treats AA as a **stubbed adapter** until partnership signed (architecture doc already sequences it Phase-2+; CAS is the Phase-1 hook).

### 0.3 Anti-patterns (grep guards — fail the phase if found)

- `regex=` in Pydantic `Field(` → must be `pattern=`
- `@app.on_event(` → must be `lifespan`
- closure-style `def require_tier(tier): def dep(): ...` → must be `__init__`/`__call__` class
- hardcoded `:free` model id without a verify-on-startup check
- `sendgrid` import / "SendGrid free" → must be `resend`
- treating OpenRouter 402 as a rate-limit retry (it is a balance/credit error — alert, don't spin)
- any cross-module `JOIN`/`INSERT` into another module's table → must go through the documented interface/event
- Celery `beat_schedule` without `app.conf.timezone` set
- `boto3.client("s3", ...)` without `region_name="auto"` for R2

---

## PHASE 1 — Infra & Project Skeleton — SHARED-INFRA on KVM4 (architecture §A6, §B5, §B6, Global §6; Reality Layer §4.2)

> **Deployment target decided: KVM4, shared-infra model.** Verified facts (read-only SSH inventory, 2026-05-17) driving this phase:
>
> - **Box = `shared-host` SSH alias → `<KVM4-HOST>`**, Ubuntu 24.04.4, 4 vCPU, **16 GB RAM, ~9.94 GB free**, 193 GB disk (57 GB free), Docker 29.3.1, ~32 containers (the `shared_`/shared-host product).
> - **No public :22/:80/:443.** Box is fully behind a **Cloudflare Tunnel (`cloudflared`)** — SSH itself is via `cloudflared access ssh` ProxyCommand. This is the exposure model: Cloudflare Tunnel ingress → internal container ports. **No origin IP is exposed; no host 80/443; no shared Caddy here** (KVM2's `co-tenant-caddy-1` is a *different box* and irrelevant now).
> - Shared services present: `shared_prometheus` (Prometheus v2.53.0), `shared_grafana` (Grafana 11.1.0), `shared_postgres` (**plain `postgres:16-alpine` — NO TimescaleDB**), `shared_redis` (`redis:7-alpine`, NOAUTH-gated, another product's), `shared_nginx` (shared-host's own, not the public edge).
> - Host ports already bound (**do not reuse**): 22 53 3001 3005-3025 3101 5433 6380 7475 7688 8080 8443 9001 9002 9190 9201 20241 65529.
> - Domain **`dhanradar.com`** already registered (Hostinger registrar); no purchase.

**Reuse decision matrix (canonical Phase-1 footprint on KVM4):**

| Component | Decision | Why |
|---|---|---|
| **Box / OS / Docker** | **REUSE** KVM4 (no new VPS) | 9.94 GB free, 4 vCPU — comfortable; ₹0 extra |
| **Public exposure / TLS** | **DEDICATED DhanRadar Cloudflare Tunnel** (NOT the existing one) — a *new named tunnel* created under the **`<CF-ACCOUNT-EMAIL>`** CF account (the account that owns `dhanradar.com`), run as a **second cloudflared systemd instance** (`cloudflared-dhanradar.service`, own `/etc/cloudflared-dhanradar/config.yml` + own credentials JSON). Ingress: `dhanradar.com/api/*` → `http://dhanradar-fastapi:8000`, default → `http://dhanradar-nextjs:3000`, `http_status:404` catch-all. DNS = **CNAME** `dhanradar.com` → `<dhanradar-tunnel-id>.cfargotunnel.com`. | The existing tunnel (`<SHARED-SSH-TUNNEL-ID>-…`, locally-managed `/etc/cloudflared/config.yml`) carries **`<SHARED-SSH-HOST> → ssh://localhost:22` — the box's SSH lifeline** — plus `<SHARED-HOST>`; a bad edit there could lock us out of the box. It is also account-scoped to the *shared-host* CF account, so it **cannot** route `dhanradar.com` (different account) anyway. A separate tunnel = zero blast radius on shared-host/SSH + correct account scoping. cloudflared is ~tiny RAM. Still no DhanRadar nginx/Caddy container — ingress path-routing replaces the architecture doc's "nginx routes /api". |
| **Observability** | **REUSE** `shared_prometheus` (add a DhanRadar scrape job to its config) + `shared_grafana` (add DhanRadar dashboards/alerts) | Shared Prom+Grafana already running; zero extra RAM |
| **PostgreSQL** | **OWN dedicated container** `timescale/timescaledb-ha:pg16` (bundles timescaledb + pgvector), mem-cap ~1.2 GB (headroom allows it) | **Mandatory, two reasons:** (1) shared `shared_postgres` is plain pg16 with **no TimescaleDB** — `mf_nav_history`/`mood_history` need it; (2) regulatory isolation — DhanRadar holds DPDP consent, 7-yr SEBI audit, financial holdings; independent `pg_dump`→R2, own blast-radius, CERT-In log isolation. Internal-only (Docker network, no host port). |
| **Redis** | **OWN dedicated container** `redis:7-alpine`, ~256 MB, `maxmemory-policy noeviction` | `shared_redis` is another product's + NOAUTH; budget-governor `ai:budget:*` keys must never be LRU-evicted; architecture namespacing assumes a dedicated instance. Internal-only. |
| **nginx / Caddy / uptime-kuma / own prometheus/grafana** | **DROP** | cloudflared ingress = the proxy; reused Prom/Grafana + CF tunnel health = uptime |

Resulting footprint: **8 internal containers** (own-postgres, own-redis, fastapi, nextjs, celery-batch, celery-mood, celery-misc, celery-beat) ≈ **~3 GB capped** → fits in ~9.94 GB free with **~6 GB margin** (relaxed vs the KVM2 plan).

**What to implement (copy the documented patterns):**

1. **External accounts/DNS:** Cloudflare zone `dhanradar.com` ✅ **DONE** (account `<CF-ACCOUNT-EMAIL>`, NS delegated, Free plan, verified 2026-05-17). The `dhanradar.com` **CNAME → `<dhanradar-tunnel-id>.cfargotunnel.com`** is created in step 4 from the *dedicated* tunnel (not the existing shared-host tunnel). **Buy the $10 OpenRouter credit** (Phase 0 §0.1#3 — key alone = 50 req/day). Create **Resend** acct + verify `dhanradar.com` DKIM (Phase 0 §0.1#1 — NOT SendGrid). Private repo under `github.com/manishjnv`. Cloudflare **R2** bucket + R2-scoped S3 token.
2. **Phase-1 investigation tasks (do first; record in `infra-notes.md`):** (a) **cloudflared = RESOLVED** (host `cloudflared.service`, locally-managed `/etc/cloudflared/config.yml`, tunnel `<SHARED-SSH-TUNNEL-ID>-…` carrying `<SHARED-SSH-HOST>`+`<SHARED-HOST>`) → **do NOT touch it**; instead the prerequisite is `cloudflared tunnel login` authenticated to the **`<CF-ACCOUNT-EMAIL>`** CF account (produces `~/.cloudflared/cert.pem` scoped to that account/zone) — needed to create the dedicated tunnel in step 4; (b) how `shared_prometheus` discovers scrape targets (`/opt/shared-host/.../prometheus.yml`?) and how to add a DhanRadar job; (c) confirm `timescale/timescaledb-ha:pg16` ships `vector`; verify/install `pg_partman` + `pg_cron`; (d) pick a clearly-free host port **only if** one is ever needed (most DhanRadar traffic stays internal+tunnel) — avoid the bound-port list above.
3. **`docker-compose.yml`** — the **8 services above**, all on a dedicated `dhanradar` Docker network, **no host port bindings** (cloudflared reaches the web/api containers over the shared Docker network or a single high free port), `deploy.resources.limits.memory` (postgres 1200M, redis 256M, fastapi 600M, nextjs 512M, celery-batch 300M, celery-mood 256M, celery-misc 256M, celery-beat 64M), `depends_on.condition: service_healthy`, healthchecks (Phase 0 Docker block).
4. **Dedicated DhanRadar tunnel — ✅ DONE 2026-05-17 (record of what exists + corrected commands; never edit `/etc/cloudflared/config.yml` or `cloudflared.service` = shared-host's shared-ssh + the box SSH lifeline):**
   - **Tunnel:** `dhanradar` = `<DHANRADAR-TUNNEL-ID>`; isolated cert `/etc/cloudflared-dhanradar/cert.pem` (scoped to `<CF-ACCOUNT-EMAIL>`, the account owning `dhanradar.com`), credentials `/etc/cloudflared-dhanradar/dhanradar.json`. `cloudflared tunnel --origincert /etc/cloudflared-dhanradar/cert.pem create --credentials-file /etc/cloudflared-dhanradar/dhanradar.json dhanradar`.
   - **DNS:** `dhanradar.com` proxied CNAME → `<DHANRADAR-TUNNEL-ID>-….cfargotunnel.com`, verified `HTTP/2 200` end-to-end. **GOTCHA (cost us a remediation): `cloudflared tunnel route dns <NAME> …` resolves the tunnel via the *default* `/etc/cloudflared/config.yml` (= shared-ssh `<SHARED-SSH-TUNNEL-ID>`) and mis-targets the CNAME.** Correct form is the **explicit UUID + overwrite**: `cloudflared tunnel --origincert /etc/cloudflared-dhanradar/cert.pem route dns --overwrite-dns <DHANRADAR-TUNNEL-ID> dhanradar.com` — or set it in the CF dashboard DNS UI (Content must read `dhanradar`, not `shared-ssh`).
   - **ingress validate correct syntax:** the `--config` is a global flag *before* the subcommand path → `cloudflared tunnel --config /etc/cloudflared-dhanradar/config.yml ingress validate` (NOT `… ingress validate --config …`). Must pass before any run.
   - **Runtime = containerized, NOT a host systemd unit.** Host `cloudflared` can't resolve Docker names; run a `cloudflared-dhanradar` **container** in the DhanRadar compose stack on the `dhanradar` network, mounting `/etc/cloudflared-dhanradar/dhanradar.json` + a real `config.yml` whose ingress is `dhanradar.com` `path: ^/api/.*` → `http://dhanradar-fastapi:8000`, then `hostname: dhanradar.com` → `http://dhanradar-nextjs:3000`, then `- service: http_status:404`. (Pin image `cloudflare/cloudflared:2026.5.0`; the host binary is 2026.3.0 and must NOT be upgraded — shared-ssh depends on it.)
   - **Process-safety rule (a `pkill -f` self-matched the SSH shell during cleanup):** never `pkill -f <pattern>` where the pattern can appear in your own command line. Enumerate with `pgrep -x cloudflared`, read `/proc/<pid>/cmdline`, kill only the PID whose cmdline contains `/etc/cloudflared-dhanradar/config.yml`; the shared-ssh systemd connector (`/etc/cloudflared/config.yml`, currently pid <PID>) is KEEP.
   - **Verify (after the compose stack exists in later Phase-1 steps):** `https://dhanradar.com/api/v1/health` → 200; `systemctl is-active cloudflared` still `active` and `/etc/cloudflared/config.yml` sha unchanged (`<SHA>…`); `<SHARED-SSH-HOST>` SSH still works.
5. **Postgres init (own container):** `CREATE EXTENSION` `timescaledb`, `vector`, `pg_trgm`, `pg_partman`, `pg_cron`; dedicated `dhanradar` DB + non-superuser role; schema-per-concern (no shared mutable tables across modules).
6. **FastAPI app:** `lifespan` startup, modular `APIRouter` per module under `/api/v1`, SQLAlchemy async engine + `get_db` yield-dependency (Phase 0 FastAPI + SQLAlchemy blocks).
7. **Celery app + Beat** `timezone="Asia/Kolkata"`, `task_routes` → `batch|mood|misc`, empty beat_schedule.
8. **Cost-governor** Redis keys `ai:budget:free:today`/`ai:budget:premium:today` with `EXPIREAT` next-UTC-midnight, `budget_guard()` stub; add DhanRadar alerts (mem>80%, p99>500ms, AI budget>900) to **reused** `shared_grafana`; Sentry DSN.

**Doc refs:** architecture §A6, §B5, §B6, Global §6, Reality Layer §4.2 infra-reuse map; Phase 0 Docker/Celery/SQLAlchemy/Postgres blocks. (Architecture §B1/Global §1's "Nginx routes /api/* to FastAPI, rest to Next.js" is **realized as cloudflared ingress path rules** on KVM4 — note this substitution.)
**Verification:** `docker compose up` → all 8 DhanRadar containers healthy; `https://dhanradar.com/api/v1/health` → 200 **through the Cloudflare Tunnel** with valid CF cert; **shared-host's existing hostnames still resolve** after cloudflared reload (curl each); `psql` in own container `\dx` lists 5 extensions; Celery boots per queue; box `free -m` still ≥4 GB free under load; DhanRadar Redis `maxmemory-policy`=`noeviction`; a DhanRadar metric appears in `shared_prometheus`/`shared_grafana`. Grep guards: no `@app.on_event`, no missing `timezone`, no host `:80/:443` binding, no DhanRadar nginx/Caddy container.
**Anti-pattern guards:** Phase 0 §0.3 + (new) never edit cloudflared ingress or `shared_prometheus` config without a backup + post-reload verification that the shared-host product still works; DhanRadar containers join only the `dhanradar` Docker network and never read/write `shared_postgres`/`shared_redis`; no host-port collision with the bound-port list.

---

## PHASE 2 — Cross-cutting Globals: Auth & Tiering · Consent/DPDP · Compliance Audit · Admin (architecture Global §2,§3,§4,§9; §B8; §C)

**Must precede any user-data or AI module** (DPDP is live; audit must exist before first AI output).

**What to implement:**

1. **Auth & Tiering** (Global §2): `users`/`subscriptions` tables (exact columns incl. `dpdp_consent_version`, `dpdp_consents JSONB`, `deletion_requested_at`), RS256 JWT in `__Host-` HttpOnly cookies, `RequireTier` **class** (`__init__`/`__call__`) + `current_user_or_anonymous`, Nginx `anon:10m rate=30r/m` zone, Razorpay webhook (`verify_webhook_signature` on raw body — Phase 0 Razorpay block), TOTP via `pyotp`.
2. **Consent/DPDP** (Global §3): `consent_audit_log` (append-only), `data_principal_requests`, `RequireConsent` class dependency, `/api/v1/consent/*` + `/data-rights/*`, `process_erasure` Celery task (30-day SLA monitor), 72 h breach task, NIC NTP (`time.nplindia.org`) on host.
3. **Compliance Audit** (Global §4): `disclaimers` (versioned), `ai_recommendation_audit` (**`pg_partman` monthly** — Phase 0 block), `rating_engine_changelog`, `get_active_disclaimer()`, `log_ai_recommendation()` fire-and-forget, `check_label_churn_gate()` (>5% → `pending_publish`, fail-closed), nightly R2 archival (boto3 `region_name="auto"`).
4. **Admin & Governance** (Global §9): `prompt_templates`/`ranking_configs`/`content_moderation_queue`, admin RBAC, PostHog flags, weight-sum 1.0±0.001 validator, two-person methodology gate (`approved_by ≠ created_by`).

**Doc refs:** architecture Global §2/§3/§4/§9, §B8 cross-cutting table, §C compliance; Phase 0 FastAPI/Razorpay/Postgres-partman blocks.
**Verification:** signup→JWT cookie set HttpOnly; anon hits gated route → 402 `{upgrade_url}`; `require_consent("ai_insights")` blocks without grant (403) and logs to `consent_audit_log`; erasure request anonymizes PII but retains audit; `ai_recommendation_audit` partition auto-creates next month; >5% churn batch lands `pending_publish`. Grep: parameterized deps are classes not closures.
**Anti-pattern guards:** no closure deps; Razorpay verify before json-parse; audit table is partitioned; consent table append-only (no UPDATE/DELETE paths).

---

## PHASE 3 — Market Data Adapter + AI/LLM Gateway (architecture §B3, §B4)

**What to implement:**

1. **Market Data Adapter** (§B4): provider-agnostic, YAML config-driven routing, circuit breaker, ordered fallback ladders; emits normalized events (`mfcentral.holdings.received`, `aa.holdings.received` [AA = **stub** until partner], NAV/price refreshed). Domain modules never call a vendor directly.
2. **AI/LLM Gateway** (§B3): `OpenRouterGateway` using OpenAI-compat client (Phase 0 OpenRouter block) — free-pool round-robin with **startup model-id verification** (Phase 0 §0.1#2), on `openai.RateLimitError`(429) rotate model, on `APIStatusError`(402) → alert "credit", on schema-validation fail → Sonnet spillover (`anthropic/claude-sonnet-4.6`) for high-stakes task types within premium budget else 3-strike skip. `QualityValidator` = Pydantic schema extending `AIOutputBase` (≥2 contributing signals; `confidence>0.7 ⇒ ≥3`; `pattern=`). `budget_guard()` enforces `ai:budget:*` inside gateway (free 1,000/day, premium soft $0.50, hard $9.50). `TASK_MODEL_PREFERENCES` read from Admin `prompt_templates` (no hardcoded prompts).

**Doc refs:** architecture §B3/§B4, §S (AIOutputBase contract), Phase 0 OpenRouter/Pydantic blocks.
**Verification:** unit-test gateway: 429 → model rotation (no sleep); 402 → alert path not retry; forced schema fail on `stock_pick` → Sonnet spillover, on `news_summary` → 3-strike skip; budget key increments and blocks at cap; adapter circuit-breaker opens on simulated 5xx and falls to next ladder rung. Grep: no hardcoded `:free` without verify; no 402-as-429.
**Anti-pattern guards:** Phase 0 §0.3.

---

## PHASE 4 — Rating / Scoring Engine v1 (architecture §S)

**The IP core. Standalone service; strict interface coupling.**

**What to implement (copy §S exactly):**

1. Deterministic factor model (MF inputs first: rolling returns, Sharpe/Sortino, drawdown, expense, AUM stability, category-rank percentile) → versioned weights from `ranking_configs`.
2. Deterministic verb-label rule table (🟢 In-form / 🟡 On-track / 🟠 Off-track / 🔴 Out-of-form) per §S2.2 — label derived from rules, **not** from the number.
3. Collapse function → `{unified_score, confidence_band, verb_label, valid_until, eval_seq}`; confidence < 0.30 ⇒ refuse ("Insufficient data").
4. Governance (§S4): 2-consecutive-eval **hysteresis** before a label flip (expose `eval_seq`); label-distribution sanity bounds; methodology write to `rating_engine_changelog`; >5% batch churn → Compliance human-review gate (Phase 2).
5. Interface only: consume `*.score.requested`/holdings events, read agreed read-only views; publish `scoring.result.published`; serve `GET /internal/v1/score/{instrument_type}/{identifier}`.

**Doc refs:** architecture §S (entire), §C governance, Phase 0 Pydantic block.
**Verification:** golden-set MF fixtures → expected label/score; flip suppressed until 2 consecutive evals; confidence floor returns "Insufficient data"; engineered >5% churn batch is held by Compliance gate; changelog row written on weight change. No domain module imports the engine's internals (grep imports).
**Anti-pattern guards:** label must not be a pure function of the numeric score; no module bypasses `scoring.result.published`.

---

## PHASE 5 — Mutual Fund Module (architecture Tier C → Mutual Fund Module)

**Launch-critical. MF-first.**

**What to implement (copy the appendix + Phase 0 casparser/AMFI blocks):**

1. Schema: `mf_funds`, `mf_nav_history` (**TimescaleDB hypertable**, 1-month chunks, continuous aggregate `mf_nav_monthly_agg` — Phase 0 Postgres block), `mf_user_holdings`, `mf_portfolio_snapshots`, `mf_cas_jobs`, `user_fund_scores`. Redis keys/TTLs per appendix incl. `mf:isin_users:{isin}` reverse index.
2. **AMFI NAV pipeline** — Celery beat `mf.nav.daily_fetch` 23:30 IST (= 18:00 UTC; `timezone` set): fetch `portal.amfiindia.com/spages/NAVAll.txt`, semicolon-split, skip non-6-field lines, bulk-upsert hypertable, refresh Redis, emit `mf.nav.refreshed`, targeted invalidation via `mf:isin_users`.
3. **CAS → 60s report** — `POST /api/v1/mf/upload/cas`: SHA-256 dedup (`mf:cas:dedup`), enqueue `mf.cas.parse`, return `{job_id, estimated_seconds:60}` <200ms; worker `casparser.read_cas_pdf(path, password)` → walk `folios[].schemes[]` (isin/amfi/units/valuation) → upsert holdings → materialize snapshot (current value, XIRR via numpy_financial+scipy.brentq, category allocation, overlap) → cache report 2h → emit `mf.holdings.updated` → Rating Engine → `scoring.result.published` → `user_fund_scores`. Round trip ≤ 60s.
4. Endpoints + scoring integration (feed signals, consume unified score via event only — never recompute).

**Doc refs:** architecture Tier C Mutual Fund Module (full), §S interface, Phase 0 casparser/AMFI/Postgres blocks.
**Verification (end-to-end):** upload a sample CAMS CAS PDF + password → status polled → `/report` returns labelled schemes in **≤60s**; AMFI beat run populates `mf_nav_history` and continuous aggregate; NAV refresh invalidates only affected users' snapshots; score arrives via `scoring.result.published` (MF module never calls the engine internals). Grep: no cross-module table writes.
**Anti-pattern guards:** no NSDL/CDSL CAS assumption (casparser is CAMS/KFintech only); raw CAS purged at 24h; SEBI disclaimer injected at serializer.

---

## PHASE 6 — Notification (Telegram) + Email substitution (architecture Global §5)

**✅ Pre-Phase-6 gate — CLEARED 2026-05-19:** (a) Resend dashboard shows `dhanradar.com` = **Verified**; (b) a live test send returned **HTTP 200** (Resend id `149a367b-d4a6-45d0-8327-032ac674be0f`, from `noreply@dhanradar.com` to the founder inbox). **Gotcha for the email module:** `api.resend.com` is behind Cloudflare and **rejects the default `Python-urllib` User-Agent with HTTP 403 / Cloudflare error 1010** — the email client must send a real `User-Agent` header, or use the official `resend` SDK (which sets one).

**What to implement:**

1. `notification_preferences`/`notification_log`; Redis `notifications:queue:{telegram,email}` lists; `celery-misc` BLPOP consumer with quiet-hours + per-channel rate caps.
2. Telegram: `sendMessage`/`sendPhoto` (Phase 0 Telegram block); public-channel daily Mood card path (bot = channel admin).
3. **Email = Resend** (`pip install resend`, Phase 0 §0.1#1) — NOT SendGrid; `resend.Emails.send({from,to,subject,html})`; cap 100/day. Use the `resend` SDK (or set a real `User-Agent`) — raw `urllib` calls to `api.resend.com` are Cloudflare-blocked (403 / error 1010). Verified-working sender domain: any `@dhanradar.com` (e.g. `noreply@dhanradar.com`).
4. Pillow share-card service (1200×630 PNG → R2, signed URL for private/portfolio cards).

**Doc refs:** architecture Global §5; Phase 0 Telegram/R2 blocks; §0.1#1 correction.
**Verification:** enqueue a test notification → delivered to Telegram test chat; Resend email sends (202); quiet-hours defers; share-card PNG lands in R2 with working presigned URL. Grep: no `sendgrid` import.
**Anti-pattern guards:** no SendGrid; Telegram failures cap at 3 retries (stale alerts have negative value).

---

## PHASE 7 — Verification & Hardening

1. **End-to-end MF-first flow:** anon browses public page → uploads CAS → ≤60s labelled report → NAV beat refresh → label change → Telegram alert. Prove each hop.
2. **Coverage:** every Phase-1–6 module's architecture-doc interface implemented; run the architecture §V coverage logic against shipped endpoints/events.
3. **Anti-pattern grep sweep:** Phase 0 §0.3 list across the repo — zero hits.
4. **Constraint audit (Haiku-suitable sweep):** container memory sum ≤ budget; AI budget keys enforce caps (force-exhaust test → 402/skip, not overspend); DPDP `require_consent` on every data-processing route; `ai_recommendation_audit` partition + R2 archival working; NIC NTP synced; secrets only from env/GitHub Secrets (secrets-scan).
5. **Adversarial gate (security-adjacent — Auth/Consent/AI-classifier):** before any deploy, run an adversarial review of Auth/Tiering, Consent/DPDP, and the Rating-Engine governance gates (JWT cookie scope, consent bypass, label-churn fail-closed, prompt-injection on AI chat). Log verdict.

---

## OPTIONAL BACKLOG — Additive popularity / virality / trust mechanics

All are **additive and decoupled** (extend an existing module via its interface; none changes a shipped module's contract), **SEBI-safe** (educational framing, no buy/sell), and **cost-aware** (≤ free-pool budget; India-retail / WhatsApp-first). Tagged by mechanic. Prioritize ★ first — highest leverage for investor adoption.

| ★ | Idea | Mechanic | Extends (interface-only) | SEBI / cost note |
|---|---|---|---|---|
| ★ | **WhatsApp "Fund Report Card" bot** — DM/forward a fund name → 🟢🟡🟠🔴 label + 3-line "why". Zero app install; India is WhatsApp-first. | Acquisition / viral | Notification + Rating Engine read API | Educational labels only; free-pool LLM for the 3-liner |
| ★ | **"Portfolio Wrapped" (annual, Spotify-style)** — Dec–Jan shareable recap card: best/worst calls, SIP streak, vs-NIFTY, diversification grade. | Viral / retention | Portfolio + Track-Record + Pillow share-card | Aggregate user's own data; one PNG/yr/user — negligible cost |
| ★ | **Public immutable "Prediction Ledger"** — every Mood Compass call & rating timestamped, append-only, publicly browsable ("here are our receipts"). | Trust / SEO moat | Compliance Audit + Track-Record (read views) | Regulated competitors *cannot* do this — durable differentiator; zero AI cost |
| ★ | **Creator/finfluencer embeddable widgets** — compliant `<iframe>` Mood Compass / fund-label badge creators drop in YouTube descriptions & blogs. | Distribution (the channel India fintech actually sells through) | UI/SSR + public read API | Disclaimer baked into widget; cached, near-zero marginal cost |
| ★ | **Vernacular AI summaries (Hindi + 2 regional)** — one-tap translate the 3-line explainer. Large under-served retail segment. | Acquisition / inclusion | AI Enrichment (additive task type) | Cheap on free-pool models; education-only |
| | **"Fund Face-off" comparison cards** — head-to-head shareable card built for WhatsApp group debates. | Viral | Search + Rating Engine + share-card | Comparative facts, no recommendation |
| | **SIP "Doctor" nudge** — quantifies the historical 7Y-CAGR cost of stopping a SIP in a drawdown (extends the existing redemption-drawdown nudge with a number). | Retention / behavioral | Behavioral Nudge (new template + param) | Educational coaching; pre-authored copy, no runtime LLM |
| | **"Crowd Mood vs Market Mood" divergence** — anonymized aggregate of user sentiment vs the model; contrarian-education content engine. | Engagement / novel content | Mood Compass + anonymized behavior aggregate | Aggregate only (DPDP-safe); reuses existing pipeline |
| | **Seasonal tax-education alerts (Feb–Jun): LTCG/tax-loss-harvest explainers** — high-utility, seasonally viral. | Acquisition / retention | Alert & Digest (new educational trigger) | Education framing; calendar-driven, no AI cost |
| | **"Explain like I'm new" toggle on every metric** — lowers the comprehension barrier that kills retail retention. | Retention / trust | UI/Design `RankingExplainer` (variant) | Static copy + cached LLM glossary; one-time cost |

**Sequencing suggestion:** the four ★ distribution/trust items (WhatsApp bot, Prediction Ledger, creator widgets, vernacular) align with architecture Phase 6 "Growth"; "Portfolio Wrapped" slots after Portfolio Intelligence (Phase 5). None blocks the MF-first critical path — treat as a post-P1 growth backlog, groomed after the Phase-7 end-to-end proof.

---

## Execution notes

- Run phases in order; each is a fresh-context session that opens by reading **Phase 0** + its own phase + the cited architecture sections.
- Phase 2 and Phase 4/Phase 5 touch security/auth/AI-classifier logic → carry the Phase 7 §5 adversarial gate before any deploy of those.
- Discovery is cached in Phase 0; re-run a targeted discovery subagent only if a library/API not listed there is needed.

---

## Standard Phase Kickoff Prompt (use verbatim for every phase)

Paste this into the fresh session, replacing `<N>` with the phase number. The four standing rules are embedded here so each session is reminded in the prompt itself, not only via infra-notes.

```
Execute Phase <N> of docs/DhanRadar_Implementation_Plan.md. First read in full:
the project CLAUDE.md overlay, docs/infra-notes.md (verified facts + the ❌
NEVER-TOUCH list + standing rules),
this plan's Phase 0 and Phase <N> sections, and the architecture sections Phase <N>
cites in docs/DhanRadar_Architecture_Final.md. Target = KVM4 via SSH alias
`shared-host`, shared-infra reuse model, dedicated `dhanradar` cloudflared tunnel
<DHANRADAR-TUNNEL-ID> run as a container. Honor every NEVER-TOUCH
rule and the three cloudflared gotchas. Scaffold/changes locally first for my
review BEFORE any KVM4 deploy or GitHub push; first commit uses the noreply
git-email pattern.

Standing rules — apply to this phase, not optional:
1. RCA: every bug fixed gets an entry appended to docs/rca/README.md (symptom,
   root cause, fix with file:line, prevention, date); read the log before debugging.
2. Feature docs: every module built or changed has docs/features/<module>.md per
   the template in docs/features/README.md, kept in sync; the phase is not done
   until it is updated.
3. UI branding: any UI work uses the design tokens (frontend/tailwind.config.js,
   frontend/src/styles/tokens.css, frontend/styles/tokens.json) and matches docs/ui-system/brand/
   and its mockups; no ad-hoc colours, spacing, typography, or off-system components.
4. Reply/summary format: answer and summarize in simple-sentence pointers under
   these sections — Implemented, Pending, Not implemented, Action for you,
   Dependencies, Issues, Deviations, Agent/model usage & % contribution,
   Improvement suggestions. No dense tables.
5. Governance gates: this is a multi-agent tiered governance model (project CLAUDE.md
   + docs/project-state/AI_GOVERNANCE_MODEL.md). Build as Builder, then run the reviews
   required by the change's tier — A standard: Architect+UI · B security/auth/billing/
   AI/compliance: Architect+Security(codex:rescue)+Compliance · C scoring/recommendation:
   Architect+Compliance+Product (Builder+Architect always) — and record them in the single
   docs/project-state/reviews/<change-id>.md with its gate ledger. No major change is "done"
   until the tier's reviews pass and the deterministic gates (tests + secrets + anti-pattern/
   IGNORE grep) are green. Security/auth/classifier and compliance-sensitive changes are
   fail-closed.

Phase 6 only: do not start until Resend shows dhanradar.com = Verified and a test
send succeeds (see the Pre-Phase-6 gate).
```
