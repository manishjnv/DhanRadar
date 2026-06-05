# DhanRadar — Reality Layer Addendum

**Version:** 1.0
**Date:** May 2026
**Status:** Companion document to DhanRadar Master Blueprint & DharRadar v2.1
**Purpose:** Captures the regulatory, unit-economics, UX-taxonomy, AI-governance, and strategic-wedge realities that the existing product/architecture docs underweight. This document is intentionally non-technical and non-overlapping with the Blueprint or v2.1 architecture.

---

## How to read this doc

| Existing doc | What it covers | What it leaves out (this doc fills) |
|---|---|---|
| DhanRadar Master Blueprint | Product vision, modules, AI principles, tech stack | Regulatory specifics, CAC math, UX label system |
| DharRadar Architecture v2.1 | Technical implementation, security, observability | DPDP/AA/CERT-In, RIA cost, build-vs-partner |
| Architecture Plan | API choices, monetization sketch | Operational regulatory burden, unit economics |
| Market Intelligence | Competitive landscape (20 platforms) | Specific UX innovation patterns from PowerUp/CRED |
| Stock & ETF Scanner | Local Windows scanner architecture | Not affected — separate scope |

---

# Part 1 — Regulatory Reality Layer

> The single biggest underweight area across all existing docs. None of these are optional if DhanRadar handles Indian user financial data or gives advice on specific schemes.

## 1.1 SEBI Investment Adviser (RIA) Registration

If DhanRadar ever moves beyond pure education into anything resembling personalised advice on specific schemes, RIA registration is mandatory. The bar is significantly higher than a single checkbox.

### Hard requirements (Corporate RIA)

| Requirement | Detail | Implication |
|---|---|---|
| Net worth | ₹50 lakh minimum, maintained continuously | Working-capital lock-in; affects fundraise sizing |
| Principal Officer | Postgraduate qualification + NISM-Series-X-A + NISM-Series-X-B + 5 years experience in financial products/securities/fund management | This is a hire, not a self-certification. Likely ₹15–25 LPA |
| Compliance Officer | Separate person from Principal Officer | Second hire OR retainer arrangement |
| BASL membership | Mandatory before grant of certificate | ~₹10K/year |
| Fee structure | Must offer BOTH options: (a) Fixed fee ≤ ₹1.25 lakh/client/year, OR (b) AUA-linked ≤ 2.5% of assets under advice | Caps your ARPU mathematically |
| Hybrid model ban | Post-Sep 2020 amendment: cannot do RIA + distribution for same client | Forces a clean separation of advisory vs commission revenue |
| Audit | Annual compliance audit by independent CA | Recurring ₹1–3 lakh |
| Record retention | 5 years for all advice records | Audit-trail infrastructure required |

### Practical paths

1. **Pure education + research analyst position** — Stay non-RIA. Publish rankings, screeners, market mood. Never recommend a specific scheme to a specific user. Lowest regulatory burden.
2. **Research Analyst (RA) registration** — Lower bar than RIA. Allows publishing model portfolios and specific scheme research, but no personalised advice.
3. **Partner with existing RIA** — White-label your tech to a registered RIA entity. They own the advisory relationship and compliance burden. You own product and AI. Faster to market by 6–12 months. Common starting pattern.
4. **Full RIA registration** — ₹50L+ tied up, 9–12 month process, ~₹25–40L Year-1 compliance cost. Only justified at scale.

### Recommended sequence for DhanRadar

Year 1 → Path 1 (pure education) using the rating labels as descriptive analytics, not advice.
Year 2 → Path 3 (partner RIA) once retention/ARPU is proven.
Year 3+ → Path 4 (own RIA) if AUA crosses ₹500 Cr.

---

## 1.2 DPDP Act 2023 — Live since 2025

Wealthtech handles PAN, bank statements, demat holdings, NAV history per user → squarely in scope. Non-compliance penalties go up to ₹250 Cr per incident.

### Minimum implementation

