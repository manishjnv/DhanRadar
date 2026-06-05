# Button

**Purpose.** Primary interaction primitive. One component, many variants via props.

## States
- default
- hover
- focus-visible (3px blue ring)
- active
- disabled (opacity .5, no pointer)
- loading (spinner, aria-busy)

## Variants
- primary (Electric Blue)
- dark (high-emphasis neutral)
- ghost
- outline
- success
- danger
- sizes: sm / md / lg
- iconOnly (44×44 min)

## Props (TypeScript)
```ts
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary'|'dark'|'ghost'|'outline'|'success'|'danger';
  size?: 'sm'|'md'|'lg';
  loading?: boolean;
  leftIcon?: ReactNode; rightIcon?: ReactNode;
  asChild?: boolean; // Radix Slot for <a> semantics
}
```

## Accessibility
- Native <button>; type set explicitly
- focus-visible ring never stripped
- aria-busy when loading; disabled communicated to AT
- iconOnly requires aria-label
- ≥44×44 touch target on mobile

## Responsive behavior
Full-width (justify-center, h-46) on mobile primary actions; inline on desktop. Stacks vertically in mobile button groups.

## Implementation notes
Use cva for variant classes + tailwind-merge to dedupe. Never hardcode colors — use token utilities (bg-blue, text-ink).

## React mapping
```tsx
<Button variant="primary" size="md" leftIcon={<Plus/>} onClick={...}>Add to Watchlist</Button>
```

## Tailwind mapping
`bg-blue text-white rounded-md px-4 py-2 font-semibold shadow-sm hover:bg-blue-700 focus-visible:ring-2 focus-visible:ring-blue/40`
