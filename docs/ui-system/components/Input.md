# Input

**Purpose.** Text/number/select/range/toggle form controls with validation states.

## States
- default
- focus (blue ring)
- filled
- error (red border + message)
- disabled
- readonly

## Variants
- text
- email
- password
- number (mono)
- select
- range/slider
- toggle

## Props (TypeScript)
```ts
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> { label?: string; error?: string; hint?: string; leftIcon?: ReactNode; }
```

## Accessibility
- <label> tied via htmlFor/id
- error via aria-describedby + role=alert live region
- ≥16px font (prevents iOS zoom)
- toggle is a real checkbox/switch with aria-checked

## Responsive behavior
Single column on mobile; two-up on desktop forms. Full-width inputs.

## Implementation notes
Integrate with react-hook-form + Zod resolver. Numeric inputs use --font-mono with tnum.

## React mapping
```tsx
<Input label="Email" type="email" error={errors.email?.message} {...register('email')} />
```

## Tailwind mapping
`h-10 px-3 bg-surface border border-line-strong rounded-md text-ink focus:border-blue focus:ring-2 focus:ring-blue/20`