| Control | Implementation |
|---|---|
| Consent management platform (CMP) | Granular per-purpose consent UI; revocation flow; consent audit log table |
| Data principal rights | API endpoints for: access, correction, erasure, portability, grievance |
| Data Protection Officer | Required if classified as Significant Data Fiduciary (likely once user count crosses threshold) |
| Breach notification | Notify Data Protection Board within 72 hours; notify affected users without undue delay |
| Cross-border transfer | India default-allowed except to negative-list countries; review before using non-Indian LLM APIs for user-specific data |
| Children's data | Verifiable parental consent if any user might be under 18; tightened processing rules |
| Purpose limitation | Cannot reuse data for new purposes without fresh consent |

### Practical artefacts to build into DharRadar's existing user model

```sql
-- Extends existing users table from v2.1 §9.1
ALTER TABLE users ADD COLUMN dpdp_consent_version INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN dpdp_consents JSONB; -- per-purpose granular
ALTER TABLE users ADD COLUMN deletion_requested_at TIMESTAMPTZ;

CREATE TABLE consent_audit_log (
  id BIGSERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  purpose VARCHAR(100), -- e.g. 'mf_analytics', 'ai_insights', 'marketing'
  action VARCHAR(20),   -- 'granted' | 'revoked' | 'updated'
  source VARCHAR(50),   -- 'onboarding' | 'settings' | 'banner'
  ip_address INET,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE data_principal_requests (
  id BIGSERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  request_type VARCHAR(30), -- 'access' | 'correction' | 'erasure' | 'portability'
  status VARCHAR(20) DEFAULT 'pending',
  filed_at TIMESTAMPTZ DEFAULT NOW(),
  resolved_at TIMESTAMPTZ,
  resolution_notes TEXT
);
```

---

## 1.3 Account Aggregator (AA) Framework

If DhanRadar ever provides cashflow-aware advice, portfolio-linked recommendations, or bank-statement-based insights, screen-scraping is illegal. You must integrate via licensed AAs.

### Licensed AA providers (current landscape)

| AA | Notes |
|---|---|
| Setu (Pinelabs) | Strong developer experience, modern APIs |
| Finvu (Cookiejar) | Largest market share, broad FIP coverage |
| OneMoney | Oldest licensed AA, conservative integration |
| CAMSFinServ | CAMS-backed, MF-focused |
| NESL Asset Data | Newer, enterprise-leaning |

### What AAs unlock

- Mutual fund holdings (via CAMS / KFintech as FIPs)
- Demat holdings (NSDL/CDSL)
- Bank statements (transaction-level, with consent)
- EPF, NPS, GST, insurance (expanding scope)

### Integration cost

- One-time integration: 4–8 weeks engineering for one AA
- Per-consent cost: ₹3–15 paise per data fetch (negligible at consumer scale)
- Consent UX is rigid (RBI-prescribed flow) — cannot be skinned freely

### Implication for DhanRadar roadmap

The Master Blueprint's "Portfolio Intelligence Module" implicitly requires AA. Add this as a Phase 2 prerequisite — not a Phase 1 feature.

---

## 1.4 CERT-In Directives (April 2022, ongoing)

Mandatory for any Indian-incorporated entity providing digital services.

| Rule | Implementation |
|---|---|
| 6-hour cyber incident reporting | Runbook + on-call rotation; pre-templated CERT-In forms |
| 180-day log retention within India | Loki retention bumped from default; storage budget; data residency check on cloud provider |
| Synchronised time source (NIC NTP / NPL) | Configure all VMs to `time.nplindia.org` or `samay1.nic.in` |
| KYC + financial transaction records retention | 5 years minimum (overlaps PMLA) |

Manish's SOC background makes this trivially achievable — most consumer founders entirely miss it.

---

## 1.5 SEBI Finfluencer Regulations (2024)

If DhanRadar partners with influencers, Twitter/YouTube creators, or paid affiliates:

