# Card

**Purpose.** Workhorse surface. 16px radius, hairline border, theme-aware. KPI / instrument / content variants.

## States
- default
- hover (optional lift)
- selected
- loading (skeleton)
- interactive (whole-card link)

## Variants
- base
- kpi
- instrument
- feature (marketing)
- elevated (shadow-md)
- android-tonal (mobile)

## Props (TypeScript)
```ts
interface CardProps { as?: ElementType; interactive?: boolean; elevation?: 'none'|'sm'|'md'; className?: string; children: ReactNode; }
```

## Accessibility
- If interactive, wrap a single primary <a>/<button>; do not nest interactive elements
- Heading inside uses correct level
- Sufficient contrast of border in dark mode

## Responsive behavior
Grids reflow 4→2→1 (desktop→tablet→mobile). KPI cards become single-column rows on narrow mobile.

## Implementation notes
Composed of CardHeader/CardBody/CardFooter sub-parts. Surface color = var(--surface); border = var(--border).

## React mapping
```tsx
<Card><CardHeader title="Holdings"/><CardBody>{...}</CardBody></Card>
```

## Tailwind mapping
`bg-surface border border-line rounded-xl overflow-hidden`
