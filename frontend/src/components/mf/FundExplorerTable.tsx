/**
 * FundExplorerTable — ranked fund comparison table for /mf/explore.
 *
 * Compliance invariants (non-negotiable):
 *   - unified_score NEVER rendered (non-neg #2)
 *   - No advisory language — only educational labels and factual data
 *   - confidence_factors rendered as High/Mid/Low badge, never as a float
 *   - Row click → educational toast only (no standalone fund page yet)
 *   - Table scrolls horizontally on mobile — no column collapsing
 */

'use client';

import * as React from 'react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import { LabelChip } from '@/components/ui/LabelChip';
import type { FundExplorerItem } from '@/features/mf/types';
import type { Label, ConfidenceBand } from '@/components/charts/ScoreRing';

// ---------------------------------------------------------------------------
// Sort types (exported so page.tsx can import SortKey)
// ---------------------------------------------------------------------------

export type SortKey = 'rank' | 'return_1y' | 'return_3y' | 'max_drawdown';

// ---------------------------------------------------------------------------
// Fund avatar — .tk-logo pattern: deterministic color from scheme name
// ---------------------------------------------------------------------------

const AVATAR_COLORS = [
  '#0A1F4A', '#1F4E9E', '#003E80', '#006B7D',
  '#1B4332', '#6A1B9A', '#B71C1C', '#374151',
] as const;