- Unregistered persons cannot give recommendations on specific securities
- All paid partnerships must be disclosed clearly in content
- "Education only" content is allowed but cannot embed buy/sell language
- DhanRadar (as the brand) is liable if a paid influencer crosses the line

### Implication

Content marketing strategy must be designed assuming SEBI-compliant constraints from day one. Pre-approved influencer brief template recommended.

---

## 1.6 MF Central Reality

MF Central (joint CAMS + KFintech utility, AMFI-backed) is the official aggregation rail. Free, authoritative. Problem: onboarding is gated, slow, and often takes 3–6 months for new fintechs.

### Practical fallback ladder

1. **MF Central direct integration** — apply early; treat as long-lead-time item.
2. **CAS (Consolidated Account Statement) PDF parsing** — user uploads CAS, parser extracts holdings. Most startups start here. ~80% accuracy out of the box; needs ongoing parser maintenance as PDF formats drift.
3. **AA framework** — once integrated (§1.3), the cleanest path. AA delivers holdings as structured JSON.

Build CAS parser first; integrate AA in parallel; treat MF Central as a Year-2 win.

---

## 1.7 IRDAI PoSP for Insurance Cross-Sell

Not in any existing doc but a clean ARPU lever.

- Point-of-Sale Person certification — far lighter than full insurance broker license
- Allows selling specified categories: term life, motor, travel, personal accident
- Per-person certification, not corporate
- Commission revenue without distribution conflict with RIA (different products)

### Why it matters

PowerUp doesn't do this. Smallcase / Groww / ET Money do it inconsistently. Insurance gap analysis as a logical extension of portfolio intelligence is a defensible product surface.

---

# Part 2 — Unit Economics Reality

> Existing docs say "subscription monetisation" and "high potential." None state the numbers that determine whether the business survives.

## 2.1 CAC math for Indian wealthtech

| Channel | Typical CAC (₹/activated user) | Notes |
|---|---|---|
| Performance marketing (Meta/Google) | 800–2000 | Most volatile; auction-driven |
| Content + SEO | 200–600 | Long lead time (12–18 months) |
| Referral program | 300–800 | Cap with per-referral incentive ceiling |
| Influencer (compliant) | 400–1500 | Wide range based on creator quality |
| Community-led (cybersec, NRI) | 100–400 | Best margin if you have credibility |

**Industry rule of thumb:** LTV/CAC > 3 to be venture-viable. At ₹499/month Pro tier with 18-month avg retention = ₹8,982 LTV → max CAC ₹3,000. Tight but workable if churn is controlled.

## 2.2 Realistic outcome scenarios

| Scenario | Year-3 ARR | Funding needed | Probability | What it requires |
|---|---|---|---|---|
| Lifestyle business | ₹1–5 Cr | ₹0–50L bootstrap | 30–40% | Niche wedge, low overhead, founder-led sales |
| Profitable SMB | ₹5–15 Cr | ₹2–5 Cr seed | 15–20% | Strong retention, 1 strong distribution channel |
| Growth-stage | ₹15–50 Cr | ₹10–20 Cr Series A | 5–10% | Category leadership in a wedge, B2B2C distribution |
| Venture-scale | ₹50 Cr+ | ₹30–100 Cr | <5% | Multi-channel, brand, regulatory moat |

**Honest framing for DhanRadar:** Plan for lifestyle business as base case. Optionality on profitable-SMB if NRI or cybersec wedge clicks. Anything above that requires a step-change event (acquisition, regulatory tailwind, viral product).

## 2.3 The "Why pay you?" forcing question

Before any feature build, answer:

| Competitor | What they offer free | Why a user would pay DhanRadar instead |
|---|---|---|
| ET Money | Free MF analytics, portfolio tracker, paid plans for goals | DhanRadar's answer: ____ |
| Groww | Free MF + stocks, AI-assisted discovery (commission-subsidised) | DhanRadar's answer: ____ |
| Tickertape | Free screener, paid MMI Pro at ~₹1500/yr | DhanRadar's answer: ____ |
| INDmoney | Free portfolio, US stocks, paid premium | DhanRadar's answer: ____ |
| PowerUp Money | Fund ratings, comparison | DhanRadar's answer: ____ |

