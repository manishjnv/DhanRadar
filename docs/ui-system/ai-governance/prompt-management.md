# Prompt Management, Versioning, Testing & Approval

## Registry
`prompts(id, task, version, template, vars, model_constraints, status, author, approved_by, created_at)`
- status: draft | in_review | canary | live | retired. One **live** per (task).
- Templates are product logic — version-controlled, reviewed, **not** free-edit config.

## Composition (every call)
```
system prompt (role + guardrails: explain-not-advise, cite sources, admit uncertainty, no numbers-invention)
+ task template (versioned)
+ retrieved context (delimited, never executed as instructions)
+ user query
```
- Guardrails are **baked into every template** so the contract can't be forgotten per-feature.

## Versioning
- Semantic-ish (task@vN). Immutable once published. Each AI output records prompt_version → reproducible + auditable.

## Testing
- **Unit:** template renders with sample vars; guardrail lines present; token budget within cap.
- **Eval:** runs golden set (evaluation-framework) — groundedness, advice-boundary, hallucination, format.
- **Injection:** adversarial inputs (ignore-instructions, data-exfil) must not break guardrails.

## Approval workflow
```
author drafts → automated evals pass → PR review (AI Platform)
  → compliance sign-off (advice-boundary + disclosures)
  → research sign-off (factual correctness)
  → governance lead approve → canary → promote
```
- Approvals recorded (who/when) + audited. Emergency rollback needs no approval (revert to prior live).
