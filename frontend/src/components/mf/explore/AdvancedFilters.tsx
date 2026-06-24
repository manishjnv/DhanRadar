/**
 * AdvancedFilters — collapsible filter panel ported from V4 S4.
 *
 * Only the filters with real backend support are interactive: Plan type and
 * Option type (server-side via /mf/funds). V4's risk / expense / AUM / SIP-XIRR
 * sliders have no public data source, so they're shown as an honest "coming
 * soon" note rather than fake controls. Category stays a prominent top-level
 * control on the page, so it is not duplicated here.
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';

type PlanFilter = 'all' | 'direct' | 'regular';
type OptionFilter = 'all' | 'growth' | 'idcw';

const PLAN_OPTIONS: { key: PlanFilter; label: string }[] = [
  { key: 'all',     label: 'All' },
  { key: 'direct',  label: 'Direct' },
  { key: 'regular', label: 'Regular' },
];
const OPTION_OPTIONS: { key: OptionFilter; label: string }[] = [
  { key: 'all',    label: 'All' },
  { key: 'growth', label: 'Growth' },
  { key: 'idcw',   label: 'IDCW' },
];

function OptButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'rounded-lg border px-3 py-1.5 text-small font-medium transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
        active ? 'bg-royal text-white border-royal' : 'bg-surface-2 border-line text-ink-secondary hover:border-royal hover:text-royal',
      )}
    >
      {children}
    </button>
  );
}

export interface AdvancedFiltersProps {
  planFilter: PlanFilter;
  optionFilter: OptionFilter;
  onPlan: (k: PlanFilter) => void;
  onOption: (k: OptionFilter) => void;
}

export function AdvancedFilters({ planFilter, optionFilter, onPlan, onOption }: AdvancedFiltersProps) {
  const [open, setOpen] = React.useState(false);
  const activeCount = (planFilter !== 'all' ? 1 : 0) + (optionFilter !== 'all' ? 1 : 0);

  return (
    <div className="rounded-xl border border-line bg-surface overflow-hidden shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="w-full flex items-center gap-3 px-5 py-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-royal/40"
      >
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-royal/10 text-royal shrink-0" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 5 H21 L14 13 V20 L10 18 V13 Z" />
          </svg>
        </span>
        <span className="text-small font-semibold text-ink">Filters</span>
        {activeCount > 0 && (
          <span className="font-mono text-caption font-semibold text-royal bg-royal/10 px-2 py-0.5 rounded-full">
            {activeCount} active
          </span>
        )}
        <span className="ml-auto text-ink-muted transition-transform" style={{ transform: open ? 'rotate(180deg)' : undefined }} aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M6 9 L12 15 L18 9" />
          </svg>
        </span>
      </button>

      {open && (
        <div className="border-t border-line px-5 py-5 grid gap-5 sm:grid-cols-2">
          <div>
            <h4 className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted mb-2.5">Plan type</h4>
            <div className="flex flex-wrap gap-2">
              {PLAN_OPTIONS.map((o) => (
                <OptButton key={o.key} active={planFilter === o.key} onClick={() => onPlan(o.key)}>{o.label}</OptButton>
              ))}
            </div>
          </div>
          <div>
            <h4 className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted mb-2.5">Option type</h4>
            <div className="flex flex-wrap gap-2">
              {OPTION_OPTIONS.map((o) => (
                <OptButton key={o.key} active={optionFilter === o.key} onClick={() => onOption(o.key)}>{o.label}</OptButton>
              ))}
            </div>
          </div>
          <p className="sm:col-span-2 text-caption text-ink-muted border-t border-line pt-3">
            Risk, expense ratio and AUM filters are in development.
          </p>
        </div>
      )}
    </div>
  );
}
