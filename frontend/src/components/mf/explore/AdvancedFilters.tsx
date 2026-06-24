/**
 * AdvancedFilters — V4 S4 advanced-filter panel (collapsible).
 *  - Plan type + Option type are REAL (drive /mf/funds server-side).
 *  - The 6 V4 filter groups + 4 range sliders are the full V4 layout, marked
 *    "preview" until their backend filters land (B77). Selections are visual.
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import { FILTER_GROUPS, FILTER_RANGES } from './sampleData';

type PlanFilter = 'all' | 'direct' | 'regular';
type OptionFilter = 'all' | 'growth' | 'idcw';

const PLAN_OPTIONS: { key: PlanFilter; label: string }[] = [
  { key: 'all', label: 'All' }, { key: 'direct', label: 'Direct' }, { key: 'regular', label: 'Regular' },
];
const OPTION_OPTIONS: { key: OptionFilter; label: string }[] = [
  { key: 'all', label: 'All' }, { key: 'growth', label: 'Growth' }, { key: 'idcw', label: 'IDCW' },
];

function Opt({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'rounded-lg border px-3 py-1.5 text-small font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
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
  // Visual (preview) multi-select state for the 6 V4 groups.
  const [picked, setPicked] = React.useState<Record<string, Set<string>>>({});
  const toggle = (group: string, opt: string) =>
    setPicked((prev) => {
      const next = new Set(prev[group] ?? []);
      next.has(opt) ? next.delete(opt) : next.add(opt);
      return { ...prev, [group]: next };
    });

  const realActive = (planFilter !== 'all' ? 1 : 0) + (optionFilter !== 'all' ? 1 : 0);
  const previewActive = Object.values(picked).reduce((s, set) => s + set.size, 0);
  const total = realActive + previewActive;

  return (
    <div className="rounded-xl border border-line bg-surface overflow-hidden shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="w-full flex items-center gap-3 px-5 py-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-royal/40"
      >
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-royal/10 text-royal shrink-0" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 5 H21 L14 13 V20 L10 18 V13 Z" /></svg>
        </span>
        <span className="text-small font-semibold text-ink">Advanced Filters</span>
        <span className="text-caption text-ink-muted hidden sm:inline">Category, risk, return, SIP, size, cost, quality, phase, portfolio</span>
        {total > 0 && <span className="font-mono text-caption font-semibold text-royal bg-royal/10 px-2 py-0.5 rounded-full">{total} active</span>}
        <span className="ml-auto text-ink-muted transition-transform" style={{ transform: open ? 'rotate(180deg)' : undefined }} aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M6 9 L12 15 L18 9" /></svg>
        </span>
      </button>

      {open && (
        <div className="border-t border-line px-5 py-5">
          {/* Real filters */}
          <div className="grid gap-5 sm:grid-cols-2 mb-5">
            <div>
              <h4 className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted mb-2.5">Plan type</h4>
              <div className="flex flex-wrap gap-2">{PLAN_OPTIONS.map((o) => <Opt key={o.key} active={planFilter === o.key} onClick={() => onPlan(o.key)}>{o.label}</Opt>)}</div>
            </div>
            <div>
              <h4 className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted mb-2.5">Option type</h4>
              <div className="flex flex-wrap gap-2">{OPTION_OPTIONS.map((o) => <Opt key={o.key} active={optionFilter === o.key} onClick={() => onOption(o.key)}>{o.label}</Opt>)}</div>
            </div>
          </div>

          {/* V4 preview groups */}
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 border-t border-line pt-5">
            {FILTER_GROUPS.map((g) => (
              <div key={g.title}>
                <h4 className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted mb-2.5">{g.title} <span className="text-ink-faint normal-case tracking-normal">· preview</span></h4>
                <div className="flex flex-wrap gap-1.5">
                  {g.options.map((o) => {
                    const on = picked[g.title]?.has(o) ?? false;
                    return (
                      <button key={o} type="button" onClick={() => toggle(g.title, o)} aria-pressed={on}
                        className={cn('rounded-lg border px-2.5 py-1 text-caption font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
                          on ? 'bg-royal text-white border-royal' : 'bg-surface-2 border-line text-ink-secondary hover:border-royal hover:text-royal')}>
                        {o}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* Range sliders (preview) */}
          <div className="grid gap-5 sm:grid-cols-2 mt-5">
            {FILTER_RANGES.map((r) => (
              <div key={r.title}>
                <h4 className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted mb-2">{r.title} <span className="text-ink-faint normal-case tracking-normal">· preview</span></h4>
                <input type="range" className="w-full accent-royal" defaultValue={50} aria-label={r.title} />
                <div className="flex justify-between font-mono text-caption text-ink-muted mt-1"><span>{r.min}</span><span>{r.mid}</span><span>{r.max}</span></div>
              </div>
            ))}
          </div>

          <div className="flex gap-2 mt-5 border-t border-line pt-4">
            <button type="button" className="rounded-lg bg-royal text-white px-4 py-2 text-small font-semibold hover:bg-royal/90 transition-colors">Apply filters</button>
            <button type="button" onClick={() => setPicked({})} className="rounded-lg border border-line bg-surface-2 text-ink px-4 py-2 text-small font-medium hover:bg-surface-3 transition-colors">Reset all</button>
          </div>
        </div>
      )}
    </div>
  );
}