If the answer is "better UX" or "more AI" — that's not enough. If the answer is "I'm the only platform that does X for cohort Y" — that's a wedge.

---

# Part 3 — UX Innovation Layer

> The sharpest underweight area. The Blueprint says "explainable rankings" generically. The actual product win is in the *label system* and *action framing*.

## 3.1 The rating taxonomy

| Label | Meaning | Action implied |
|---|---|---|
| 🟢 In-form | Outperforming category over 1Y + 3Y with controlled drawdown | Continue / increase SIP |
| 🟡 On-track | Matching category, no red flags | Hold |
| 🟠 Off-track | Underperforming category 12+ months OR fund manager change | Review, consider alternatives |
| 🔴 Out-of-form | Sustained underperformance + structural concerns | Consider exit (educational language only) |

### Why this works

- **Verbs, not numbers.** Users act on verbs. They don't act on "Sharpe ratio 1.42."
- **Mental model from sport.** Familiar from cricket/football commentary — instant comprehension.
- **Defensible.** Each label is backed by 4–6 quantitative criteria. Publish the criteria. Hide nothing.
- **Compliant.** Educational descriptive language, not "buy/sell" recommendation.

### Implementation note

The rating engine output schema becomes a label + confidence + 3-line explanation + linked metrics, not a numeric score. This is a fundamental API contract decision — get it right at v1.

```python
# Pseudocode for the rating output contract
class FundRating(BaseModel):
    scheme_code: str
    label: Literal["in_form", "on_track", "off_track", "out_of_form"]
    confidence: Literal["high", "medium", "low"]  # not 0.0-1.0 — labels here too
    primary_reason: str  # one sentence, plain English
    supporting_signals: list[Signal]  # the 4-6 quant criteria
    contradicting_signals: list[Signal]  # honesty about uncertainty
    valid_until: datetime  # ratings expire; transparency about cadence
    methodology_url: str  # always link to published methodology
```

## 3.2 "Users don't see data → they see action"

The entire UI thesis in one sentence.

| Old wealthtech UX | DhanRadar UX |
|---|---|
| Sharpe 1.4, Alpha 2.1%, Beta 0.85 | "🟢 In-form — beating category by 3.2% over 3Y with lower drawdown" |
| 5-star Morningstar rating | "🟡 On-track — performing as expected for its category" |
| Returns table (1M/3M/1Y/3Y/5Y) | "🟠 Off-track — slipped from top quartile to bottom half over last 12 months" |
| Risk-o-meter (regulatory) | Kept (mandatory) + plain-English interpretation alongside |

**Data is the *evidence*, not the *product*.** Available on tap, not pushed.

## 3.3 The CRED-style hook

Free → Emotional → Upsell.

| Stage | CRED equivalent | DhanRadar equivalent |
|---|---|---|
| Free hook | Credit score check | Portfolio health score (CAS upload, 60s analysis) |
| Emotional moment | "Your score went up by 15 points" | "3 of your 7 funds are 🔴 Out-of-form" |
| Curiosity | "Why?" / "How?" | Detailed scheme-by-scheme breakdown (gated for free) |
| Upsell | CRED Max credit card | Pro tier with real-time alerts + AI co-pilot + AA-linked auto-sync |

**Critical constraint:** the free analyser must be *useful enough to share*, not crippled. Free = the report. Pro = the *changes* and *alerts* and *AI*.

## 3.4 Behavioral coaching as a distinct pillar

Not a "community feature." A first-class product surface.

