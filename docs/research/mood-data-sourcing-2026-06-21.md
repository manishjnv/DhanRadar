# Market Mood — Phase 2 Data-Sourcing Dig (FII / DII / PCR / News)

Date: 2026-06-21. Status: RESEARCH (no code). Owner: founder + Builder.
Plan context: `docs/project-state/MOOD_IMPROVEMENT_PLAN.md` §3.1, §6, §7 (Phase 2).

All source facts below were fetched live on 2026-06-21. Where a source could not be
verified, it is marked unverified — nothing here is asserted from memory.

## 0. Why this dig

The mood engine has 11 weighted factors but only 7 carry real data, so it sits in
**permanent degraded mode** (confidence capped ~0.40, AI commentary withheld every day).
The four stubbed factors are `fii_flows`, `dii_flows`, `put_call_ratio`, `news_sentiment`.
This dig finds a viable, ToS-clean, **KVM4-reachable** source for each.

Hard constraint carried into the dig: **NSE direct is geo-blocked from the KVM4 box** (the
reason the engine already uses Yahoo Finance for its macro signals). Any source that only
works from an Indian residential IP, or that NSE anti-bot-blocks, is not viable in production.

## 1. Headline result

- **One integration unlocks three signals.** The **Upstox developer market-data API** returns
  FII flows, DII flows, **and** a pre-computed Put-Call Ratio — free, as clean JSON, from
  endpoints that are explicitly exempt from the SEBI static-IP rule and are reachable from a
  non-IN cloud IP. One Upstox account + one 1-year **Analytics Token** covers `fii_flows`,
  `dii_flows`, and `put_call_ratio`.
- **GDELT covers the fourth.** The **GDELT DOC 2.0 API** is a free, no-key, commercial-use-
  permitted news index with good Indian-market coverage; it feeds the `news_sentiment` factor
  as a headline source, with the sentiment itself computed in-house by the governed OpenRouter
  gateway (stack lock).
- **Net:** exiting degraded mode is tractable and **$0 in feed cost**. The only real gate is a
  one-time operational dependency: a designated Upstox brokerage account to hold the token.

Summary verdict:

| Signal | Recommended source | Cost | KVM4-reachable | Main caveat |
| --- | --- | --- | --- | --- |
| `fii_flows` | Upstox `/v2/market/fii` | Free | Yes | Needs Upstox account/token; history from Apr-2026 |
| `dii_flows` | Upstox `/v2/market/dii` | Free | Yes | Same account/token as FII |
| `put_call_ratio` | Upstox `/v2/market/pcr` | Free | Yes | Same account/token; broker-goodwill dependency |
| `news_sentiment` | GDELT DOC 2.0 API (headline source) | Free | Yes | Sentiment computed in-house; attribution required |

## 2. FII / DII flows

FII and DII daily cash-market net flows share the same sources (they are published together).

### Recommended — Upstox Developer API

- Endpoints: `GET https://api.upstox.com/v2/market/fii` and `.../v2/market/dii`
  (params `data_type=NSE_EQ|CASH`, `interval=1D`, optional `from`).
- Returns clean JSON per record: `time_stamp`, `buy_amount`, `sell_amount`, plus contract/OI
  fields. Daily interval returns up to ~30 trading days per call.
- Auth: a read-only **Analytics Token** (1-year validity, no daily OAuth refresh) — purpose-
  built for server-side scheduled jobs like the 09:00 / 16:00 IST refresh.
