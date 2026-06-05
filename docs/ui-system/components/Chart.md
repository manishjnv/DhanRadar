# Chart

**Purpose.** Data viz family: ScoreRing, AreaChart (price/NAV), Sparkline, Donut, FactorBars, gauges.

## States
- default
- loading (skeleton)
- empty
- error
- hover (tooltip, desktop)
- count-up animation on mount

## Variants
- ScoreRing (sizes 36–200)
- AreaChart
- Sparkline
- Donut
- FactorBars
- FairValueGauge

## Props (TypeScript)
```ts
interface ScoreRingProps { score: number; size?: number; stroke?: number; }
interface AreaChartProps { data: number[]; width: number; height: number; positive?: boolean; }
```

## Accessibility
- Each chart ships a visually-hidden <table> of its data + <figcaption> takeaway
- ScoreRing aria-label="Score 86 of 100, Strong Buy"
- prefers-reduced-motion disables count-up
- color paired with label/value, never alone

## Responsive behavior
Full-bleed + simplified axes on mobile; tooltips on desktop only. SVG scales fluidly.

## Implementation notes
Use lightweight in-house SVG primitives (delivered) over heavy chart libs for bundle size. Recharts/TradingView only where interaction demands.

## React mapping
```tsx
<ScoreRing score={86} size={96} /> <AreaChart data={series} width={720} height={210} positive />
```

## Tailwind mapping
container `w-full`; colors via stroke=var(--positive)/var(--negative)
