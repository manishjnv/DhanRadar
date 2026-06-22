'use client';

/**
 * CommandPalette — global ⌘K / Ctrl+K fund search overlay.
 *
 * Design authority: docs/ui-system/screens/ai-search.md (prominent ⌘K overlay,
 * ResultList with scheme_name + amc_name + sebi_category) and the topbar search
 * widget in docs/ui-system/html/hifi-screens.html.
 *
 * Compliance rules honoured:
 *  - NO scores / numeric bands in DOM (non-negotiable #2)
 *  - NO advisory verbs (non-negotiable #1) — search results show only fund identity
 *  - Uses api.get() from @/lib/apiClient (credentials:'include', /api/v1 base)
 *  - Navigates to /mf/fund/[isin] (confirmed fund detail route)
 */

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { Search, X } from 'lucide-react';
import { cn } from '@/lib/cn';
import { api } from '@/lib/apiClient';
import { Skeleton } from '@/components/ui/Skeleton';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SearchResult {
  isin: string;
  scheme_name: string;
  // Display-only clean name from the backend (taxonomy.derive_short_name).
  // scheme_name stays the official AMFI name (shown as the hover title).
  fund_name_short: string | null;
  amc_name: string | null;
  sebi_category: string | null;
  plan_type: string | null;
  option_type: string | null;
  idcw_frequency: string | null;
}

// Humanise an idcw_frequency token for the secondary line.
const FREQ_LABELS: Record<string, string> = {
  daily: 'Daily',
  weekly: 'Weekly',
  fortnightly: 'Fortnightly',
  monthly: 'Monthly',
  quarterly: 'Quarterly',
  half_yearly: 'Half-Yearly',
  annual: 'Annual',
};

// Backend returns the list directly: GET /api/v1/mf/search → SearchResult[]
type SearchResponse = SearchResult[];

