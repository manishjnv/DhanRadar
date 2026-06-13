# Gate ledger — b27-canonical-signal-names

**Change:** Introduce a canonical signal-name registry for `LabelSignals.contributing` and
`contradicting` strings. New `backend/dhanradar/scoring/engine/signal_names.py` defines
`SignalName` (a `StrEnum` of 9 keys), `SIGNAL_DISPLAY` (key → compliance-approved phrase),
`CANONICAL_SIGNAL_PHRASES` (frozenset of the 9 approved phrases, for allow-list enforcement),
and a `display(name: SignalName) -> str` helper. All 9 producers that previously emitted
inline string literals — 7 in `mf/cohort.py` and 2 in `mf/signals.py` — now call
`display(SignalName.X)`. Phrase text is byte-identical to the prior literals; public API
(a `list[str]` field on `ScoringResult`) is structurally unchanged. No numeric, no label,
no confidence change. No database migration. The `CANONICAL_SIGNAL_PHRASES` frozenset
exists and is tested; runtime enforcement at the call site is a follow-on (noted as a
NIT, resolved via docstring softening — see Conditions). LLM commentary signals are a
separate field on `ScoringResult` and never enter the label-signal lists; verified by the
independent reviewer.

**Branch:** `fix/b27-canonical-signal-names` — PR #\<pending\>

**Classification:** Tier C — load-bearing scoring path (`scoring/engine/`). Required
reviews: Builder + Architect + Compliance + Product (independent agents; builder ≠
reviewer). No Security review required for this change (no auth/payment/AI/consent seam
touched).

## Deterministic gates

| Gate | Result |
|---|---|
| Backend unit tests (816) | PASS |
| `ci_guards` / anti-pattern grep | PASS |
| Alembic migrations job | PASS (no migration in this change) |
| `ruff` lint | PASS — clean |
| Frontend build / tsc | PASS — no FE changes |

All deterministic gates green before reviewer tokens were spent.

## Verdicts

| Review dimension | Agent | Verdict |
|---|---|---|
| Builder | Sonnet subagent (fix/b27-canonical-signal-names) | — |
| Architect + Compliance + Product (Tier C) | Sonnet subagent (independent; orchestrator = Fable, 2026-06-13) | ACCEPT |

## Independent review — evidence

Verification performed by the independent Sonnet subagent against the branch source:

- **Byte-identity verified.** All 9 `display(SignalName.X)` return values were confirmed
  byte-equal to the inline literals they replace; no phrase text was silently altered.
- **Completeness.** All 9 signal-phrase producers rewired: 7 in `mf/cohort.py`, 2 in
  `mf/signals.py`. No inline signal-phrase literals remain in the codebase outside the
  registry module itself.
- **No import cycle.** `signal_names.py` imports only stdlib (`enum`, `frozenset`); it
  does not import from `scoring.engine` internals, `mf`, `billing`, or any domain module.
  The `mf/*` callers import `signal_names` from `scoring.engine` — consistent with the
  architecture's inward-only coupling direction.
- **Behavior invariant.** `ScoringResult.contributing` / `contradicting` remain
  `list[str]`; serialization and the `to_public()` projection are unchanged. No test that
  previously passed would fail against the new code.
- **Test discipline.** The PR ships byte-exact pin tests (asserting each of the 9
  `display()` values is the precise approved phrase string) and producer-conformance tests
  (asserting every call site produces a value in `CANONICAL_SIGNAL_PHRASES`). These serve
  as the regression guard for future phrase changes.
- **LLM-separation finding.** LLM commentary signals live in a separate `ScoringResult`
  field (`ai_signals` / commentary output) and are never merged into the
  `contributing`/`contradicting` lists — verified by the reviewer against the
  `ScoringResult` schema. The registry governs only the rule-table label-signal strings,
  not AI-generated copy.
- **Allow-list not yet enforced at runtime.** `CANONICAL_SIGNAL_PHRASES` is built and
  tested but is not yet wired as a runtime guard at the call site. A future enforcement
  pass would raise on an unrecognised phrase before it reaches `ScoringResult`. Noted as
  a NIT; the docstring was softened (see Conditions) so it describes the frozenset as the
  reference set, not a currently-active runtime gate.

## Conditions applied before merge

One NIT from the independent review was applied in-branch before the ledger was closed:

- **NIT (applied):** The original module docstring described `CANONICAL_SIGNAL_PHRASES`
  as enforcing a runtime allow-list — this overstated the current behaviour (the frozenset
  is tested but not yet wired as a runtime guard). Docstring softened to describe it as
  the "compliance-approved reference set"; enforcement is marked as a follow-on. No logic
  change; tests unchanged.

## Accepted residuals

- **NIT residual — runtime enforcement (low):** `CANONICAL_SIGNAL_PHRASES` is not yet
  wired as a runtime reject guard at the call sites. A future follow-on would raise before
  an unrecognised phrase reaches `ScoringResult`, preventing phrase-drift without a
  registry update. Low priority — the byte-exact pin tests provide equivalent CI
  protection.

**Merge-eligible** — all deterministic gates green; Tier-C independent review ACCEPT;
NIT applied.

## Deploy record

Pending — human-gated; not yet deployed.
