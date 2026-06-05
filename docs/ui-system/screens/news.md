# Screen — News Center

**Purpose.** Market + holding-relevant news, tagged, filterable, linked to instruments.

## Layout
Tag filter bar (incl. my holdings). Feed (wide) + side rail (trending, calendar). Each item: tag·time·headline·linked ticker.

## Components
- TagFilter
- NewsCard
- TrendingRail
- EconCalendar

## API requirements
- `GET /v1/news?tag=&scope=`
- `/news/trending`
- `/calendar`

## Data model (entities)
- news
- instruments
- holdings

## Loading states
Card skeletons; rail skeletons.

## Error states
Feed error → retry; PWA shows cached feed with offline banner.

## Responsive rules
2-col → stacked; rail moves below feed on mobile; pull-to-refresh on PWA.

## Analytics events
- `news_view`
- `news_filter`
- `news_ticker_click`