| Trigger | Coaching intervention |
|---|---|
| User checks portfolio >5 times/day during a market drop | "Markets fluctuate. Your goal is 7 years away. Here's what happened in 2008, 2020." |
| User adds 8th MF in same category | "You already hold 3 large-cap funds with 67% overlap. Adding this won't increase diversification." |
| User searches "best fund 2026" | "There is no single 'best.' Here's how to evaluate vs your goal." |
| User about to redeem during a 10%+ drawdown | "This is the bottom-quartile worst month for this category. Historically, redeeming here has hurt 7Y CAGR by X%." |

### Why it differentiates

- PowerUp doesn't have this
- Groww/ET Money optimise for transaction completion (commission revenue)
- A platform that *talks users out of bad decisions* builds the strongest trust and lowest churn

### Data requirement

Behavioral nudges require event-stream logging of user actions, not just CRUD on portfolio table. Add this to the DharRadar event-tracking middleware (already exists for gamification in v2.1 §10.1) — reuse the same pipeline.

## 3.5 Real-time cadence as a wedge

| Competitor | Rating cadence | DhanRadar cadence |
|---|---|---|
| PowerUp | Monthly | Daily + event-triggered |
| Morningstar | Quarterly | Daily + event-triggered |
| Value Research | Monthly | Daily + event-triggered |
| Manual research | Ad hoc | Push alerts |

Event triggers that change a fund's label:
- Fund manager change
- AUM crossing thresholds (concentration risk)
- Style drift detected
- Drawdown breaches category median
- New SEBI circular affects category

This is technically free for DhanRadar — DharRadar v2.1 already has the batch + alert infrastructure. Repurpose `celery-social` queue patterns for fund-event alerts.

---

# Part 4 — Strategic Wedges

> "Compete horizontally with Groww" is not a strategy. These are.

## 4.1 Vertical wedge options

| Wedge | Size | Why it fits Manish | Why it converts |
|---|---|---|---|
| Cybersecurity professionals | ~500K in India, ₹15L+ CTC | Existing brand from IntelWatch / SOC background; trusted in community | High income, high anxiety about market, value explainability |
| NRIs (US/UK/UAE) | ~30M globally, large MF AUM | Underserved by all majors due to FATCA/CRS complexity | High willingness to pay; English-comfortable; remote-friendly |
| FIRE community (India) | ~50K active, growing | Aligns with educational positioning | Highest LTV; long retention; community-led growth |
| Tier-2 doctors/CAs | ~2M | Existing trust in professionals; under-served by digital wealthtech | Word-of-mouth strong; lower CAC |

### Recommended: cybersec wedge first

