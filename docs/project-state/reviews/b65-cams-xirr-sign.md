# Gate ledger — b65-cams-xirr-sign

**Change:** Normalize CAS transaction sign convention at the parse boundary so CAMS
portfolios (purchases printed POSITIVE by casparser) produce correct XIRR values.
Root cause: `parse_cas` in `backend/dhanradar/mf/cas.py` passed casparser's statement
convention straight through to `ParsedTxn`; `snapshot.xirr()` requires outflows
negative; all-purchase portfolios produced all-same-sign flows and tripped the
all-same-sign guard, returning `null`. Fix: per-type sign normalization
(`_TXN_INFLOW_AS_PRINTED = {DIVIDEND_PAYOUT}`; `_TXN_FLOW_EXCLUDED =
{DIVIDEND_REINVEST, SEGREGATION, STT_TAX, STAMP_DUTY_TAX, TDS_TAX, MISC, UNKNOWN}`;
everything else negated). Observability added: worker logs
`mf.snapshot.built {funds, cashflows, xirr_computed}` (boolean only — DPDP log
discipline). 7 regression tests including exact bug repro; fixtures migrated to
statement convention. RCA entry 2026-06-12 in `docs/rca/README.md`.

**Branch:** `fix/b65-cams-xirr-sign` — head `a5a6af7` at review time.
**PR:** #109 — squash-merged 2026-06-13 (IST), merge commit `412f126`.

**Classification:** Tier A — bug fix; `mf/cas.py` and `tasks/mf.py` are NOT on the
load-bearing path list. Required reviews: Builder + Architect (inline). No
Security/Compliance/UI reviewer required for this tier.

## Deterministic gates (pre-review, CI run 27420947600 on `a5a6af7`)

| Gate | Result |
|---|---|
| Backend unit tests (790) + integration | PASS |
| `ci_guards` / anti-pattern grep | PASS |
| Alembic migrations job | PASS |
| Frontend build | PASS |
| Lint (ruff) | FAIL — advisory only; none of the PR's three Python files appear among the 52 failing I001 locations (all pre-existing debt) |

Lint failure is pre-existing debt; it does not block merge on this repo.

## Verdicts (independent agents; builder ≠ reviewer)

| Review | Agent | Verdict |
|---|---|---|
| Builder | prior session 2026-06-12 (commit `a5a6af7`) | — |
| Architect | Sonnet subagent (orchestrator = Fable, 2026-06-13) | ACCEPT |

## Architect review — evidence

Verification performed by the independent Sonnet subagent against the live source
(three-dot merge-base diff):

- casparser 1.0.1 `TransactionType` enum names confirmed to match the fix's sets
  exactly — `DIVIDEND_REINVEST` (not `DIVIDEND_REINVESTMENT`) verified at
  `.venv/Lib/site-packages/casparser/enums.py:48`; all other routed names present.
- Sign directions correct per transaction type at portfolio level; `DIVIDEND_PAYOUT`
  kept as printed (cash credited to the investor) is semantically correct;
  `REVERSAL` pairs self-cancel after negation.
- CDSL path (`txns=[]`, `xirr=None` by design) is unaffected.
- Only consumer of `ParsedTxn.amount` downstream is `parsed_to_snapshot_holdings`
  (`tasks/mf.py:63`); no other call site is impacted.
- `_slog` is at module scope; no PII or amounts are logged — only counts and the
  boolean `xirr_computed` (DPDP log discipline).
- Lane clean: exactly the 5 expected files changed (`mf/cas.py`, `tasks/mf.py`,
  `tests/unit/test_mf_module.py`, `BLOCKERS.md`, `docs/rca/README.md`).
- The 7 new regression tests fail on the pre-fix code, confirming they exercise the
  actual defect.

**NITs (both accepted; neither blocks merge):**

1. Missing-type test comment could note that an explicit `type: None` value follows
   the same default-negate path as an absent key.
2. The negate-default is documented only in comments; unknown future
   `TransactionType` values are silently negated (the statement-convention-correct
   default). Undetectable from tests alone; covered by the drift residual below.

## Conditions applied before merge

None. ACCEPT with no BLOCKERs or MAJORs. The reviewer's sole condition — that the
casparser-drift residual be logged in BLOCKERS.md — was already satisfied inside
the PR itself (B65 row, final sentence).

## Accepted residuals (logged, not fixed)

- **NIT-1:** test comment precision — low-value prose change; accepted.
- **NIT-2 / B65 residual (LOW):** no CI sentinel against upstream casparser
  sign-convention drift. A known-good PDF fixture or a version-pin guard would
  close it. Logged in the B65 BLOCKERS row; not merge-blocking.

**Merge-eligible** — all deterministic gates green (lint advisory and pre-existing);
Architect ACCEPT. Operator instruction 2026-06-13 ("complete b65") authorized
completion in-session; merge + deploy executed under it.

## Deploy record

Deployed 2026-06-13 (IST) to KVM4 via `scripts/deploy.sh deploy`.

- Box state verified before deploy: `3fae69b`, clean tree, all containers healthy;
  no concurrent deploy in flight.
- Result: app containers recreated; `fastapi` + `nextjs` healthy.
- Smoke: `GET /api/v1/health` → 200.
- Box now at `412f126`; `alembic_version` remains `0018` (no migration in this
  change).
- Fix grep-verified inside the deployed `celery-batch` image: `_TXN_FLOW_EXCLUDED`
  present.

**Open after deploy:** founder live-proof pending — re-upload the CAMS CAS PDF and
confirm `xirr_pct` non-null. The worker log line
`mf.snapshot.built … xirr_computed=true` is the confirmation signal.
