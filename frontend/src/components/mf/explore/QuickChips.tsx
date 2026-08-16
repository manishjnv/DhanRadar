/**
 * QuickChips — "Quick Discovery" row: every entry in the shared QUICK_INTENTS
 * registry (Phase C chip consolidation), rendered as one-click presets.
 *
 * Single-select. Every chip is a real category filter, a real /mf/funds sort,
 * or a real page/anchor link — never decorative (docs/features/
 * leaderboard-interactivity-plan.md Phase C). No advisory framing.
 */
'use client';

import * as React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/cn';
import { QUICK_INTENTS, type QuickIntent } from '@/features/mf/quickIntents';

export function QuickChips({
  active,
  onSelect,
}: {
  active: string | null;
  onSelect: (intent: QuickIntent) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {QUICK_INTENTS.map((intent) => {
        const isActive = active === intent.id;
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
      })}
    </div>
  );
}