- Cost: free (₹0 per Upstox's pricing page).
- ToS: official documented API from a SEBI-registered broker; no redistribution bar found in
  the docs. Upstox suggests "contact us" for a custom/business app — recommended before launch,
  not a dev blocker. Data is NSE-sourced → keep standard NSE-data + Upstox attribution.
- Freshness: daily provisional (post-market). The 09:00 pull reliably has the prior trading
  day; the 16:00 pull may catch same-day provisional if NSE has published. No source offers
  intraday FII/DII — this is a market-wide limitation, not Upstox-specific.
- Geo: market-data endpoints are explicitly **exempt** from the SEBI static-IP requirement and
  show no geo-block — reachable from KVM4.
- Limitation: history only from 1-Apr-2026 (API launched May 2026).

### Key alternatives (and why not)

- **NSE FII/DII activity** (`/api/fiidiiTradeReact`): canonical, but **geo-blocked from KVM4**
  and anti-bot/ToS-gated. Not viable.
- **SEBI FPI stats** and **CDSL FII daily**: free and geo-reachable, but HTML-scrape only and
  the equity net-flow tables lag / update on a slower cycle than same-day. Usable only as a
  cross-check, not the primary feed.
- **Trendlyne / IIFL / Groww**: geo-reachable, show provisional same-day numbers, but HTML-only
  and no scraping licence — fragile. Acceptable as a one-time backfill or emergency stopgap,
  never the licensed primary.
- **NSDL FPI portal, 5paisa, Moneycontrol, MacroMicro**: blocked (socket drops / 403 / fetch-
  blocked) from a non-IN cloud IP. Not viable.

### Integration note

Feeds `fii_flows` (weight 0.10) and `dii_flows` (weight 0.08). A new `UpstoxFlowsProvider`
slots beside the Yahoo provider in `service.py`, normalizing net flow to the engine's 0–1
scale (1 = greed/bullish): **net inflow → toward 1, net outflow → toward 0**, scaled against a
rolling window so a single large day does not saturate. Normalization band is a build-time
decision (Tier-C-adjacent: it shapes the score) and must be reviewed with the scoring/compliance
gate.

## 3. Put-Call Ratio (PCR)

### Recommended — Upstox Developer API

- Endpoint: `GET https://api.upstox.com/v2/market/pcr` (params `instrument_key`, `expiry`,
  `date`, `bucket_interval`). Covers Nifty / Bank Nifty etc.
- Returns `data.pcr` (float, e.g. `0.6162`) + `spot_closing_price` + an `insights[]` series —
  **PCR is pre-computed**, no OI math needed.
- Auth / cost / geo: same Analytics Token, free, geo-reachable as §2. Twice-daily cadence is
  well within rate limits.
- ToS: official market-information API (launched May 2026); read-only token; no documented
  third-party-display prohibition.

### Key alternatives (and why not)

- **NSE option chain**: canonical PCR source but **geo-blocked + anti-bot + ToS-prohibits
  scraping**. Not viable.
- **DhanHQ option chain API** (`POST https://api.dhan.co/v2/optionchain`): free, geo-reachable,
  but returns raw OI — PCR must be derived server-side (`sum(put OI)/sum(call OI)`). Good
  **fallback** if the Upstox token is unavailable; same broker-account dependency class.
- **Angel One SmartAPI / ICICI Breeze**: workable for data reads but operationally fragile —
  Angel One uses TOTP session auth (hard to automate on a server); ICICI Breeze is
  resident-Indian-account-only. Lower preference.
- **TrueData** (authorised vendor): paid (~₹1,440–2,796/mo) **and** product redistribution
  needs a separate NSE/SEBI-approved data-vendor licence. Not recommended at this stage.
- **Sensibull / Opstra / NiftyTrader**: web-UI only, no clean API, no redistribution licence.
  Not viable.

### Integration note

Feeds `put_call_ratio` (weight 0.07). PCR is **contrarian**: very high PCR (puts ≫ calls)
typically reads as fear/oversold, very low as greed. The normalization into the 0–1 (1 = greed)
scale must therefore **invert** relative to a raw-bullish signal — this direction is an explicit
build-time decision and must be unit-tested and reviewed with the scoring/compliance gate so the
factor does not push the regime the wrong way.

## 4. News sentiment (headline source; sentiment computed in-house)

Scope: DhanRadar computes sentiment with its own governed OpenRouter gateway. This sources only
the **headline/article feed**; any third-party pre-computed sentiment field must be discarded at
ingestion (stack-lock). The in-house sentiment output stays descriptive (positive/negative tone)
and is screened by the existing advisory-verb filter.

### Recommended — GDELT DOC 2.0 API

- Endpoint: `https://api.gdeltproject.org/api/v2/doc/doc` with e.g.
  `query=nifty OR sensex OR "indian stock market" OR NSE OR BSE OR "mutual fund"`,
  `sourcecountry:india`, `sourcelang:english`, `mode=ArtList`, `format=json`, `timespan=…`.
- Returns JSON article list: title, URL, source domain, `seendate`, country, language. No key.
- Cost: free. GDELT's licence explicitly permits **"unlimited and unrestricted use for any
  academic, commercial, or governmental use … without fee"**; attribution required (cite GDELT
  with a link to gdeltproject.org).
- ToS risk: low. Headline + URL + metadata only (no full-text redistribution), analogous to RSS.
  Discard GDELT's own `V2Tone` score — sentiment is in-house.
- Freshness: near-real-time index, rolling ~3-month window; twice-daily pulls = 2 calls/day,
  trivially within limits. Send a real `User-Agent` and retry once on a 429 (the only failure
  seen in testing was burst-parallel 429, not normal cadence).
- Geo: not restricted; reachable from KVM4.
- Coverage: indexes major Indian English press (ET, Mint, Business Standard, Hindu, ANI, PTI…).

### Secondary / complementary — NewsData.io free tier

