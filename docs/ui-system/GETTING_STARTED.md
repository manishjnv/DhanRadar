# Getting Started (exact commands)

## 0. Prereqs
Node 20, Python 3.12, Docker, uv (`pip install uv`), npm.

## 1. Local infra
```
cd project-config
cp .env.example .env        # fill secrets (LLM key, Razorpay, JWT keys)
docker compose up -d        # postgres (auto-loads contracts/schema.sql), redis, elasticsearch
```

## 2. Seed data
```
# load contracts/seed-data.json via your seed script (instruments, scores, demo user)
psql "$DATABASE_URL" -f contracts/schema.sql   # if not auto-loaded
```

## 3. API (FastAPI)
```
cd api && uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

## 4. Web (Next.js)
```
cd web && npm ci
npm run gen:api            # generates src/types/api.ts from contracts/openapi.yaml
# copy tokens: cp ../tokens/css-variables.css src/styles/tokens.css
npm run dev                # http://localhost:3000
```

## 5. Verify
- API docs at /docs (FastAPI auto OpenAPI) match contracts/openapi.yaml
- Dashboard renders with seed instruments + scores
- Theme toggle (class on <html>) flips light/dark

## Build order
tokens → components/ui → backend(schema/auth/api) → data/AI → app screens → devops. Phase-1 MVP first (dashboard, stock detail, AI explain, search, alerts, auth, billing).
