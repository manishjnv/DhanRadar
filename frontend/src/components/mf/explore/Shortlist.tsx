/**
 * Shortlist — V4 floating compare tray. Self-contained launcher + panel.
 * Compare wiring is illustrative for now (founder: UI first, functionality later).
 */
'use client';
import * as React from 'react';
import { cn } from '@/lib/cn';

export function Shortlist() {
  const [open, setOpen] = React.useState(false);

  return (
    <>
      {/* Launcher pill */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="fixed bottom-5 right-5 z-30 inline-flex items-center gap-2 rounded-full bg-[color:var(--dr-navy,#0B1F3A)] text-white px-4 py-2.5 text-small font-semibold shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/50"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 3h14v18l-7-4-7 4Z" /></svg>
        Shortlist
        <span className="font-mono text-caption bg-white/15 rounded-full px-2 py-0.5">0</span>
      </button>

      {/* Panel */}
      <div
        className={cn(
          'fixed bottom-20 right-5 z-30 w-[300px] max-w-[calc(100vw-2.5rem)] rounded-2xl border border-line-strong bg-surface shadow-lg overflow-hidden transition-all',
          open ? 'opacity-100 translate-y-0 pointer-events-auto' : 'opacity-0 translate-y-3 pointer-events-none',
        )}
        role="dialog"
        aria-label="Shortlist"
        aria-hidden={!open}
      >
        <div className="flex items-center gap-2 bg-[color:var(--dr-navy,#0B1F3A)] text-white px-4 py-3">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M5 3h14v18l-7-4-7 4Z" /></svg>
          <span className="text-small font-semibold flex-1">Shortlist</span>
          <button type="button" onClick={() => setOpen(false)} aria-label="Close shortlist" className="text-white/70 hover:text-white">✕</button>
        </div>
        <div className="px-4 py-8 text-center">
          <p className="text-small text-ink-muted">Add funds from the explorer to compare them side by side.</p>
        </div>
        <div className="border-t border-line p-3">
          <button type="button" disabled className="w-full rounded-lg bg-surface-2 border border-line text-ink-muted px-4 py-2 text-small font-medium cursor-not-allowed">
            ⇄ Compare
          </button>
        </div>
      </div>
    </>
  );
}
