# Feature — Notification module

**Status:** built (backend + FE preferences screen) · **Phase:** Phase 6
**Last updated:** 2026-06-06

## Purpose & scope

All outbound delivery for DhanRadar: Telegram (Bot API) and email (Resend) at
launch, plus the Pillow 1200×630 share-card PNG service. It is **delivery-only** —
it generates no content. Domains (Alert/Digest, Mood Compass, Behavioral Nudge,
Gamification, MF) publish a structured job; this module renders a fixed template,
enforces quiet-hours + per-channel rate caps, delivers, logs, and retries transient
failures. It exists so every domain need not re-implement channel handling,
quiet-hours, or rate limiting.

## Non-goals

- No content generation (templates render a label + disclosure; the label/score is
  computed by the Rating Engine, never here).
- No WhatsApp at P1 (Y2; a `whatsapp_number` pref can be stored but is not delivered).
- No mobile push; no creator revenue-share.
- **No advisory vocabulary** (buy/sell/hold/switch/avoid/caution) and **no numeric
  score / weight / fair value** in any delivered message or card (non-neg #1/#2).
- Not SendGrid — email is Resend only (non-neg #8).

## Public interface (the only coupling surface)

REST (all under `/api/v1`):

- `GET  /notifications/preferences` (authed) — read channel addresses, quiet-hours,
  opt-in map. 401 if anonymous.
- `POST /notifications/preferences` (authed) — partial update; only the keys the
  client sends are written (`extra="forbid"`). 401 if anonymous; 422 on a bad
  `quiet_hours`/`telegram_chat_id`.
- `POST /notifications/test` (authed, **Pro**) — enqueue a `test_ping` to a channel.
  401 (anonymous) → 402 (below Pro) → 400 (`telegram_not_set`) → 200.

Programmatic (consumed by other domains):

- `await service.publish_notification(redis, user_id, channel, template_id, data, priority)`
  — LPUSH a job onto `notifications:queue:{channel}` (architecture §5 interface).
- `await sharecard.generate_share_card(template, data, redis=None) -> url`.

Events: consumes domain events (Alert/Mood/Nudge/Gamification) by being handed a
publish call; emits none.

## Data

Postgres schema `notify` (schema-per-concern, non-neg #7; Alembic `0005`):

- `notification_preferences` — PK `user_id` (FK `auth.users.id` CASCADE),
  `telegram_chat_id`, `email_verified`, `whatsapp_number`, `quiet_hours_start/end`
  (`TIME`, IST), `channels_enabled` (JSONB opt-in map), `updated_at`.
- `notification_log` — append-only delivery audit: `id`, `user_id`, `channel`,
  `template_id`, `status` (`sent|failed|rate_capped`), `error_text` (OPAQUE code
  only — never a raw provider body/PII), `created_at`.

Redis:

- `notifications:queue:{telegram,email}` — delivery lists, **no TTL** (a worker-down
  window must not lose jobs). Publish = LPUSH (head); drain = RPOP (tail) = FIFO.
- `notif:rate:{user}:{channel}:{YYYY-MM-DD}` — daily counter, 86400 s TTL. Caps:
  **3 Telegram/day, 1 email/day**.
- `notif:share_card:{template}:{hash}` — cached share-card URL, 3600 s.

## Pipeline / behaviour

1. A domain calls `publish_notification(...)` → a `NotificationJob` is LPUSH'd onto
   the channel queue.
2. `dhanradar.tasks.misc.drain_notifications` (Celery beat, **every minute**, misc
   queue) drains each channel with a bounded RPOP loop (per-tick cap 100). For each
   job (`_handle_job`, isolated in try/except so one failure can't sink the tick):
   1. **Opt-in gate** — `channels_enabled[channel]` must be true (fail-closed).
   2. **Quiet hours** — a `normal`-priority job inside the user's IST window is
      re-queued (LPUSH head; loop-safe — not re-processed this tick); `high` bypasses.
   3. **Rate cap** — over the daily channel cap → logged `rate_capped`, dropped.
   4. **Render** — `templates.render(template_id, data)`; an unknown template is
      logged `failed`/`unknown_template` and delivered to no one.
   5. **Deliver** — Telegram `sendMessage` (parse_mode HTML) or Resend `POST /emails`
      (email requires `email_verified` + the user's `auth.users.email`).
   6. **Outcome** — success → increment the rate counter + log `sent`; transient
      failure → re-queue with `attempts+1` up to the channel retry cap (Telegram 3);
      permanent (or retries exhausted) → log `failed` (+ email bounce flips
      `email_verified=false`).
3. Share cards: `generate_share_card` renders a 1200×630 PNG (Pillow, lazy import) →
   uploads to R2 (`await asyncio.to_thread`, boto3 is sync) → returns a public URL
   (mood/badge/fund_label templates, if `R2_PUBLIC_BASE_URL` set) or a presigned URL
   (private/portfolio). The disclosure + NOT_ADVICE is drawn on every card, including
   the fallback path.

Beat: `notify-drain` = `crontab(minute="*")` (see `celery_app.py`).

## Config & flags

`config.py`: `TELEGRAM_BOT_TOKEN` (empty ⇒ Telegram delivery **disabled**, fail-closed),
`TELEGRAM_API_BASE`, `TELEGRAM_PUBLIC_CHANNEL_ID` (daily Mood card, deferred),
`RESEND_API_KEY` (empty ⇒ email disabled), `RESEND_API_BASE`, `EMAIL_FROM`
(`noreply@dhanradar.com`), `NOTIFY_USER_AGENT` (Cloudflare-1010 guard),
`R2_PUBLIC_BASE_URL`. New dep: `Pillow` (lazily imported).

## Failure modes & fallbacks

- Telegram fail → up to 3 transient retries then `failed` (stale alerts have negative
  value); permanent 4xx drops immediately.
- Resend bounce (permanent) → `email_verified=false` (re-verify required) + log.
- `api.resend.com` is behind Cloudflare and 403s the default urllib UA (error 1010);
  the client always sends `NOTIFY_USER_AGENT`.
- Missing token/key → delivery fails **closed** (no call, logged), never crashes.
- Pillow draw error → fallback static card (still disclosed); Pillow absent →
  `ShareCardError("pillow_unavailable")`.
- Worker down → queues persist (no TTL); quiet-hours re-checked at delivery time.
- Malformed queued job → dropped with a warning, does not sink the tick.

## Dependencies

Consumes (by interface): `scoring.engine.schemas` (DISCLOSURE_BUNDLE / NOT_ADVICE /
DISCLAIMER_VERSION / label enums), `auth.users` (read-only: email for delivery, tier
for `/test` — PII read at delivery time minimises PII at rest in the broker),
`storage` (R2), Redis, Celery. Build-vs-partner: Telegram/Resend/Pillow = build/free;
WhatsApp = partner (Y2).

## Verification

- `python -m pytest tests/unit/test_notifications.py` — 49 unit tests (templates
  disclosure/no-advisory/no-numeric, quiet-hours table, rate caps, publish, channel
  classify + delivery, share-card URL selection + PNG magic).
- `tests/integration/test_notifications.py` — 10 tests (preferences round-trip,
  422/401/402/400 gates, `/test` enqueue, **drain end-to-end** delivers with the
  disclosure, **quiet-hours defers**). Runs in CI (needs PG); collects locally.
- `python scripts/ci_guards.py` — confirms no advisory verb in any delivered template
  (the guard scans all backend `.py/.json`).
- Manual (post-deploy, gated): set `TELEGRAM_BOT_TOKEN`, `POST /notifications/test`
  → message lands in the test chat with the disclosure footer; Resend send returns
  2xx; a share card lands in R2 with a working URL.

## Compliance & DPDP posture (read before go-live)

- Every delivered template + share card carries the disclosure bundle + NOT_ADVICE +
  the in-force `DISCLAIMER_VERSION`, injected structurally so a new template cannot
  omit it. Labels are action-free educational form words only.
- ~~**B31 (deploy gate):**~~ **RESOLVED** — the deliver seam sends PII + labels to
  **non-Indian** processors (Telegram, Resend/Tokyo), and a `channels_enabled` opt-in is
  **not** a DPDP cross-border grant. `tasks/misc.py` `_handle_job` **step 1b** now enforces
  the per-processor `cross_border_notify` consent (ADR-0024) fail-closed BEFORE any
  transport: no grant ⇒ `log_delivery(..., "cross_border_consent_required")` + drop (no
  retry — a retry would re-attempt the blocked transfer). Fresh read → revoke honoured
  immediately; audit records an opaque code only (no chat_id/email/body). Test:
  `test_drain_skips_without_cross_border_consent` (Telegram never invoked without the grant).
  Ledger `reviews/b31-notify-cross-border-gate.md`. **Still inert for real users until the
  Consent-module grant/revoke writer lands (non-neg #10) — safe (every user fails closed).**
- **B26 (deploy gate):** every delivered label owes an `ai_recommendation_audit` row
  `(label, model_used, disclaimer_version)`; `notification_log` records channel/
  template/status only.
- **B32 (low):** rate-cap counter is non-atomic (single-beat-worker safe; Redis Lua
  before multi-worker); `/test` rate-limit is IP-keyed.

## Frontend

- `/settings/notifications` (authed, in the app shell). Loads `GET
  /notifications/preferences`; channel toggles (Telegram + Email; WhatsApp shown
  "Coming soon", disabled) with a Telegram chat-id field (client-validated
  `^-?\d{1,20}$`) and an email Verified/Unverified chip (read-only); IST quiet-hours
  start/end (`<input type=time>` → HH:MM) + Clear; Save computes a diff and POSTs
  **only changed allowed keys** (never `email_verified`/`whatsapp`). Test-send is
  Pro-gated in the UI — disabled with a "Pro" tag + upgrade hint for non-Pro tiers,
  matching the backend 402. Files: `frontend/src/features/notifications/{types,api}.ts`,
  `frontend/src/app/(app)/settings/notifications/page.tsx`. Token-only styling; no
  numeric/advisory surface.

## Pending (not built this phase)

- Daily public-channel Mood card (needs the Mood Compass module + its
  `mood.snapshot.published` event).
- WhatsApp delivery (Y2).

## Changelog

- 2026-06-06 — FE preferences screen built (`/settings/notifications`, Tier-A UI):
  diff-based partial save, Pro-gated test-send (disabled + hint for non-Pro), accessible
  toggles, token-only styling. MSW mocks for all three endpoints. tsc + eslint +
  anti-pattern sweep green.
- 2026-06-06 — Module built (Phase 6): `notify` schema + migration 0005; preferences
  API + `/test` (Pro); Telegram + Resend transports (real UA); template renderer
  (disclosure/label-only, no numeric/advisory); Pillow share-card → R2; Celery
  beat drain (ADR-0021). Governance: Tier-A+Compliance+Security fan-out, all
  ACCEPT-WITH-CONDITIONS; MAJOR/MINORs fixed in-branch (see RCA 2026-06-06 + ledger
  `reviews/phase6-notification.md`); B31/B32 filed, B26 extended.
