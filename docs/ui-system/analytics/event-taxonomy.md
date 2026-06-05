# Event Taxonomy

*Growth PM · Product Analytics Lead. Sink: PostHog. PII-free; identify via anon→user merge on signup. Extends contracts/analytics-events.md.*

## Conventions
- `object_action` snake_case (e.g., `recommendation_clicked`). Past-tense actions.
- Every event carries **super-properties:** `user_id?`, `anon_id`, `plan`, `platform` (web/ios/android/pwa), `session_id`, `request_id`, `app_version`, `ts`.
- Properties typed; bounded cardinality (no free-text in props).
- One canonical name per concept; no duplicates.

## Domains
| Domain | Prefix |
|---|---|
| Acquisition | `acq_` / page/referrer |
| Activation | `activation_` |
| Engagement | feature verbs |
| Retention | session_* |
| Referral | `referral_` |
| Subscription | `subscription_`/`checkout_` |
| Recommendation | `recommendation_` |
| AI | `ai_` |
| Search | `search_` |
| Portfolio | `portfolio_` |
| Alerts | `alert_` |

## Lifecycle states (user property)
`anonymous → signed_up → activated → engaged → paying → power → dormant → churned`