type PaletteState = 'idle' | 'loading' | 'results' | 'empty';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// CommandPalette
// ---------------------------------------------------------------------------

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const router = useRouter();

  const dialogRef        = React.useRef<HTMLDivElement>(null);
  const inputRef         = React.useRef<HTMLInputElement>(null);
  const restoreFocusRef  = React.useRef<HTMLElement | null>(null);
  const debounceRef      = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  // Track the latest query so stale responses are discarded.
  const latestQueryRef   = React.useRef<string>('');

  const [query,       setQuery]       = React.useState('');
  const [results,     setResults]     = React.useState<SearchResult[]>([]);
  const [state,       setState]       = React.useState<PaletteState>('idle');
  const [activeIndex, setActiveIndex] = React.useState(-1);

  // Derived listbox id
  const listboxId  = 'cmd-palette-listbox';
  const inputId    = 'cmd-palette-input';

  // ---------------------------------------------------------------------------
  // Open / close lifecycle
  // ---------------------------------------------------------------------------

  React.useEffect(() => {
    if (!open) return;

    // Capture element to restore focus when dialog closes.
    restoreFocusRef.current = document.activeElement as HTMLElement | null;

    // Autofocus the input.
    requestAnimationFrame(() => inputRef.current?.focus());

    // Prevent body scroll while open.
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  // Restore focus when dialog closes.
  React.useEffect(() => {
    if (!open) {
      restoreFocusRef.current?.focus?.();
    }
  }, [open]);

  // Reset state when closed.
  React.useEffect(() => {
    if (!open) {
      setQuery('');
      setResults([]);
      setState('idle');
      setActiveIndex(-1);
    }
  }, [open]);

  // ---------------------------------------------------------------------------
  // Focus trap (mirrors MobileDrawer in AppShell.tsx)
  // ---------------------------------------------------------------------------

  React.useEffect(() => {
    if (!open) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        onClose();
        return;
      }

      if (e.key === 'Tab') {
        const panel = dialogRef.current;
        if (!panel) return;
        const focusables = panel.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
        );
        if (!focusables.length) return;
        const first  = focusables[0];
        const last   = focusables[focusables.length - 1];
        const active = document.activeElement;
        if (e.shiftKey) {
          if (active === first || !panel.contains(active)) {
            e.preventDefault();
            last.focus();
          }
        } else if (active === last || !panel.contains(active)) {
          e.preventDefault();
          first.focus();
        }
        return;
      }

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIndex((prev) =>
          results.length === 0 ? -1 : Math.min(prev + 1, results.length - 1),
        );
        return;
      }

      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((prev) =>
          results.length === 0 ? -1 : Math.max(prev - 1, 0),
        );
        return;
      }

      if (e.key === 'Enter') {
        if (activeIndex >= 0 && results[activeIndex]) {
          handleSelect(results[activeIndex]);
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, results, activeIndex, onClose]);

  // ---------------------------------------------------------------------------
  // Search: debounce → fetch → discard stale
  // ---------------------------------------------------------------------------

  function runSearch(q: string) {
    latestQueryRef.current = q;

    if (q.length < 2) {
      setState('idle');
      setResults([]);
      setActiveIndex(-1);
      return;
    }

    setState('loading');

    api
      .get<SearchResponse>(`/mf/search?q=${encodeURIComponent(q)}&limit=10`)
      .then((data) => {
        // Discard if a newer query has since been issued.
        if (latestQueryRef.current !== q) return;

        // Backend returns SearchResult[] directly (not wrapped in {results:[...]}).
        const list = Array.isArray(data) ? data : [];
        setResults(list);
        setState(list.length > 0 ? 'results' : 'empty');
        setActiveIndex(-1);
      })
      .catch(() => {
        if (latestQueryRef.current !== q) return;
        setResults([]);
        setState('empty');
        setActiveIndex(-1);
      });
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const q = e.target.value;
    setQuery(q);
    setActiveIndex(-1);

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runSearch(q), 200);
  }

  // ---------------------------------------------------------------------------
  // Select a fund → navigate
  // ---------------------------------------------------------------------------

  function handleSelect(result: SearchResult) {
    onClose();
    router.push(
      `/mf/fund/${encodeURIComponent(result.isin)}?category=${encodeURIComponent(result.sebi_category ?? '')}`,
    );
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (!open) return null;

  const showList    = state === 'results' && results.length > 0;
  const showEmpty   = state === 'empty';
  const showLoading = state === 'loading';
  const showIdle    = state === 'idle';

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/40"
        aria-hidden="true"
        onClick={onClose}
      />

      {/* Dialog */}
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Search funds"
        className={cn(
          'fixed inset-x-4 top-[10vh] z-50 mx-auto max-w-xl',
          'rounded-md border border-line bg-surface shadow-lg',
          'flex flex-col overflow-hidden',
        )}
      >
        {/* Search input row */}
        <div className="flex items-center gap-3 border-b border-line px-4 py-3">
          <Search
            size={18}
            strokeWidth={2}
            className="shrink-0 text-ink-muted"
            aria-hidden="true"
          />
          <input
            ref={inputRef}
            id={inputId}
            type="search"
            role="combobox"
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            aria-label="Search funds"
            aria-expanded={showList}
            aria-controls={listboxId}
            aria-activedescendant={
              activeIndex >= 0 ? `cmd-option-${activeIndex}` : undefined
            }
            placeholder="Search funds by name or AMC…"
            value={query}
            onChange={handleInputChange}
            className={cn(
              'min-w-0 flex-1 bg-transparent text-body text-ink outline-none',
              'placeholder:text-ink-muted',
            )}
          />
          {/* Keyboard shortcut chip — hidden on mobile per design doc */}
          <span
            className="hidden shrink-0 select-none rounded border border-line bg-surface-2 px-1.5 py-0.5 font-mono text-caption text-ink-muted sm:inline"
            aria-hidden="true"
          >
            esc
          </span>
          <button
            type="button"
            aria-label="Close search"
            onClick={onClose}
            className={cn(
              'shrink-0 rounded-md p-1 text-ink-secondary',
              'hover:bg-surface-2 hover:text-ink',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
            )}
          >
            <X size={16} strokeWidth={2} aria-hidden="true" />
          </button>
        </div>

        {/* Results area */}
        <div className="max-h-[60vh] overflow-y-auto">

          {/* Idle state: prompt */}
          {showIdle && (
            <p className="px-4 py-6 text-center text-small text-ink-muted">
              Type at least 2 characters to search funds
            </p>
          )}

          {/* Loading state: skeleton rows */}
          {showLoading && (
            <div className="space-y-0" aria-busy="true" aria-label="Searching…">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="flex min-h-[44px] items-center gap-3 border-b border-line px-4 py-3 last:border-b-0"
                >
                  <div className="flex flex-1 flex-col gap-1.5">
                    <Skeleton className="h-3.5 w-3/5" />
                    <Skeleton className="h-3 w-2/5" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Empty state */}
          {showEmpty && (
            <p className="px-4 py-6 text-center text-small text-ink-muted">
              No funds found for &ldquo;{query}&rdquo;
            </p>
          )}

          {/* Results listbox */}
          {showList && (
            <ul
              id={listboxId}
              role="listbox"
              aria-label="Fund search results"
              className="divide-y divide-line"
            >
              {results.map((result, idx) => {
                const isActive = idx === activeIndex;
                const optionId = `cmd-option-${idx}`;

                // Plan/option labels — same mapping as FundExplorerTable.tsx lines 219–228.
                const planLabel = result.plan_type
                  ? result.plan_type === 'direct' ? 'Direct' : 'Regular'
                  : null;
                const baseOptionLabel = result.option_type
                  ? result.option_type === 'growth'             ? 'Growth'
                  : result.option_type === 'idcw'               ? 'IDCW'
                  : result.option_type === 'dividend_reinvest'  ? 'Div Reinvest'
                  : 'Div Payout'
                  : null;
                // Prefix the payout cadence for income-distribution options
                // (e.g. "Monthly IDCW"); Growth has no frequency.
                const freqLabel =
                  result.idcw_frequency && result.option_type !== 'growth'
                    ? FREQ_LABELS[result.idcw_frequency] ?? null
                    : null;
                const optionLabel = baseOptionLabel
                  ? [freqLabel, baseOptionLabel].filter(Boolean).join(' ')
                  : null;

                // Prominent label = clean short name; fall back to the official
                // name when the backend has not derived one (old cached rows).
                const primaryLabel = result.fund_name_short || result.scheme_name;

                const secondaryParts = [result.amc_name, planLabel, optionLabel].filter(Boolean);

                return (
                  <li
                    key={result.isin}
                    id={optionId}
                    role="option"
                    aria-selected={isActive}
                    onMouseEnter={() => setActiveIndex(idx)}
                    className="flex"
                  >
                    {/*
                     * Interactive wrapper is a <button> so keyboard events are
                     * native (click on Enter/Space) and jsx-a11y is satisfied.
                     * The outer <li role="option"> carries the ARIA identity;
                     * the <button> is the focusable/activatable element.
                     */}
                    <button
                      type="button"
                      tabIndex={-1}
                      onClick={() => handleSelect(result)}
                      className={cn(
                        'flex flex-1 min-h-[44px] cursor-pointer items-center gap-3 px-4 py-3 text-left',
                        'transition-colors w-full',
                        'focus-visible:outline-none',
                        isActive
                          ? 'bg-royal/10 text-ink'
                          : 'text-ink hover:bg-surface-2',
                      )}
                    >
                      <div className="flex flex-1 flex-col gap-0.5 min-w-0">
                        {/* Clean short name; the official AMFI name stays available
                            on hover (title) so the full legal name is never lost. */}
                        <span
                          className="truncate text-small font-medium text-ink"
                          title={result.scheme_name}
                        >
                          {primaryLabel}
                        </span>
                        <span className="truncate text-caption text-ink-muted">
                          {secondaryParts.join(' · ')}
                        </span>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </>
  );
}
