/**
 * Shortlist — localStorage-backed compare tray (cap 4).
 *
 * useShortlist() manages the set of {isin, name} items and is called both by
 * ExplorerBody (to pass add/check handlers down to the table and card grid)
 * and by the Shortlist panel component itself.
 *
 * Compare CTA navigates to /mf/compare?isins=A,B,C,...
 */
'use client';
import * as React from 'react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/cn';

const STORAGE_KEY = 'dr:shortlist:v1';
export const SHORTLIST_MAX = 4;

export interface ShortlistItem {
  isin: string;
  name: string;
}

// ---------------------------------------------------------------------------
// Hook — shared state between the page and the floating panel
// ---------------------------------------------------------------------------

export function useShortlist() {
  const [items, setItems] = React.useState<ShortlistItem[]>(() => {
    if (typeof window === 'undefined') return [];
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? (parsed as ShortlistItem[]) : [];
    } catch {
      return [];
    }
  });

  const toggle = React.useCallback((isin: string, name: string) => {
    setItems((prev) => {
      const idx = prev.findIndex((x) => x.isin === isin);
      let next: ShortlistItem[];
      if (idx >= 0) {
        next = prev.filter((x) => x.isin !== isin);
      } else if (prev.length >= SHORTLIST_MAX) {
        return prev; // cap reached — no-op
      } else {
        next = [...prev, { isin, name }];
      }
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  }, []);

  const remove = React.useCallback((isin: string) => {
    setItems((prev) => {
      const next = prev.filter((x) => x.isin !== isin);
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  }, []);

  const isIn = React.useCallback((isin: string) => items.some((x) => x.isin === isin), [items]);

  return {
    items,
    toggle,
    remove,
    isIn,
    isins: items.map((x) => x.isin),
    isFull: items.length >= SHORTLIST_MAX,
    count: items.length,
  };
}

// ---------------------------------------------------------------------------
// AddShortlistButton — rendered inline in table rows and card footers
// ---------------------------------------------------------------------------

export function AddShortlistButton({
  isin,
  name,
  isIn,
  isFull,
  onToggle,
  size = 'sm',
}: {
  isin: string;
  name: string;
  isIn: boolean;
  isFull: boolean;
  onToggle: (isin: string, name: string) => void;
  size?: 'sm' | 'xs';
}) {
  const added = isIn;
  const disabled = !added && isFull;
  return (
    <button
      type="button"
      aria-label={added ? `Remove ${name} from shortlist` : `Add ${name} to shortlist`}
      aria-pressed={added}
      disabled={disabled}
      data-testid={`shortlist-btn-${isin}`}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        onToggle(isin, name);
      }}
      className={cn(
        'inline-flex items-center justify-center rounded-lg border transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
        size === 'xs' ? 'h-6 w-6 text-[11px]' : 'h-7 w-7 text-[13px]',
        added
          ? 'border-royal bg-royal/10 text-royal hover:bg-royal/20'
          : disabled
            ? 'border-line bg-surface-2 text-ink-faint cursor-not-allowed opacity-40'
            : 'border-line bg-surface text-ink-muted hover:border-royal hover:text-royal',
      )}
    >
      {added ? '✓' : '+'}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Floating panel component
// ---------------------------------------------------------------------------

export interface ShortlistProps {
  items: ShortlistItem[];
  onRemove: (isin: string) => void;
  count: number;
}

export function Shortlist({ items, onRemove, count }: ShortlistProps) {
  const [open, setOpen] = React.useState(false);
  const router = useRouter();

  const canCompare = items.length >= 2;
  const compareUrl = `/mf/compare?isins=${items.map((x) => x.isin).join(',')}`;

  return (
    <>
      {/* Launcher pill */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={`Shortlist — ${count} fund${count !== 1 ? 's' : ''} added`}
        data-testid="shortlist-launcher"
        className={cn(
          'fixed bottom-5 right-5 z-30 inline-flex items-center gap-2 rounded-full text-white px-4 py-2.5 text-small font-semibold shadow-lg',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/50 transition-colors',
          count > 0 ? 'bg-[color:var(--dr-navy,#0B1F3A)]' : 'bg-[color:var(--dr-navy,#0B1F3A)]/70',
        )}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M5 3h14v18l-7-4-7 4Z" />
        </svg>
        Shortlist
        <span className="font-mono text-caption bg-white/15 rounded-full px-2 py-0.5" aria-hidden="true">
          {count}/{SHORTLIST_MAX}
        </span>
      </button>

      {/* Panel */}
      <div
        className={cn(
          'fixed bottom-20 right-5 z-30 w-[300px] max-w-[calc(100vw-2.5rem)] rounded-2xl border border-line-strong bg-surface shadow-lg overflow-hidden transition-all',
          open ? 'opacity-100 translate-y-0 pointer-events-auto' : 'opacity-0 translate-y-3 pointer-events-none',
        )}
        role="dialog"
        aria-label="Shortlist"
        aria-modal={open}
        aria-hidden={!open}
        data-testid="shortlist-panel"
      >
        {/* Header */}
        <div className="flex items-center gap-2 bg-[color:var(--dr-navy,#0B1F3A)] text-white px-4 py-3">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <path d="M5 3h14v18l-7-4-7 4Z" />
          </svg>
          <span className="text-small font-semibold flex-1">Shortlist</span>
          <span className="font-mono text-caption opacity-60">{count}/{SHORTLIST_MAX}</span>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close shortlist"
            className="ml-2 text-white/70 hover:text-white focus-visible:outline-none"
          >
            ✕
          </button>
        </div>

        {/* Item list */}
        {items.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <p className="text-small text-ink-muted">
              Add up to {SHORTLIST_MAX} funds from the explorer to compare them side by side.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-line" aria-label="Shortlisted funds">
            {items.map((item) => (
              <li key={item.isin} className="flex items-center gap-2 px-4 py-2.5">
                <span className="text-small text-ink flex-1 truncate" title={item.name}>{item.name}</span>
                <button
                  type="button"
                  aria-label={`Remove ${item.name} from shortlist`}
                  data-testid={`shortlist-remove-${item.isin}`}
                  onClick={() => onRemove(item.isin)}
                  className="shrink-0 text-ink-muted hover:text-red transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}

        {/* Footer — Compare CTA */}
        <div className="border-t border-line p-3">
          <button
            type="button"
            disabled={!canCompare}
            data-testid="shortlist-compare-btn"
            onClick={() => {
              setOpen(false);
              router.push(compareUrl);
            }}
            className={cn(
              'w-full rounded-lg px-4 py-2 text-small font-medium transition-colors',
              canCompare
                ? 'bg-royal text-white hover:bg-royal/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/50'
                : 'bg-surface-2 border border-line text-ink-muted cursor-not-allowed',
            )}
          >
            ⇄ Compare {canCompare ? `(${count})` : '— add 2+ funds'}
          </button>
        </div>
      </div>
    </>
  );
}
