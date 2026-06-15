/**
 * FundExplorerTable — side-by-side comparison table for the Fund Explorer page.
 *
 * Compliance invariants:
 *   - unified_score NEVER rendered (non-neg #2) — we show rank ordinal + label only.
 *   - No advisory language: no "invest", "avoid", "switch" — only factual data.
 *   - confidence_factors rendered as "High"/"Medium"/"Low" text, never as a float.
 *   - Clicking a row shows an educational prompt (no standalone fund page yet).
 *   - Table is horizontally scrollable on small screens (no column collapsing).
 */

'use client';

import * as React from 'react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import { LabelChip } from '@/components/ui/LabelChip';
import type { FundExplorerItem } from '@/features/mf/types';
import type { Label, ConfidenceBand } from '@/components/charts/ScoreRing';

// ---------------------------------------------------------------------------
// Sort types
// ---------------------------------------------------------------------------

export type SortKey = 'rank' | 'return_1y' | 'return_3y' | 'max_drawdown';

const SORT_LABELS: Record<SortKey, string> = {
  rank:         'Power Rank',
  return_1y:    '1Y Return',
  return_3y:    '3Y Return',
  max_drawdown: 'Drawdown',
};

// ---------------------------------------------------------------------------
// Factor band rendering
// ---------------------------------------------------------------------------

const FACTOR_CLASSES: Record<'high' | 'medium' | 'low', string> = {
  high:   'text-emerald',
  medium: 'text-amber',
  low:    'text-red',
};

const FACTOR_LABELS: Record<'high' | 'medium' | 'low', string> = {
  high:   'High',
  medium: 'Medium',
  low:    'Low',
};

function FactorCell({ value }: { value: 'high' | 'medium' | 'low' | null | undefined }) {
  if (!value) return <span className="text-ink-muted">—</span>;
  return (
    <span className={cn('font-medium', FACTOR_CLASSES[value])}>
      {FACTOR_LABELS[value]}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Sortable column header
// ---------------------------------------------------------------------------

function SortHeader({
  label,
  sortKey,
  activeSort,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  activeSort: SortKey;
  onSort: (key: SortKey) => void;
}) {
  const isActive = activeSort === sortKey;
  return (
    <th
      className={cn(
        'pb-2 text-right font-medium cursor-pointer select-none whitespace-nowrap',
        isActive ? 'text-ink' : 'text-ink-muted',
      )}
      onClick={() => onSort(sortKey)}
    >
      {label}
      {isActive && <span className="ml-1 text-caption">▲</span>}
    </th>
  );
}

// ---------------------------------------------------------------------------
// Main table
// ---------------------------------------------------------------------------

export interface FundExplorerTableProps {
  funds: FundExplorerItem[];
  activeSort: SortKey;
  onSort: (key: SortKey) => void;
}

export function FundExplorerTable({ funds, activeSort, onSort }: FundExplorerTableProps) {
  const handleRowClick = () => {
    toast('Upload your CAS to see this fund in your portfolio report.', {
      action: { label: 'Upload', onClick: () => { window.location.href = '/mf/upload'; } },
    });
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small min-w-[720px]" data-testid="fund-explorer-table">
        <thead>
          <tr className="border-b border-line text-caption text-ink-muted">
            <th className="pb-2 w-8 text-center font-medium">#</th>
            <th className="pb-2 text-left font-medium">Fund</th>
            <SortHeader label="Rank" sortKey="rank" activeSort={activeSort} onSort={onSort} />
            <th className="pb-2 text-left font-medium pl-4">Assessment</th>
            <th className="pb-2 text-right font-medium">Consistency</th>
            <th className="pb-2 text-right font-medium">Recency</th>
            <th className="pb-2 text-right font-medium">Volatility</th>
            <SortHeader label="1Y Return" sortKey="return_1y" activeSort={activeSort} onSort={onSort} />
            <SortHeader label="3Y Return" sortKey="return_3y" activeSort={activeSort} onSort={onSort} />
          </tr>
        </thead>
        <tbody>
          {funds.map((fund, idx) => {
            const cf = fund.confidence_factors;
            return (
              <tr
                key={fund.isin}
                className="border-b border-line last:border-0 hover:bg-surface-2 cursor-pointer transition-colors"
                onClick={handleRowClick}
                data-testid={`fund-row-${fund.isin}`}
              >
                {/* Row number */}
                <td className="py-2.5 text-center text-ink-muted text-caption tabular-nums">
                  {idx + 1}
                </td>

                {/* Fund name + AMC */}
                <td className="py-2.5 pr-4">
                  <p className="font-medium text-ink leading-snug">{fund.scheme_name}</p>
                  {fund.amc_name && (
                    <p className="text-caption text-ink-muted">{fund.amc_name}</p>
                  )}
                </td>

                {/* Rank badge */}
                <td className="py-2.5 pr-3 text-right tabular-nums">
                  <span className="inline-flex items-center gap-0.5 text-caption font-medium text-ink-secondary">
                    <span className="text-ink font-semibold">#{fund.category_rank}</span>
                    <span className="text-ink-muted"> of {fund.category_total}</span>
                  </span>
                </td>

                {/* Label */}
                <td className="py-2.5 pl-4 pr-3">
                  <LabelChip
                    label={fund.verb_label as Label}
                    confidenceBand={(fund.confidence_band ?? undefined) as ConfidenceBand | undefined}
                  />
                </td>

                {/* Confidence factors */}
                <td className="py-2.5 pr-3 text-right">
                  <FactorCell value={cf?.consistency} />
                </td>
                <td className="py-2.5 pr-3 text-right">
                  <FactorCell value={cf?.recency} />
                </td>
                <td className="py-2.5 pr-3 text-right">
                  <FactorCell value={cf?.volatility} />
                </td>

                {/* Returns */}
                <td className="py-2.5 pr-3 text-right tabular-nums">
                  {fund.return_1y_pct != null ? (
                    <span className={fund.return_1y_pct >= 0 ? 'text-emerald' : 'text-red'}>
                      {fund.return_1y_pct >= 0 ? '+' : ''}
                      {fund.return_1y_pct.toFixed(2)}%
                    </span>
                  ) : (
                    <span className="text-ink-muted">—</span>
                  )}
                </td>
                <td className="py-2.5 text-right tabular-nums">
                  {fund.return_3y_pct != null ? (
                    <span className={fund.return_3y_pct >= 0 ? 'text-emerald' : 'text-red'}>
                      {fund.return_3y_pct >= 0 ? '+' : ''}
                      {fund.return_3y_pct.toFixed(2)}%
                    </span>
                  ) : (
                    <span className="text-ink-muted">—</span>
                  )}
                </td>
              </tr>
            );
          })}

          {funds.length === 0 && (
            <tr>
              <td colSpan={9} className="py-12 text-center text-ink-muted text-small">
                No funds found for this category.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
