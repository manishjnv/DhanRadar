# Screen — Watchlist

**Purpose.** Track a set; spot moves; act fast. Multiple lists, sparkline + live Score + quick alerts.

## Layout
List switcher chips. Table: instrument · sparkline · price/change · Score · alert toggle. Add primary action.

## Components
- ListSwitcher
- WatchlistTable
- Add
- swipe actions (mobile)
- Empty/Loading

## API requirements
- `GET /v1/watchlists`
- `/{id}/items`
- `POST/DELETE items`
- `POST /v1/alerts`

## Data model (entities)
- watchlists
- watchlist_items
- alert_rules
- instruments
- scores

## Loading states
Skeleton rows.

## Error states
Inline retry; optimistic add rolls back on failure with a toast.

## Responsive rules
Table → mobile rows; sparkline hidden <360px; swipe-for-alert/remove.

## Analytics events
- `watchlist_view`
- `watchlist_add`
- `watchlist_remove`
- `alert_toggle`
