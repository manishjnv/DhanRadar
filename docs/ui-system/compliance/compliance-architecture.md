# DhanRadar — Compliance Architecture

*Prepared by: SEBI Compliance Consultant · Fintech Legal Architect · Product Compliance Lead. Informational, not legal advice — validate with retained Indian securities counsel before launch.*

## 1. Core stance: Research, not Advisory
DhanRadar is a **research analytics + education platform**. It is **not** an investment adviser and does **not** provide personalized investment advice. Two SEBI regimes are relevant:
- **SEBI (Investment Advisers) Regulations, 2013 (RIA)** — triggered by *personalized advice for consideration*. We deliberately do **not** do this.
- **SEBI (Research Analysts) Regulations, 2014 (RA)** — triggered by *publishing research reports / "buy/sell/hold" recommendations on securities to the public*.

> **Determination required (P0):** Our Score "signal bands" (Strong Buy…Avoid) may be construed as RA-style recommendations. **Engage counsel; register as / partner with a SEBI-registered Research Analyst before publishing rated signals, OR reframe to non-recommendatory analytics.** This is a launch gate.

## 2. Research vs Advisory separation (architecture)
| Allowed (Research/Education) | Prohibited (Advisory) without RIA |
|---|---|
| Objective scores, factor analytics, screeners | "You should buy X" / personalized to a user's goals |
| Generic education, methodology disclosure | Tailored portfolio construction for a fee |
| Fair-value estimates with methodology | Assurance of returns |
| Portfolio **observations** (concentration, drift) | Portfolio **instructions** (sell X, buy Y) |

**Technical separation:**
- A code-level **boundary**: the recommendation/scoring engine is non-personalized; no user goals/risk-profile feed the Score. Personalization is limited to *filtering/surfacing* public analytics, never altering the analytic itself.
- All "signal" copy is **band-descriptive** ("Score 86 — Strong Buy band"), with a persistent "not advice" disclaimer.
- A **Compliance Gate service** wraps any user-facing recommendation/AI output: injects disclosures, blocks advice-pattern language, logs to the audit trail.

## 3. SEBI considerations (checklist)
- RA applicability determination + registration/partnership (P0).
- If RA: research-report format, disclosures of conflicts/holdings, past-performance disclaimers, RA reg number on reports.
- Advertisement Code adherence (no performance promises, balanced view, risk warnings).
- KYC obligations only if we ever handle securities/funds (we do not — execution is on the user's broker).
- Grievance redressal + SCORES integration if RA/RIA registered.

## 4. Suitability & risk profiling
Even as research, we capture a **risk profile** to (a) tailor *education and surfacing* (not advice), (b) gate risk-appropriate content warnings, (c) evidence good-faith user protection. See `risk-profiling-engine.md`. **The profile never changes a Score** (preserves research/advisory separation).

## 5. Recommendation framework
See `recommendation-disclosure-framework.md`: every surfaced signal carries methodology link, confidence, sources, "not advice", and (if RA) analyst disclosures.

## 6. Disclosures, disclaimers, T&C, Privacy
See `disclaimer-framework.md` and `legal-requirements.md`. DPDP-aligned privacy, consent framework, retention.

## 7. Audit & evidence
See `audit-trail-spec.md`: immutable, hash-chained record of every recommendation shown, its inputs, model version, disclosures rendered, and user acknowledgements — for regulatory defensibility.

## 8. AI-specific compliance
AI never advises. Every AI output: "AI-generated, informational, not advice", grounded + cited, confidence-bounded, and logged. Prohibited-language classifier blocks advisory phrasing pre-render.

## 9. Governance
- Named **Compliance Officer**; compliance review gate on any change to scoring copy, signal bands, AI prompts, or disclosures.
- Quarterly compliance audit; legal review of advertisements; incident process for mis-statements.
