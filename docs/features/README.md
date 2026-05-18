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

- _none yet — Phase 1 delivered infra skeleton only; first module docs land with Phase 2+._
