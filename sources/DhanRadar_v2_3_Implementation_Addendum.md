# DhanRadar v2.3 — Implementation Stack Addendum

**Status:** Active overlay on v2.2 — additive, does not supersede  
**Date:** May 2026 · **Prepared by:** Manish · **Classification:** Internal  
**Builds on:** v2.2 (Strategic & Architectural Update) · v2.1 · Master Blueprint

---

## Document Changelog (Updated)

| Version | Date | Scope | Status |
|---|---|---|---|
| v2.0 | Feb 2026 | Initial production architecture | Superseded |
| v2.1 | Mar 2026 | Production-grade gap resolution (14 gaps + 8 partials) | Superseded |
| v2.2 | May 2026 | Strategic & product alignment with Master Blueprint + competitor analysis | Active |
| **v2.3 (this addendum)** | **May 2026** | **Implementation stack: Hostinger KVM 2 + OpenRouter + Claude Code + Windows dev + GitHub** | **Active overlay on v2.2** |

**v2.3 introduces:**
- Hostinger KVM 2 hosting fit + 12-container resource plan (down from v2.2's 19)
- OpenRouter AI strategy ($10 unlock for 1,000 free reqs/day + premium spillover)
- Claude Code single-user compliance setup pattern
- Local Windows dev environment (`E:\code\DhanRadar`) + GitHub workflow (`manishjnv/dhanradar`)
- Revised cost model: ~₹1,090/month operating (~90% reduction vs v2.2)
- Break-even at 6 Pro subscribers (vs 73 in v2.2)
- Day-one setup checklist
- Updated risk register and phase adjustments

**v2.3 does NOT change:**
- Any of the 14 v2.2 architecture recommendations (still in scope)
- Any of the 10 competitor-research enhancements (still in scope)
- Pricing strategy (Pro ₹1,999/yr, Pro+ ₹3,999/yr — confirmed)
- 18-week phased plan structure (only intra-phase task sequencing changes)
- Domain references — **note the change to dhanradar.in** (not .com)

---

# Part X — v2.3 Implementation Stack

## 10.1 Environment Configuration Snapshot

| Component | v2.3 Configuration |
|---|---|
| VPS provider | Hostinger |
| VPS plan | KVM 2 |
| VPS specs | 2 vCPU AMD EPYC, 8 GB RAM, 100 GB NVMe SSD, 8 TB bandwidth |
| VPS cost | $8.99/month promotional (~₹756/month) |
| OS | Ubuntu 24.04 LTS |
| Domain | dhanradar.in |
| CDN / DNS / SSL | Cloudflare free tier |
| AI provider (production runtime) | OpenRouter — $10 credit → 1,000 free model reqs/day + spillover |
| AI provider (development) | Claude Code on VPS, Claude Max 20 plan |
| Local dev environment | Windows 11, `E:\code\DhanRadar` |
| Version control | Git |
| Repository | github.com/manishjnv/dhanradar (private until launch) |
| Email | SendGrid free tier (100/day) |
| Object storage | Cloudflare R2 (10 GB free) — replaces MinIO |
| Payment processor | Razorpay (subscription mode) |
| Error tracking | Sentry free tier (5K events/month) |
| Product analytics | PostHog free tier (1M events/month) |
| Uptime monitoring | Uptime Kuma (self-hosted) |

---

## 10.2 Hostinger KVM 2 Resource Allocation

### Resource availability vs v2.1 baseline

| Resource | KVM 2 | v2.1 baseline (Hetzner CPX21) | Verdict |
|---|---|---|---|
| RAM | 8 GB | 4 GB | Better — comfortable headroom |
| vCPU | 2 cores | 3 cores | Tighter — must cap concurrency |
| Storage | 100 GB NVMe | 80 GB NVMe | Better |
| Bandwidth | 8 TB/month | Adequate | More than enough for early launch |

### Container memory budget (12 containers, ~4.2 GB total)

| Container | Allocated | Notes |
|---|---|---|
| nginx | 64 MB | Reverse proxy + SSL termination |
| nextjs | 512 MB | Next.js with `node --max-old-space-size=400` |
| fastapi | 600 MB | Gunicorn 2 workers (down from v2.1's 4) |
| postgres | 1.5 GB | `shared_buffers=512MB`, `work_mem=8MB` |
| redis | 256 MB | `maxmemory 200mb`, LRU eviction |
| celery-batch | 300 MB | Stock + MF batch jobs |
| celery-mood | 256 MB | Mood Compass twice-daily |
| celery-misc | 256 MB | Digest + gamification + social consolidated |
| celery-beat | 64 MB | Scheduler |
| prometheus | 200 MB | Metrics, 15-day retention |
| grafana | 150 MB | Dashboards |
| uptime-kuma | 100 MB | Self-hosted uptime monitor |
| **Total** | **~4.2 GB** | **3.8 GB headroom for Postgres cache + OS** |

### What was dropped from v2.1's 19-container plan

| Dropped service | Reason | Replacement |
|---|---|---|
| postgres_replica | Streaming replica overkill at <10K MAU | Nightly logical backup (`pg_dump`) to Cloudflare R2 |
| elasticsearch | Heavy on memory and CPU | Postgres GIN indexes + `tsvector` full-text search |
| minio | 200 MB used | Cloudflare R2 (10 GB free, S3-compatible) |
| loki + promtail | 300 MB combined | `docker logs` + journalctl, add Loki later if needed |
| celery-social, celery-dlq, celery-gamification | 3 separate workers wasteful | Consolidated into `celery-misc` |
| 4 fastapi workers | Too many for 2 vCPU | 2 fastapi workers |

---

## 10.3 OpenRouter AI Strategy

### The $10 Unlock — Day One Critical Action

Without spending $10, OpenRouter's free tier is capped at **50 requests per day total** across all free models. Once you purchase $10 of credits, the limit jumps to **1,000 free model requests per day** — and it stays at that limit even after credits are consumed by paid model usage.

**Action: Buy the $10 credit on Day 1, even before writing the OpenRouter adapter.** This is the architectural unlock that makes the entire AI strategy viable.

### Daily Request Budget (1,000 free model cap)

Conservative allocation for early launch (≤10K MAU):

| Workload | Reqs/day | Free model | Caching | Notes |
|---|---|---|---|---|
| Stock batch (top 500 NSE stocks) | 500 | DeepSeek V3 / Llama 3.3 70B | 7-day TTL | Recompute only on >5% price move OR earnings/news |
| MF/ETF batch (top 300 funds) | 200 | Qwen 2.5 72B | Daily NAV / weekly full | NAV-only updates daily |
| News tagging + summary | 100 | Llama 3.3 70B | 24h TTL | Bloom dedup before LLM |
| Mood Compass (2× daily) | 2 | DeepSeek R1 (free) or Sonnet (spillover) | 12h TTL | Flagship feature — quality matters |
| AI chat (50 chats × 2 turns) | 100 | Llama 3.3 70B | 1h TTL on identical queries | Cap context aggressively |
| "Why X moved today" (top 20) | 20 | DeepSeek V3 | 24h TTL | Public SEO landing pages |
| Search AI | 50 | Llama 3.3 70B | 24h TTL by query hash | Strong cache |
| **Total free reqs** | **972** | | | **28 buffer for retries** |
| Premium spillover (high-stakes only) | ~20 | Claude Sonnet | — | ~$0.10/day → $3/month |

### Free Model Pool (round-robin to handle 20 req/min limit)

```python
# backend/app/gateway/openrouter_adapter.py
FREE_MODEL_POOL = [
    "deepseek/deepseek-chat-v3:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "google/gemma-3-27b-it:free",
    "mistralai/mistral-small-3.1:free",
]

PREMIUM_SPILLOVER = "anthropic/claude-3.5-sonnet"

class OpenRouterGateway:
    BASE_URL = "https://openrouter.ai/api/v1"
    DAILY_FREE_BUDGET = 1000
    DAILY_PREMIUM_BUDGET_USD = 0.50  # ~$15/month spillover cap
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.model_index = 0
    
    async def call(self, prompt: str, task_type: str, schema: type[BaseModel]) -> BaseModel:
        free_used = int(await self.redis.get("ai:budget:free:today") or 0)
        premium_used = float(await self.redis.get("ai:budget:premium:today") or 0)
        
        # Premium spillover for high-stakes tasks
        if task_type in {"mood_commentary", "earnings_summary"} \
           and (free_used > 850 or task_type == "mood_commentary"):
            if premium_used < self.DAILY_PREMIUM_BUDGET_USD:
                return await self._call_premium(PREMIUM_SPILLOVER, prompt, schema)
        
        # Free model round-robin
        model = FREE_MODEL_POOL[self.model_index % len(FREE_MODEL_POOL)]
        self.model_index += 1
        
        try:
            response = await self._call_model(model, prompt)
            await self.redis.incr("ai:budget:free:today")
            return self._validate(response, schema)
        except RateLimitError:
            # Try next model in pool (RPM may be exhausted on this one)
            return await self.call(prompt, task_type, schema)
        except SchemaValidationError:
            # Quality failure — try premium fallback for critical tasks
            if task_type in {"stock_pick", "mf_pick"}:
                return await self._call_premium(PREMIUM_SPILLOVER, prompt, schema)
            raise
    
    async def _call_premium(self, model: str, prompt: str, schema):
        response = await self._call_model(model, prompt)
        cost_usd = self._estimate_cost(response)
        await self.redis.incrbyfloat("ai:budget:premium:today", cost_usd)
        return self._validate(response, schema)
```

### Quality Validation Layer (new requirement vs v2.2)

Free models hallucinate more than Sonnet. Strict Pydantic schemas + sanity bounds prevent bad outputs from poisoning the database.

```python
# backend/app/schemas/stock_pick.py
class StockPickV2(BaseModel):
    ticker: str = Field(pattern=r"^[A-Z]{1,12}$")
    confidence_score: float = Field(ge=0.0, le=1.0)
    contributing_signals: list[str] = Field(min_length=2, max_length=10)
    contradicting_signals: list[str] = Field(default_factory=list, max_length=5)
    bull_target_12m: float = Field(ge=-0.50, le=2.00)  # bounded sanity
    bear_target_12m: float = Field(ge=-0.80, le=1.00)
    thesis: str = Field(min_length=50, max_length=500)
    
    @model_validator(mode="after")
    def targets_must_make_sense(self):
        if self.bear_target_12m >= self.bull_target_12m:
            raise ValueError("Bear target must be below bull target")
        if self.confidence_score > 0.7 and len(self.contributing_signals) < 3:
            raise ValueError("High confidence requires 3+ supporting signals")
        return self

# Failure handling: 3 strikes per (ticker, day) → log & skip
class QualityValidator:
    async def validate_or_skip(self, raw_output: dict, schema: type[BaseModel],
                                ticker: str, redis) -> BaseModel | None:
        try:
            return schema(**raw_output)
        except ValidationError as e:
            fails_today = await redis.incr(f"ai:fails:{ticker}:{today()}")
            await redis.expire(f"ai:fails:{ticker}:{today()}", 86400)
            if fails_today >= 3:
                await self._log_failure(ticker, raw_output, e)
                return None  # Skip this ticker today
            raise  # Retry
```

### Caching Strategy Adjustments (vs v2.1/v2.2)

Because every cache miss costs a precious daily quota slot, all TTLs in v2.1 must increase:

| Cache | v2.1 TTL | v2.3 TTL | Invalidation trigger |
|---|---|---|---|
| Stock pick | 48h | **7 days** | >5% price move, earnings, major news |
| News summary | 1h | **24h** | n/a (just expire) |
| Mood Compass | n/a | **12h** | Scheduled regeneration only |
| AI chat response | 1h | **1h** (same) | n/a |
| Search results | 1h | **24h** | n/a |
| MF analysis | 48h | **weekly** | Quarterly rebalance, manager change |
| SWOT engine | weekly | **monthly** | Earnings announcement |

---

## 10.4 Claude Code Setup & Single-User Compliance

### Setup Pattern on Hostinger VPS

```bash
# SSH to VPS as your admin user (NOT root, NOT a service account)
ssh manish@dhanradar.in

# Install Node 20+ (required for Claude Code)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verify
node --version  # should be v20.x or higher

# Install Claude Code globally for your user
npm install -g @anthropic-ai/claude-code

# Authenticate with Claude Max 20 account (browser-based flow)
cd /home/manish/dhanradar
claude
# → Browser opens, authenticate, return to terminal

# Use only in interactive sessions
claude
> "refactor the OpenRouter gateway to add retry-with-jitter on 429 errors"
```

### Three Compliance Guardrails

These are structural, not just policy:

1. **Personal user account only** — Run Claude Code only under your `manish` user. Never under `www-data`, `dhanradar`, `root`, or any service account. This makes the single-user constraint enforced by Linux user permissions.

2. **No production runtime integration** — Do NOT wire Claude Code into:
   - cron jobs
   - systemd services
   - FastAPI endpoints
   - Celery tasks
   - GitHub Actions runners
   
   Production AI calls go through OpenRouter only. Claude Code is a development tool, not a runtime dependency.

3. **No session sharing** — If you bring on a contractor or co-developer later, they use their own Claude Code license. Never share the auth session, API key, or terminal access to your authenticated `claude` instance.

### Budget Separation (Critical Mental Model)

| Bucket | Pays for | Cost | Where it appears |
|---|---|---|---|
| **Claude Max 20** (personal) | You writing the application | ~$200/month | Personal subscription, not company opex |
| **OpenRouter** (company) | The application serving end users | $10/quarter | Company opex |

Don't conflate the two. They appear in different lines of your books. Your Max 20 plan is your personal developer productivity tool; OpenRouter is the production AI infrastructure.

---

## 10.5 Local Development Environment (E:\code\DhanRadar)

### Windows Setup Stack

| Tool | Version | Purpose |
|---|---|---|
| Windows 11 | Latest | Host OS |
| Docker Desktop | Latest | With WSL2 backend (better performance than Hyper-V) |
| WSL2 + Ubuntu 24.04 | Latest | Linux compatibility for development |
| VS Code | Latest | Editor + Remote-WSL extension |
| Git for Windows | Latest | Version control (with Git Bash) |
| Python | 3.11.x | Backend development (via pyenv-win or system install) |
| Node.js | 20 LTS | Frontend development |
| Claude Code (Windows) | Latest | Optional — local development assistant |

### Local Folder Structure (`E:\code\DhanRadar`)

```
E:\code\DhanRadar\
├── .git\
├── .github\
│   ├── workflows\
│   │   ├── test.yml
│   │   ├── deploy.yml
│   │   ├── security.yml
│   │   └── lint.yml
│   ├── dependabot.yml
│   └── ISSUE_TEMPLATE\
├── .gitignore
├── .env.example                     # template only — never commit secrets
├── .pre-commit-config.yaml
├── README.md
├── LICENSE
├── docker-compose.yml               # production compose
├── docker-compose.dev.yml           # dev overrides (hot reload, debugger ports)
├── Makefile                         # common commands wrapped
├── backend\
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── app\
│   │   ├── main.py
│   │   ├── api\                     # FastAPI routes
│   │   ├── core\                    # auth, deps, logging, config
│   │   ├── services\                # business logic
│   │   ├── gateway\                 # OpenRouter + market data adapters
│   │   ├── workers\                 # Celery tasks
│   │   ├── db\                      # SQLAlchemy + Redis clients
│   │   ├── schemas\                 # Pydantic v2 models
│   │   └── dedup\                   # Bloom + SimHash
│   ├── tests\
│   │   ├── conftest.py
│   │   ├── unit\
│   │   ├── integration\
│   │   └── load\                    # k6 scripts
│   └── alembic\                     # DB migrations
├── frontend\
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── app\
│   ├── components\
│   ├── lib\
│   └── public\
├── nginx\
│   └── nginx.conf
├── prometheus\
│   └── prometheus.yml
├── grafana\
│   ├── dashboards\
│   └── datasources\
├── scripts\
│   ├── deploy.sh
│   ├── backup.sh
│   ├── restore.sh
│   └── seed.py
├── docs\
│   ├── architecture\
│   │   ├── v2.1-architecture.docx
│   │   ├── v2.2-strategic-update.md
│   │   └── v2.3-implementation-addendum.md
│   ├── api\
│   ├── ops\
│   └── compliance\
└── .vscode\
    ├── settings.json
    ├── launch.json
    └── extensions.json
```

### Development Workflow

```bash
# In WSL2 Ubuntu, mount E: drive
cd /mnt/e/code/DhanRadar

# Initial setup (one time)
git clone git@github.com:manishjnv/dhanradar.git .
cp .env.example .env       # populate with dev values
pre-commit install

# Daily development
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
make test                  # runs pytest
make lint                  # runs Black + Ruff + Prettier + ESLint
make dev                   # starts dev servers with hot reload

# Before committing
pre-commit run --all-files
git add .
git commit -m "feat(mood): add Mood Compass daily worker"
git push origin feature/mood-compass
```

### `.env.example` Template

```bash
# Application
APP_ENV=development
APP_NAME=DhanRadar
APP_URL=http://localhost:3000

# Database
DATABASE_URL=postgresql+asyncpg://dhanradar:dev@postgres:5432/dhanradar
REDIS_URL=redis://redis:6379/0

# AI Gateway (OpenRouter)
OPENROUTER_API_KEY=sk-or-v1-xxxxx
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_DAILY_FREE_BUDGET=1000
OPENROUTER_DAILY_PREMIUM_BUDGET_USD=0.50

# Auth
JWT_PRIVATE_KEY_PATH=/secrets/jwt_private.pem
JWT_PUBLIC_KEY_PATH=/secrets/jwt_public.pem
JWT_ISSUER=dhanradar.in
JWT_AUDIENCE=dhanradar-api

# External services
RAZORPAY_KEY_ID=rzp_test_xxxxx
RAZORPAY_KEY_SECRET=xxxxx
SENDGRID_API_KEY=SG.xxxxx
SENTRY_DSN=https://xxxxx@sentry.io/xxxxx
POSTHOG_API_KEY=phc_xxxxx

# Object storage (Cloudflare R2)
R2_ACCOUNT_ID=xxxxx
R2_ACCESS_KEY_ID=xxxxx
R2_SECRET_ACCESS_KEY=xxxxx
R2_BUCKET=dhanradar-prod

# Domain
DOMAIN=dhanradar.in
COOKIE_DOMAIN=.dhanradar.in
```

---

## 10.6 GitHub Repository Structure (manishjnv/dhanradar)

### Repository Settings

| Setting | Value |
|---|---|
| Repository | github.com/manishjnv/dhanradar |
| Visibility | Private until launch, then evaluate open-sourcing parts |
| Default branch | `main` |
| Branch protection on `main` | Required PR review (1+), passing CI, no force push |
| Squash merging | Enabled |
| Auto-delete head branches | Enabled |
| Discussions | Enabled (for contributor collaboration later) |
| Issues | Enabled with templates |

### Branch Strategy

```
main           ← production, protected
  ↑
develop        ← integration branch
  ↑
feature/*      ← topic branches (feature/mood-compass, feature/portfolio-overlap)
hotfix/*       ← urgent production fixes (PR directly to main + back-merge to develop)
release/v*     ← release preparation branches
```

### GitHub Actions Workflows

| Workflow | Trigger | Purpose |
|---|---|---|
| `test.yml` | Every push, PR | pytest with 80% coverage gate, frontend Vitest |
| `lint.yml` | Every push, PR | Black, Ruff, Prettier, ESLint, YAML lint |
| `security.yml` | Daily + PR | Snyk dependency scan, Bandit Python SAST, Trivy Docker scan |
| `deploy.yml` | Push to main | SSH to Hostinger, pull + rebuild, health check |
| `dependabot.yml` | Weekly | Dependency updates (pip, npm, GitHub Actions) |

### Required GitHub Secrets

```
# SSH deployment
HOSTINGER_HOST              = your.dhanradar.in IP
HOSTINGER_SSH_USER          = manish
HOSTINGER_SSH_PRIVATE_KEY   = (deploy key, ed25519)

# OpenRouter
OPENROUTER_API_KEY          = sk-or-v1-xxxxx

# Database (production)
DATABASE_URL                = postgresql://...
REDIS_URL                   = redis://...

# Razorpay
RAZORPAY_KEY_ID             = rzp_live_xxxxx
RAZORPAY_KEY_SECRET         = xxxxx
RAZORPAY_WEBHOOK_SECRET     = xxxxx

# Email
SENDGRID_API_KEY            = SG.xxxxx

# Object storage
R2_ACCOUNT_ID               = xxxxx
R2_ACCESS_KEY_ID            = xxxxx
R2_SECRET_ACCESS_KEY        = xxxxx

# Observability
SENTRY_DSN                  = https://xxxxx@sentry.io/xxxxx
SENTRY_AUTH_TOKEN           = xxxxx
POSTHOG_API_KEY             = phc_xxxxx

# CI tools
SNYK_TOKEN                  = xxxxx
CODECOV_TOKEN               = xxxxx (optional)

# Notification
DEPLOY_TELEGRAM_BOT_TOKEN   = xxxxx (admin alerts)
DEPLOY_TELEGRAM_CHAT_ID     = xxxxx
```

### Sample `deploy.yml`

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  test:
    uses: ./.github/workflows/test.yml
  
  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.HOSTINGER_HOST }}
          username: ${{ secrets.HOSTINGER_SSH_USER }}
          key: ${{ secrets.HOSTINGER_SSH_PRIVATE_KEY }}
          script: |
            cd /home/manish/dhanradar
            git pull origin main
            docker compose pull
            docker compose up -d --no-deps --build fastapi nextjs celery-batch celery-mood celery-misc
            docker compose ps
      
      - name: Health check
        run: |
          for i in {1..10}; do
            if curl -fsS https://dhanradar.in/health; then
              echo "✓ Healthy"
              exit 0
            fi
            sleep 5
          done
          echo "✗ Health check failed"
          exit 1
      
      - name: Notify deployment
        if: always()
        run: |
          STATUS="${{ job.status }}"
          curl -X POST "https://api.telegram.org/bot${{ secrets.DEPLOY_TELEGRAM_BOT_TOKEN }}/sendMessage" \
            -d "chat_id=${{ secrets.DEPLOY_TELEGRAM_CHAT_ID }}" \
            -d "text=🚀 DhanRadar deploy: $STATUS (commit ${{ github.sha }})"
