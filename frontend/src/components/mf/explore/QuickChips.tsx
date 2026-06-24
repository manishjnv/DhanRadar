/**
 * QuickChips — V4 "Quick Discovery" one-click filters, made compliant.
 *
 * These are SORT/FILTER PRESETS only — they drive the exact same sort/plan/
 * option state the toolbar controls already use. No new fetching/sorting logic,
 * and no advisory framing (V4's "Top Rated / AI Recommended / Beginner Friendly"
 * imply advice and are replaced with neutral, rank/return-based presets).
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import type { SortKey } from '@/components/mf/FundExplorerTable';

type PlanFilter = 'all' | 'direct' | 'regular';
type OptionFilter = 'all' | 'growth' | 'idcw';

export interface QuickChipsProps {
  sort: SortKey;
  sortDir: 'asc' | 'desc';
  planFilter: PlanFilter;
  optionFilter: OptionFilter;
  onSort: (key: SortKey, dir: 'asc' | 'desc') => void;
  onPlan: (key: PlanFilter) => void;
  onOption: (key: OptionFilter) => void;
}

type Chip =
  | { kind: 'sort'; label: string; icon: string; key: SortKey; dir: 'asc' | 'desc' }
  | { kind: 'plan'; label: string; icon: string; value: PlanFilter }
  | { kind: 'option'; label: string; icon: string; value: OptionFilter };

const CHIPS: Chip[] = [
  { kind: 'sort',   label: 'Top Ranked', icon: '🏆', key: 'rank',      dir: 'asc'  },
  { kind: 'sort',   label: 'Best 1Y',    icon: '📈', key: 'return_1y', dir: 'desc' },
  { kind: 'sort',   label: 'Best 3Y',    icon: '📊', key: 'return_3y', dir: 'desc' },
  { kind: 'sort',   label: 'Best 5Y',    icon: '🗓', key: 'return_5y', dir: 'desc' },
  { kind: 'plan',   label: 'Direct Plans', icon: '💸', value: 'direct' },
  { kind: 'option', label: 'Growth Option', icon: '🌱', value: 'growth' },
];

export function QuickChips({
  sort, sortDir, planFilter, optionFilter, onSort, onPlan, onOption,
}: QuickChipsProps) {
  function isActive(chip: Chip): boolean {
    if (chip.kind === 'sort')   return sort === chip.key && sortDir === chip.dir;
    if (chip.kind === 'plan')   return planFilter === chip.value;
    return optionFilter === chip.value;
  }

  function apply(chip: Chip) {
    if (chip.kind === 'sort')   { onSort(chip.key, chip.dir); return; }
    if (chip.kind === 'plan')   { onPlan(planFilter === chip.value ? 'all' : chip.value); return; }
    onOption(optionFilter === chip.value ? 'all' : chip.value);
  }

  return (
    <div className="flex flex-wrap gap-2">
      {CHIPS.map((chip) => {
        const active = isActive(chip);
        return (
          <button
            key={chip.label}
            type="button"
            onClick={() => apply(chip)}
            aria-pressed={active}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-small font-medium transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
              active
                ? 'bg-ink text-bg border-ink'
                : 'bg-surface border-line text-ink-secondary hover:border-royal hover:text-royal',
            )}
          >
            <span aria-hidden="true">{chip.icon}</span>
            {chip.label}
          </button>
        );
      })}
    </div>
  );
}
