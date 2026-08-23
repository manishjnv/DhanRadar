/**
 * ExploreHero — V4 hero: 6 stat tiles only.
 *
 * Real values (total funds, categories, market mood WORD) are passed in; the
 * other three tiles are illustrative "preview" facts. NO numeric mood score
 * (non-neg #2) — the mood tile shows the regime word only.
 */
'use client';

import * as React from 'react';
import { REGIME_DISPLAY, type Regime } from '@/components/mood/MoodGauge';

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
  /** Tile 4 — hero.trending_category (no "best" framing; just trending). */
  trendingCategory?: string | null;
  /** Tile 5 — top mover name from movers_up.rows[0]. */
  topMoverName?: string | null;
  /** Tile 5 — rank delta from movers_up.rows[0].rank_delta. */
  topMoverDelta?: number | null;
  /** Tile 6 — top category name from category_inflows.rows[0]. */
  topInflowCategory?: string | null;
  /** Tile 6 — net flow in crore from category_inflows.rows[0]. */
  topInflowCr?: number | null;
}

export function ExploreHero({ totalFunds, categoryCount, moodRegime, trendingCategory, topMoverName, topMoverDelta, topInflowCategory, topInflowCr }: ExploreHeroProps) {
  const moodWord =
    moodRegime && moodRegime !== 'data_unavailable' && moodRegime !== 'insufficient_data'
      ? REGIME_DISPLAY[moodRegime]
      : '—';

  const tile4Value = trendingCategory
    ? trendingCategory.replace(/^[^-]+-\s*/, '').replace(/\s*Fund$/i, '') || trendingCategory
    : '—';
  const tile5Value = topMoverName
    ? topMoverName.split(' ').slice(0, 2).join(' ')
    : '—';
  const tile5Hint = topMoverDelta != null
    ? `${topMoverDelta > 0 ? '+' : ''}${topMoverDelta} ranks`
    : undefined;
  const tile6Value = topInflowCategory
    ? topInflowCategory.replace(/^[^-]+-\s*/, '').replace(/\s*Fund$/i, '') || topInflowCategory
    : '—';
  const tile6Hint = topInflowCr != null
    ? `${topInflowCr >= 0 ? '+' : '\u2212'}\u20B9${Math.abs(topInflowCr) >= 1000 ? (Math.abs(topInflowCr) / 1000).toFixed(1) + 'k' : Math.abs(topInflowCr).toFixed(0)} Cr`
    : undefined;

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
          <StatTile label="Trending category" value={<span className="text-h3">{tile4Value}</span>} />
          <StatTile label="Most improved" value={<span className="text-h3">{tile5Value}</span>} hint={tile5Hint} />
          <StatTile label="Highest inflows" value={<span className="text-h3">{tile6Value}</span>} hint={tile6Hint} />
        </div>
      </div>
    </div>
  );
}
