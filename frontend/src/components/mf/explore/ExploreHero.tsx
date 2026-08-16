/**
 * ExploreHero — V4 hero: 6 stat tiles + quick-action buttons.
 *
 * Real values (total funds, categories, market mood WORD) are passed in; the
 * other three tiles are illustrative "preview" facts. NO numeric mood score
 * (non-neg #2) — the mood tile shows the regime word only.
 *
 * Quick-action buttons render the first ~9 entries of the shared QUICK_INTENTS
 * registry (Phase C chip consolidation) — every button is a real category
 * filter, a real sort, or a real page/anchor link, never decorative.
 */
'use client';

import * as React from 'react';
import Link from 'next/link';
import { REGIME_DISPLAY, type Regime } from '@/components/mood/MoodGauge';
import { QUICK_INTENTS, type QuickIntent } from '@/features/mf/quickIntents';

const HERO_INTENTS = QUICK_INTENTS.slice(0, 9);

function StatTile({ label, value, hint, preview }: { label: string; value: React.ReactNode; hint?: string; preview?: boolean }) {
  return (
    <div className="bg-white/[0.06] px-4 py-3">
      <div className="text-caption uppercase tracking-[0.05em] font-semibold text-white/55 leading-tight flex items-center gap-1">
        {label}
        {preview && <span className="text-[9px] font-semibold text-white/40 normal-case tracking-normal">· preview</span>}
      </div>
      <div className="font-mono text-h3 font-semibold text-white mt-1 leading-none tabular-nums">
        {value}
        {hint && <span className="text-small font-medium text-white/70 ml-1">{hint}</span>}
      </div>
    </div>
  );
}

export interface ExploreHeroProps {
  totalFunds: number | null;
  categoryCount: number | null;
  moodRegime: Regime | null;
  /** Quick-intent handler — fires the intent's real backing (category/sort/href). */
  onIntent?: (intent: QuickIntent) => void;
  activeIntentId?: string | null;
}

export function ExploreHero({ totalFunds, categoryCount, moodRegime, onIntent, activeIntentId }: ExploreHeroProps) {
  const moodWord =
    moodRegime && moodRegime !== 'data_unavailable' && moodRegime !== 'insufficient_data'
      ? REGIME_DISPLAY[moodRegime]
      : '—';

  return (
    <div
      className="relative overflow-hidden rounded-2xl px-7 py-8 sm:px-9 sm:py-9 shadow-lg"
      style={{ background: 'linear-gradient(135deg, var(--dr-navy, #0B1F3A) 0%, #15315C 55%, var(--dr-royal, #1E5EFF) 130%)' }}
    >
      <div aria-hidden="true" className="pointer-events-none absolute -right-16 -top-24 h-72 w-72 rounded-full" style={{ background: 'radial-gradient(circle, rgba(30,94,255,0.40), transparent 70%)' }} />
      <div className="relative z-[1]">
        <h1 className="text-h1 font-medium text-white tracking-[-0.02em]">Discover Mutual Funds</h1>
        <p className="mt-2 text-body text-white/75 max-w-xl leading-relaxed">
          Find the right fund for your goals, risk profile, and current market — best funds first, not a list of thousands. Educational analysis only.
        </p>

        {/* 6 stat tiles */}
        <div className="mt-6 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-px rounded-xl overflow-hidden bg-white/10">
          <StatTile label="Funds ranked" value={totalFunds != null ? totalFunds.toLocaleString('en-IN') : '—'} />
          <StatTile label="Categories" value={categoryCount != null ? categoryCount.toLocaleString('en-IN') : '—'} />
          <StatTile label="Market mood" value={<span className="text-h3">{moodWord}</span>} />
          <StatTile label="Best category" value={<span className="text-h3">Small Cap</span>} preview />
          <StatTile label="Most improved" value={<span className="text-h3">Healthcare</span>} hint="+11" preview />
          <StatTile label="Highest inflows" value={<span className="text-h3">Flexi</span>} hint="+₹8.9k Cr" preview />
        </div>

        {/* Quick-intent buttons — real category/sort/anchor backing (Phase C). */}
        <div className="mt-5 flex flex-wrap gap-2">
          {HERO_INTENTS.map((intent) => {
            const active = activeIntentId === intent.id;
            const label = intent.icon ? `${intent.icon} ${intent.label}` : intent.label;
            const className =
              'rounded-lg border px-3.5 py-2 text-small font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50 ' +
              (active ? 'bg-white text-[color:var(--dr-navy,#0B1F3A)] border-white' : 'bg-white/10 text-white border-white/20 hover:bg-white/20');
            return intent.backing.kind === 'href' ? (
              <Link key={intent.id} href={intent.backing.href} title={intent.rule} onClick={() => onIntent?.(intent)} className={className}>
                {label}
              </Link>
            ) : (
              <button key={intent.id} type="button" title={intent.rule} onClick={() => onIntent?.(intent)} aria-pressed={active} className={className}>
                {label}
              </button>
            );
          })}
        </div>
        {activeIntentId && (
          <p className="mt-2.5 text-caption text-white/70">
            How this list is built: {QUICK_INTENTS.find((q) => q.id === activeIntentId)?.rule}
          </p>
        )}
      </div>
    </div>
  );
}
