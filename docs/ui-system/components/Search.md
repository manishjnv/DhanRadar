# Search

**Purpose.** Global ⌘K search with autosuggest; results show logo, name, ticker, sector, live Score.

## States
- empty
- typing (debounced)
- loading
- results
- no-results
- error

## Variants
- topbar inline
- command palette (modal)
- hero (marketing)
- mobile full-width

## Props (TypeScript)
```ts
interface SearchProps { placeholder?: string; onSelect?: (instrument: Instrument)=>void; scope?: 'all'|'stocks'|'funds'; }
```

## Accessibility
- role=combobox + aria-expanded + aria-activedescendant
- arrow-key navigation of results
- results in listbox with option roles
- ⌘K hint hidden from AT / shown visually

## Responsive behavior
Full-width on mobile, ⌘K hint hidden on touch. Modal palette on desktop.

## Implementation notes
Backed by GET /instruments/search (Elasticsearch). Debounce 200ms. AI Search variant adds a grounded answer block above results.

## React mapping
```tsx
<Search scope="all" onSelect={(i)=>router.push(`/stocks/${i.symbol}`)} />
```

## Tailwind mapping
`h-9 pl-9 pr-2 bg-surface-2 border border-line rounded-lg text-sm`
