# Feature — Mood Compass module

**Status:** partial (compute + persistence + public API + event/audit/card built;
real signals, embed widget, commentary, mood_history deferred — B35) ·
**Phase:** Phase 2 (built post-B26) · **Last updated:** 2026-06-06

## Purpose & scope

An anonymous public "market mood" acquisition magnet: a twice-daily market **regime**
(0–100 internally) over 11 weighted macro/market inputs, classified into 5 buckets,
with a best-effort plain-English commentary. Owns `market_mood` + `mood:*` Redis.
Delivery is not here — it emits `mood.snapshot.published` and posts the daily public
card via the Notification interface.

## Non-goals

- No buy/sell/advice; the regime is an educational market read, not a directive (non-neg #1).
- Not an input to the per-security DhanRadar Score (explicitly distinct).
- No public numeric — the 0–100 `mood_score` / confidence float stay server-side (non-neg #2).
- No hallucinated commentary (withheld when degraded / refused).

## Public interface (anon)

- `GET /api/v1/market/mood` → `MoodPublic` (regime, confidence_band, data_quality,
  contributing/contradicting factors, commentary, disclosure, NOT_ADVICE, disclaimer_version).
  404 `mood_unavailable` when no snapshot yet.
- `GET /api/v1/market/mood/history?days=N` (1..365) → `[{snapshot_date, regime}]`.
- `GET /api/v1/market/why-today` → `WhyToday` (commentary + evidence + disclosure).
- `GET /api/v1/market/flows` — **public** — raw FII/DII/PCR facts derived from the twice-daily
  mood snapshot (DOM-allowed public market data; no DhanRadar-computed output).
- Emits `mood.snapshot.published` (via `emit_published`: B26 audit + public card).
- Deferred: `GET /market/mood/embed` (creator widget).

## Frontend

- `/mood` — a **public** route (top-level `app/mood/`, outside the `(app)` group → no
  AuthGuard, no AppShell), matching the anonymous backend; also linked from the app
  sidebar for signed-in users. Renders a band-only `MoodGauge` (semicircular arc; regime
  word + confidence-band word, **never a number**), commentary (withheld when
  degraded/absent), "Supporting"/"Counterweights" factor lists (neutral `+`/`−` markers —
  no up/down arrows that imply buy/sell), a 30-day regime history strip, and the
  `disclosure` + `not_advice` strings + `<Disclaimer/>` (non-neg #9). 404 → "being
  computed" empty state. `MoodGauge` uses a **symmetric attention colour scale** (both
  extremes red, neutral cyan) so greed is never coloured as positive/buy. Files:
  `frontend/src/features/mood/{types,api}.ts`, `frontend/src/components/mood/MoodGauge.tsx`
  (owns the `Regime` enum + `REGIME_COLOR`/`REGIME_DISPLAY`, mirroring ScoreRing),
  `frontend/src/app/mood/page.tsx`.

## Data

Schema `mood` (Alembic 0007): `market_mood` (snapshot_date PK, snapshot_time,
`mood_score`/`confidence_score` **server-side**, `regime`, `confidence_band`,
`inputs_available`, `input_vector` JSONB, `contributing_factors`/`contradicting_factors`
JSONB, `ai_commentary`, `model_used`, `data_quality`). Redis `mood:latest` 12h.
`mood_history` (pgvector, AI-Enrichment analogues) deferred.

## Signal providers (as-built)

- **YahooMacroProvider** (primary) — 6 signals: `nifty_trend`, `global_indices`,
  `india_vix`, `us_bond_10y`, `oil_brent`, `usd_inr`.
- **UpstoxAnalyticsProvider** (supplemental, live 2026-06-22) — 3 signals: `fii_flows`,
  `dii_flows`, `put_call_ratio`. PCR expiry is resolved from the live Upstox
  `/option/contract` list — NSE Nifty weekly expiry is **Tuesday** (not Thursday).
- **News-sentiment AI signal** (governed gateway consumer) — 1 signal: `news_sentiment`
  (GDELT-sourced, sanctioned B56-f5).
- **market_breadth** — wired (Yahoo sector/constituent adapter reads Redis `signal:breadth:last`);
  live value depends on the Redis cache being warm (cold outside market hours → absent, not an error).

All 11 inputs live as of 2026-06-22: engine runs at `inputs_available=11`, `data_quality=ok`
(out of degraded mode; B69 resolved). Celery mood worker memory limit: 384 MB (bumped from
192 MB, PR #315, to clear a full-snapshot OOM).

## Pipeline / behaviour

1. `compute_mood_snapshot` (Celery `mood` queue, beat **09:00 & 16:00 IST**) →
   `service.compute_and_store`.
2. Ingest 11 signals via registered providers (above). Normalize 0–1, missing dropped
   (never imputed), decrement `inputs_available`.
3. Weighted score = Σ(value·weight present)/Σ(weight present)·100 → bucket. Weights:
   nifty_trend .15 · market_breadth .12 · india_vix .10 · fii_flows .10 · global_indices .10 ·
   dii_flows .08 · us_bond_10y .08 · oil_brent .07 · usd_inr .07 · put_call_ratio .07 ·
   news_sentiment .06 (Σ=1.00). Buckets: extreme_fear 0–19 / fear 20–39 / neutral 40–59 /
   greed 60–79 / extreme_greed 80–100 (contiguous bounds — no gaps).
4. Confidence = coverage (Σ present weight); `<7` inputs → capped ≤0.40 + `degraded` +
   commentary withheld; **`<0.30` → regime coerced to `insufficient_data`** (refuse floor,
   non-neg #4); all-missing → skip + retry.
5. Commentary (best-effort, injected hook; advisory-screened before publish) → persist
   `market_mood` (upsert by date) → cache `mood:latest` → `emit_published` (audit + card).

## Config & flags

`TELEGRAM_PUBLIC_CHANNEL_ID` (empty ⇒ public card is a no-op). No other new env.

## Failure modes & fallbacks

- All inputs missing → snapshot skipped, endpoint 404s (until real signals — B35).
- `<7` inputs → degraded snapshot, commentary withheld. `<0.30` confidence → `insufficient_data`.
- Commentary with an advisory verb → withheld (publish regime alone).
- Persist/cache/emit are best-effort and isolated — a failure never breaks the snapshot.

## Admin surfaces (as-built 2026-06-22)

- `GET /admin/mood-status` — signal-coverage panel endpoint (RequireAdmin); returns
  per-signal live/absent status and current `inputs_available` / `data_quality`.
- **Admin Operations page** — Upstox is a monitored ingestion source (`source_key=upstox_analytics`)
  visible under `mf.ingestion_runs` + `mf.source_health`, alongside existing sources.

## Dependencies

Consumes: YahooMacroProvider + UpstoxAnalyticsProvider (signals), the AI gateway (commentary,
governed gateway), Compliance (`record_served_label`), Notification (`post_public_card`), the
scoring engine's disclosure constants. Build entirely in-house.

## Compliance posture

- Public surface = regime bucket + confidence band + commentary + evidence; **never a number**
  (non-neg #2 — Compliance-confirmed; a Fear&Greed public number would be a BLOCKER).
- Regime labels are sentiment descriptors, framed "educational market-regime read, not advice".
- Disclosure + NOT_ADVICE + disclaimer_version on every public surface + the cached payload +
  the card. B26 audit on the served regime. `<0.30` confidence refuses (insufficient_data).
- Mood carries no user PII → no consent/cross-border gate (unlike the per-user notif seam B31).

## Verification

- `pytest tests/unit/test_mood.py` (22: weights, all-regime, degraded, floor coercion,
  bucket boundaries, factor split, public-card no-op) + `tests/integration/test_mood.py`
  (6: compute_and_store persists, GET /mood 200 with no numeric leak, 404, history, B26
  audit row, upsert idempotency). `ci_guards.py` + `anti_pattern_sweep.py`.

## Changelog

- 2026-06-22 — Upstox Analytics live (PRs #296/#315/#316): `UpstoxAnalyticsProvider`
  supplemental adapter feeds FII flows, DII flows, and PCR; PCR Tuesday-expiry fix (NSE
  Nifty weekly expiry resolved from live `/option/contract` list); mood worker OOM resolved
  (192 MB → 384 MB, PR #315); engine now at 11/11 inputs, `data_quality=ok` (B69 resolved).
  New surfaces on `feat/upstox-ops-surfacing` (pending review): `GET /market/flows` (public
  FII/DII/PCR facts card), `GET /admin/mood-status` signal-coverage panel, Upstox as a
  monitored source on the Admin Operations page.
- 2026-06-06 — FE public page built (`/mood`, Tier-A UI): band-only `MoodGauge`
  (symmetric non-advisory colour scale), factor lists, 30-day history strip, disclosure +
  NOT_ADVICE rendered, 404/empty/error states. MSW mocks for `/market/mood`,
  `/mood/history`, `/why-today`. tsc + eslint + anti-pattern sweep green.
- 2026-06-06 — Module built (Phase 2, post-B26): `mood` schema + Alembic 0007; pure compute
  (11 weights, 5 buckets, confidence, factors); twice-daily Celery beat; anon endpoints;
  `mood.snapshot.published` (B26 audit + public card via Notification interface); ADR-0023.
  Tier-C governance (Architect+Compliance+Product), all ACCEPT-WITH-CONDITIONS; the
  sub-0.30-regime refuse + bucket-gap + commentary-screen fixed in-branch. Go-live gaps →
  B35. Ledger: `reviews/mood-compass.md`.
