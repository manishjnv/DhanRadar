'use client';

/**
 * AmcCoverageTable — compact, sortable per-AMC × per-field data-coverage table.
 *
 * Founder spec (verbatim): tight font (text-[11px]/mono for numeric), tight
 * padding/margins, sortable by EVERY column header (client-side, aria-sort),
 * sticky header, first column = AMC short name, cells like "A·M 334"
 * (mode·freq count), legend line below the table.
 *
 * Sort state is self-contained (no lifted prop) — the whole table is one
 * client-side dataset (54 AMCs max), so there is no server-side pagination to
 * coordinate with.
 */

import * as React from 'react';
import { cn } from '@/lib/cn';
import type { AmcCoverageRow, CoverageField } from '@/features/admin/api';

export type AmcSortKey = 'amc' | 'fund_count' | 'staleness' | 'completeness' | CoverageField;

function formatCell(mode: 'A' | 'ML' | '-', freq: string, count: number): string {
  const n = count.toLocaleString('en-IN');
  if (mode === '-') return n;
  return `${mode}\u00B7${freq} ${n}`;
}

// Staleness ("Updated") column: how current the DISCLOSED data is for this AMC
// (see backend CoverageMeta.staleness_definition), not whether the pipeline ran
// today. Thresholds are a judgement call, not a hard SEBI/SLA rule: SEBI monthly
// disclosures normally lag ~10-15 days after month-end, so <=45d is routine;
// 46-90d is worth a look; >90d (roughly 2 missed monthly cycles) is flagged red.
function formatStaleness(days: number | null): string {
  if (days === null) return '\u2014';
  if (days < 60) return `${days}d`;
  return `${Math.floor(days / 30)}mo`;
}

function stalenessClass(days: number | null): string {
  if (days === null) return 'text-ink-muted';
  if (days > 90) return 'text-red font-semibold';
  if (days > 45) return 'text-amber font-semibold';
  return 'text-ink-secondary';
}

// Overall per-AMC source badge, rendered next to the short name so "which
// AMCs are automated vs manual" is a glance, not a per-cell scan. "none" is
// intentionally not rendered (an untracked AMC gets no badge, not a noisy one).
const SOURCE_TAG_LABEL: Record<AmcCoverageRow['source_tag'], string> = {
  auto: 'Auto',
  manual: 'Manual',
  mixed: 'Mixed',
  none: '',
};

const SOURCE_TAG_CLASSES: Record<AmcCoverageRow['source_tag'], string> = {
  auto: 'bg-royal/10 text-royal',
  manual: 'bg-amber/10 text-amber',
  mixed: 'bg-ink-muted/15 text-ink-muted',
  none: '',
};

function SourceTagBadge({ tag }: { tag: AmcCoverageRow['source_tag'] }) {
  if (tag === 'none') return null;
  return (
    <span
      className={cn(
        'ml-1.5 inline-block rounded px-1 py-0.5 align-middle font-mono text-[9px] font-semibold uppercase tracking-wide',
        SOURCE_TAG_CLASSES[tag],
      )}
    >
      {SOURCE_TAG_LABEL[tag]}
    </span>
  );
}

function SortHeader({
  label,
  sortKey,
  activeSort,
  sortDir,
  onSort,
  align = 'right',
}: {
  label: string;
  sortKey: AmcSortKey;
  activeSort: AmcSortKey;
  sortDir: 'asc' | 'desc';
  onSort: (k: AmcSortKey) => void;
  align?: 'left' | 'right';
}) {
  const isActive = activeSort === sortKey;
  return (
    <th
      scope="col"
      aria-sort={isActive ? (sortDir === 'desc' ? 'descending' : 'ascending') : 'none'}
      tabIndex={0}
      onClick={() => onSort(sortKey)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSort(sortKey);
        }
      }}
      className={cn(
        'sticky top-0 z-10 bg-surface-2 py-1.5 px-2 font-mono text-[10px] font-semibold uppercase tracking-[0.06em]',
        'cursor-pointer select-none whitespace-nowrap transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-royal/40',
        align === 'right' ? 'text-right' : 'text-left',
        isActive ? 'text-royal' : 'text-ink-muted hover:text-ink',
      )}
    >
      {label}
      <span
        className={cn('ml-1 transition-opacity', isActive ? 'text-royal opacity-100' : 'opacity-30')}
        aria-hidden="true"
      >
        {isActive ? (sortDir === 'desc' ? '\u25BE' : '\u25B4') : '\u2195'}
      </span>
    </th>
  );
}

export interface AmcCoverageTableProps {
  rows: AmcCoverageRow[];
  fieldOrder: CoverageField[];
  fieldLabels: Record<CoverageField, string>;
}