```

---

## 10.7 Architecture Changes (Drop / Replace / Add)

### Dropped from v2.1/v2.2

| Component | Reason |
|---|---|
| Hetzner CPX21 references | Replaced with Hostinger KVM 2 throughout |
| Anthropic Batch API | Replaced with OpenRouter free model pool |
| dharradar.com / dhanradar.com | Replaced with dhanradar.in everywhere |
| Postgres streaming replica | Logical backup to R2 sufficient at current scale |
| Elasticsearch | Postgres GIN + tsvector for FTS |
| MinIO | Cloudflare R2 free tier |
| Loki + Promtail | Postpone — use docker logs for early launch |
| celery-social, celery-dlq, celery-gamification | Consolidated into celery-misc |
| Anthropic Pro dev account | Replaced by Claude Max 20 |

### Replaced

| v2.1/v2.2 | v2.3 replacement | Savings |
|---|---|---|
| Anthropic Haiku batch (₹3,780/mo) | OpenRouter free models (₹0) | ₹3,780/mo |
| Anthropic Sonnet content (₹336/mo) | OpenRouter free models (₹0) | ₹336/mo |
| Anthropic Sonnet chat (₹588/mo) | OpenRouter free models (₹0) | ₹588/mo |
| Mood Compass AI (₹450/mo) | OpenRouter free + spillover (~₹100) | ₹350/mo |
| Hetzner CPX21 (₹1,680/mo) | Hostinger KVM 2 (₹756/mo) | ₹924/mo |
| MinIO ops (₹0 but RAM cost) | Cloudflare R2 free | RAM saving |
| Anthropic Pro (₹1,680/mo) | Claude Max 20 (personal, not opex) | ₹1,680/mo |

### Added

| New component | Purpose |
|---|---|
| `OpenRouterAdapter` in LLM Gateway | Free model rotation + spillover routing |
| `QualityValidator` Pydantic layer | Reject hallucinated outputs from free models |
| Daily AI budget tracker (Redis) | `ai:budget:free:today`, `ai:budget:premium:today` |
| Cloudflare R2 client | S3-compatible object storage replacement for MinIO |
| Postgres FTS schema | Replaces Elasticsearch search |
| Cloudflare R2 nightly DB backup script | Replaces streaming replica |

---

## 10.8 Revised Docker Compose (12 Containers)

```yaml
# docker-compose.yml
version: '3.9'

