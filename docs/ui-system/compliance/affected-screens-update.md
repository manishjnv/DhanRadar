# Affected Screens — Compliance Updates

Compliance changes to apply across the already-designed screens (design system unchanged; these are content/behavior additions).

| Screen | Update |
|---|---|
| **Onboarding** | Add optional **risk-profiling questionnaire** (skippable); capture T&C/Privacy consent + NOT_ADVICE acknowledgement (logged); granular consent toggles (marketing/insights/AI-training off by default). |
| **Stock/Fund/ETF Detail** | Signal reframed to band-descriptive ("Score 86 · Strong Buy band"); persistent NOT_ADVICE; methodology link on score; DATA footnote on charts; FAIR_VALUE disclaimer on fair value; PAST_PERF on score history. |
| **Recommendation Hub** | Each card: disclosure bundle (methodology, confidence, sources, NOT_ADVICE). Reason box stays; no imperative language. |
| **AI Search / Assistant / Explain** | AI tag + AI disclaimer on every output; prohibited-language gate; sources + confidence; "not advice" persistent. |
| **Portfolio / Insights** | Insights framed as **observations** (never instructions); risk warnings tuned to risk profile; NOT_ADVICE. |
| **Watchlist / Alerts** | Alert notifications carry NOT_ADVICE; no "act now" urgency. |
| **Subscription** | GST-inclusive pricing + breakdown; refund/cancellation terms; invoice immutability. |
| **Settings** | Consent management center (view/withdraw consents, export/erase data, manage AA consent, risk-profile retake). |
| **Footer (all)** | Short NOT_ADVICE + links to T&C, Privacy, Disclosures, Methodology, Grievance. |
| **Emails** | NOT_ADVICE footer; unsubscribe; grievance contact. |
| **New: Methodology (public)** | Already in IA — ensure it discloses score construction (research methodology disclosure). |
| **New: Disclosures / Grievance page** | Add to footer + legal. |

**Engineering:** all rendered via the **Compliance Gate** service + versioned disclaimer strings so the audit trail logs exactly what each user saw.
