# ⚠️ Original-package architecture docs — REFERENCE ONLY, do not follow

These files (`01-product-strategy` … `07-figma-structure-and-handoff`, plus `FINAL_AUDIT.md`,
`GAP_CLOSURE.md`, `VALIDATION_REPORT.md`) are the **original UI package's** own architecture
write-ups. The package is **harvest-not-adopt**: it describes a **different stack, auth model, API
shape, and data model** than the real DhanRadar and is internally self-contradictory.

**Do not build from these.** They conflict with the project on, at minimum: Elasticsearch (real:
Postgres FTS), bearer/Authorization-header auth (real: `__Host-` cookie RS256 JWT), bare `/v1`
paths (real: `/api/v1`), advisory `buy/sell/hold` framing (real: educational labels only), flat
`public` schema (real: schema-per-concern), and Manrope/cool tokens (real: Geist/warm).

## Canonical sources of truth instead

- **Architecture / module contracts:** `../../DhanRadar_Architecture_Final.md`
- **Phase sequence / allowed APIs / anti-patterns:** `../../DhanRadar_Implementation_Plan.md`
- **API contract:** `../../project-state/CANONICAL_OPENAPI_ALIGNMENT.md`
- **Design system:** `../../project-state/CANONICAL_DESIGN_SYSTEM_ALIGNMENT.md` + live `frontend/` tokens
- **What to KEEP/MERGE/REPLACE/IGNORE from this package:** `../../project-state/MIGRATION_STRATEGY_FINAL.md`

Mine these only for harvest value (compliance frameworks, analytics taxonomies, scoring numbers)
already classified in `MIGRATION_STRATEGY_FINAL.md` — never as build instructions.