services:
  # ── Edge ─────────────────────────────────────────────────
  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on: [fastapi, nextjs]
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 128M

  # ── Application ─────────────────────────────────────────
  nextjs:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      - NODE_ENV=production
      - NEXT_PUBLIC_API_URL=https://dhanradar.in/api
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 600M

  fastapi:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: gunicorn app.main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    depends_on: [postgres, redis]
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 700M

  # ── Workers ─────────────────────────────────────────────
  celery-batch:
    build:
      context: ./backend
    command: celery -A app.workers worker -Q batch -c 2 -l info
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    depends_on: [postgres, redis]
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 350M

  celery-mood:
    build:
      context: ./backend
    command: celery -A app.workers worker -Q mood -c 1 -l info
    depends_on: [postgres, redis]
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 300M

  celery-misc:
    build:
      context: ./backend
    command: celery -A app.workers worker -Q misc -c 1 -l info
    # Handles: digest, gamification, social posting, share cards
    depends_on: [postgres, redis]
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 300M

  celery-beat:
    build:
      context: ./backend
    command: celery -A app.workers beat -l info
    depends_on: [redis]
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 100M

  # ── Data ─────────────────────────────────────────────────
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: dhanradar
      POSTGRES_USER: dhanradar
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgres/postgresql.conf:/etc/postgresql/postgresql.conf:ro
    command: postgres -c config_file=/etc/postgresql/postgresql.conf
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 1.6G

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 200mb --maxmemory-policy allkeys-lru --appendonly yes
    volumes:
      - redis_data:/data
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 256M

  # ── Observability ───────────────────────────────────────
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=15d'
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 220M

  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 180M

  uptime-kuma:
    image: louislam/uptime-kuma:1
    volumes:
      - uptime_kuma_data:/app/data
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 120M

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:
  uptime_kuma_data:
