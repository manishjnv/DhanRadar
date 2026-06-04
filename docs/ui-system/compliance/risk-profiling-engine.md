# Risk Profiling Engine

*Purpose: capture investor risk tolerance/capacity for content suitability + user protection — NOT to personalize the Score (research/advisory separation preserved).*

## Questionnaire (scored)
| # | Question | Dimension | Options→score |
|---|---|---|---|
| 1 | Age band | capacity | <30=4 …>60=1 |
| 2 | Investment horizon | capacity | <1y=1 … >7y=5 |
| 3 | Income stability | capacity | unstable=1 … very stable=5 |
| 4 | % of savings to invest | capacity | >50%=1 … <10%=5 |
| 5 | Reaction to a 20% drop | tolerance | sell all=1 … buy more=5 |
| 6 | Investing experience | tolerance | none=1 … advanced=5 |
| 7 | Goal | both | capital protection=1 … aggressive growth=5 |
| 8 | Prior loss experience | tolerance | never invested=2 … comfortable=5 |

## Scoring → profile
- Sum (8–40) → **Conservative (≤18) · Moderate (19–30) · Aggressive (31–40)**.
- Capacity vs tolerance mismatch flagged ("your tolerance is high but capacity is low") as an **educational note**, not advice.

## Use (compliant)
- **Content suitability:** high-risk instruments (small-caps, sectoral funds) show a contextual risk warning to Conservative profiles.
- **Education surfacing:** recommend *lessons*, not securities.
- **Onboarding:** optional; skippable; re-prompt annually or on major life-event toggle.
- **Hard rule:** profile is **excluded** from the scoring engine inputs (enforced by code boundary + test). It may filter *which* public analytics are surfaced, never the analytic's value.

## Data
- Stored in `risk_profiles(user_id, answers jsonb, score, profile, version, completed_at)`; versioned; consent-captured; DPDP export/erasure applies.

## Disclosures
- "This profile helps us tailor education and risk warnings. It is not investment advice and does not change any Score."