export function AmcCoverageTable({ rows, fieldOrder, fieldLabels }: AmcCoverageTableProps) {
  const [sortKey, setSortKey] = React.useState<AmcSortKey>('completeness');
  const [sortDir, setSortDir] = React.useState<'asc' | 'desc'>('asc');

  const onSort = React.useCallback(
    (key: AmcSortKey) => {
      if (key === sortKey) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortKey(key);
        setSortDir(key === 'amc' ? 'asc' : 'desc');
      }
    },
    [sortKey],
  );

  const sorted = React.useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      let av: number | string;
      let bv: number | string;
      if (sortKey === 'amc') {
        av = a.short_name.toLowerCase();
        bv = b.short_name.toLowerCase();
      } else if (sortKey === 'fund_count') {
        av = a.fund_count;
        bv = b.fund_count;
      } else if (sortKey === 'staleness') {
        // null (never updated) sorts as the most-stale extreme, regardless of
        // direction — an AMC with no data yet is never "fresher" than one that
        // is merely old.
        av = a.staleness_days ?? Number.POSITIVE_INFINITY;
        bv = b.staleness_days ?? Number.POSITIVE_INFINITY;
      } else if (sortKey === 'completeness') {
        av = a.completeness_pct;
        bv = b.completeness_pct;
      } else {
        av = a.fields[sortKey].covered_count;
        bv = b.fields[sortKey].covered_count;
      }
      if (av < bv) return sortDir === 'asc' ? -1 : 1;
      if (av > bv) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
    return copy;
  }, [rows, sortKey, sortDir]);

  return (
    <div className="flex flex-col gap-2">
      <div className="max-h-[70vh] overflow-auto rounded-lg border border-line">
        <table className="w-full text-[11px]">
          <caption className="sr-only">
            Per-AMC data coverage — funds tracked, per-field coverage counts, and overall
            completeness. Sortable by any column.
          </caption>
          <thead>
            <tr>
              <SortHeader
                label="AMC"
                sortKey="amc"
                activeSort={sortKey}
                sortDir={sortDir}
                onSort={onSort}
                align="left"
              />
              <SortHeader
                label="Funds"
                sortKey="fund_count"
                activeSort={sortKey}
                sortDir={sortDir}
                onSort={onSort}
              />
              <SortHeader
                label="Updated"
                sortKey="staleness"
                activeSort={sortKey}
                sortDir={sortDir}
                onSort={onSort}
              />
              {fieldOrder.map((f) => (
                <SortHeader
                  key={f}
                  label={fieldLabels[f]}
                  sortKey={f}
                  activeSort={sortKey}
                  sortDir={sortDir}
                  onSort={onSort}
                />
              ))}
              <SortHeader
                label="Complete %"
                sortKey="completeness"
                activeSort={sortKey}
                sortDir={sortDir}
                onSort={onSort}
              />
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr
                key={row.amc_name}
                className="border-t border-line last:border-b-0 hover:bg-surface-2/50 transition-colors"
              >
                <th
                  scope="row"
                  title={row.amc_name}
                  className="py-1 px-2 text-left font-medium text-ink whitespace-nowrap"
                >
                  <span>{row.short_name}</span>
                  <SourceTagBadge tag={row.source_tag} />
                </th>
                <td className="py-1 px-2 text-right font-mono tabular-nums text-ink-secondary">
                  {row.fund_count.toLocaleString('en-IN')}
                </td>
                <td
                  title={row.last_updated ?? 'No disclosure data yet'}
                  className={cn(
                    'py-1 px-2 text-right font-mono tabular-nums whitespace-nowrap',
                    stalenessClass(row.staleness_days),
                  )}
                >
                  {formatStaleness(row.staleness_days)}
                </td>
                {fieldOrder.map((f) => {
                  const cell = row.fields[f];
                  return (
                    <td
                      key={f}
                      className="py-1 px-2 text-right font-mono tabular-nums text-ink-secondary whitespace-nowrap"
                    >
                      {formatCell(cell.mode, cell.freq, cell.covered_count)}
                    </td>
                  );
                })}
                <td className="py-1 px-2 text-right font-mono tabular-nums font-semibold text-ink">
                  {row.completeness_pct.toFixed(1)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-caption text-ink-muted">
        A=auto ML=manual &middot; Y/Q/W/M/D/O=frequency &middot; number = funds covered &middot;
        Auto/Manual/Mixed badge next to AMC = that AMC&apos;s overall source &middot; Updated =
        days/months since the latest disclosure we hold (amber &gt;45d, red &gt;90d) &middot;
        Category = how many funds have their SEBI category recorded (platform-wide, no mode/freq tag)
      </p>
    </div>
  );
}
