# DhanRadar — Feature Documentation

Every module has its own feature document here, named `docs/features/<module>.md`. It is created when the module is first built and updated whenever the module changes. This is a standing rule: a phase or change is not "done" until the affected module's feature doc reflects reality. The template mirrors the per-module appendix shape in `DhanRadar_Architecture_Final.md` so the spec and the as-built doc stay aligned.

## Module feature-doc template (copy to `docs/features/<module>.md`)

```
# Feature — <Module Name>

**Status:** built | partial | planned     **Phase:** <which phase delivered it>
**Last updated:** YYYY-MM-DD

## Purpose & scope
Plain-language description of what this module does and the user/value it serves.

## Non-goals
What this module deliberately does not do (including the SEBI educational boundary where relevant).

## Public interface (the only coupling surface)
REST endpoints (method + path + purpose) and events emitted/consumed. Other modules
depend only on what is listed here.

## Data
Postgres tables (key columns), Redis keys + TTLs, any TimescaleDB/partitioning.

## Pipeline / behaviour
Numbered flow with triggers, schedules (Celery beat times), and the cache-invalidation
rules. How it actually works, step by step.

## Config & flags
Env vars, feature flags, model/prompt versions, tunables.

## Failure modes & fallbacks
What breaks, what the fallback is, what is logged/alerted.

## Dependencies
Which modules/services it consumes (by interface), and build-vs-partner stance.

## Verification
How to prove this module works end-to-end (commands, tests, MCP/curl checks).

## Changelog
- YYYY-MM-DD — what changed and why (link the RCA entry if a bug fix).
```

## Index of module docs

(Add a line here as each module doc is created.)

- [auth.md](auth.md) — Auth & Tiering (Phase 2): RS256 JWT `__Host-` cookies, refresh rotation, tier gates.
- [market-data-adapter.md](market-data-adapter.md) — Market Data Adapter (Phase 3): provider interface + circuit breaker.
- [ai-gateway.md](ai-gateway.md) — AI/LLM Gateway (Phase 3): governed OpenRouter gateway + budget + advisory screen.
- [rating-scoring-engine.md](rating-scoring-engine.md) — Rating/Scoring Engine v1 (Phase 4): rule-table labels, no-numeric boundary.
- [mutual-fund.md](mutual-fund.md) — Mutual Fund module (Phase 5): CAS → ≤60s labelled report.
- [notification.md](notification.md) — Notification module (Phase 6): Telegram + Resend email + share-cards, quiet-hours + rate caps.
- [compliance-audit.md](compliance-audit.md) — Compliance Audit module (B26): 7-yr `ai_recommendation_audit` + disclaimer registry + served-label writes + R2 archival.
