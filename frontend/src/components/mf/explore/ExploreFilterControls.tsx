'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';

export const RISKOMETER_OPTIONS = [
  'Low', 'Low to Moderate', 'Moderate', 'Moderately High', 'High', 'Very High',
] as const;

export function getRiskometerParam(riskFilter: string[]) {
  return riskFilter.length > 0 ? riskFilter.join(',') : undefined;
}

export function QuickDiscoveryRiskFilters({ riskFilter, hasActiveFilters, onRisk, onReset }: {
  riskFilter: string[];
  hasActiveFilters: boolean;
  onRisk: (risk: string[]) => void;
  onReset: () => void;
}) {
  return (
    <>
      <div className="flex items-center gap-2 flex-wrap mb-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.06em] font-medium text-ink-muted shrink-0">Risk</span>
        <div className="flex flex-wrap gap-1">
          {RISKOMETER_OPTIONS.map((band) => (
            <button key={band} type="button" onClick={() => {
              onRisk(riskFilter.includes(band) ? riskFilter.filter((r) => r !== band) : [...riskFilter, band]);
            }}
              aria-pressed={riskFilter.includes(band)}
              data-testid={`risk-pill-${band.replace(/\s/g, '-')}`}
              className={cn('rounded-lg border px-2.5 py-1 text-caption font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
                riskFilter.includes(band)
                  ? 'bg-royal text-white border-royal'
                  : 'bg-surface-2 border-line text-ink-secondary hover:border-royal hover:text-royal')}>
              {band}
            </button>
          ))}
        </div>
        {hasActiveFilters && (
          <button type="button" onClick={onReset}
            className="text-caption text-ink-muted hover:text-ink font-medium ml-auto transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
            Reset filters
          </button>
        )}
      </div>
      {riskFilter.length > 0 && (
        <p className="text-caption text-ink-muted mb-2">Funds without a published riskometer are not shown while this filter is on.</p>
      )}
    </>
  );
}

export function FundExplorerEmptyState({ categoryName, hasActiveFilters, search, onReset }: {
  categoryName: string;
  hasActiveFilters: boolean;
  search: string;
  onReset: () => void;
}) {
  return (
    <div className="rounded-lg border border-line bg-surface-2 p-8 text-center">
      <div className="text-2xl mb-3" aria-hidden="true">🔍</div>
      {hasActiveFilters && !search.trim() ? (
        <>
          <p className="text-small font-medium text-ink">No funds in {categoryName} match these filters.</p>
          <button type="button" onClick={onReset}
            className="mt-3 inline-flex items-center px-4 py-2 rounded-lg border border-line bg-surface text-ink-secondary hover:text-ink font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
            Clear filters
          </button>
        </>
      ) : (
        <>
          <p className="text-small font-medium text-ink">No funds found</p>
          <p className="mt-1 text-caption text-ink-muted">Try a different name or clear the search.</p>
        </>
      )}
    </div>
  );
}
