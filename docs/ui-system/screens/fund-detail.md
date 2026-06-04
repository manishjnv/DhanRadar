# Screen — Mutual Fund Detail

**Purpose.** Fund research that fights recency bias: Score, NAV, rolling returns, risk metrics, holdings, manager.

## Layout
Header + SIP CTA. Split: NAV chart + Fund Score. Lower split: rolling-returns table + fund details/holdings/manager.

## Components
- FundHeader
- NAVChart
- ScorePanel
- RollingReturnsTable
- FundDetails
- SIP CTA + modal

## API requirements
- `GET /v1/funds/{sym}`
- `/nav-history`
- `/rolling-returns`
- `/score`
- `POST /v1/sip (premium)`

## Data model (entities)
- instruments(type=fund)
- instrument_prices(NAV)
- scores

## Loading states
NAV chart skeleton; rolling-returns rows shimmer.

## Error states
Coverage-missing → empty state with "request coverage"; data fetch error → retry.

## Responsive rules
Split → stacked. SIP CTA sticky at bottom on mobile.

## Analytics events
- `fund_view`
- `rolling_return_period`
- `sip_start`
- `sip_confirm`
