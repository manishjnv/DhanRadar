# Table

**Purpose.** Dense data display with mono numbers, sortable headers, row hover. Collapses to cards on mobile.

## States
- default
- sorted (asc/desc indicator)
- row-hover
- loading (skeleton rows)
- empty
- error

## Variants
- standard
- compact
- card-list (mobile)
- virtualized (long lists)

## Props (TypeScript)
```ts
interface TableProps<T> { columns: Column<T>[]; data: T[]; sort?: SortState; onSort?: (key)=>void; rowHref?: (row:T)=>string; loading?: boolean; }
```

## Accessibility
- Native <table>/<thead>/<tbody>; <th scope="col">
- sort state via aria-sort
- row links keyboard-reachable
- caption or aria-label describing the table

## Responsive behavior
Below md, transform rows into stacked cards (no horizontal scroll for core data). Use @tanstack/virtual for >100 rows.

## Implementation notes
Numeric cells right-aligned, --font-mono, tnum. Server-side sort/paginate for large sets.

## React mapping
```tsx
<Table columns={cols} data={stocks} sort={sort} onSort={setSort} rowHref={r=>`/stocks/${r.symbol}`} />
```

## Tailwind mapping
`w-full text-sm` · th `text-[10px] uppercase tracking-wide text-ink-muted font-mono`
