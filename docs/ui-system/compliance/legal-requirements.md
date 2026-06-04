# Legal Requirements — T&C, Privacy, Consent, Retention

## Terms & Conditions (must include)
- Nature of service: **research/education, not advice**; no RIA relationship; no assured returns.
- Eligibility (18+, Indian residents for certain features), account rules, acceptable use.
- IP ownership (Scores, content proprietary); API/usage limits; subscription terms (billing, trial, cancellation, refunds, GST).
- Limitation of liability; "as-is"; market-risk acknowledgement; indemnity.
- Third-party data disclaimer (vendor accuracy); broker/AA relationship (we don't execute).
- Governing law (India), dispute resolution, grievance redressal contact.
- Changes-to-terms process + notice.

## Privacy Policy (DPDP-aligned)
- Data collected (account, usage, holdings via AA, AI interactions) + purposes.
- Legal basis = **consent** (purpose-bound, granular); how to withdraw.
- Sharing: processors (cloud, email/SMS, LLM, payments) under DPAs; no sale of personal data.
- Rights: access, correction, **export, erasure**; grievance officer + SLA.
- Security measures; breach notification; cross-border processing disclosure; cookies.
- Children: not directed at <18; no knowing collection.

## User Consent Framework
- **Layered consent** at signup: T&C + Privacy (required); marketing (off default); "use my portfolio for insights" (off default); AI training on anonymized interactions (off default).
- AA consent separate (purpose, data types, duration, frequency, revocation).
- Each consent: recorded with timestamp + policy version; re-consent on material policy change.
- Consent ledger: `consents(user_id, type, granted, version, ts)`.

## Data Retention (summary)
| Data | Retention |
|---|---|
| Account/PII | life of account + statutory tail; erasable |
| Recommendation evidence | ≥5y (confirm) WORM |
| Audit log | 400d hot + WORM |
| AI interactions | retained; exportable; consent-gated training |
| Marketing data | until opt-out |
| Backups | per backup policy; erasure honored on restore |

*All periods to be confirmed with counsel against current SEBI/DPDP rules.*
