# RecommendationCard

**Purpose.** Signature surface — Score, signal, fair-value target, and a plain-English reason. Never a signal without a why.

## States
- default
- loading (skeleton)
- expanded (full explainability)
- added (success)
- low-confidence (caveat shown)

## Variants
- grid (desktop 2-up)
- stacked (mobile)
- compact (dashboard)
- with bull/bear toggle

## Props (TypeScript)
```ts
interface RecCardProps { instrument: Instrument; score: number; signal: Signal; target: number; reason: string; confidence: number; sources: Source[]; onAdd: ()=>void; onExplain: ()=>void; }
```

## Accessibility
- Signal conveyed by label + color + icon
- reason text is real content (not decorative)
- "Why 86?" is a button → AI explain
- confidence has text equivalent

## Responsive behavior
2-up grid desktop → 1-up mobile. Reason box always present at every size.

## Implementation notes
The reason box is non-negotiable (brand promise). Confidence + sources attach per the AI contract: answer→reasoning→confidence→sources. "Not advice" disclaimer in footer.

## React mapping
```tsx
<RecommendationCard instrument={i} score={86} signal="strong_buy" target={3120} reason={r} confidence={78} sources={s} onAdd={...} onExplain={...} />
```

## Tailwind mapping
card `bg-surface border border-line rounded-xl`; reason `bg-bg-alt rounded-lg p-3 text-sm text-ink-2`
