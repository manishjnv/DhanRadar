# Screen — Admin Dashboard

**Purpose.** Separate audited ops shell: users, billing, content, score-model config, data health.

## Layout
Distinct admin shell (red accent). Ops KPI row. Work area: user-management table + data/model panels. Switcher to AI-Ops.

## Components
- Admin shell
- Ops KPIs
- UserMgmtTable
- DataSourceMonitor
- ScoreModelPanel

## API requirements
- `GET /v1/admin/metrics`
- `/admin/users`
- `/admin/data-sources`
- `/admin/score-model`
- `POST /admin/users/{id}/suspend|refund`

## Data model (entities)
- users
- subscriptions
- ingest_runs
- scores
- audit_log

## Loading states
KPI + table skeletons.

## Error states
Ops data unavailable → incident banner (auto-reported); destructive actions require step-up auth.

## Responsive rules
Desktop-first; tables scroll. Not optimized for mobile (internal tool).

## Analytics events
- `admin_user_view`
- `admin_user_suspend`
- `admin_refund`
- `admin_content_publish (all audited)`
