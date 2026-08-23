/**
 * QuickChips — "Quick Discovery" row: first 7 popular entries inline, rest behind "More ▾".
 *
 * Batch G consolidation: every chip is a real category filter, a real /mf/funds sort,
 * or a real page/anchor link — never decorative (docs/features/
 * leaderboard-interactivity-plan.md Phase C). Single-select. No advisory framing.
 */
'use client';

import * as React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/cn';
import { QUICK_INTENTS, type QuickIntent } from '@/features/mf/quickIntents';

// First 7 intents render inline; rest go into "More ▾" overflow.
const INLINE_COUNT = 7;

function ChipButton({
  intent,
  isActive,
  onSelect,
}: {
  intent: QuickIntent;
  isActive: boolean;
  onSelect: (intent: QuickIntent) => void;
}) {
  const label = intent.icon ? `${intent.icon} ${intent.label}` : intent.label;
  const className = cn(
    'inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-small font-medium transition-colors',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
    isActive
      ? 'bg-ink text-bg border-ink'
      : 'bg-surface border-line text-ink-secondary hover:border-royal hover:text-royal',
  );
  return intent.backing.kind === 'href' ? (
    <Link key={intent.id} href={intent.backing.href} title={intent.rule} onClick={() => onSelect(intent)} className={className}>
      {label}
    </Link>
  ) : (
    <button key={intent.id} type="button" title={intent.rule} onClick={() => onSelect(intent)} aria-pressed={isActive} className={className}>
      {label}
    </button>
  );
}

export function QuickChips({
  active,
  onSelect,
}: {
  active: string | null;
  onSelect: (intent: QuickIntent) => void;
}) {
  const [moreOpen, setMoreOpen] = React.useState(false);
  const moreRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    function handler(e: MouseEvent) {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) setMoreOpen(false);
    }
    if (moreOpen) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [moreOpen]);

  const inlineIntents = QUICK_INTENTS.slice(0, INLINE_COUNT);
  const overflowIntents = QUICK_INTENTS.slice(INLINE_COUNT);

  return (
    <div className="flex flex-wrap gap-2 items-center">
      {inlineIntents.map((intent) => (
        <ChipButton
          key={intent.id}
          intent={intent}
          isActive={active === intent.id}
          onSelect={onSelect}
        />
      ))}
      {overflowIntents.length > 0 && (
        <div ref={moreRef} className="relative">
          <button
            type="button"
            onClick={() => setMoreOpen((o) => !o)}
            aria-expanded={moreOpen}
            className="inline-flex items-center gap-1 rounded-full border border-line bg-surface px-3 py-1.5 text-small font-medium text-ink-secondary hover:border-royal hover:text-royal transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
          >
            More ▾
          </button>
          {moreOpen && (
            <div className="absolute left-0 top-full mt-1 z-20 min-w-[200px] rounded-xl border border-line bg-surface shadow-lg p-2 flex flex-col gap-1">
              {overflowIntents.map((intent) => {
                const label = intent.icon ? `${intent.icon} ${intent.label}` : intent.label;
                const isActive = active === intent.id;
                const btnClass = cn(
                  'w-full text-left px-3 py-1.5 rounded-lg text-small font-medium transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
                  isActive
                    ? 'bg-ink text-bg'
                    : 'text-ink-secondary hover:text-royal hover:bg-surface-2',
                );
                return intent.backing.kind === 'href' ? (
                  <Link
                    key={intent.id}
                    href={intent.backing.href}
                    title={intent.rule}
                    onClick={() => {
                      onSelect(intent);
                      setMoreOpen(false);
                    }}
                    className={btnClass}
                  >
                    {label}
                  </Link>
                ) : (
                  <button
                    key={intent.id}
                    type="button"
                    title={intent.rule}
                    onClick={() => {
                      onSelect(intent);
                      setMoreOpen(false);
                    }}
                    aria-pressed={isActive}
                    className={btnClass}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