function FundAvatar({ name }: { name: string }) {
  const idx = ((name.charCodeAt(0) || 0) + (name.charCodeAt(1) || 0)) % AVATAR_COLORS.length;
  return (
    <div
      className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-[11px] shrink-0 select-none"
      style={{ background: AVATAR_COLORS[idx] }}
      aria-hidden="true"
    >
      {name[0]?.toUpperCase() ?? '?'}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Factor badge — .badge style: bordered pill, mono text, color-coded
// ---------------------------------------------------------------------------

const FACTOR_CONFIG = {
  high:   { text: 'text-emerald', label: 'High' },
  medium: { text: 'text-amber',   label: 'Mid'  },
  low:    { text: 'text-red',     label: 'Low'  },
} as const;

function FactorCell({ value }: { value: 'high' | 'medium' | 'low' | null | undefined }) {
  if (!value) return <span className="font-mono text-[11px] text-ink-muted">—</span>;
  const cfg = FACTOR_CONFIG[value];
  return (
    <span className={cn(
      'inline-flex items-center px-1.5 py-px rounded border border-current',
      'font-mono text-[10px] font-semibold uppercase tracking-wide',
      cfg.text,
    )}>
      {cfg.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Sortable column header — .dt th: mono, uppercase, muted, clickable
// ---------------------------------------------------------------------------

function SortHeader({
  label, sortKey, activeSort, onSort,
}: {
  label: string;
  sortKey: SortKey;
  activeSort: SortKey;
  onSort: (k: SortKey) => void;
}) {
  const isActive = activeSort === sortKey;
  return (
    <th
      scope="col"
      className={cn(
        'pb-3 px-3 text-right font-mono text-[10px] uppercase tracking-[0.06em] font-semibold',
        'cursor-pointer select-none whitespace-nowrap transition-colors',
        isActive ? 'text-ink' : 'text-ink-muted hover:text-ink-secondary',
      )}
      onClick={() => onSort(sortKey)}
    >
      {label}
      <span className={cn('ml-1 text-royal transition-opacity', isActive ? 'opacity-100' : 'opacity-0')}>
        ▴
      </span>
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
      {/* min-w ensures horizontal scroll on mobile — never collapses columns */}
      <table
        className="w-full border-collapse text-[13.5px] min-w-[800px]"
        data-testid="fund-explorer-table"
      >
        {/* thead: .dt th pattern — mono, uppercase, 10px, muted, tracking */}
        <thead>
          <tr className="border-b border-line">
            <th scope="col" className="pb-3 px-3 w-10 text-center font-mono text-[10px] uppercase tracking-[0.06em] font-semibold text-ink-muted">
              #
            </th>
            <th scope="col" className="pb-3 px-3 text-left font-mono text-[10px] uppercase tracking-[0.06em] font-semibold text-ink-muted">
              Fund
            </th>
            <SortHeader label="Rank"   sortKey="rank"         activeSort={activeSort} onSort={onSort} />
            <th scope="col" className="pb-3 px-3 text-left font-mono text-[10px] uppercase tracking-[0.06em] font-semibold text-ink-muted">
              Assessment
            </th>
            <th scope="col" className="pb-3 px-3 text-right font-mono text-[10px] uppercase tracking-[0.06em] font-semibold text-ink-muted">
              Consistency
            </th>
            <th scope="col" className="pb-3 px-3 text-right font-mono text-[10px] uppercase tracking-[0.06em] font-semibold text-ink-muted">
              Recency
            </th>
            <th scope="col" className="pb-3 px-3 text-right font-mono text-[10px] uppercase tracking-[0.06em] font-semibold text-ink-muted">
              Volatility
            </th>
            <SortHeader label="1Y Ret" sortKey="return_1y"   activeSort={activeSort} onSort={onSort} />
            <SortHeader label="3Y Ret" sortKey="return_3y"   activeSort={activeSort} onSort={onSort} />
          </tr>
        </thead>

        {/* tbody: .dt td pattern — 13px 14px padding, hover surface-2 */}
        <tbody>
          {funds.map((fund, idx) => {
            const cf = fund.confidence_factors;
            return (
              <tr
                key={fund.isin}
                className="border-b border-line last:border-0 hover:bg-surface-2 cursor-pointer transition-colors group"
                onClick={handleRowClick}
                data-testid={`fund-row-${fund.isin}`}
              >
                {/* Row number */}
                <td className="py-3 px-3 text-center font-mono text-[11px] text-ink-muted tabular-nums">
                  {idx + 1}
                </td>

                {/* Fund — .tk pattern: avatar + name + plan/option chips */}
                <td className="py-3 px-3">
                  <div className="flex items-center gap-2.5">
                    <FundAvatar name={fund.scheme_name} />
                    <div className="min-w-0">
                      <p className="font-medium text-ink leading-snug group-hover:text-royal transition-colors line-clamp-2">
                        {fund.scheme_name}
                      </p>
                      {fund.amc_name && (
                        <p className="font-mono text-[10.5px] text-ink-muted mt-0.5">{fund.amc_name}</p>
                      )}
                      {(fund.plan_type || fund.option_type || fund.amc_level_aum_crore != null) && (
                        <div className="flex items-center flex-wrap gap-1 mt-1">
                          {fund.plan_type && (
                            <span className="inline-flex items-center px-1.5 py-px rounded bg-surface-3 border border-line font-mono text-[9px] font-semibold uppercase tracking-wide text-ink-secondary">
                              {fund.plan_type === 'direct' ? 'Direct' : 'Regular'}
                            </span>
                          )}
                          {fund.option_type && (
                            <span className="inline-flex items-center px-1.5 py-px rounded bg-surface-3 border border-line font-mono text-[9px] font-semibold uppercase tracking-wide text-ink-secondary">
                              {fund.option_type === 'growth' ? 'Growth'
                                : fund.option_type === 'idcw' ? 'IDCW'
                                : fund.option_type === 'dividend_reinvest' ? 'Div Reinvest'
                                : 'Div Payout'}
                            </span>
                          )}
                          {fund.amc_level_aum_crore != null && (
                            <span className="font-mono text-[9px] text-ink-muted">
                              AMC AUM: ₹{fund.amc_level_aum_crore.toLocaleString('en-IN', { maximumFractionDigits: 0 })} Cr
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </td>

                {/* Rank — #N/M in mono */}
                <td className="py-3 px-3 text-right whitespace-nowrap tabular-nums">
                  <span className="font-mono text-[13px] font-semibold text-ink">
                    #{fund.category_rank}
                  </span>
                  <span className="font-mono text-[11px] text-ink-muted">
                    /{fund.category_total}
                  </span>
                </td>

                {/* Assessment label */}
                <td className="py-3 px-3">
                  <LabelChip
                    label={fund.verb_label as Label}
                    confidenceBand={(fund.confidence_band ?? undefined) as ConfidenceBand | undefined}
                  />
                </td>

                {/* Factor badges */}
                <td className="py-3 px-3 text-right">
                  <FactorCell value={cf?.consistency} />
                </td>
                <td className="py-3 px-3 text-right">
                  <FactorCell value={cf?.recency} />
                </td>
                <td className="py-3 px-3 text-right">
                  <FactorCell value={cf?.volatility} />
                </td>

                {/* Returns — mono, colored, +/- prefix */}
                <td className="py-3 px-3 text-right tabular-nums whitespace-nowrap">
                  {fund.return_1y_pct != null ? (
                    <span className={cn(
                      'font-mono text-[13px] font-semibold',
                      fund.return_1y_pct >= 0 ? 'text-emerald' : 'text-red',
                    )}>
                      {fund.return_1y_pct >= 0 ? '+' : ''}{fund.return_1y_pct.toFixed(1)}%
                    </span>
                  ) : (
                    <span className="font-mono text-[11px] text-ink-muted">—</span>
                  )}
                </td>
                <td className="py-3 px-3 text-right tabular-nums whitespace-nowrap">
                  {fund.return_3y_pct != null ? (
                    <span className={cn(
                      'font-mono text-[13px] font-semibold',
                      fund.return_3y_pct >= 0 ? 'text-emerald' : 'text-red',
                    )}>
                      {fund.return_3y_pct >= 0 ? '+' : ''}{fund.return_3y_pct.toFixed(1)}%
                    </span>
                  ) : (
                    <span className="font-mono text-[11px] text-ink-muted">—</span>
                  )}
                </td>
              </tr>
            );
          })}

          {funds.length === 0 && (
            <tr>
              <td colSpan={9} className="py-16 text-center">
                <p className="text-small font-medium text-ink">No funds match your search</p>
                <p className="text-caption text-ink-muted mt-1">Try a different name or clear the search</p>
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
