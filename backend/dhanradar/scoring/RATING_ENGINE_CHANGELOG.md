# Rating-Engine Changelog (seed)

File-based seed of the `rating_engine_changelog` (the DB table is created with the
scoring engine in Implementation-Plan Phase 4). Every methodology change appends
an entry here until the table exists. Source of truth for the spec:
`docs/project-state/FINAL_SCORING_SPEC.md`.

---

## v1 — initial proposal (DRAFT, NOT ACTIVATED)

- **model_version:** `v1`
- **status:** `draft` · **activated:** `false`
- **created_by:** architecture-review
- **approved_by:** _null_ — **two-person methodology gate pending** (`approved_by ≠ created_by`, BLOCKERS B6)
- **date:** 2026-06-05
- **factors_before:** _none_ (first version)
- **factors_after:** quality 0.24 · valuation 0.22 · momentum 0.20 · **trend 0.22** · risk 0.12 (Σ = 1.00 ± 0.001)
- **methodology_url:** <https://dhanradar.com/methodology>
- **config:** `ranking_configs_v1.json`

**Gating before activation (all required):**

1. Backtest pass-gates (`FINAL_SCORING_SPEC.md` §8): monotonic bucket spread over ≥3 windows; positive/stable IC; no single-axis alpha; turnover in bounds.
2. Calibration reliability-curve within ±10% (releases the confidence-% exposure gate).
3. Two-person methodology approval (`approved_by ≠ created_by`).

**Notes:**

- REC-D1 applied: 5-axis kept with **Trend** (Growth nested as Trend sub-factors); `earnings_revision` + `relative_strength` moved Momentum→Trend (single-axis, no double-count).
- Numeric weights are **PROPOSED** — canonical as a starting point, not frozen until the gates above pass.
- This step (Stage 2 Step 8) stages configuration only. No engine code, no DB migration, no scoring execution.

---

## v1 engine implementation (Phase 4) — 2026-06-06

- The deterministic engine that CONSUMES `ranking_configs_v1.json` is now built
  (`backend/dhanradar/scoring/engine/`). **No methodology/weight change** — weights
  remain the PROPOSED v1 above; `activated:false` stands. Label is rule-table-derived
  (not the score); confidence floor → `insufficient_data`; 2-eval hysteresis; churn>5%
  → Compliance hold; `make_changelog_entry(enforce_two_person=True)` enforces the B6 gate
  at activation. Feature doc: `docs/features/rating-scoring-engine.md`.
- Activation still gated by the three pass-gates above (backtest, calibration, two-person).
