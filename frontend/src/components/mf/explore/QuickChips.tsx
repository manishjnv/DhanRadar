/**
 * QuickChips — V4 "Quick Discovery" (15 one-click presets).
 *
 * Single-select, single source of visual truth. A few presets map to the real
 * sort (handled by the page via onSelect); the rest are preview presets until
 * their data lands. No advisory framing (labels carry no buy/sell/hold verbs).
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import { DISCOVERY_CHIPS } from './sampleData';

export function QuickChips({
  active,
  onSelect,
}: {
  active: string | null;
  onSelect: (chip: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {DISCOVERY_CHIPS.map((chip) => {
        const isActive = active === chip;
        return (
          <button
            key={chip}
            type="button"
            onClick={() => onSelect(chip)}
            aria-pressed={isActive}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-small font-medium transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
              isActive
                ? 'bg-ink text-bg border-ink'
                : 'bg-surface border-line text-ink-secondary hover:border-royal hover:text-royal',
            )}
          >
            {chip}
          </button>
        );
      })}
    </div>
  );
}
