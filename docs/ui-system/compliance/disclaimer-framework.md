# Disclaimer Framework

Centralized, versioned disclaimer strings rendered by the Compliance Gate. IDs let the audit trail record exactly what each user saw.

## Standard disclaimers (versioned)
- `DISC_NOT_ADVICE` (global, all rec/AI surfaces):
  > "Informational only. DhanRadar is a research analytics platform, not an investment adviser. This is not investment advice. Investments are subject to market risks; read all related documents carefully."
- `DISC_AI` (AI outputs):
  > "✦ AI-generated and informational. May be incomplete or inaccurate. Not investment advice."
- `DISC_PAST_PERF` (returns/history):
  > "Past performance does not guarantee future results."
- `DISC_FAIR_VALUE` (fair value):
  > "Fair-value estimates are model-based, carry assumptions, and may be wrong. Not a price target recommendation."
- `DISC_DATA` (data surfaces):
  > "Data from third-party providers; accuracy/timeliness not guaranteed."
- `DISC_RA` (only if RA-registered):
  > "Prepared by [Name], SEBI Research Analyst Reg. No. [____]. [Conflict/holding disclosures]."

## Placement matrix
| Surface | Disclaimers |
|---|---|
| Recommendation card / signal | NOT_ADVICE (+ RA if applicable) |
| AI search/assistant/explain | AI + NOT_ADVICE |
| Fair value | FAIR_VALUE + NOT_ADVICE |
| Score history / returns | PAST_PERF |
| Any data table/chart | DATA (footnote) |
| Onboarding | NOT_ADVICE acknowledgement (logged) |
| Footer (all pages) | NOT_ADVICE (short) |
| Emails | NOT_ADVICE (footer) |

## Rules
- Disclaimers are **non-dismissible context**, not modals to click away (except the one onboarding acknowledgement, which is logged).
- Version bump → re-render + re-log; never silently change legal text.