```

### Postgres Tuning for KVM 2 (8 GB RAM)

```conf
# postgres/postgresql.conf — sized for 1.6 GB container limit
shared_buffers = 512MB                    # 25% of allocated RAM
effective_cache_size = 1200MB             # 75% of allocated RAM
work_mem = 8MB
maintenance_work_mem = 128MB
max_connections = 100
random_page_cost = 1.1                    # NVMe SSD
effective_io_concurrency = 200
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
```

---

## 10.9 Revised Cost Model

### Monthly Operating Cost (v2.3)

| Line Item | Provider | USD/mo | INR/mo | Notes |
|---|---|---|---|---|
| Hostinger KVM 2 | Hostinger | $8.99 | ₹756 | Promotional rate |
| dhanradar.in domain | Hostinger/registrar | $0.65 | ₹54 | Annualized (~₹650/yr) |
| Cloudflare | Cloudflare | $0 | ₹0 | Free tier |
| Cloudflare R2 storage | Cloudflare | $0 | ₹0 | 10 GB free |
| OpenRouter spillover | OpenRouter | $3.33 | ₹280 | $10 every ~3 months |
| SendGrid email | SendGrid | $0 | ₹0 | 100/day free |
| GitHub | GitHub | $0 | ₹0 | Free for solo dev |
| Sentry | Sentry | $0 | ₹0 | 5K events/mo free |
| PostHog | PostHog | $0 | ₹0 | 1M events/mo free |
| Snyk | Snyk | $0 | ₹0 | Open source plan |
| **Total infrastructure** | | **$13** | **₹1,090** | |

### Personal/Marketing Costs (Separate Books)

| Line Item | Cost | Note |
|---|---|---|
| Claude Max 20 (personal dev tool) | ~₹16,800/mo | Your personal subscription, not company opex |
| Creator partnerships (months 1–6) | ~₹50,000/mo | Company marketing budget |
| Razorpay processing fees | ~2.36% of revenue | Only kicks in with paying users |

### Cost Comparison: v2.1 → v2.2 → v2.3

| Version | Monthly Infra Cost | vs Budget (₹15K) |
|---|---|---|
| v2.1 | ₹9,744 | 65% |
| v2.2 | ₹10,944 | 73% |
| **v2.3** | **₹1,090** | **7%** |

### Break-Even Analysis (v2.3)

- Pro at ₹199/mo, contribution after 2.36% Razorpay ≈ ₹194/mo
- **Break-even: 6 Pro subscribers** to cover infrastructure
- Compared to v2.2's break-even of 73 Pro subscribers
- This shifts DhanRadar from "needs ~70 paying users to survive" to "viable at hobby scale"

### Year 1 Revenue Projection (Same as v2.2 — Targets Unchanged)

- 100K MAU target
- 2,000 Pro × ₹1,999/yr = ₹40L
- 200 Pro+ × ₹3,999/yr = ₹8L
- Lifetime founder (1,000 × ₹4,999) = ₹50L (one-time)
- Year 1 ARR: ₹48L recurring + ₹50L founder = **~₹98L total**
- Gross margin: 98%+ (infrastructure ~₹13K/year against ₹48L ARR)

---

## 10.10 v2.3 Risk Register Additions

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| OpenRouter free models removed or rate-limited further | Medium | High | Adapter layer makes provider swap config-only; $10 spillover for emergency premium fallback; budget hard cap at $9.50 to preserve buffer |
| 1,000 reqs/day quota exhausted on traffic spike | Medium | Medium | Hard cap on Pro+ AI chat; degrade gracefully (cached responses + "AI temporarily limited"); Redis budget tracker visible to ops |
| Free model output quality below acceptable threshold | Medium-High | High | Pydantic validation rejects bad outputs; manual spot-check top 50 weekly picks; Track Record page exposes any drift; spillover to Sonnet for failed validations on stock_pick / mf_pick |
| KVM 2 OOM under traffic burst | Low | High | 3.8 GB headroom; Docker memory limits per container; Prometheus alert at 80% RAM |
| Hostinger renewal price jump | High in 24 months | Medium | Promotional ~$9 → renewal ~$22/mo; still affordable, plan migration path to Hetzner if needed |
| Claude Code single-user policy violation | Low | High | Personal user account only; no service-account install; no API exposure; documented in compliance notes |
| .in domain SEO disadvantage vs .com | Low-Medium | Low | India-targeted SEO favors .in for Indian queries; minor disadvantage for global discovery (acceptable tradeoff) |
| Cloudflare R2 egress charges if traffic spikes | Low | Low | First 10 GB storage + Class A operations free; egress to Cloudflare network free; monitor in dashboard |
| Razorpay onboarding delays for SaaS | Medium | Medium | Apply 6 weeks before launch; have Stripe India backup plan |
| WSL2 + Docker Desktop performance issues on Windows | Low | Low | Use WSL2 backend (not Hyper-V); disable indexing on E:\code\DhanRadar; mount via /mnt/e |

---

## 10.11 Phased Plan — v2.3 Specific Adjustments

The 18-week v2.2 plan stands. v2.3 adjusts intra-phase task ordering to de-risk the OpenRouter dependency early.

### Phase 1 (Weeks 1–2) — Foundation + Anonymous Access — *v2.3 Adjustments*

**Add to Day 1:**
- Provision Hostinger KVM 2 + Ubuntu 24.04 setup
- Buy `dhanradar.in` domain
- Configure Cloudflare DNS + SSL
- Create GitHub repo `manishjnv/dhanradar` (private)
- Initialize `E:\code\DhanRadar` locally
- Install Claude Code on VPS as `manish` user
- **Purchase $10 OpenRouter credits — UNLOCKS 1,000/day quota**
- Generate OpenRouter API key

**Add to Week 1:**
- Write `OpenRouterAdapter` as the very first gateway component
- Smoke-test free model rotation under 20 req/min limit
- Validate $10 unlock works (verify 1,000/day cap is active)

### Phase 2 (Weeks 3–4) — Mood Compass + Public Discovery — *v2.3 Adjustments*

**Critical validation:**
- Run Mood Compass on free models for **one full week** before public launch
- A/B compare free model output quality vs Sonnet output (use $5 of spillover for the comparison)
- If DeepSeek V3 / Llama 3.3 70B output is acceptable for Mood Compass commentary, route there permanently
- If not, configure Mood Compass to always use Sonnet via spillover (~$2/month sustained)

### Phase 3 (Weeks 5–7) — AI Engine — *v2.3 Adjustments*

By end of Phase 3, you'll have empirical data on which free model wins on which task. Bake those decisions into routing config:

```python
TASK_MODEL_PREFERENCES = {
    "stock_pick": "deepseek/deepseek-chat-v3:free",       # winner from testing
    "mf_pick": "qwen/qwen-2.5-72b-instruct:free",
    "news_summary": "meta-llama/llama-3.3-70b-instruct:free",
    "swot_engine": "deepseek/deepseek-chat-v3:free",
    "mood_commentary": "anthropic/claude-3.5-sonnet",     # premium spillover
    "earnings_summary": "anthropic/claude-3.5-sonnet",    # premium spillover
    "ai_chat": "meta-llama/llama-3.3-70b-instruct:free",
    "search": "meta-llama/llama-3.3-70b-instruct:free",
    "why_today": "deepseek/deepseek-chat-v3:free",
}
```

### Other phase adjustments

- **Phase 5 (Pro launch):** Razorpay onboarding takes 4-6 weeks for SaaS — start application in Phase 3 (Week 5)
- **Phase 6 (Distribution):** WhatsApp Business API setup also has 2-3 week lead time — start in Phase 5
- **Phase 7 (Launch prep):** Verify Hostinger renewal pricing 60 days before launch; if jump is significant, plan Hetzner migration

---

## 10.12 Day-One Setup Checklist

Sequential checklist for first day of implementation. Each item should be completable in under 30 minutes.

### Domain & DNS

- [ ] Purchase `dhanradar.in` domain (Hostinger or external registrar like GoDaddy/Namecheap)
- [ ] Add domain to Cloudflare (free plan)
- [ ] Update nameservers at registrar to Cloudflare
- [ ] Enable Cloudflare proxy (orange cloud) for `@`, `www`, `api`
- [ ] Enable "Full (strict)" SSL mode in Cloudflare
- [ ] Enable "Always Use HTTPS" in Cloudflare
- [ ] Create page rule: `*dhanradar.in/*` → cache level standard

### VPS Provisioning

- [ ] Order Hostinger KVM 2 plan
- [ ] Select Ubuntu 24.04 LTS
- [ ] Generate SSH key pair (`ssh-keygen -t ed25519`) on local machine
- [ ] Add SSH public key to Hostinger control panel
- [ ] SSH into VPS as root, create `manish` user with sudo
- [ ] Disable root SSH login, password auth (`/etc/ssh/sshd_config`)
- [ ] Configure UFW firewall (allow 22, 80, 443 only)
- [ ] Install Docker Engine + Docker Compose
- [ ] Install Node 20 + npm
- [ ] Install Claude Code: `npm install -g @anthropic-ai/claude-code`
- [ ] Authenticate Claude Code with Max 20 account

### GitHub Repository

- [ ] Create private repo: `github.com/manishjnv/dhanradar`
- [ ] Add `.gitignore` (Python + Node + macOS/Windows + IDE)
- [ ] Add `README.md` with project intro
- [ ] Add `LICENSE` (MIT or proprietary)
- [ ] Add `.env.example` template
- [ ] Configure branch protection on `main`
- [ ] Add deploy SSH key to repository → Settings → Deploy keys
- [ ] Add all GitHub Actions secrets (per §10.6 list)
- [ ] Create `.github/workflows/test.yml`, `deploy.yml`, `security.yml`

### Local Development (Windows)

- [ ] Install Docker Desktop with WSL2 backend
- [ ] Install Ubuntu 24.04 in WSL2
- [ ] Install Git for Windows
- [ ] Install VS Code + Remote-WSL extension
- [ ] Install Python 3.11 (via pyenv-win or system)
- [ ] Install Node 20 LTS
- [ ] Create `E:\code\DhanRadar` and clone repo: `git clone git@github.com:manishjnv/dhanradar.git E:\code\DhanRadar`
- [ ] Configure Git user: `git config user.name "Manish"; git config user.email "your@email.com"`
- [ ] Install pre-commit: `pip install pre-commit && pre-commit install`

### OpenRouter

- [ ] Sign up at openrouter.ai
- [ ] **Purchase $10 in credits — CRITICAL for 1,000/day free model quota**
- [ ] Generate API key
- [ ] Test with curl: `curl https://openrouter.ai/api/v1/models -H "Authorization: Bearer $OPENROUTER_API_KEY"`
- [ ] Verify free model access by calling `meta-llama/llama-3.3-70b-instruct:free`
- [ ] Add API key to GitHub Secrets and `.env`

### Cloudflare R2 (Object Storage)

- [ ] Enable R2 in Cloudflare dashboard (no credit card needed for free tier)
- [ ] Create bucket: `dhanradar-prod`
- [ ] Generate R2 API token with Object Read+Write
- [ ] Note Account ID + Access Key ID + Secret Access Key
- [ ] Add to GitHub Secrets and `.env`

### Initial Deploy

- [ ] Push initial commit to `main` branch
- [ ] Verify GitHub Actions test workflow passes
- [ ] Manually trigger first deploy to Hostinger
- [ ] Verify `https://dhanradar.in/health` returns 200
- [ ] Verify Grafana accessible at `https://dhanradar.in:3001/grafana`
- [ ] Verify Uptime Kuma running

### Optional Day-1 Polish

- [ ] Set up Cloudflare email routing (`hello@dhanradar.in` forwards to your Gmail)
- [ ] Apply for SendGrid free tier
- [ ] Apply for Sentry free tier
- [ ] Apply for PostHog free tier
- [ ] Apply for Snyk open source plan
- [ ] Apply for Razorpay (allow 4-6 weeks)

---

## 10.13 Documentation Structure (Where Each Doc Lives)

```
docs/
├── architecture/
│   ├── v2.1-architecture.docx              # Original v2.1 (March 2026)
│   ├── v2.2-strategic-update.md            # Strategic alignment (May 2026)
│   └── v2.3-implementation-addendum.md     # This document
├── api/
│   ├── openapi.yaml                        # Auto-generated from FastAPI
│   └── developer-guide.md
├── ops/
│   ├── deployment.md
│   ├── runbook-incidents.md
│   ├── backup-restore.md
│   └── monitoring.md
└── compliance/
    ├── disclaimers/
    │   ├── ai-picks-v1.md
    │   ├── mf-research-v1.md
    │   └── mood-v1.md
    ├── audit-policy.md
    └── sebi-positioning.md
```

---

# Closing — v2.3 Summary

**v2.3 makes DhanRadar buildable on a side-project budget.**

| Metric | v2.2 | v2.3 |
|---|---|---|
| Monthly infrastructure | ₹10,944 | ₹1,090 |
| Containers | 19 | 12 |
| Break-even subscribers | 73 | 6 |
| AI provider | Anthropic direct | OpenRouter (free + spillover) |
| Hosting | Hetzner CPX21 | Hostinger KVM 2 |
| Domain | dhanradar.com | dhanradar.in |

**Strategic recommendations from v2.2 are unchanged.** Anonymous access, Mood Compass, Track Record, Portfolio Intelligence, the 18-week phased plan, and the Pro/Pro+ pricing strategy all remain in scope. v2.3 just makes them deliverable on minimal infrastructure.

**Critical Day-1 actions:**
1. Buy $10 OpenRouter credits (unlocks the entire free model strategy)
2. Provision Hostinger KVM 2 + dhanradar.in
3. Set up `E:\code\DhanRadar` linked to `github.com/manishjnv/dhanradar`
4. Install Claude Code on VPS as personal user only

**Year 1 target unchanged:** ~₹48L recurring ARR + ₹50L lifetime founder revenue at 98%+ gross margin.

---

DhanRadar v2.3 — Confidential | dhanradar.in | Development Ready  
*v2.2 strategic recommendations unchanged. v2.3 = implementation stack overlay.*  
Prepared by: Manish · github.com/manishjnv · May 2026
