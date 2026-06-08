# Review Ledger — Plus Label-Change Alerts

- **Change-id:** `plus-label-change-alerts`
- **Branch:** `hardening/launch-gate-blockers`
- **Date:** 2026-06-08
- **Tier:** B (rides the load-bearing Notification deliver seam — B31 cross-border consent +
  B26 compliance audit) — full inline review this session.
- **Build sequence:** the last remaining Plus tracking feature. With this, the Plus feature set
  (AI commentary · history · auto re-score · multi-portfolio · alerts) is COMPLETE.

## What existed vs. what was added

- **Existed:** the Notification deliver seam (`tasks/misc.py` `_handle_job`) already enforces B31
  (`cross_border_notify` consent, fail-closed drop), quiet-hours, per-channel rate caps, and the
  B26 `record_served_label` audit; `mf_label_change` was already wired into `_LABEL_TEMPLATES`; the
  `_t_mf_label_change` template + `publish_notification` enqueue interface existed. The monthly
  re-score (`_monthly_rescore`) was per-portfolio (multi-portfolio, `cef5345`).
- **Added (the diff-and-notify gap only):**
  - `mf/history.py`: `get_prior_label(db, portfolio_id, isin, before_date)` (most recent label
    before a date, portfolio-scoped); `append_score_history` now returns `inserted: bool`
    (rowcount==1) as the idempotency signal.
  - `notifications/templates.py`: `_t_mf_label_change` now names the portfolio in the copy
    (`portfolio_name`, **escaped** via `_esc` in both text + html); label words also `_esc`'d in
    html (defence-in-depth).
  - `tasks/mf.py` `_monthly_rescore`: per holding, read the prior label, and **only when**
    `inserted ∧ prior≠None ∧ prior≠new` enqueue `mf_label_change` (both channels, best-effort) via
    `publish_notification` — riding the existing deliver seam. The payload carries
    `new_label`/`isin`/`confidence_band` (B26 audit) + `scheme_name`/`portfolio_name`/`prior_label`
    (copy) + `disclaimer_version` (generation-time, B26 tie).

The deliver seam (`tasks/misc.py`) is **unchanged** — B31, quiet-hours, rate-cap, B26 all apply
automatically. No parallel notification path.

## Deterministic gates

- `ruff` clean on all changed files. `anti_pattern_sweep` + `ci_guards` (advisory scan over the new
  template copy + secrets) passed. Full unit suite **511 passed** (the 2 `test_market_data`
  failures are the known pre-existing network/DNS ones; +1 harmless multi-portfolio xfail
  placeholder). 19 new alert tests.

## Acceptance proof

| # | Item | Proof |
|---|------|-------|
| 1 | changed label → alert; unchanged → none | `test_alert_enqueued_when_label_changes` (both channels) / `test_no_alert_when_label_unchanged` / `_no_prior` / `_not_inserted` (idempotency) |
| 2 | Plus-gated — Free gets no alert | `test_free_user_no_alert` (is_plus=False → loop continues before scoring) |
| 3 | portfolio-scoped (names the portfolio) | `test_mf_label_change_contains_portfolio_name` + `get_prior_label` portfolio_id filter |
| 4 | rides B31 (no consent → dropped, fail-closed) | `test_b31_consent_gate_drops_job` (transport NOT called; `cross_border_consent_required` logged) |
| 5 | factual/educational, no advisory verb, no numeric | `test_mf_label_change_no_advisory_verbs` / `_no_numeric_score` / `_disclosure_footer_present` |
| 6 | B26 audit at deliver (label + in-force disclaimer_version) | `test_b26_record_served_label_on_delivery` (label==new_label, surface, identifier) |
| + | injection-safe (escaped portfolio/scheme) | `test_mf_label_change_html_injection_portfolio_name` / `_scheme_name` |

## Security review (adversarial — Sonnet takeover)

`codex:rescue` **n/a** — codex companion unhealthy (ChatGPT-account entitlement). Independent
Sonnet adversarial pass per the approved fallback ladder. **Verdict: ACCEPT-WITH-CONDITIONS** (no
blockers). Adjudication:

- **Consent bypass (B31), numeric/PII leak, idempotency, audit completeness, isolation, fail-open —
  PASS.** The alert only calls `publish_notification` (no parallel path); `priority` defaults to
  `normal` and even `high` would only skip quiet-hours, not the step-1b consent gate; the `inserted`
  guard makes same-day re-runs and concurrent beats safe (atomic `ON CONFLICT`); the payload carries
  the three keys B26 needs; the enqueue is try/except best-effort and writes no notification table.
- **Should-fix — `disclaimer_version` not stamped at enqueue:** **APPLIED.** The payload now carries
  `DISCLAIMER_VERSION` (generation-time), so the B26 audit ties to what was in force when the label
  was generated — not the live constant at drain time (matches the documented deliver-seam intent
  and how the MF report/commentary stamp it).
- **Should-fix — `_esc` the label words in html:** **APPLIED** (defence-in-depth; `LABEL_DISPLAY` is
  ASCII today but escaping future-proofs a localised label).
- **Nit — pre-filter channels by user prefs:** **DECLINED** — enqueue-both-let-deliver-filter is the
  established pattern (the deliver seam's step-1 opt-in drops the disabled channel + rate caps bound
  it); pre-filtering would pull a notify-prefs read into the MF re-score (isolation smell) for a
  cosmetic gain.
- **Nit — `_esc` docstring:** **APPLIED** (now mentions user-named portfolios).

## Compliance review (Opus)

**Verdict: ACCEPT.** Non-neg #1 (factual educational copy — "moved from <old> to <new> … not an
action to take"; no advisory verbs; ci_guards advisory scan green), #2 (label + band word only; no
numeric in the message; the payload `disclaimer_version` is a date string used for audit, never
rendered), #9 (disclosure bundle + `NOT_ADVICE` ride via `render()`; the B26 audit row carries the
generation-time disclaimer version), module isolation (enqueue via the interface; no cross-module
table writes; no engine recompute), and B31 (consent rides automatically, no bypass) all hold.

## Status

Merge-eligible (Tier-B inline ACCEPT / ACCEPT-WITH-CONDITIONS, conditions applied). NOT
deploy-eligible until the Phase-7 §5 pre-deploy gate + **B31/B48 consent re-enforce** (alerts are
inert-but-safe until users can grant `cross_border_notify`) + separate human approval.
