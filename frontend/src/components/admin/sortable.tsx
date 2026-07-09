'use client';

/**
 * Shared client-side table sorting + search for admin tables.
 *
 * useSort(rows, accessors, initial?) — returns rows sorted by the active
 * column; toggle() flips asc/desc. Accessors return string | number | null;
 * nulls always sort last. SortableTh renders the clickable header cell with
 * an aria-sort attribute and a direction arrow, matching the admin table
 * header style. matchesQuery() is the one-line case-insensitive row filter
 * used by table search boxes.
 */

import * as React from 'react';
import { cn } from '@/lib/cn';

export type SortDir = 'asc' | 'desc';
export type SortAccessor<T> = (row: T) => string | number | null | undefined;

export function useSort<T>(
  rows: T[],
  accessors: Record<string, SortAccessor<T>>,
  initial?: { key: string; dir: SortDir },
) {
  const [sort, setSort] = React.useState<{ key: string; dir: SortDir } | null>(
    initial ?? null,
  );

  const sorted = React.useMemo(() => {
    if (!sort) return rows;
    const acc = accessors[sort.key];
    if (!acc) return rows;
    const mul = sort.dir === 'asc' ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = acc(a);
      const bv = acc(b);
      if (av == null && bv == null) return 0;
      if (av == null) return 1; // nulls last regardless of direction
      if (bv == null) return -1;
      if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * mul;
      return String(av).localeCompare(String(bv)) * mul;
    });
    // accessors is expected to be a stable module-level object per table
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, sort]);

  const toggle = React.useCallback((key: string) => {
    setSort((s) =>
      s?.key === key
        ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: 'asc' },
    );
  }, []);

  return { sorted, sort, toggle };
}

export function SortableTh({
  label,
  sortKey,
  sort,
  onToggle,
  className,
}: {
  label: string;
  /** Omit sortKey to render a plain, non-sortable header cell. */
  sortKey?: string;
  sort: { key: string; dir: SortDir } | null;
  onToggle: (key: string) => void;
  className?: string;
}) {
  const active = sortKey != null && sort?.key === sortKey;
  const base =
    'pb-2 pr-4 text-left text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono';
  if (sortKey == null) {
    return (
      <th scope="col" className={cn(base, className)}>
        {label}
      </th>
    );
  }
  return (
    <th
      scope="col"
      aria-sort={active ? (sort!.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
      className={cn(base, className)}
    >
      <button
        type="button"
        onClick={() => onToggle(sortKey)}
        className={cn(
          'inline-flex items-center gap-1 uppercase tracking-wide hover:text-ink transition-colors',
          active && 'text-ink',
        )}
        title={`Sort by ${label}`}
      >
        {label}
        <span aria-hidden="true" className="text-[9px]">
          {active ? (sort!.dir === 'asc' ? '▲' : '▼') : '↕'}
        </span>
      </button>
    </th>
  );
}

/** Case-insensitive match of a query against any of the given field values. */
export function matchesQuery(
  query: string,
  ...values: Array<string | number | null | undefined>
): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return values.some((v) => v != null && String(v).toLowerCase().includes(q));
}
