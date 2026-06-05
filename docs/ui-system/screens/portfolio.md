# Screen — Portfolio Tracker

**Purpose.** "Is everything OK?" — aggregated value + Portfolio Score, allocation, holdings, gated analytics.

## Layout
Header (add/sync/report). Top row: value+trend (wide) + Score + allocation donut. Tabs: Holdings/Analytics(gated)/Transactions. Holdings table with per-row score.

## Components
- ValueCard+chart
- KPI(XIRR/benchmark/score)
- AllocationDonut
- Tabs
- HoldingsTable
- Add/Sync flow
- Report(async)

## API requirements
- `GET /v1/portfolio`
- `/holdings`
- `/analytics (pro)`
- `/transactions`
- `POST /v1/holdings`
- `/sync`
- `GET /v1/portfolio/report (async→S3)`

## Data model (entities)
- holdings
- transactions
- broker_links
- instruments
- scores

## Loading states
Value card + KPI skeletons; holdings skeleton rows; report shows progress.

## Error states
Sync failure → actionable error (reconnect broker); analytics gated → paywall not error.

## Responsive rules
3-col top → stacked; holdings table → card list on mobile.

## Analytics events
- `portfolio_view`
- `holding_add`
- `broker_sync`
- `analytics_gate_hit`
- `report_download`
