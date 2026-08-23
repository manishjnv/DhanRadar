/**
 * AdvancedFilters — real server-side filter controls for /mf/explore.
 *
 * Filters: Plan type, Option type (existing), Risk multi-select, Max TER,
 * Min AUM. Fantasy Quality/Market-phase/Portfolio groups and return sliders
 * removed (EXPLORE E3; they had no backend filter support).
 *
 * All selections are threaded through page state → useFundExplorer params.
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';

type PlanFilter   = 'all' | 'direct' | 'regular';
type OptionFilter = 'all' | 'growth' | 'idcw';

const PLAN_OPTIONS: { key: PlanFilter; label: string }[] = [
  { key: 'all', label: 'All' }, { key: 'direct', label: 'Direct' }, { key: 'regular', label: 'Regular' },
];
const OPTION_OPTIONS: { key: OptionFilter; label: string }[] = [
  { key: 'all', label: 'All' }, { key: 'growth', label: 'Growth' }, { key: 'idcw', label: 'IDCW' },
];
const RISKOMETER_OPTIONS = [
  'Very Low', 'Low', 'Moderate', 'Moderately High', 'High', 'Very High',
] as const;

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
  riskFilter: string[];
  onRisk: (r: string[]) => void;
  maxTer: string;
  onMaxTer: (v: string) => void;
  minAum: string;
  onMinAum: (v: string) => void;
  onApply: () => void;
  onReset: () => void;
}

export function AdvancedFilters({
  planFilter, optionFilter, onPlan, onOption,
  riskFilter, onRisk,
  maxTer, onMaxTer,
  minAum, onMinAum,
  onApply, onReset,
}: AdvancedFiltersProps) {
  const [open, setOpen] = React.useState(false);

  function toggleRisk(opt: string) {
    onRisk(riskFilter.includes(opt) ? riskFilter.filter((r) => r !== opt) : [...riskFilter, opt]);
  }

  const activeCount =
    (planFilter !== 'all' ? 1 : 0) +
    (optionFilter !== 'all' ? 1 : 0) +
    riskFilter.length +
    (maxTer ? 1 : 0) +
    (minAum ? 1 : 0);

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
        <span className="text-caption text-ink-muted hidden sm:inline">Plan, option, risk, expense ratio, AUM</span>
        {activeCount > 0 && (
          <span className="font-mono text-caption font-semibold text-royal bg-royal/10 px-2 py-0.5 rounded-full">
            {activeCount} active
          </span>
        )}
        <span className="ml-auto text-ink-muted transition-transform" style={{ transform: open ? 'rotate(180deg)' : undefined }} aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M6 9 L12 15 L18 9" /></svg>
        </span>
      </button>

      {open && (
        <div className="border-t border-line px-5 py-5">
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {/* Plan type */}
            <div>
              <h4 className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted mb-2.5">Plan type</h4>
              <div className="flex flex-wrap gap-2">
                {PLAN_OPTIONS.map((o) => (
                  <Opt key={o.key} active={planFilter === o.key} onClick={() => onPlan(o.key)}>{o.label}</Opt>
                ))}
              </div>
            </div>

            {/* Option type */}
            <div>
              <h4 className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted mb-2.5">Option type</h4>
              <div className="flex flex-wrap gap-2">
                {OPTION_OPTIONS.map((o) => (
                  <Opt key={o.key} active={optionFilter === o.key} onClick={() => onOption(o.key)}>{o.label}</Opt>
                ))}
              </div>
            </div>

            {/* Risk riskometer multi-select */}
            <div>
              <h4 className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted mb-2.5">Risk (SEBI riskometer)</h4>
              <div className="flex flex-wrap gap-1.5">
                {RISKOMETER_OPTIONS.map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => toggleRisk(opt)}
                    aria-pressed={riskFilter.includes(opt)}
                    data-testid={`risk-opt-${opt.replace(/\s/g, '-')}`}
                    className={cn(
                      'rounded-lg border px-2.5 py-1 text-caption font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
                      riskFilter.includes(opt)
                        ? 'bg-royal text-white border-royal'
                        : 'bg-surface-2 border-line text-ink-secondary hover:border-royal hover:text-royal',
                    )}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>

            {/* Max TER */}
            <div>
              <h4 className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted mb-2.5">Max expense ratio (%)</h4>
              <input
                type="number"
                min={0}
                max={5}
                step={0.05}
                placeholder="e.g. 1.0"
                value={maxTer}
                onChange={(e) => onMaxTer(e.target.value)}
                data-testid="max-ter-input"
                className="h-[38px] w-full rounded-lg border border-line bg-surface pl-3 pr-3 text-small text-ink font-medium focus-visible:outline-none focus-visible:border-royal focus-visible:ring-2 focus-visible:ring-royal/40 transition-colors"
              />
            </div>

            {/* Min AUM */}
            <div>
              <h4 className="font-mono text-caption uppercase tracking-[0.06em] font-semibold text-ink-muted mb-2.5">Min AUM (₹ Cr)</h4>
              <input
                type="number"
                min={0}
                step={100}
                placeholder="e.g. 500"
                value={minAum}
                onChange={(e) => onMinAum(e.target.value)}
                data-testid="min-aum-input"
                className="h-[38px] w-full rounded-lg border border-line bg-surface pl-3 pr-3 text-small text-ink font-medium focus-visible:outline-none focus-visible:border-royal focus-visible:ring-2 focus-visible:ring-royal/40 transition-colors"
              />
            </div>
          </div>

          <div className="flex gap-2 mt-5 border-t border-line pt-4">
            <button
              type="button"
              onClick={onApply}
              data-testid="filters-apply"
              className="rounded-lg bg-royal text-white px-4 py-2 text-small font-semibold hover:bg-royal/90 transition-colors"
            >
              Apply filters
            </button>
            <button
              type="button"
              onClick={onReset}
              data-testid="filters-reset"
              className="rounded-lg border border-line bg-surface-2 text-ink px-4 py-2 text-small font-medium hover:bg-surface-3 transition-colors"
            >
              Reset all
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

