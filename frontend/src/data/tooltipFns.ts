/**
 * tooltipFns.ts — the dynamic chart tooltips (UI_DATA_ARCHITECTURE_PLAN.md §28.3/§28.5/§28.7).
 *
 * Static tooltips live as strings in components.json (grep-coverable for #1/#2). A `tooltip_fn`
 * can't be JSON, so the FEW dynamic ones (the two real data-point charts) live here, typed
 * `(pt: SafePoint) => string`. They are compliant BY CONSTRUCTION: `SafePoint` has no
 * `score`/`weight`/`fairValue` key to interpolate, so a tip cannot leak a DhanRadar composite
 * score (#2). `ownValue` is the user's OWN number (₹ / %), which is #2-exempt. Keep this map
 * tiny — only charts whose component sets `has_tooltip_fn: true` in the manifest.
 */
import type { SafePoint } from './envelope';

export const tooltipFns: Record<string, (pt: SafePoint) => string> = {
  // Allocation donut segment — the user's own share of their own portfolio.
  allocation_donut: (pt) => `${pt.label}: ${pt.ownValue ?? '—'} of your portfolio.`,
  // Return-over-time area point — the user's own annualised return at a date.
  xirr_area: (pt) => `${pt.label}: ${pt.ownValue ?? '—'} per year.`,
};
