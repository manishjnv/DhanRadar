/**
 * DriverFactorList — COMPLIANCE-CRITICAL "Supporting / Counterweights" driver bars.
 *
 * Renders each mood driver factor as a label + a NUMBERLESS magnitude bar whose
 * fill reflects a coarse 3-way tier ("strong" | "moderate" | "slight") computed
 * server-side. ABSOLUTELY NO number, percentage, weight, or raw contribution is
 * shown or implied (non-neg #2): the bar width is one of three discrete steps and
 * carries no value tooltip. The neutral +/− marker keeps the Supporting vs
 * Counterweight grouping without implying buy/sell (non-neg #1).
 *
 * Safe fallback: an unknown / missing tier renders the lowest (neutral) bar
 * rather than throwing or rendering a bare value.
 */

import * as React from 'react';
import type { MoodFactor } from '@/features/mood/types';

// Three DISCRETE fill widths — the only magnitude information shown. These are
// Tailwind class names, never rendered text, so no digit reaches the DOM text.
const TIER_FILL: Record<string, string> = {
  strong: 'w-full',
  moderate: 'w-2/3',
  slight: 'w-1/3',
};

export interface DriverFactorListProps {
  heading: string;
  items: MoodFactor[];
  marker: '+' | '−';
}

export function DriverFactorList({ heading, items, marker }: DriverFactorListProps) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="text-small font-medium text-ink mb-2">{heading}</p>
      <ul className="space-y-2.5">
        {items.map((item) => (
          <li key={item.label} className="text-small text-ink">
            <div className="flex items-center gap-1.5">
              <span className="text-ink-muted select-none" aria-hidden="true">
                {marker}
              </span>
              <span>{item.label}</span>
            </div>
            {/* Numberless magnitude bar — discrete tier width, no value shown. */}
            <div
              className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-surface-3"
              role="presentation"
            >
              <div
                className={`h-full rounded-full bg-royal ${TIER_FILL[item.tier] ?? TIER_FILL.slight}`}
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
