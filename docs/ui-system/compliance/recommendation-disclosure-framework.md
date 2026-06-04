# Recommendation Disclosure Framework

Every surface that shows a Score/signal/AI output must render the **disclosure bundle**.

## Mandatory elements (per recommendation surface)
1. **Signal framing:** "Score 86 · Strong Buy band" — band-descriptive, not imperative.
2. **Methodology link:** "How this score is calculated" → public Methodology page.
3. **Confidence:** band (High/Moderate/Low) once calibrated.
4. **Sources + freshness:** Source Attribution.
5. **Not-advice disclaimer:** "Informational only. Not investment advice. Markets carry risk."
6. **AI tag (if AI-generated):** "✦ AI-generated · informational" + same disclaimer.
7. **(If RA-registered):** analyst name + SEBI RA reg no. + conflict/holding disclosure + past-performance caveat.

## Compliance Gate (service)
```
renderRecommendation(payload) →
  1. assert no advisory phrasing (classifier: "you should", "we advise", "guaranteed")
  2. attach disclosure bundle
  3. log to audit trail (what was shown, inputs, model_version, disclosures, ts, user)
  4. return decorated payload
```
- Blocks render if advisory language detected → routes to safe template.

## Prohibited language (blocklist, non-exhaustive)
"you should buy/sell", "we recommend you", "guaranteed returns", "sure shot", "can't lose", "best stock to buy now (personalized)".

## Advertisement compliance
Marketing must show balanced view + risk warning; no performance promises; no testimonials implying assured returns.