- Free tier ($0): `country=in`, `category=business`, `language=en`; commercial use permitted
  (confirmed); headline + snippet + URL. Caveat: **12-hour article delay** on the free tier (so
  the 09:00 pull sees the prior evening at best), and a 97k-source mix that needs a domain
  allowlist. Upgrade to Basic ($199.99/mo) only if real-time is needed post-revenue.

### Do not use

- **Google News RSS** — feed XML explicitly limits use to "personal, non-commercial"; product
  use is prohibited.
- **NewsAPI.org free tier** — "cannot be used in a staging or production environment"; paid tier
  is $449/mo (disproportionate now).
- **Mediastack free** — non-commercial + 100 calls/month.
- **Indian publisher RSS direct** (ET, Moneycontrol, Business Standard, LiveMint, BusinessLine,
  NDTV Profit, CNBC-TV18) — all blocked (403 / fetch-blocked) from the cloud VPS, and commercial
  syndication needs a per-publisher licence. **Reuters** free RSS is dead since 2020.

### Integration note

Feeds `news_sentiment` (weight 0.06) — the lowest weight, so an imperfect signal here moves the
regime least. Pipeline: GDELT headline pull → in-house OpenRouter sentiment (descriptive,
advisory-verb-filtered) → normalize aggregate tone to 0–1 (positive → toward 1). The sentiment
compute is a **separate build step** that lands as a new AI-gateway consumer and gets the full
inline Tier-B review (it is a load-bearing AI-gateway path).

## 5. Governance and data-quality posture

- **Provenance + freshness** must be stamped per source on every snapshot (which provider, when
  fetched) — the engine already tracks this pattern; extend it for the new providers.
- **No imputing across granularity** (the B67 rule): use the published net flow / PCR as-is; do
  not synthesize intraday values that no source provides.
- **Broker-goodwill dependency.** FII/DII/PCR all hang off a free broker API whose terms can
  change (both Upstox and Dhan have changed API terms before). This needs a token-rotation +
  terms-watch entry in the ops runbook, and the engine must degrade gracefully (it already does)
  if the feed drops — a missing factor decrements coverage, it does not crash.
- **Attribution.** NSE-sourced data via a broker should carry NSE + provider attribution; GDELT
  requires its attribution line.
- **No personal data** in any of these feeds → no DPDP concern. Market data only.
- **Compliance stays intact.** None of these signals reach the DOM as numbers — they feed the
  server-side score only; the public surface remains label + band. Adding them does not change
  the no-numeric-in-DOM or no-advice posture.

## 6. Open decisions for founder

- **Upstox account.** Will you designate/open an Upstox brokerage account (free, one-time KYC)
  for DhanRadar to hold a 1-year Analytics Token? This single decision unlocks 3 of the 4
  signals. (Note: you already hold ARN/MFD + broker-adjacent accounts — confirm whether an
  Upstox account exists or should be opened specifically for this.)
- **Pre-launch ToS confirmation.** Should we send Upstox the "business/custom app" enquiry their
  docs mention before going live, to remove any ambiguity on product use? Recommended.
- **News tier.** Start with GDELT-only (free, ~12h-fresh-enough for a sentiment context signal),
  or also wire NewsData.io free as a complementary feed now? Paid real-time news is deferred to
  post-revenue.
- **History/backfill.** Accept that FII/DII history starts Apr-2026 and PCR May-2026 (fine —
  mood history is only weeks old anyway), or do a one-time best-effort HTML backfill from a
  geo-reachable aggregator? Recommended: skip backfill, accumulate forward.

## 7. Suggested sequencing (for a later build session, each gated)

1. Founder opens/designates the Upstox account + generates the Analytics Token (no code).
2. Wire `UpstoxFlowsProvider` (FII + DII) → exits degraded mode the moment it reaches 9/11
   present signals. Scoring/compliance gate on the normalization.
3. Wire Upstox PCR (→ 10/11), with the contrarian-inversion unit-tested.
4. Wire GDELT headline pull + in-house OpenRouter sentiment (→ 11/11), full Tier-B AI-gateway
   review; then turn on the already-built-but-unused AI commentary hook now that confidence
   clears the floor.

## 8. Sources

- Live fetches 2026-06-21: Upstox developer docs (`get-fii` / `get-dii` / `get-pcr`,
  analytics-token + static-IP exemption pages); DhanHQ, Angel One SmartAPI, ICICI Breeze,
  TrueData docs/pricing; GDELT DOC 2.0 API + licence; NewsData.io, NewsAPI.org, Mediastack,
  Marketaux pricing/ToS; SEBI FPI stats, CDSL FII daily, Trendlyne, IIFL, Groww pages.
- Repo context: `backend/dhanradar/mood/{compute.py,service.py}`, `docs/infra-notes.md`
  (NSE geo-block), `docs/project-state/MOOD_IMPROVEMENT_PLAN.md`.
