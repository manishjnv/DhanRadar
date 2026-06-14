'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import type { Label } from '@/components/charts/ScoreRing';
import type { MfScheme } from '@/features/mf/types';

const LABEL_ORDER: Label[] = [
  'in_form',
  'on_track',
  'off_track',
  'out_of_form',
  'insufficient_data',
];

const LABEL_DISPLAY: Record<Label, string> = {
  in_form:           'In-form',
  on_track:          'On-track',
  off_track:         'Off-track',
  out_of_form:       'Out-of-form',
  insufficient_data: 'Unrated',
};

// Mirrors LabelChip's LABEL_CLASSES — same token palette, no ad-hoc colors.
const LABEL_CHIP_CLASSES: Record<Label, string> = {
  in_form:           'bg-emerald/10 text-emerald',
  on_track:          'bg-cyan/10 text-cyan',
  off_track:         'bg-amber/10 text-amber',
  out_of_form:       'bg-red/10 text-red',
  insufficient_data: 'bg-surface-2 text-ink-muted',
};

interface Props {
  schemes: MfScheme[];
  activeFilter: Label | null;
  onFilterChange: (label: Label | null) => void;
}

export function PortfolioHealthSummary({ schemes, activeFilter, onFilterChange }: Props) {
  const counts = React.useMemo(() => {
    const acc: Partial<Record<Label, number>> = {};
    for (const s of schemes) {
      acc[s.label] = (acc[s.label] ?? 0) + 1;
    }
    return acc;
  }, [schemes]);

  const visibleLabels = LABEL_ORDER.filter((l) => (counts[l] ?? 0) > 0);

  if (visibleLabels.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-caption text-ink-muted shrink-0">Your portfolio:</span>
      {visibleLabels.map((label) => {
        const isActive = activeFilter === label;
        return (
          <button
            key={label}
            type="button"
            onClick={() => onFilterChange(isActive ? null : label)}
            aria-pressed={isActive}
            className={cn(
              'inline-flex items-center gap-1 rounded-full px-3 py-1 text-caption font-medium transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
              LABEL_CHIP_CLASSES[label],
              isActive && 'ring-2 ring-current',
            )}
          >
            {LABEL_DISPLAY[label]}
            <span className="tabular-nums opacity-70">({counts[label]})</span>
          </button>
        );
      })}
      {activeFilter !== null && (
        <button
          type="button"
          onClick={() => onFilterChange(null)}
          className="text-caption text-ink-muted underline underline-offset-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded"
        >
          Show all
        </button>
      )}
    </div>
  );
}
