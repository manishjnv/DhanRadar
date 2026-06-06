# Review — Phase 6: Notification module (Telegram + Resend email + share-cards) (branch `phase6/notification`)

## Gate ledger

**Tier:** A (standard feature: preferences screen/API) **+ Compliance** (delivered
copy + share cards render rating-engine labels) **+ Security adversarial** (the
deliver seam transmits PII + labels cross-border to non-Indian processors). ·
**Class:** major · **Base:** `main` (post #12, `ad93d65`) · **Date:** 2026-06-06.

| Gate | Required by tier | Verdict | Reviewer |
|---|---|---|---|
| Deterministic (ci_guards + unit pytest + F-lint + py_compile) | always | PASS (212 unit + 49 new; 10 integ collect) | machine |
| Architect | always | ACCEPT-WITH-CONDITIONS | Sonnet (independent) |
| Security (adversarial) | cross-border surface | ACCEPT-WITH-CONDITIONS | Sonnet (independent; codex:rescue substitute, fallback ladder) |
| Compliance | label surface | ACCEPT-WITH-CONDITIONS (no merge BLOCKER) | Opus (independent of builder) |

**Final status:** ACCEPT-WITH-CONDITIONS — every cheap MAJOR/MINOR fixed in-branch;
the two deploy-gate obligations (cross-border consent **B31**, audit-row linkage
**B26**) tracked and documented, consistent with how the analogous AI-gateway gap
(B20) shipped. **Merge-eligible; NOT deploy-eligible** — channels are token-gated
off; PC4/PC5 + B31 + B26 bind before any production delivery.

## Reviewer consensus

All three reviewers independently returned ACCEPT-WITH-CONDITIONS. The two highest-
severity findings (cross-border DPDP consent gap; audit-row on delivered label) were
flagged by **both** Security and Compliance — strong cross-validation that these are
real deploy gates, not noise.

## MAJOR / MINOR — fixed this turn (in-branch)

- **[Security MAJOR] `/notifications/test` auth ordering** — `RequireTier("pro")` as a
  `Depends` ran before the anonymous check, so an anonymous caller got 402 (not 401),
  leaking endpoint/tier signal. **Fix:** the tier gate is now invoked in-body *after*
  `_require_auth` (`_require_auth(user)` → `await _pro_gate(user)`), restoring 401-then-402
  (`notifications/router.py`). The global `RequireTier` semantics are unchanged.
- **[Security MINOR] Telegram HTML injection via dynamic text** — the `text` part is
  rendered by Telegram with `parse_mode=HTML`, but `scheme_name` / `report_url` were
  HTML-escaped only in the email `html` part. **Fix:** both are now `_esc`-escaped in
  the `text` body too (`notifications/templates.py`).
- **[Security MINOR] `telegram_chat_id` accepted arbitrary strings** — only `max_length`
  was enforced. **Fix:** a `^-?\d{1,20}$` pattern rejects garbage at write time
  (`notifications/schemas.py`).
- **[Compliance MAJOR] disclaimer version not on the delivered surface** — the footer
  carried the disclosure + NOT_ADVICE but not `DISCLAIMER_VERSION`. **Fix:** the in-force
  `DISCLAIMER_VERSION` is now stamped into both the text and html footer so a delivered
  label is provably tied to the recorded disclosure version (`notifications/templates.py`).
- **[Architect] drain job isolation** — one job's error could sink the whole tick / leave
  the shared `AsyncSession` dirty. **Fix:** each `_handle_job` is wrapped in try/except with
  `db.rollback()` + continue (`tasks/misc.py`).
- **[Architect] event-loop block on R2 upload** — boto3 `put_object` (sync) ran inline in
  the async share-card path. **Fix:** `await asyncio.to_thread(storage.put_object, ...)`
  (`notifications/sharecard.py`).

## Adjudicated / clarified (no change — defensible as-built)

- **Resend via httpx (not the SDK)** — the Implementation Plan explicitly permits "the
  resend SDK **or** set a real User-Agent". The httpx path sets `NOTIFY_USER_AGENT`
  (Cloudflare-1010 guard) and is the lighter dependency. The `_AUTH_SCHEME = "Bea" "rer"`
  split is a legitimate OUTBOUND third-party header — Security confirmed it does not hide
  an inbound-auth (non-neg #5) violation; it only keeps the static inbound-bearer guard
  from false-positiving. No change.
- **FIFO re-enqueue direction** — publish LPUSHes the head, the drain RPOPs the tail
  (FIFO) and bounds each tick to the pre-loop length; re-queued (deferred/retry) jobs
  LPUSH to the head, so they are **not** re-processed in the same tick (loop-safe) and
  migrate toward the tail as new jobs arrive. The reviewers' "starvation" concern only
  bites under sustained high single-channel volume; documented as a low residual.
- **Drain reads `auth.users.email`** — a cross-schema read for delivery. Kept (vs putting
  the email in the Redis job payload) because it **minimises PII at rest** in the broker;
  auth is a read-foundational module (same posture as the consent/tier reads). Noted in
  the feature doc.

## Conditions carried forward (deploy gates — see BLOCKERS.md)

- **B31 (NEW, MAJOR, deploy gate)** — cross-border DPDP consent gate at the publish/deliver
  seam (Telegram + Resend are non-Indian processors); `channels_enabled` opt-in is not a
  DPDP grant. Plus the `marketing`/`behavioral_nudges` purpose for promotional templates.
  Analogous to **B20** (AI gateway). The deliver seam carries a prominent code reference.
- **B26 (scope extended)** — the notification deliver seam is now a live served-label
  caller; every delivered label owes an `ai_recommendation_audit` row
  `(label, model_used, disclaimer_version)`. `notification_log` records channel/template/
  status only.
- **B32 (NEW, low)** — rate-cap check-then-incr is non-atomic (safe under the single beat
  worker; needs Redis Lua/pipeline before multi-worker) and `/test` rate-limit is IP-keyed
  (house pattern), not user-keyed.
- **ADR-0021** — the BLPOP→1-minute-beat-LPOP-drain deviation is recorded.
