/**
 * ExploreHero — V4 hero: 6 stat tiles + 9 quick-action buttons.
 *
 * Real values (total funds, categories, market mood WORD) are passed in; the
 * other three tiles are illustrative "preview" facts. NO numeric mood score
 * (non-neg #2) — the mood tile shows the regime word only.
 */
'use client';

import * as React from 'react';
import { REGIME_DISPLAY, type Regime } from '@/components/mood/MoodGauge';
import { HERO_QUICK } from './sampleData';

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
  /** Quick-action handler — preset name; wiring is illustrative for now. */
  onQuick?: (name: string) => void;
  activeQuick?: string | null;
}

export function ExploreHero({ totalFunds, categoryCount, moodRegime, onQuick, activeQuick }: ExploreHeroProps) {
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

        {/* 9 quick-action buttons */}
        <div className="mt-5 flex flex-wrap gap-2">
          {HERO_QUICK.map((q) => {
            const active = activeQuick === q;
            return (
              <button
                key={q}
                type="button"
                onClick={() => onQuick?.(q)}
                aria-pressed={active}
                className={
                  'rounded-lg border px-3.5 py-2 text-small font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50 ' +
                  (active ? 'bg-white text-[color:var(--dr-navy,#0B1F3A)] border-white' : 'bg-white/10 text-white border-white/20 hover:bg-white/20')
                }
              >
                {q}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
