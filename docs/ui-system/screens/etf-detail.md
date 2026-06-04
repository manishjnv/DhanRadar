# Screen — ETF Detail

**Purpose.** ETF analysis bridging stock+fund: price/iNAV, tracking error, expense, liquidity, index, holdings.

## Layout
Header + buy/watch. Split: price-vs-iNAV chart + ETF Score. ETF-KPI row. Lower split: index breakdown + holdings.

## Components
- ETFHeader
- Price/iNAV overlay chart
- ScorePanel
- ETF-KPIs
- IndexBreakdown
- HoldingsTable

## API requirements
- `GET /v1/etfs/{sym}`
- `/inav`
- `/holdings`
- `/index-breakdown`
- `/score`

## Data model (entities)
- instruments(type=etf)
- instrument_prices
- scores
- holdings(constituents)

## Loading states
Chart + KPI skeletons.

## Error states
iNAV delayed → show LTP with delayed badge; retry.

## Responsive rules
Split → stacked; KPI row 4→2 cols.

## Analytics events
- `etf_view`
- `inav_toggle`
- `holding_drill`