- Lowest CAC (Manish's existing network)
- Highest credibility match
- Validates rating engine before scaling

NRI wedge as Phase 2 — bigger TAM but needs FATCA/CRS compliance infrastructure.

## 4.2 DharRadar infrastructure reuse map

DharRadar v2.1 and DhanRadar share ~70% infrastructure. This is the single biggest economic lever given the 2-hours/day constraint.

| Component (from DharRadar v2.1) | Reuse for DhanRadar | Modification needed |
|---|---|---|
| LLM Gateway (§6) | Same — multi-model routing | Add MF-specific prompts to registry |
| Redis cache (§3.1) | Same — replace `picks:` namespace with `mf:` | Key conventions identical |
| PostgreSQL primary + replica (§3.2) | Same instance, separate schemas | New tables only |
| Prometheus + Grafana + Loki (§5) | Same observability stack | Add MF-specific dashboards |
| Celery workers (§7.1 §10.1) | Same — add `mf-batch`, `mf-alerts` queues | New tasks, same pattern |
| FastAPI Depends() DI (§7.1) | Same | Add MF service classes |
| JWT auth + 2FA (§4) | Same | Single SSO across both products |
| PostHog feature flags (§8.2) | Same | Cross-product experiments |
| k6 load testing (§6.2) | Same | New test scripts |
| Pillow share cards (§10.2) | Same — MF rating cards instead of stock picks | Template change only |
| Gamification engine (§10.1) | Same — adapt badges to MF behaviors | "SIP Streaker" already maps |
| Onboarding flow (§9.2) | Same 5-step pattern, different content | Risk profile reused as-is |
| Consent layer (§9.1) | Same | New consent purposes added |

### Cost impact

DhanRadar Phase 1 incremental cost over DharRadar baseline (₹9,744/month): roughly **₹2,000–3,000/month** for MF-specific AI batches and storage. Combined platform stays under ₹13,000/month — within Manish's original ₹15,000 budget for either product alone.

## 4.3 Open-sourcing the methodology

Counterintuitive but powerful moat.

**Publish:**
- The rating algorithm criteria (what makes a fund 🟢 vs 🟠)
- The Market Mood Index components and weights
- Backtests of the rating system over 10 years
- Code for the deterministic parts (not the LLM prompts)

**Keep proprietary:**
- The data pipeline (AA integration, real-time NAV processing)
- The AI prompts and tuning
- User behavior data
- The label cadence and trigger logic
- Operational excellence (uptime, latency)

### Why it works

- Builds institutional trust (analysts can audit the methodology)
- SEBI views transparency favorably
- Differentiates from black-box competitors
- Cost of replication is high even with published methodology (data + ops + brand)

## 4.4 ONDC Financial Services as future channel

ONDC for financial products is coming online (timelines fluid). Could become a distribution rail that bypasses CAC entirely.

**Not a build-now item.** A track-and-evaluate item. Monitor quarterly.

---

# Part 5 — AI Governance

> Neither prior doc discussed adversarial testing of the rating engine. This is the highest-severity unaddressed risk.

## 5.1 The trust collapse risk

A single bad recommendation that goes viral on Twitter/Reddit can end a wealthtech brand. Recent examples (anonymised): multiple robo-advisors lost 40–80% of users post-2022 over isolated bad calls amplified by social media.

### Failure modes to test

| Failure mode | Adversarial test | Guardrail |
|---|---|---|
| Hallucinated scheme name | Ask AI about a non-existent fund | Strict schema validation; deny non-DB tickers |
| Outdated data presented as current | Query about a fund that closed/merged | `valid_until` on all responses; staleness checks |
| Confidently wrong | Prompt with leading question | Confidence label mandatory; "I don't know" must be allowable output |
| Recommendation drift | Same query, ratings flip every week without underlying change | Hysteresis on rating transitions (require 2 consecutive evaluations to flip) |
| Cohort bias | Rating system favours large-AUM funds (survivorship bias) | Backtest including dead/merged funds; flag if alpha drops |
| Adversarial prompts | "Pretend you're an unregulated advisor" | System prompt + output filter; refuse + log |
| Confidence collapse in drawdown | All funds rated 🔴 in a market crash | Sanity check: % of universe in each label must stay within bounds |

## 5.2 Mandatory governance artefacts

1. **Rating engine changelog.** Every methodology change versioned, dated, justified. Public.
2. **Adversarial test suite.** 100+ test cases run on every model/methodology update. Block deploy on regression.
3. **Human review gate.** Any time >5% of funds change label in a single batch, human review before publish.
4. **Confidence floor.** No public-facing rating with confidence below threshold. Default to "Insufficient data" label.
5. **Append-only audit log.** Every rating, every user-facing AI output, retained 5 years. Required for RIA path; good hygiene regardless.
6. **Disagreement disclosure.** If two underlying signals contradict, show both. Don't hide uncertainty.

## 5.3 Pre-launch red-team checklist

| Test | Pass criterion |
|---|---|
| Run 1000 rating queries; check for hallucinations | <0.1% hallucination rate |
| Compare ratings to Value Research / Morningstar historical | Directionally aligned >80% of overlapping coverage |
| Backtest rating-following strategy over 10 years | Beats benchmark before fees |
| Stress-test during 2008, 2020 crash periods | No systemic failure modes |
| Adversarial prompt suite | 100% refusal rate on out-of-scope requests |
| Latency under load | p99 < 500ms at 10× expected load |

---

# Part 6 — Build vs Partner Decision

The unspoken assumption in all existing docs is "build everything." That may not be optimal.

| Decision | Build | Partner | Hybrid (recommended) |
|---|---|---|---|
| RIA registration | Year 3 | Year 1 (partner with existing RIA) | Partner Y1; own RIA from Y3 |
| AA integration | Year 2 | Year 1 (Setu/Finvu BaaS) | Always partner — no advantage to building |
| KYC | Never | Always (Karza / Digio / IDfy) | Always partner |
| CAS parsing | Year 1 | Year 1 (Pinelabs / Karza offer this) | Build to control quality |
| Rating engine | Always build | Never | Build — this is the IP |
| AI infrastructure | Build (DharRadar already has) | — | Reuse DharRadar |
| Payment | Razorpay | Razorpay | Always partner |
| Notification (Telegram/email) | Build | — | Build (free, simple) |

### Recommended Year-1 stance

Build the rating engine + AI layer + UX. Partner everything else. Time saved: 6–9 months. Cost saved: ₹15–25 lakh.

---

# Part 7 — 90-Day Execution Plan (Outline)

> Detailed plan to be written separately. This is the outline shape.

| Days | Focus | Key deliverables |
|---|---|---|
| 1–15 | Foundation | Legal entity confirm, choose RIA path (recommend Path 1 — pure education), DharRadar infra fork for DhanRadar |
| 16–30 | Rating engine v1 | Deterministic rating algorithm coded, backtested, published methodology page |
| 31–45 | Data ingestion | AMFI NAV pipeline (TimescaleDB), CAS parser, initial fund universe |
| 46–60 | UX | Free portfolio analyser (CAS upload → 60s rating report) — the CRED-style hook |
| 61–75 | Beta launch | Cybersec community soft launch, 100 beta users, feedback loop |
| 76–90 | Iterate | Add Telegram alerts, real-time rating change notifications, prep for public launch |

Assumes 2 hours/day = ~180 hours over 90 days. Aggressive but feasible if scope held to above.

---

# Appendix A — Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| SEBI enforcement against unregistered advice | Medium | High | Path 1 strict; legal review of every user-facing string |
| DPDP non-compliance penalty | Medium | High | CMP from day one; DPO appointed at threshold |
| AA integration delays | High | Medium | CAS parser as bridge |
| Bad recommendation goes viral | Medium | Catastrophic | Governance §5; conservative confidence floors |
| Burnout from 2hr/day + DharRadar parallel | High | High | Aggressive infra reuse; honest sequencing |
| CAC overruns | High | High | Cybersec wedge first; defer paid acquisition |
| LLM API cost spike | Medium | Medium | Existing DharRadar budget caps; same gateway |
| Founder regulatory risk (personal liability as Principal Officer) | Medium | High | Partner-RIA model removes this initially |

---

# Appendix B — Open Decisions

These are explicit "must decide before Phase 1 build" questions:

1. **Pure education (Path 1) or partner RIA (Path 3) for Year 1?** Default recommendation: Path 1. Document the line you will not cross.
2. **Cybersec wedge or NRI wedge first?** Default: cybersec (lower CAC, faster validation).
3. **Build CAS parser or buy?** Default: build (quality control matters for the hook product).
4. **Telegram-first or email-first for alerts?** Default: Telegram (faster delivery, free, fits Indian retail).
5. **Open-source methodology — yes or no?** Default: yes, after Year 1 once stable.
6. **Combined DharRadar + DhanRadar brand, or separate?** Default: separate brands, shared infrastructure. Cleaner positioning.

---

# Document control

| Version | Date | Changes |
|---|---|---|
| 1.0 | May 2026 | Initial addendum — reality layer covering regulatory, unit economics, UX taxonomy, AI governance, strategic wedges, build-vs-partner |

**Pairs with:** DhanRadar Master Blueprint v1.0, DharRadar Architecture v2.1
**Does not replace:** Any existing doc — fills explicit gaps only.
**Next deliverable:** 90-day execution plan with daily 2-hour allocation.
