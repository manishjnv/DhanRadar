# Review Ledger — First AI-gateway consumer: MF report portfolio commentary

- **Change ID:** `ai-consumer-mf-commentary`
- **Date:** 2026-06-07
- **Branch / PR:** `feat/ai-consumer` → `main`
- **Governance tier:** **B** (AI gateway / consent / compliance) **+ C** (commentary on a
  scored surface). Full inline review in-session (load-bearing path; not deferred to the
  phase audit).
- **Gates the consumer wires:** B20 (DPDP cross-border), B21 (`model_used` audit), B22
  (confidence floor), B23 (advisory screen), B26 (third audit seam).

## What landed

The governed OpenRouter gateway gains its first end-to-end consumer: a **portfolio-level
AI commentary** on the MF CAS→report pipeline. Commentary is **non-blocking** — any
refusal/failure omits it and the report still serves (architecture §MF line 257).

- **Gateway (B21 enabler):** `complete()` now returns `CompletionResult(output, model_used)`
  (frozen dataclass) instead of the bare schema instance, so callers can record the winning
  model. Behaviour is otherwise byte-for-byte unchanged (B20 deny-first, 429-rotate-no-sleep,
  402→`CreditExhaustedError`, 3-strike, budget increments, `AllFreeModelsFailedError`).
- **Consumer:** `dhanradar/mf/commentary.py` — `maybe_generate_commentary(...)`, called from
  `tasks/mf.py::_run_pipeline` after scoring, before report assembly. New
  `MfPortfolioCommentary(AIOutputBase)` schema (`summary` field). `PortfolioReport.commentary`
  (optional) carries it; `assemble_report` threads it through so the cached + served report
  surface it.

## Gate-by-gate

- **B20 — DPDP cross-border.** `assert_consent(user_id, "cross_border_ai", db)` is the FIRST
  gate; on `ConsentRequiredError` (or any DB error, via the outer catch) the path returns
  `None` — fail-closed, no payload reaches OpenRouter. `contains_personal_data=True` and
  `cross_border_consent_verified=True` are passed only after consent passes. The
  `OpenRouterGateway` client is lazy-constructed AFTER the gates, so an omitted path never
  opens a connection. **Data minimization:** `build_messages` uses a positive allowlist
  (`verb_label`/`confidence_band`/signals only); ISIN, scheme name, folio, units, and amounts
  never leave. `category_allocation` is category→pct aggregate (per `build_snapshot`), no
  fund identifiers.
- **B21 / B26 — audit.** `model_used` from `CompletionResult` is written via
  `record_served_label(surface="mf_report_ai", model=model_used, disclaimer_version,
  prompt_version="mf_commentary_v1", recommendation_type="educational_label")` — only on the
  served path. The audit write is wrapped so an audit-layer failure can never drop a clean,
  already-screened commentary (house posture: serve + alert-on-audit-failure).
- **B22 — confidence floor (non-neg #4).** Enforced at the AI layer twice: pre-call (no usable
  labels → `log_low_confidence` + omit) and post-call (`model confidence < 0.30`, NaN/inf-safe
  via `math.isfinite` → `log_low_confidence` + omit).
- **B23 — advisory screen.** Two independent nets: `quality.py` inside `complete()` (rejects
  the whole output), plus a defense-in-depth regex over the published `summary` in the
  consumer. Full domain-signed taxonomy remains tracked (B23, still OPEN).
- **SEBI labelling (non-neg #1/#9; architecture line 220/257).** The served commentary is
  SEBI-disclaimer-postfixed (`AI-generated insight, not investment advice`) so the label rides
  with the string itself, in addition to the report's disclosure bundle.

## Deterministic gates

- `pytest tests/unit` — **326 passed** (incl. 8 commentary unit tests + 2 new gateway
  `model_used` tests). Integration suite **collects clean** (96) — the CI backend job
  (Postgres) is the real run; do not merge over a pending/failed check (RCA 2026-06-07).
- `python scripts/ci_guards.py` — exit 0 (no non-negotiable / secret violations).
- `ruff --select I001,F401` clean on new files (repo does not gate `UP`/`Optional` style;
  house style retained).

## Reviews

- **Tier-B Security — ACCEPT.** Independent Sonnet adversarial pass (codex:rescue n/a — no
  Codex entitlement; approved Sonnet-takeover fallback). First pass: **REVISE**, 3 findings:
  (1) `category_allocation` had no shape assertion (defense-in-depth) → documented contract
  (verified aggregate, no live leak); (2) audit-or-nothing could drop a clean commentary if
  `record_served_label` raised → wrapped audit, still serves + test; (3) NaN confidence bypass
  of `< 0.30` → `math.isfinite` guard + test. Re-review verdict: **ACCEPT**, no regression on
  previously-clean vectors (B20 fail-closed, PII allowlist, B23 nets, served-only audit,
  total non-blocking catch, gateway semantics preserved).
- **Tier-C Compliance — ACCEPT.** Opus. SEBI educational boundary, no-numeric, confidence
  floor, DPDP cross-border, audit-tie-to-version all satisfied. One condition applied in
  session: the served commentary must be SEBI-disclaimer-postfixed per architecture line
  257/220 → done (`AI_DISCLAIMER` postfix + test).

### Conditions / follow-ups (non-blocking)

- **B23** advisory taxonomy is still a non-exhaustive core set pending domain sign-off — the
  consumer adds a second net but does not close B23.
- In production the commentary **refuses until `cross_border_ai` consent capture exists** (the
  Consent-module writer is a later slice) — the gate firing/refusing is the correct, tested
  behaviour, not a defect.
- **Mood Compass** commentary is the trivial fast-follow (its `generate_commentary` hook
  already exists; slots in with `contains_personal_data=False` once market-data signals land).

## Verdict

**Complete for merge** (deterministic gates green + Tier-B/C ACCEPT). **Merge-eligible, not
deploy-eligible** — KVM4 deploy stays gated on PC4/PC5 human approval + B36/B37/B38.
