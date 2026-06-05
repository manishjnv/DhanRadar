# Watchlist

**Purpose.** Track a set; row shows logo, sparkline, price/change, live Score, alert toggle. Multiple lists.

## States
- default
- loading
- empty (cold-start CTA)
- optimistic add/remove
- alert-toggling

## Variants
- desktop table
- mobile list (sparkline drops on narrow)
- compact (dashboard widget)

## Props (TypeScript)
```ts
interface WatchlistProps { lists: Watchlist[]; activeListId: string; onAdd: ()=>void; onToggleAlert: (sym)=>void; }
```

## Accessibility
- List switcher as tabs (role=tablist)
- alert toggle = switch with aria-checked
- row → instrument link keyboard-reachable
- swipe actions have button equivalents

## Responsive behavior
Desktop table; mobile rows with swipe-for-alert/remove; sparkline hidden < 360px to keep numbers legible.

## Implementation notes
Optimistic updates (instant UI, rollback on error). Backed by /watchlists + /alerts. Live Score via SSE invalidation.

## React mapping
```tsx
<Watchlist lists={lists} activeListId={id} onAdd={openSearch} onToggleAlert={mutate} />
```

## Tailwind mapping
row `flex items-center gap-3 py-3 border-b border-line`
