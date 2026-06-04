# Screen — Recommendation Hub

**Purpose.** Curated scored ideas; every card carries signal + plain-English reason + confidence.

## Layout
Sticky filter chips (signal + sector). 2-up grid of RecommendationCards. Pagination.

## Components
- FilterChips
- RecommendationCard
- Pagination
- Empty/Loading

## API requirements
- `GET /v1/recommendations?signal=&sector=`
- `POST /v1/watchlists/{id}/items`
- `GET /v1/ai/explain/{symbol}`

## Data model (entities)
- scores
- instruments
- watchlist_items
- ai_messages

## Loading states
Card skeletons (header + body + footer placeholders).

## Error states
Inline error card with retry; preserves applied filters.

## Responsive rules
2-up → 1-up. Filter chips horizontally scroll on mobile. FAB for quick-add on Android.

## Analytics events
- `rec_view`
- `rec_filter`
- `rec_add_watchlist`
- `rec_why_click`
