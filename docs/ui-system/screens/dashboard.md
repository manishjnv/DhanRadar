# Screen — Dashboard

**Purpose.** Daily signed-in home. Answers "what changed?" + "what should I look at?" at a glance.

## Layout
AppShell (sidebar+topbar). Row 1: 4 index KPIs. Row 2: top-scored table (wide) + news/heatmap stack. Footer strip: portfolio snapshot + learning streak.

## Components
- AppShell
- IndexKPI ×4
- TopScoredTable
- NewsList
- SectorHeatmap
- PortfolioSnapshot
- Skeleton/Empty/Error

## API requirements
- `GET /v1/indices`
- `GET /v1/instruments/top-scored`
- `GET /v1/news?scope=market`
- `GET /v1/portfolio/summary`
- `GET /v1/sectors/heatmap`

## Data model (entities)
- instruments
- scores
- instrument_prices
- news
- holdings

## Loading states
Per-widget skeletons (independent React Query). KPIs show shimmer bars; table shows 5 skeleton rows.

## Error states
Per-widget error card with retry; one widget failing never blanks the page.

## Responsive rules
4-col KPIs → 2-col → single-row cards. Two-column body → stacked on mobile. Sidebar → bottom tab bar.

## Analytics events
- `dashboard_view`
- `top_scored_click`
- `widget_customize`
- `heatmap_sector_click`
