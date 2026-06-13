# Review ledger — B66-f1 part 2: MF cohort rewire to `sebi_category`

Change-id: `b66f1-pt2-cohort-sebi-rewire` · Branch: `feat/b66f1-cohort-sebi-category`
Tier: **C** (scoring / recommendation methodology) · Date: 2026-06-13

## What changed

Repoints the MF peer-cohort **grouping key** from the raw `mf_funds.category` string
to the validated canonical `mf_funds.sebi_category` (B66 taxonomy), behind a
**versioned, OFF-BY-DEFAULT** switch.

- `backend/dhanradar/tasks/mf.py` — `_COHORT_GROUPING_KEY = "category"` (active),
  `_grouping_column()`, and a `grouping_key` param on `_build_cohort_context` /
  `_compute_cohort`. The two cohort column reads now use the resolved column.
- `backend/dhanradar/scoring/ranking_configs_v1.json` — `labels.cohort_grouping_key`
  mirror (lockstep-tested).
- `backend/tests/unit/test_mf_cohort.py` — 5 tests (dormant-default guard, column
  resolver, sebi-grouping + NULL fail-safe, lockstep).
- `backend/alembic/versions/0022_mf_funds_cohort_key_indexes.py` — btree indexes on
  `category` (closes B58-f3) and `sebi_category`.

**Merging is a behavioural no-op**: the default key stays `"category"`. Flipping to
`"sebi_category"` shifts live labels and is an **un-activated methodology delta**
until a new `ranking_configs` version clears the two-person gate (B6/B28) + explicit
prod activation.

NULL fail-safe (when activated): funds with `sebi_category` NULL (pre-2017 legacy
umbrellas Income/Growth/Gilt) are excluded by SQL `IN` + the `if c` target filter →
uncohorted → `on_track`. Never auto-mapped. Raw `category` is never mutated.

## Deterministic gates (all green)

- pytest: 942 unit passed + 1 xfailed; `test_mf_cohort.py` + `test_mf_taxonomy.py`
  120 passed. New cohort tests pass.
- ruff: clean on all changed Python files.
- ci_guards.py: exit 0 (no non-negotiable violations; secrets scan clean).
- ci_guards meta-tests: 7 passed.
- Migration: single linear head `0021 → 0022`; `sebi_category` created in-chain (0004);
  index-only, reversible.

## Backtest (read-only, LIVE prod data 2026-06-13, 14,041 funds)

Faithful: the published fund label is today a pure function of the cohort output
(`manager_change` / `structural_concern` have no data writer; `insufficient_data` is
invariant under the rewire — coverage untouched, `nav_points < 4` short-circuits).

- **196 funds (1.40%)** change final published label.
  off_track→on_track 131 · on_track→off_track 41 · in_form→on_track 17 ·
  on_track→in_form 5 · off_track→in_form 2.
- Distribution delta: on_track **+102**, off_track **−92**, in_form **−10**,
  insufficient_data **+0**.
- Concentrated in two clusters:
  - **Income umbrella dissolved (113 flips)** — a 4,618-fund heterogeneous pseudo-cohort
    (FMPs + debt of all durations) that BEFORE produced a category-relative benchmark;
    AFTER those funds are sebi NULL → uncohorted → on_track.
  - **ELSS cohort completed (83 flips)** — 80 previously mis-tagged bare-"ELSS" funds
    join the canonical 200-fund ELSS cohort, raising the median (1Y −4.20→−2.59,
    3Y 32.10→38.48). **57 are SECOND-ORDER**: clean ELSS funds whose own key did not
    change but whose label flipped because the median moved (41 on_track→off_track).
- Malformed→canonical relocations: 426 funds across 3 variants (309 double-space
  "Other  ETFs", 80 bare "ELSS", 37 curly-apostrophe "Children's Fund").

## Review verdicts (independent agents)

### Architect / Adversarial methodology — VERDICT: ACCEPT

All 5 checks PASS: margin band resolves correctly for every canonical leaf;
`build_benchmark` groups by exact leaf equality (no class mixing); NULL-safe incl.
empty-string (`canonical_for` cannot emit `""`, and `if c` drops it); no silent
activation (both live call sites use the default; lockstep test fails on any
constant↔JSON divergence); migration CI-safe and reversible; backtest model faithful
to the pipeline. No code change required.

### Compliance — VERDICT: ACCEPT-WITH-CONDITIONS

No SEBI-boundary violation in the diff (label enum unchanged, no advisory verb, no
numeric in DOM). Conditions are **pre-activation, not pre-merge**:

- **C1 (blocks activation):** NULL-`sebi_category` funds reach `compare_to_cohort(own,
  None)` → bare `CategoryRelative()` → `on_track` with an EMPTY context pane. `on_track`
  = "matching category, no red flags", but no comparison was made. Add a distinguishing
  context signal (reuse `COHORT_THIN_BENCHMARK` or a new `COHORT_NO_CANONICAL_CATEGORY`)
  so the label reads honest-not-positive. Signal-string addition is itself Tier-C
  compliance-reviewed.
- **C2 (pre-activation gate):** activation PR must bump `ranking_configs` to a new
  version (v1.2), increment `DISCLAIMER_VERSION`, update the methodology page, and clear
  the two-person gate (`approved_by ≠ created_by`).

### Product — VERDICT: ACCEPT-WITH-CONDITIONS

Converges with Compliance on the NULL-context finding. Conditions (pre-activation):

- **P1 (= Compliance C1):** surface a "category benchmark unavailable — pre-2017 AMFI
  category not mapped to SEBI taxonomy" signal for NULL-sebi funds instead of a silent
  `on_track`. (Filed B71.)
- **P2 (B58-f5 extension):** label-glossary footnote for cohort-recalibration-driven
  flips (the 41 peer-driven ELSS on_track→off_track), tied to the monthly-rescore alert
  copy so a peer-set change is not read as "your fund got worse".
- **P3 (pre-activation gate):** proactive user notice before the first post-activation
  rescore ("we updated how peer groups are formed — some labels may change").

## Eligibility

- **MERGE-ELIGIBLE** as WIP: the dormant (off-by-default) code is ACCEPTED by all three
  reviewers; deterministic gates green.
- **NOT activation-eligible.** Activation is blocked on the pre-activation checklist:
  B71 (NULL-context signal, Compliance C1 / Product P1) · B58-f5 extension (P2) ·
  user comms (P3) · ranking_configs v1.2 + `DISCLAIMER_VERSION` bump + two-person gate
  (C2) · separate explicit human + founder approval.
