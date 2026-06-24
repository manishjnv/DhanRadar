/**
 * ExploreHero — premium gradient hero ported from V4.
 *
 * Stat tiles show ONLY factual, public counts and the market-mood regime WORD
 * (never the numeric mood score — non-negotiable #2). V4's "best category /
 * most improved / highest inflows" tiles are omitted because no data source
 * backs them (no-fake-data rule).
 */
'use client';

import * as React from 'react';
import { REGIME_DISPLAY, type Regime } from '@/components/mood/MoodGauge';

function StatTile({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="bg-white/[0.06] px-4 py-3">
      <div className="text-caption uppercase tracking-[0.05em] font-semibold text-white/55 leading-tight">
        {label}
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
  /** Market-mood regime word, or null while loading / unavailable. */
  moodRegime: Regime | null;
}

export function ExploreHero({ totalFunds, categoryCount, moodRegime }: ExploreHeroProps) {
  const moodWord =
    moodRegime && moodRegime !== 'data_unavailable' && moodRegime !== 'insufficient_data'
      ? REGIME_DISPLAY[moodRegime]
      : '—';

  return (
    <div
      className="relative overflow-hidden rounded-2xl px-7 py-8 sm:px-9 sm:py-9 shadow-lg"
      style={{
        background:
          'linear-gradient(135deg, var(--dr-navy, #0B1F3A) 0%, #15315C 55%, var(--dr-royal, #1E5EFF) 130%)',
      }}
    >
      {/* Decorative glow — pointer-events none, aria-hidden */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-16 -top-24 h-72 w-72 rounded-full"
        style={{ background: 'radial-gradient(circle, rgba(30,94,255,0.40), transparent 70%)' }}
      />
      <div className="relative z-[1]">
        <h1 className="text-h1 font-medium text-white tracking-[-0.02em]">Discover Mutual Funds</h1>
        <p className="mt-2 text-body text-white/75 max-w-xl leading-relaxed">
          Compare funds by rank, assessment, and returns — best funds first, not a list of thousands.
          Educational analysis only.
        </p>

        <div className="mt-6 grid grid-cols-2 sm:grid-cols-3 gap-px rounded-xl overflow-hidden bg-white/10 max-w-2xl">
          <StatTile label="Funds ranked" value={totalFunds != null ? totalFunds.toLocaleString('en-IN') : '—'} />
          <StatTile label="Categories" value={categoryCount != null ? categoryCount.toLocaleString('en-IN') : '—'} />
          <StatTile label="Market mood" value={<span className="text-h3">{moodWord}</span>} />
        </div>
      </div>
    </div>
  );
}
