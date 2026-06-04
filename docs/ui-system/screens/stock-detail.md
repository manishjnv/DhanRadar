# Screen — Stock Detail

**Purpose.** Flagship research surface for one stock: Score + reasoning + price + fundamentals, AI explain from any metric.

## Layout
Breadcrumb + sticky header (actions). Split: price chart (wide) + score panel. Tabs: Overview/Financials/Peers/SWOT/Valuation. Below: pros/cons + fair value (gated).

## Components
- StockHeader
- PriceChart+PeriodSwitch
- ScorePanel(ring+FactorBars)
- Tabs
- ProsCons
- FairValueGauge(gated)
- AI-explain affordances

## API requirements
- `GET /v1/stocks/{sym}`
- `GET /v1/instruments/{sym}/score`
- `/score/history`
- `/financials`
- `/peers`
- `/fair-value (pro)`
- `GET /v1/ai/explain/{sym}`
- `POST /v1/alerts`

## Data model (entities)
- instruments
- scores
- instrument_prices
- corporate_actions
- alert_rules

## Loading states
Chart skeleton (200px), score ring placeholder, tab content skeletons. Price streams via SSE after first paint.

## Error states
If live price fails: show last-computed Score with a stale banner; chart shows retry. Never blanks the score.

## Responsive rules
Split → stacked on mobile. Tabs become a horizontally scrollable strip. Chart full-bleed.

## Analytics events
- `stock_view`
- `period_change`
- `tab_change`
- `factor_explain`
- `alert_create`
- `fairvalue_gate_hit`
