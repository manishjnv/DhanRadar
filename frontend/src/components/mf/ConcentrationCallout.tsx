/**
 * ConcentrationCallout — D1 portfolio X-ray factual concentration summary.
 *
 * Renders the top-3 categories by allocation as objective facts — no advice,
 * no advisory verbs (buy/sell/hold/switch/exit/avoid/rebalance). Lives inside
 * the Category Allocation card body, below the AllocationDonut.
 *
 * Compliance: non-neg #1 (no advisory), #2 (no numeric scores), #9 (disclosure
 * is on the page-level DisclosureBundle — not duplicated here).
 */

import * as React from 'react';
import type { AllocationSlice } from '@/features/mf/types';

export interface ConcentrationCalloutProps {
  allocation: AllocationSlice[];
}

export function ConcentrationCallout({ allocation }: ConcentrationCalloutProps) {
  const top3 = [...allocation].sort((a, b) => b.pct - a.pct).slice(0, 3);
  const dominant = top3[0];

  if (!dominant) return null;

  return (
    <div className="mt-4 pt-4 border-t border-line">
      <p className="text-caption font-bold tracking-widest uppercase text-ink-muted mb-2">
        Concentration
      </p>
      <ul className="flex flex-col gap-1.5">
        {top3.map((s) => (
          <li key={s.category} className="flex items-center justify-between text-small">
            <span className="text-ink">{s.category}</span>
            <span className="tabular-nums font-medium text-ink">
              {s.pct.toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
      {dominant.pct > 50 && (
        <p className="mt-2 text-caption text-ink-muted">
          {dominant.category} makes up more than half your portfolio.
        </p>
      )}
    </div>
  );
}
